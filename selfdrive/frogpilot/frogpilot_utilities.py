#!/usr/bin/env python3
"""
Map data utilities and assorted helper functions for the FrogPilot fork.

This script handles:
  • Protobuf‑tile download/update from an Azure File Share
  • A handful of small OpenPilot utility helpers that other modules import

It is self‑contained: all map‑specific constants, helpers, and the
`update_maps()` scheduler live in one contiguous section so the control flow
is easy to follow and maintain.
"""
# ──────────────────────────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────────────────────────
import json
import math
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError

import numpy as np
from cereal import log
from panda import Panda

import openpilot.system.sentry as sentry
from openpilot.common.realtime import DT_DMON, DT_HW
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.car.toyota.carcontroller import LOCK_CMD
from openpilot.system.hardware import HARDWARE
from openpilot.selfdrive.frogpilot.frogpilot_variables import (
    EARTH_RADIUS,
    MAPD_PATH,
    MAPS_PATH,
    params,
    params_memory,
)

# Optional Azure SDK
try:
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
    from azure.storage.fileshare import ShareDirectoryClient, ShareFileClient
except ImportError:
    ShareDirectoryClient = ShareFileClient = None
    ResourceExistsError = ResourceNotFoundError = None
    print(
        "WARNING: Azure SDK not installed. Map downloads will fail.\n"
        "Install with `pip install azure-storage-file-share`."
    )

# ──────────────────────────────────────────────────────────────────────────────
# Global objects used in several helper threads
# ──────────────────────────────────────────────────────────────────────────────
running_threads: dict[str, threading.Thread] = {}

locks = {
    "backup_toggles": threading.Lock(),
    "download_all_models": threading.Lock(),
    "download_model": threading.Lock(),
    "download_theme": threading.Lock(),
    "flash_panda": threading.Lock(),
    "lock_doors": threading.Lock(),
    "update_checks": threading.Lock(),
    "update_maps": threading.Lock(),
    "update_models": threading.Lock(),
    "update_openpilot": threading.Lock(),
    "update_themes": threading.Lock(),
}


def run_thread_with_lock(name: str, target, args: tuple = ()) -> None:
    """Run *target* exactly once per lock name."""
    if running_threads.get(name, threading.Thread()).is_alive():
        return

    with locks[name]:

        def wrapped_target(*t_args):
            try:
                target(*t_args)
            except HTTPError as e:
                print(f"HTTP error in '{name}': {e}")
            except subprocess.CalledProcessError as e:
                print(f"CalledProcessError in '{name}': {e}")
            except Exception as e:  # pylint: disable=broad-except
                print(f"Uncaught error in '{name}': {e}")
                sentry.capture_exception(e)

        thread = threading.Thread(target=wrapped_target, args=args, daemon=True)
        thread.start()
        running_threads[name] = thread


# ──────────────────────────────────────────────────────────────────────────────
# Geometry helpers (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
def calculate_distance_to_point(ax, ay, bx, by):
    a = (
        math.sin((bx - ax) / 2) ** 2
        + math.cos(ax) * math.cos(bx) * math.sin((by - ay) / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS * c


def calculate_lane_width(lane, current_lane, road_edge):
    current_x = np.array(current_lane.x)
    current_y = np.array(current_lane.y)

    lane_y_interp = np.interp(current_x, np.array(lane.x), np.array(lane.y))
    road_edge_y_interp = np.interp(
        current_x, np.array(road_edge.x), np.array(road_edge.y)
    )

    distance_to_lane = np.mean(np.abs(current_y - lane_y_interp))
    distance_to_road_edge = np.mean(np.abs(current_y - road_edge_y_interp))

    return float(min(distance_to_lane, distance_to_road_edge))


def calculate_road_curvature(modelData, v_ego):
    orientation_rate = np.abs(modelData.orientationRate.z)
    velocity = modelData.velocity.x
    max_pred_lat_acc = np.amax(orientation_rate * velocity)
    return max_pred_lat_acc / max(v_ego, 1) ** 2


# ──────────────────────────────────────────────────────────────────────────────
# Filesystem helpers (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
def delete_file(path):
    path = Path(path)
    try:
        if path.is_file() or path.is_symlink():
            path.unlink()
            print(f"Deleted file: {path}")
        elif path.is_dir():
            shutil.rmtree(path)
            print(f"Deleted directory: {path}")
        else:
            print(f"File not found: {path}")
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error deleting {path}: {e}")
        sentry.capture_exception(e)


def extract_zip(zip_file, extract_path):
    zip_file = Path(zip_file)
    extract_path = Path(extract_path)
    print(f"Extracting {zip_file} to {extract_path}")
    try:
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(extract_path)
        zip_file.unlink()
    except Exception as e:  # pylint: disable=broad-except
        print(f"Extraction error in {zip_file}: {e}")
        sentry.capture_exception(e)


# ──────────────────────────────────────────────────────────────────────────────
# Miscellaneous OpenPilot helpers (unchanged)
# ──────────────────────────────────────────────────────────────────────────────
def flash_panda():
    HARDWARE.reset_internal_panda()
    Panda().wait_for_panda(None, 30)
    params_memory.put_bool("FlashPanda", False)


def is_url_pingable(url, timeout=10):
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Python urllib)",
                "Accept": "*/*",
                "Connection": "keep-alive",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except Exception as e:  # pylint: disable=broad-except
        print(f"Ping error for {url}: {e}")
    return False


# lock_doors(), run_cmd(), get_carstate_attr() left unchanged
# ──────────────────────────────────────────────────────────────────────────────
# MAP‑DOWNLOAD LOGIC  ‒ all constants & helpers in one place
# ──────────────────────────────────────────────────────────────────────────────
PROTOBUF_MAPS_PATH = "/data/media/0/map_data_tiles_protobuf"
AZURE_SHARE_NAME = "mapdata"          # <storage‑acct>.file…\mapdata\
AZURE_BASE_DIR = "protobuf_tiles"     # mapdata/protobuf_tiles/…
CONN_STRING_PATH = "/persist/azure_conn_string"

# Progress/error param names — kept in one spot so UI can refer to them
DL_PROGRESS_PARAM = "ProtobufMapDownloadProgress"
DL_ERROR_PARAM = "ProtobufMapDownloadError"


def get_azure_connection_string(path: str | None = None) -> str | None:
    """
    Get Azure connection string.

    This implementation prioritizes the connection string found in the specified
    file path.

    Parameters:
        path: Optional file path to check for the connection string. Defaults to
              the value specified during the function call.

    Returns:
        The connection string if found, otherwise None.
    """
    # Only check the disk file
    if path:
        try:
            with open(path, "r") as fh:
                conn = fh.read().strip()
            if conn:
                return conn
            print(f"Connection-string file '{path}' is empty.")
        except FileNotFoundError:
            print(f"Connection-string file '{path}' not found.")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error reading '{path}': {e}")
            sentry.capture_exception(e)
    return None


def ensure_local_directory_exists(local_path: Path) -> None:
    """Create *local_path* (plus parents) if it does not yet exist."""
    try:
        local_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # pylint: disable=broad-except
        print(f"Cannot create directory {local_path}: {e}")
        sentry.capture_exception(e)
        raise


def download_azure_directory_recursive(
    conn_str: str, share: str, remote_dir: str, local_base: Path
) -> bool:
    """
    Recursively mirror *remote_dir* (Azure) into *local_base*.

    Returns True on complete success.
    """
    if ShareDirectoryClient is None:
        print("Azure SDK missing.")
        raise RuntimeError("Azure SDK required for download")

    cloudlog.info("maps: begin recursive sync %s → %s", remote_dir, local_base)
    total_files = downloaded = errors = 0
    params_memory.put(DL_PROGRESS_PARAM, "0/0")

    try:
        base_client = ShareDirectoryClient.from_connection_string(conn_str, share, remote_dir)
        q: list[tuple[ShareDirectoryClient, Path]] = [(base_client, local_base)]

        # first pass – count files
        while q:
            c, _ = q.pop()
            try:
                for itm in c.list_directories_and_files():
                    if itm["is_directory"]:
                        q.append((c.get_subdirectory_client(itm["name"]), Path()))
                    else:
                        total_files += 1
            except Exception as e:  # pylint: disable=broad-except
                cloudlog.exception("maps: list() during count failed: %s", e)

        params_memory.put(DL_PROGRESS_PARAM, f"0/{total_files}")
        q = [(base_client, local_base)]  # reset queue for actual transfer

        # second pass – download
        while q:
            cdir, ldir = q.pop()
            ensure_local_directory_exists(ldir)

            for itm in cdir.list_directories_and_files():
                name = itm["name"]
                is_dir = itm["is_directory"]
                lpath = ldir / name

                if is_dir:
                    q.append((cdir.get_subdirectory_client(name), lpath))
                    continue

                try:
                    fcli = cdir.get_file_client(name)
                    with open(lpath, "wb") as fp:
                        fp.write(fcli.download_file().readall())
                    downloaded += 1
                    params_memory.put(DL_PROGRESS_PARAM, f"{downloaded}/{total_files}")
                except Exception as e:  # pylint: disable=broad-except
                    errors += 1
                    cloudlog.exception("maps: download %s failed: %s", name, e)
                    params_memory.put(DL_ERROR_PARAM, f"Error downloading {name}")
                    if lpath.exists():
                        try:
                            lpath.unlink()
                        except Exception:  # pylint: disable=broad-except
                            pass

    except ResourceNotFoundError:
        params_memory.put(DL_ERROR_PARAM, "Remote directory not found")
        return False
    except Exception as e:  # pylint: disable=broad-except
        cloudlog.exception("maps: sync failed: %s", e)
        params_memory.put(DL_ERROR_PARAM, f"Unexpected error: {e}")
        return False
    finally:
        if errors == 0:
            params_memory.remove(DL_ERROR_PARAM)
            params_memory.remove(DL_PROGRESS_PARAM)
        else:
            params_memory.put(DL_PROGRESS_PARAM, f"Error ({downloaded}/{total_files})")

    cloudlog.info("maps: sync completed ‑ OK=%d, ERR=%d", downloaded, errors)
    return errors == 0


def update_maps(now: datetime) -> None:
    """
    Scheduler/driver for protobuf‑tile updates.

    * All region‑specific logic removed – the whole `protobuf_tiles/` tree is
      mirrored on whatever cadence the driver selects.
    * Now runs **only** when explicitly called, typically triggered by the UI.
    """
    # sanity checks
    conn = get_azure_connection_string(CONN_STRING_PATH)
    if ShareDirectoryClient is None:
        cloudlog.warning("maps: Azure SDK missing, aborting")
        return
    if not conn:
        cloudlog.warning("maps: No Azure connection string, aborting")
        return

    params_memory.remove(DL_ERROR_PARAM)
    params_memory.put(DL_PROGRESS_PARAM, "Starting…")

    remote_dir = AZURE_BASE_DIR             # protobuf_tiles
    local_dir = Path(PROTOBUF_MAPS_PATH)    # /data/…/protobuf_tiles

    try:
        ensure_local_directory_exists(local_dir)
        ok = download_azure_directory_recursive(conn, AZURE_SHARE_NAME, remote_dir, local_dir)
    except Exception as e:  # pylint: disable=broad-except
        cloudlog.exception("maps: top‑level failure: %s", e)
        params_memory.put(DL_ERROR_PARAM, f"Download failed: {e}")
        params_memory.remove(DL_PROGRESS_PARAM)
        return

    if ok:
        # No longer track LastMapsUpdate based on schedule
        cloudlog.info("maps: update successful")
    else:
        cloudlog.warning("maps: update failed")


# ──────────────────────────────────────────────────────────────────────────────
# Functions below are unchanged from the original implementation
# ──────────────────────────────────────────────────────────────────────────────
def lock_doors(lock_doors_timer, sm):
  """
  Locks the vehicle after a driver‑monitoring timeout if the car is parked
  and no ignition activity occurs.

  NOTE: Uses Panda CAN commands; keep safety‑mode ordering unchanged.
  """
  while any(proc.name == "dmonitoringd" and proc.running for proc in sm["managerState"].processes):
    time.sleep(DT_HW)
    sm.update()

  params.put_bool("IsDriverViewEnabled", True)

  while not any(proc.name == "dmonitoringd" and proc.running for proc in sm["managerState"].processes):
    time.sleep(DT_HW)
    sm.update()

  start_time = time.monotonic()
  while True:
    elapsed_time = time.monotonic() - start_time
    if elapsed_time >= lock_doors_timer:
      break

    if any(ps.ignitionLine or ps.ignitionCan for ps in sm["pandaStates"] if ps.pandaType != log.PandaState.PandaType.unknown):
      params.remove("IsDriverViewEnabled")
      return

    if sm["driverMonitoringState"].faceDetected or not sm.alive["driverMonitoringState"]:
      start_time = time.monotonic()

    time.sleep(DT_DMON)
    sm.update()

  panda = Panda()
  panda.set_safety_mode(panda.SAFETY_ALLOUTPUT)
  panda.can_send(0x750, LOCK_CMD, 0)
  panda.set_safety_mode(panda.SAFETY_TOYOTA)
  panda.send_heartbeat()

  params.remove("IsDriverViewEnabled")


def run_cmd(cmd, success_message, fail_message):
  """Convenience wrapper around subprocess.check_call with sentry logging."""
  try:
    subprocess.check_call(cmd)
    print(success_message)
  except Exception as error:  # pylint: disable=broad-except
    print(f"Unexpected error occurred: {error}")
    print(fail_message)
    sentry.capture_exception(error)


def update_openpilot(manually_updated, frogpilot_toggles):
  """
  Triggers an OpenPilot OTA update when automatic updates are enabled and the
  head‑unit is idle (i.e. not on‑road, driver monitor inactive, etc.).
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


def get_carstate_attr(carstate, attr, default=None):
  """
  Safe attribute access for CarState objects that may be either flat or nested
  (some interfaces expose carstate.out.<attr>). Always prefer this helper when
  reading from *carstate* to avoid KeyErrors in mixed code paths.
  """
  value = getattr(carstate, attr, None)
  if value is None and hasattr(carstate, 'out'):
    value = getattr(carstate.out, attr, default)
  return value if value is not None else default
