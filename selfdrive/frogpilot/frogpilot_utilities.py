#!/usr/bin/env python3
import json
import math
import numpy as np
import shutil
import subprocess
import threading
import time
import urllib.request
import zipfile
import os

import openpilot.system.sentry as sentry

from pathlib import Path
from urllib.error import HTTPError

from cereal import log
from openpilot.common.realtime import DT_DMON, DT_HW
from openpilot.selfdrive.car.toyota.carcontroller import LOCK_CMD
from openpilot.system.hardware import HARDWARE
from panda import Panda

from openpilot.selfdrive.frogpilot.frogpilot_variables import EARTH_RADIUS, MAPD_PATH, MAPS_PATH, params, params_memory

# --- START ADDITION ---
try:
    from azure.storage.fileshare import ShareFileClient, ShareDirectoryClient
    from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
except ImportError:
    # Allow the script to run but downloads will fail if Azure SDK isn't present
    ShareFileClient = None
    ShareDirectoryClient = None
    ResourceNotFoundError = None
    ResourceExistsError = None
    print("WARNING: Azure SDK not installed. Map downloads will fail. Install with: pip install azure-storage-file-share")
# --- END ADDITION ---

# --- START ADDITION ---
PROTOBUF_MAPS_PATH = "/data/media/0/map_data_tiles_protobuf" # New path for our Protobuf tiles
AZURE_SHARE_NAME = "mapdata"
AZURE_BASE_DIR = "protobuf_tiles"
CONN_STRING_PATH = "/persist/azure_conn_string"
# --- END ADDITION ---

running_threads = {}

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
  "update_themes": threading.Lock()
}

def run_thread_with_lock(name, target, args=()):
  if not running_threads.get(name, threading.Thread()).is_alive():
    with locks[name]:
      def wrapped_target(*t_args):
        try:
          target(*t_args)
        except HTTPError as error:
          print(f"HTTP error while accessing {api_url}: {error}")
        except subprocess.CalledProcessError as error:
          print(f"CalledProcessError in thread '{name}': {error}")
        except Exception as error:
          print(f"Error in thread '{name}': {error}")
          sentry.capture_exception(error)
      thread = threading.Thread(target=wrapped_target, args=args, daemon=True)
      thread.start()
      running_threads[name] = thread

def calculate_distance_to_point(ax, ay, bx, by):
  a = math.sin((bx - ax) / 2) * math.sin((bx - ax) / 2) + math.cos(ax) * math.cos(bx) * math.sin((by - ay) / 2) * math.sin((by - ay) / 2)
  c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
  return EARTH_RADIUS * c

def calculate_lane_width(lane, current_lane, road_edge):
  current_x = np.array(current_lane.x)
  current_y = np.array(current_lane.y)

  lane_y_interp = np.interp(current_x, np.array(lane.x), np.array(lane.y))
  road_edge_y_interp = np.interp(current_x, np.array(road_edge.x), np.array(road_edge.y))

  distance_to_lane = np.mean(np.abs(current_y - lane_y_interp))
  distance_to_road_edge = np.mean(np.abs(current_y - road_edge_y_interp))

  return float(min(distance_to_lane, distance_to_road_edge))

# Credit goes to Pfeiferj!
def calculate_road_curvature(modelData, v_ego):
  orientation_rate = np.abs(modelData.orientationRate.z)
  velocity = modelData.velocity.x
  max_pred_lat_acc = np.amax(orientation_rate * velocity)
  return max_pred_lat_acc / max(v_ego, 1)**2

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
  except Exception as error:
    print(f"An error occurred when deleting {path}: {error}")
    sentry.capture_exception(error)

def extract_zip(zip_file, extract_path):
  zip_file = Path(zip_file)
  extract_path = Path(extract_path)
  print(f"Extracting {zip_file} to {extract_path}")

  try:
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
      zip_ref.extractall(extract_path)
    zip_file.unlink()
    print(f"Extraction completed: {zip_file} has been removed")
  except Exception as error:
    print(f"An error occurred while extracting {zip_file}: {error}")
    sentry.capture_exception(error)

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
        "Connection": "keep-alive"
      }
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
      return response.status == 200
  except Exception as error:
    print(f"Unexpected error when pinging {url}: {error}")
  return False

def lock_doors(lock_doors_timer, sm):
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
  try:
    subprocess.check_call(cmd)
    print(success_message)
  except Exception as error:
    print(f"Unexpected error occurred: {error}")
    print(fail_message)
    sentry.capture_exception(error)

def update_maps(now):
  # --- START REMOVAL ---
  # while not MAPD_PATH.exists():
  #   time.sleep(60)
  # --- END REMOVAL ---

  maps_selected = json.loads(params.get("MapsSelected", encoding="utf-8") or "{}")
  if not (maps_selected.get("nations") or maps_selected.get("states")):
    return

  day = now.day
  is_first = day == 1
  is_Sunday = now.weekday() == 6
  schedule = params.get_int("PreferredSchedule")

  # --- START MODIFICATION ---
  # Check if the *protobuf* map base directory exists, then check for specific regions later
  protobuf_maps_base_exists = Path(PROTOBUF_MAPS_PATH).is_dir()
  # For now, assume we only handle single state selection for simplicity in download logic
  # We'll need to refine this to handle multiple states/nations if maps_selected can contain them
  selected_regions = maps_selected.get("states", []) + maps_selected.get("nations", []) # Combine for now
  target_region = selected_regions[0].lower() if selected_regions else None # Example: 'california'
  region_path_exists = False
  if protobuf_maps_base_exists and target_region:
      region_path_exists = (Path(PROTOBUF_MAPS_PATH) / target_region).is_dir()

  # Determine if download is needed:
  # 1. Region is selected but corresponding directory doesn't exist (Initial download)
  # 2. Directory exists, but update is scheduled
  needs_download = False
  if target_region and not region_path_exists:
      print(f"Protobuf map data for selected region '{target_region}' not found locally. Triggering download.")
      needs_download = True
  elif target_region and region_path_exists:
      # Existing logic for scheduled updates
      if schedule == 0: # Daily check
          pass # Handled below by checking LastMapsUpdate
      elif schedule == 1 and is_Sunday: # Weekly check
          pass # Handled below by checking LastMapsUpdate
      elif schedule == 2 and is_first: # Monthly check
          pass # Handled below by checking LastMapsUpdate
      else: # Schedule doesn't require update today
          return

      # Check if already updated today
      suffix = "th" if 4 <= day <= 20 or 24 <= day <= 30 else ["st", "nd", "rd"][day % 10 - 1]
      todays_date = now.strftime(f"%B {day}{suffix}, %Y")
      if params.get("LastMapsUpdate", encoding="utf-8") == todays_date:
          return # Already updated today
      else:
          print(f"Scheduled map update required for region '{target_region}'.")
          needs_download = True
  else:
       # No region selected or other condition
       return

  if not needs_download:
      return

  # --- END MODIFICATION ---

  # --- START REMOVAL ---
  # suffix = "th" if 4 <= day <= 20 or 24 <= day <= 30 else ["st", "nd", "rd"][day % 10 - 1]
  # todays_date = now.strftime(f"%B {day}{suffix}, %Y")

  # if maps_downloaded and params.get("LastMapsUpdate", encoding="utf-8") == todays_date:
  #   return

  # if params.get("OSMDownloadProgress", encoding="utf-8") is None:
  #   params_memory.put("OSMDownloadLocations", json.dumps(maps_selected))

  # while params.get("OSMDownloadProgress", encoding="utf-8") is not None:
  #   time.sleep(60)
  # --- END REMOVAL ---

  # --- START PLACEHOLDER for Azure Download Logic ---
  # print(f"Placeholder: Would initiate Azure download for region: {target_region} now...")
  # TODO: Implement Azure download logic here
  #  - Read connection string
  #  - Connect to Azure ShareFileClient/ShareDirectoryClient
  #  - Determine remote path (e.g., protobuf_tiles/california)
  #  - Create local path (e.g., /data/media/0/map_data_tiles_protobuf/california)
  #  - Download files/directories recursively
  #  - Handle errors
  #  - Update progress param (e.g., ProtobufMapDownloadProgress)
  # --- START REPLACEMENT ---
  print(f"Initiating Azure map download for region: {target_region}")
  params_memory.put("ProtobufMapDownloadProgress", "Starting...") # Initial progress state
  params_memory.remove("ProtobufMapDownloadError") # Clear previous errors

  download_success = False
  conn_str = get_azure_connection_string(CONN_STRING_PATH)

  if conn_str and ShareDirectoryClient is not None:
      # Define remote and local paths
      remote_region_path = f"{AZURE_BASE_DIR}/{target_region}" # e.g., protobuf_tiles/california
      local_region_path = Path(PROTOBUF_MAPS_PATH) / target_region # e.g., /data/media/0/.../california

      try:
          # Ensure the parent directory exists locally (/data/media/0/map_data_tiles_protobuf)
          ensure_local_directory_exists(Path(PROTOBUF_MAPS_PATH))

          # Perform the recursive download
          # The helper function handles creating subdirs and updating progress/error params
          download_success = download_azure_directory_recursive(
              conn_str,
              AZURE_SHARE_NAME,
              remote_region_path,
              local_region_path
          )
      except Exception as e:
          print(f"Error during map download process initiation: {e}")
          sentry.capture_exception(e)
          params_memory.put("ProtobufMapDownloadError", f"Download failed: {e}")
          params_memory.remove("ProtobufMapDownloadProgress") # Remove progress on setup error
          download_success = False
  elif ShareDirectoryClient is None:
       print("Azure SDK missing, download cannot proceed.")
       params_memory.put("ProtobufMapDownloadError", "Azure SDK missing")
       params_memory.remove("ProtobufMapDownloadProgress")
  else:
       # Connection string error already printed by helper
       params_memory.put("ProtobufMapDownloadError", "Connection string error")
       params_memory.remove("ProtobufMapDownloadProgress")

  # --- END REPLACEMENT ---

  # Simulate download completion for now
  # time.sleep(5) # Placeholder delay -- REMOVED

  # --- END PLACEHOLDER ---

  # --- START MODIFICATION ---
  # Update LastMapsUpdate param ONLY on successful completion
  if download_success:
      suffix = "th" if 4 <= day <= 20 or 24 <= day <= 30 else ["st", "nd", "rd"][day % 10 - 1]
      todays_date = now.strftime(f"%B {day}{suffix}, %Y")
      params.put("LastMapsUpdate", todays_date)
      print(f"Map download/update process completed successfully for {target_region}. Updated LastMapsUpdate.")
  else:
      print(f"Map download/update process failed for {target_region}. LastMapsUpdate not changed.")
  # --- END MODIFICATION ---

def update_openpilot(manually_updated, frogpilot_toggles):
  if not frogpilot_toggles.automatic_updates or manually_updated:
    return

  subprocess.run(["pkill", "-SIGUSR1", "-f", "system.updated.updated"], check=False)
  while not params.get("UpdaterState", encoding="utf-8") == "checking...":
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
  Safely retrieves attributes from CarState objects, handling different data structures.

  IMPORTANT: Use this helper in all FrogPilot modules when accessing CarState attributes!
  This ensures compatibility with both direct and nested CarState objects throughout the codebase.

  OpenPilot has two different CarState object structures:
  1. A flat structure with direct attributes (used in modeld.py and other modules)
  2. A nested structure with an 'out' property (used in CarController and vehicle interfaces)

  This helper handles both formats to ensure compatibility across different parts of the system.

  Usage examples:
    v_ego = get_carstate_attr(carstate, 'vEgo', 0.0)
    standstill = get_carstate_attr(carstate, 'standstill', False)
    left_blinker = get_carstate_attr(carstate, 'leftBlinker', False)

  Args:
      carstate: The CarState object to get the attribute from
      attr: The attribute name to retrieve
      default: Default value to return if attribute is not found

  Returns:
      The attribute value or default if not found
  """
  # First try direct access
  value = getattr(carstate, attr, None)

  # If not found and object has 'out' property, try accessing through 'out'
  if value is None and hasattr(carstate, 'out'):
      value = getattr(carstate.out, attr, default)

  # Return either the found value or default
  return value if value is not None else default

# --- START ADDITION: Azure Helpers ---
def get_azure_connection_string(path: str) -> str | None:
    """Reads the Azure connection string from the specified file path."""
    try:
        with open(path, "r") as f:
            conn_str = f.read().strip()
        if not conn_str:
            print(f"Error: Connection string file '{path}' is empty.")
            return None
        # print(f"Successfully read connection string from {path}") # Too verbose for on-device
        return conn_str
    except FileNotFoundError:
        print(f"Error: Connection string file not found at '{path}'. Download cannot proceed.")
        return None
    except Exception as e:
        print(f"Error reading connection string from '{path}': {e}")
        sentry.capture_exception(e)
        return None

def ensure_local_directory_exists(local_path: Path):
    """Ensures a local directory exists, creating it if necessary."""
    try:
        local_path.mkdir(parents=True, exist_ok=True)
        # print(f"Ensured local directory exists: {local_path}") # Too verbose
    except Exception as e:
        print(f"Error creating local directory {local_path}: {e}")
        sentry.capture_exception(e)
        raise # Propagate error as we can't download without the dir

def download_azure_directory_recursive(conn_str: str, share_name: str, remote_dir_path: str, local_base_path: Path):
    """Recursively downloads files from an Azure directory to a local path."""
    if ShareDirectoryClient is None:
        print("Azure SDK not available, cannot download directory.")
        raise Exception("Azure SDK required for download.")

    print(f"Starting recursive download from Azure: {share_name}/{remote_dir_path} to {local_base_path}")
    total_files = 0
    downloaded_files = 0
    error_files = 0
    progress_param = "ProtobufMapDownloadProgress"
    error_param = "ProtobufMapDownloadError"

    try:
        # Base directory client for the starting remote path
        base_dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, remote_dir_path)
        items_to_process = [(base_dir_client, local_base_path)] # Queue of (ShareDirectoryClient, local_path)

        # First pass to count total files (optional, but good for progress)
        # This could be slow for very large directories. Consider skipping if performance is an issue.
        print("Counting total files in remote directory...")
        count_queue = [base_dir_client]
        while count_queue:
            current_dir_client_for_count = count_queue.pop(0)
            try:
                 for item in current_dir_client_for_count.list_directories_and_files():
                     if item['is_directory']:
                         count_queue.append(current_dir_client_for_count.get_subdirectory_client(item['name']))
                     else:
                         total_files += 1
            except Exception as e:
                 print(f"Warning: Error listing contents of {current_dir_client_for_count.directory_path} during count: {e}")
                 # Continue counting other parts if possible
        print(f"Found approximately {total_files} files to download.")
        params_memory.put(progress_param, f"0/{total_files}") # Initial progress

        # Start processing the download queue
        while items_to_process:
            current_dir_client, current_local_path = items_to_process.pop(0)
            ensure_local_directory_exists(current_local_path)

            try:
                for item in current_dir_client.list_directories_and_files():
                    item_name = item['name']
                    item_is_directory = item['is_directory']
                    local_item_path = current_local_path / item_name

                    if item_is_directory:
                        print(f"  Found remote directory: {item_name}")
                        items_to_process.append((current_dir_client.get_subdirectory_client(item_name), local_item_path))
                    else: # It's a file
                        print(f"  Downloading file: {item_name} to {local_item_path}")
                        try:
                            file_client = current_dir_client.get_file_client(item_name)
                            with open(local_item_path, "wb") as local_file:
                                download_stream = file_client.download_file()
                                local_file.write(download_stream.readall())
                            downloaded_files += 1
                            print(f"    Downloaded {item_name} successfully.")
                            # Update progress
                            if total_files > 0:
                                params_memory.put(progress_param, f"{downloaded_files}/{total_files}")
                        except Exception as file_e:
                            print(f"    Error downloading file {item_name}: {file_e}")
                            sentry.capture_exception(file_e)
                            error_files += 1
                            params_memory.put(error_param, f"Error downloading {item_name}: {file_e}")
                            # Optionally delete partial file?
                            if local_item_path.exists():
                                try: local_item_path.unlink() catch: pass

            except Exception as list_e:
                 print(f"Error listing contents of Azure directory {current_dir_client.directory_path}: {list_e}")
                 sentry.capture_exception(list_e)
                 params_memory.put(error_param, f"Error listing Azure dir {current_dir_client.directory_path}")
                 # Potentially stop or try to continue?
                 # For now, let loop continue if possible, but this might leave partial downloads.

    except ResourceNotFoundError:
        print(f"Error: Remote Azure directory not found: {share_name}/{remote_dir_path}")
        params_memory.put(error_param, f"Remote directory not found: {remote_dir_path}")
        return False # Indicate failure
    except Exception as e:
        print(f"An unexpected error occurred during Azure download: {e}")
        sentry.capture_exception(e)
        params_memory.put(error_param, f"Unexpected download error: {e}")
        return False # Indicate failure
    finally:
        # Clean up progress param on exit (success or failure)
        # Keep error param on failure
        if error_files == 0:
             params_memory.remove(progress_param)
             params_memory.remove(error_param) # Clear previous errors on success
        else:
             # Maybe set progress to error state?
             params_memory.put(progress_param, f"Error ({downloaded_files}/{total_files})")

    print(f"Recursive download finished. Downloaded: {downloaded_files}, Errors: {error_files}")
    return error_files == 0 # Return True if successful
# --- END ADDITION: Azure Helpers ---

