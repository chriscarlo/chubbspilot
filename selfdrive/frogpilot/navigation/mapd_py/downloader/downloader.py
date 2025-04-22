"""
Reimplementation of the mapd downloader logic in Python.
Downloads and extracts map data from map-data.pfeifer.dev based on params.
NOW: Acts as a trigger for the Azure Protobuf map downloader.
"""

import os
# import requests # Removed - No longer used
# import tarfile # Removed - No longer used
# import gzip # Removed - No longer used
import shutil # Keep for potential future cleanup? Or remove if update_maps handles all cleanup.
# import math # Removed - No longer used
# import json # Removed - No longer used
import time
# import threading # Removed - No longer used
from datetime import datetime # Added

# --- START MODIFICATION ---
# Remove old param imports
# from .params import (get_param, put_param, remove_param, get_param_json,
#                      put_param_json, get_base_path,
#                      DOWNLOAD_BOUNDS, DOWNLOAD_LOCATIONS, DOWNLOAD_PROGRESS,
#                      get_param # Re-import get_param specifically if needed, though already imported
#                      )
# from .locations import NATION_BOXES, STATE_BOXES, load_locations # Removed - No longer used

# Import the new update function and necessary modules
from openpilot.common.params import Params # Added for potential direct param access if needed later
from openpilot.common.realtime import Ratekeeper # Added for service loop
import openpilot.system.sentry as sentry # Added for error reporting
from openpilot.common.swaglog import cloudlog # Added for logging
from openpilot.selfdrive.frogpilot.frogpilot_utilities import update_maps

# Define update frequency (e.g., check every 15 minutes) - Moved from deleted map_downloader.py
UPDATE_CHECK_INTERVAL_SECONDS = 60 * 15
# --- END MODIFICATION ---


# Constants - Remove old constants
# GROUP_AREA_BOX_DEGREES = 2
# DOWNLOAD_URL_BASE = "https://map-data.pfeifer.dev/offline"
# TMP_DOWNLOAD_DIR = os.path.join(get_base_path(), "tmp", "offline")
# TARGET_EXTRACT_DIR = get_base_path() # Extract directly into the base OSM path
# DOWNLOAD_TIMEOUT = 60 # seconds

# Remove Cancel Param Key
# OSM_CANCEL_DOWNLOAD = "OSMCancelDownload"

# Remove old directory creation
# Ensure necessary directories exist
# os.makedirs(TMP_DOWNLOAD_DIR, exist_ok=True)
# os.makedirs(TARGET_EXTRACT_DIR, exist_ok=True)

# --- Remove Old Progress Tracking ---
# progress_lock = threading.Lock()
# current_progress = { ... }
# def _update_progress_param(): ...
# def _reset_progress(...): ...
# def _increment_progress(...): ...
# def _set_error_progress(...): ...
# --- End Remove Old Progress Tracking ---


# --- Remove Old Core Download Logic ---
# def _calculate_adjusted_bounds(bounds): ...
# def _count_files_for_bounds(bounds): ...
# def _check_cancel_requested(): ...
# def _download_and_extract_file(lat_group, lon_group, location_name): ...
# def download_bounds(bounds, location_name="CUSTOM"): ...
# --- End Remove Old Core Download Logic ---

# --- START MODIFICATION: Replace run_downloader with service loop ---
# def run_downloader():
#     """Main function to check params and trigger downloads."""
#     # Remove old logic...
#
#     # --- NEW LOGIC ---
#     print("Map Downloader Service loop calling update_maps")
#     cloudlog.info("Map Downloader Service loop calling update_maps") # Use cloudlog
#     try:
#         now = datetime.now()
#         update_maps(now) # Call the function from frogpilot_utilities
#     except Exception as e:
#         cloudlog.exception("mapd_py.downloader.run_downloader_exception")
#         sentry.capture_exception(e)
#
#     # Old cleanup/param removal is removed as update_maps handles its own state.
#     print(f"Map Downloader cycle finished") # Simplified message

def main():
  """Main service loop for the map downloader trigger."""
  cloudlog.info("Starting map downloader trigger service (mapd_py.downloader)")
  sentry.init(sentry.SentryProject.SELFDRIVE) # Or appropriate project

  params = Params() # Need params instance to check/put the trigger
  rk = Ratekeeper(1.0 / UPDATE_CHECK_INTERVAL_SECONDS, print_delay_threshold=None)

  while True:
    # Initialize check_triggered to False at the start of each loop iteration
    check_triggered = False
    try:
      # Check for the trigger parameter first
      if params.get_bool("TriggerMapDownloadCheck"):
        cloudlog.info("Map download check manually triggered.")
        params.put_bool("TriggerMapDownloadCheck", False) # Reset trigger
        check_triggered = True
        now = datetime.now()
        update_maps(now) # Run the check immediately
        # Reset Ratekeeper timer to prevent immediate timed check after triggered check
        rk.monitor_time = time.monotonic() # Reset monitor start time
        rk.last_monitor_time = rk.monitor_time # Ensure next keep_time waits full interval

      # Let Ratekeeper handle the timed check *only if not manually triggered*
      # keep_time() will call update_maps if the interval has passed since the last check
      # (which we reset above if manually triggered)
      if rk.keep_time() and not check_triggered:
        now = datetime.now()
        cloudlog.info(f"Map downloader trigger service checking for updates (scheduled) at {now}")
        update_maps(now)
      elif not check_triggered:
        # If keep_time() returned False and wasn't triggered, it means the interval hasn't passed.
        # We can sleep briefly to avoid busy-waiting, Ratekeeper handles the main interval.
        time.sleep(1) # Sleep 1 second if no trigger and not time for scheduled check

    except Exception as e:
      cloudlog.exception("mapd_py.downloader.service_loop_exception")
      sentry.capture_exception(e)
      # Avoid rapid error loops, wait before retrying
      time.sleep(60)

    # No longer need rk.keep_time() here as it's handled conditionally above
    # rk.keep_time()

# --- END MODIFICATION ---


if __name__ == "__main__":
    # --- START MODIFICATION: Call main() instead of run_downloader() ---
    # This allows running the script directly for testing the service loop
    # run_downloader() # Old call removed
    main() # New call to start the service loop
    # --- END MODIFICATION ---