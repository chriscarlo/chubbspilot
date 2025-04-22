#!/usr/bin/env python3
"""
Downloads protobuf‑tile maps from Azure and (elsewhere in the codebase)
uploads logs or models back to the same share.

All map‑specific code lives in the **MAP SECTION** below.  There is now
*no notion of “region”* – the downloader simply synchronises whatever is
inside <share>/protobuf_tiles/ to /data/media/0/map_data_tiles_protobuf/.
"""

# ────────────────────────────────────────────────────────────────────
# Imports
# ────────────────────────────────────────────────────────────────────
import json
import math
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError

import numpy as np
from cereal import log
from openpilot.common.realtime import DT_DMON, DT_HW
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.car.toyota.carcontroller import LOCK_CMD
from openpilot.system.hardware import HARDWARE
import openpilot.system.sentry as sentry
from panda import Panda

# ────────────────────────────────────────────────────────────────────
# MAP SECTION  – everything concerned with Azure map tiles
# ────────────────────────────────────────────────────────────────────

# 1.  Constants that define *where* the files live
PROTOBUF_MAPS_PATH = "/data/media/0/map_data_tiles_protobuf"   # local root
AZURE_SHARE_NAME   = "mapdata"                                 # Azure share
AZURE_BASE_DIR     = "protobuf_tiles"                          # sub‑directory
CONN_STRING_PATH   = "/persist/azure_conn_string"              # legacy fallback

# 2.  Optional Azure SDK (script still runs without it – uploads will fail)
try:
    from azure.storage.fileshare import ShareDirectoryClient
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    ShareDirectoryClient     = None
    ResourceNotFoundError    = None
    print("WARNING: Azure SDK not installed. Map download will be skipped.")

# 3.  Public entry point – called once a day/week/month by manager.py
def update_maps(now):
    """
    Download /protobuf_tiles/ from the Azure ‘mapdata’ share unless a recent
    successful run is already recorded in params['LastMapsUpdate'].
    """
    # honour owner’s preferred cadence
    schedule = params.get_int("PreferredSchedule")  # 0=daily 1=weekly 2=monthly
    if not _should_run_today(now, schedule):
        return

    cloudlog.info("update_maps: starting map sync (no per‑state filter).")
    params_memory.put("ProtobufMapDownloadProgress", "Starting…")
    params_memory.remove("ProtobufMapDownloadError")

    conn_str = _get_azure_connection_string()
    if not conn_str or ShareDirectoryClient is None:
        err = "Azure SDK missing" if ShareDirectoryClient is None else "No connection string"
        cloudlog.warning(f"update_maps: {err}, aborting.")
        params_memory.put("ProtobufMapDownloadError", err)
        params_memory.remove("ProtobufMapDownloadProgress")
        return

    remote_dir = AZURE_BASE_DIR                     # protobuf_tiles
    local_dir  = Path(PROTOBUF_MAPS_PATH)           # /data/…/protobuf_tiles
    success    = _download_azure_directory_recursive(conn_str, AZURE_SHARE_NAME,
                                                     remote_dir, local_dir)

    if success:
        suffix = "th" if 4 <= now.day <= 20 or 24 <= now.day <= 30 \
                       else ["st", "nd", "rd"][now.day % 10 - 1]
        params.put("LastMapsUpdate", now.strftime(f"%B {now.day}{suffix}, %Y"))
        cloudlog.info("update_maps: completed successfully.")
    else:
        cloudlog.warning("update_maps: failed.")

# 4.  Helper – is today the right day to run?
def _should_run_today(now, schedule: int) -> bool:
    """Returns True if maps should be refreshed according to *schedule*."""
    if schedule == 0:     # daily
        pass
    elif schedule == 1:   # weekly
        if now.weekday() != 6:   # Sunday only
            return False
    elif schedule == 2:   # monthly
        if now.day != 1:         # 1st of the month
            return False

    last = params.get("LastMapsUpdate", encoding="utf-8")
    return last != now.strftime("%B %-d, %Y")      # already done today?

# 5.  Helper – connection‑string discovery in env ▸ param ▸ file order
def _get_azure_connection_string() -> str | None:
    """Return the storage‑account connection string or None."""
    env = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if env:
        return env.strip()

    param = params.get("AzureConnString", encoding="utf-8")
    if param:
        return param.strip()

    try:
        with open(CONN_STRING_PATH, "r") as fh:
            file_cs = fh.read().strip()
        if file_cs:
            return file_cs
        print(f"Connection‑string file '{CONN_STRING_PATH}' is empty.")
    except FileNotFoundError:
        print(f"Connection‑string file '{CONN_STRING_PATH}' not found.")
    except Exception as e:
        print(f"Error reading connection‑string file: {e}")
        sentry.capture_exception(e)

    return None

# 6.  Helper – ensure a directory exists
def _ensure_local_dir(path: Path):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        sentry.capture_exception(e)
        raise

# 7.  Recursive downloader with progress + error reporting to params_memory
def _download_azure_directory_recursive(conn_str: str, share: str,
                                        remote_dir: str, local_dir: Path) -> bool:
    if ShareDirectoryClient is None:
        return False

    cloudlog.info(f"update_maps: syncing {share}/{remote_dir} → {local_dir}")
    progress_key = "ProtobufMapDownloadProgress"
    error_key    = "ProtobufMapDownloadError"

    total = downloaded = errors = 0
    try:
        root = ShareDirectoryClient.from_connection_string(conn_str, share, remote_dir)
        # first count (rough estimate – keeps UI honest)
        queue = [root]
        while queue:
            d = queue.pop()
            for it in d.list_directories_and_files():
                if it["is_directory"]:
                    queue.append(d.get_subdirectory_client(it["name"]))
                else:
                    total += 1
        params_memory.put(progress_key, f"0/{total}")

        # actual download
        queue = [(root, local_dir)]
        while queue:
            d_client, l_path = queue.pop()
            _ensure_local_dir(l_path)
            for it in d_client.list_directories_and_files():
                if it["is_directory"]:
                    queue.append(
                        (d_client.get_subdirectory_client(it["name"]),
                         l_path / it["name"]))
                else:
                    try:
                        with open(l_path / it["name"], "wb") as lf:
                            lf.write(d_client.get_file_client(it["name"])
                                              .download_file().readall())
                        downloaded += 1
                        params_memory.put(progress_key, f"{downloaded}/{total}")
                    except Exception as f_err:
                        errors += 1
                        sentry.capture_exception(f_err)
                        params_memory.put(error_key,
                                          f"Error downloading {it['name']}: {f_err}")

    except ResourceNotFoundError:
        params_memory.put(error_key, f"Remote path not found: {remote_dir}")
        return False
    except Exception as e:
        sentry.capture_exception(e)
        params_memory.put(error_key, f"Unexpected error: {e}")
        return False
    finally:
        if errors == 0:
            params_memory.remove(progress_key)
            params_memory.remove(error_key)

    return errors == 0

# ────────────────────────────────────────────────────────────────────
# Everything below here is unchanged utility / vehicle logic
# ────────────────────────────────────────────────────────────────────

EARTH_RADIUS = 6371000.0  # metres  (normally imported from frogpilot_variables)
MAPD_PATH    = Path("/data/media/0/mapd")           # placeholder
MAPS_PATH    = Path(PROTOBUF_MAPS_PATH)             # alias for legacy code

running_threads = {}
locks = {
    "backup_toggles":   threading.Lock(),
    "download_all_models": threading.Lock(),
    "download_model":   threading.Lock(),
    "download_theme":   threading.Lock(),
    "flash_panda":      threading.Lock(),
    "lock_doors":       threading.Lock(),
    "update_checks":    threading.Lock(),
    "update_maps":      threading.Lock(),
    "update_models":    threading.Lock(),
    "update_openpilot": threading.Lock(),
    "update_themes":    threading.Lock(),
}

def run_thread_with_lock(name, target, args=()):
    if not running_threads.get(name, threading.Thread()).is_alive():
        with locks[name]:
            def wrapped(*a):
                try:
                    target(*a)
                except HTTPError as e:
                    print(f"HTTP error: {e}")
                except subprocess.CalledProcessError as e:
                    print(f"CalledProcessError in thread '{name}': {e}")
                except Exception as e:
                    print(f"Error in '{name}': {e}")
                    sentry.capture_exception(e)
            t = threading.Thread(target=wrapped, args=args, daemon=True)
            t.start()
            running_threads[name] = t

# ── assorted helpers (unchanged) ───────────────────────────────────
def calculate_distance_to_point(ax, ay, bx, by):
    a = math.sin((bx - ax) / 2)**2 + math.cos(ax) * math.cos(bx) * math.sin((by - ay) / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS * c

def calculate_lane_width(lane, current_lane, road_edge):
    cx = np.array(current_lane.x)
    cy = np.array(current_lane.y)
    ly = np.interp(cx, lane.x, lane.y)
    ry = np.interp(cx, road_edge.x, road_edge.y)
    return float(min(np.mean(np.abs(cy - ly)), np.mean(np.abs(cy - ry))))

def calculate_road_curvature(modelData, v_ego):
    orientation_rate = np.abs(modelData.orientationRate.z)
    velocity         = modelData.velocity.x
    return np.amax(orientation_rate * velocity) / max(v_ego, 1)**2

def delete_file(path):
    path = Path(path)
    try:
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    except Exception as e:
        sentry.capture_exception(e)

def extract_zip(zip_file, extract_path):
    try:
        with zipfile.ZipFile(zip_file, "r") as z:
            z.extractall(extract_path)
        Path(zip_file).unlink()
    except Exception as e:
        sentry.capture_exception(e)

def flash_panda():
    """
    Force‑flashes the internal Panda then clears the FlashPanda toggle so the
    action is not repeated on the next boot.
    """
    HARDWARE.reset_internal_panda()
    Panda().wait_for_panda(None, 30)
    params_memory.put_bool("FlashPanda", False)


def is_url_pingable(url: str, timeout: int = 10) -> bool:
    """
    Performs a simple HTTP GET and returns True on HTTP 200.

    Meant for quick connectivity checks; *not* a robust health probe.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Python urllib)",
                "Accept":      "*/*",
                "Connection":  "keep-alive",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as rsp:
            return rsp.status == 200
    except Exception as e:
        print(f"Ping to {url} failed: {e}")
    return False


def lock_doors(lock_doors_timer: float, sm):
    """
    Waits until driver monitoring starts, then counts down *lock_doors_timer*
    seconds of uninterrupted face absence before sending the CAN door‑lock
    command (0x750 / `LOCK_CMD`).

    The loop resets if
      • ignition turns on
      • the driver’s face is detected again
      • driverMonitoringState dies
    """
    # wait for dmonitoringd to die and re‑spawn (as OP does during view toggle)
    while any(p.name == "dmonitoringd" and p.running for p in sm["managerState"].processes):
        time.sleep(DT_HW)
        sm.update()

    params.put_bool("IsDriverViewEnabled", True)

    while not any(p.name == "dmonitoringd" and p.running for p in sm["managerState"].processes):
        time.sleep(DT_HW)
        sm.update()

    start = time.monotonic()
    while True:
        if time.monotonic() - start >= lock_doors_timer:
            break

        if any(ps.ignitionLine or ps.ignitionCan for ps in sm["pandaStates"]
               if ps.pandaType != log.PandaState.PandaType.unknown):
            params.remove("IsDriverViewEnabled")
            return

        if sm["driverMonitoringState"].faceDetected or not sm.alive["driverMonitoringState"]:
            start = time.monotonic()

        time.sleep(DT_DMON)
        sm.update()

    panda = Panda()
    panda.set_safety_mode(panda.SAFETY_ALLOUTPUT)
    panda.can_send(0x750, LOCK_CMD, 0)
    panda.set_safety_mode(panda.SAFETY_TOYOTA)
    panda.send_heartbeat()
    params.remove("IsDriverViewEnabled")


def run_cmd(cmd: list[str], ok_msg: str, fail_msg: str):
    """Thin wrapper around subprocess.check_call with basic logging."""
    try:
        subprocess.check_call(cmd)
        print(ok_msg)
    except Exception as e:
        print(f"run_cmd() caught: {e}\n{fail_msg}")
        sentry.capture_exception(e)


def update_openpilot(manually_updated: bool, frogpilot_toggles):
    """
    Fires the standard updater flow unless ‘automatic updates’ is disabled or a
    manual update was just performed.
    """
    if not frogpilot_toggles.automatic_updates or manually_updated:
        return

    subprocess.run(["pkill", "-SIGUSR1", "-f", "system.updated.updated"], check=False)
    while params.get("UpdaterState", encoding="utf-8") != "checking...":
        time.sleep(DT_HW)
    while params.get("UpdaterState", encoding="utf-8") == "checking...":
        time.sleep(DT_HW)

    if not params.get_bool("UpdaterFetchAvailable"):
        return

    while params.get("UpdaterState", encoding="utf-8") != "idle":
        time.sleep(DT_HW)

    subprocess.run(["pkill", "-SIGHUP", "-f", "system.updated.updated"], check=False)
    while not params.get_bool("UpdateAvailable"):
        time.sleep(DT_HW)

    while params.get_bool("IsOnroad") or running_threads.get("lock_doors", threading.Thread()).is_alive():
        time.sleep(60)

    HARDWARE.reboot()


def get_carstate_attr(carstate, attr: str, default=None):
    """
    Uniform attribute accessor that copes with both flat and nested CarState
    layouts (the latter exposes data under .out).
    """
    val = getattr(carstate, attr, None)
    if val is None and hasattr(carstate, "out"):
        val = getattr(carstate.out, attr, default)
    return val if val is not None else default
