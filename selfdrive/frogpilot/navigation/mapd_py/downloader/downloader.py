"""
Reimplementation of the mapd downloader logic in Python.
Downloads and extracts map data from map-data.pfeifer.dev based on params.
"""

import os
import requests
import tarfile
import gzip
import shutil
import math
import json
import time
import threading
from .params import (get_param, put_param, remove_param, get_param_json,
                     put_param_json, get_base_path,
                     DOWNLOAD_BOUNDS, DOWNLOAD_LOCATIONS, DOWNLOAD_PROGRESS,
                     get_param # Re-import get_param specifically if needed, though already imported
                     )
from .locations import NATION_BOXES, STATE_BOXES, load_locations

# Constants
GROUP_AREA_BOX_DEGREES = 2
DOWNLOAD_URL_BASE = "https://map-data.pfeifer.dev/offline"
TMP_DOWNLOAD_DIR = os.path.join(get_base_path(), "tmp", "offline")
TARGET_EXTRACT_DIR = get_base_path() # Extract directly into the base OSM path
DOWNLOAD_TIMEOUT = 60 # seconds

# Add Cancel Param Key
OSM_CANCEL_DOWNLOAD = "OSMCancelDownload"

# Ensure necessary directories exist
os.makedirs(TMP_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(TARGET_EXTRACT_DIR, exist_ok=True)

# --- Progress Tracking ---
# Thread-safe progress tracking
progress_lock = threading.Lock()
current_progress = {
    "total_files": 0,
    "downloaded_files": 0,
    "locations_to_download": [],
    "location_details": {}, # {location_name: {"location_total_files": X, "location_downloaded_files": Y}}
    "current_action": "Idle", # e.g., "Downloading", "Extracting", "Error", "Complete"
    "error_message": ""
}

def _update_progress_param():
    """Writes the current progress state to the param."""
    with progress_lock:
        # Make a copy to avoid race conditions during JSON serialization
        progress_copy = current_progress.copy()
        # Update action based on state
        if progress_copy["error_message"]:
            progress_copy["current_action"] = "Error"
        elif progress_copy["downloaded_files"] == progress_copy["total_files"] and progress_copy["total_files"] > 0:
             progress_copy["current_action"] = "Complete"
    put_param_json(DOWNLOAD_PROGRESS, progress_copy, persistent=False)


def _reset_progress(locations_to_download, total_files, location_details):
    """Resets the progress structure for a new download job."""
    with progress_lock:
        current_progress["total_files"] = total_files
        current_progress["downloaded_files"] = 0
        current_progress["locations_to_download"] = locations_to_download
        current_progress["location_details"] = location_details
        current_progress["current_action"] = "Starting"
        current_progress["error_message"] = ""
    _update_progress_param()


def _increment_progress(location_name):
    """Increments the downloaded file count for a specific location and overall."""
    with progress_lock:
        current_progress["downloaded_files"] += 1
        if location_name in current_progress["location_details"]:
            current_progress["location_details"][location_name]["location_downloaded_files"] += 1
        current_progress["current_action"] = "Downloading" # Or Extracting if we split steps
    _update_progress_param()

def _set_error_progress(message):
    """Sets an error state in the progress."""
    with progress_lock:
        current_progress["current_action"] = "Error"
        current_progress["error_message"] = str(message)
    _update_progress_param()


# --- Core Download Logic ---

def _calculate_adjusted_bounds(bounds):
    """Calculates the grid boundaries based on GROUP_AREA_BOX_DEGREES."""
    min_lat_f = bounds.get("min_lat", 0.0)
    min_lon_f = bounds.get("min_lon", 0.0)
    max_lat_f = bounds.get("max_lat", 0.0)
    max_lon_f = bounds.get("max_lon", 0.0)

    min_lat = int(math.floor(min_lat_f / GROUP_AREA_BOX_DEGREES)) * GROUP_AREA_BOX_DEGREES
    min_lon = int(math.floor(min_lon_f / GROUP_AREA_BOX_DEGREES)) * GROUP_AREA_BOX_DEGREES
    max_lat = int(math.floor(max_lat_f / GROUP_AREA_BOX_DEGREES)) * GROUP_AREA_BOX_DEGREES
    max_lon = int(math.floor(max_lon_f / GROUP_AREA_BOX_DEGREES)) * GROUP_AREA_BOX_DEGREES

    # Adjust max bounds if necessary (exclusive range in Go vs inclusive here)
    if max_lat_f > float(max_lat):
         max_lat += GROUP_AREA_BOX_DEGREES
    if max_lon_f > float(max_lon):
         max_lon += GROUP_AREA_BOX_DEGREES

    return min_lat, min_lon, max_lat, max_lon

def _count_files_for_bounds(bounds):
    """Counts the number of grid files needed for a given bounds dict."""
    if not bounds:
        return 0
    min_lat, min_lon, max_lat, max_lon = _calculate_adjusted_bounds(bounds)
    lat_steps = (max_lat - min_lat) // GROUP_AREA_BOX_DEGREES
    lon_steps = (max_lon - min_lon) // GROUP_AREA_BOX_DEGREES
    return lat_steps * lon_steps

def _check_cancel_requested():
    """Checks if the cancellation parameter is set."""
    # Read as bytes, check if it's '1'
    cancel_flag = get_param(OSM_CANCEL_DOWNLOAD, persistent=False, default=b'0')
    return cancel_flag == b'1'

def _download_and_extract_file(lat_group, lon_group, location_name):
    """Downloads a single tar.gz file and extracts it."""
    # --- Cancellation Check --- Start
    if _check_cancel_requested():
        print("Cancellation requested, stopping download.")
        _set_error_progress("Download cancelled by user.") # Set specific cancel status
        return False # Indicate failure due to cancellation
    # --- Cancellation Check --- End

    filename = f"{lat_group}/{lon_group}.tar.gz"
    url = f"{DOWNLOAD_URL_BASE}/{filename}"
    # Use explicit path join for clarity
    download_path_dir = os.path.join(TMP_DOWNLOAD_DIR, str(lat_group))
    download_path = os.path.join(download_path_dir, f"{lon_group}.tar.gz")

    os.makedirs(download_path_dir, exist_ok=True)
    print(f"Downloading: {url} to {download_path}")

    try:
        print(f"--> Attempting requests.get for {url}") # DEBUG
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Remove verify=False from the request
        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT, headers=headers) as r:
            print(f"--> requests.get successful, status code: {r.status_code}") # DEBUG
            r.raise_for_status() # Check for HTTP errors

            print(f"--> Opening {download_path} for writing.") # DEBUG
            with open(download_path, 'wb') as f:
                print(f"--> Opened {download_path}, iterating content...") # DEBUG
                chunk_count = 0
                for chunk in r.iter_content(chunk_size=8192):
                    # print(f"--> Writing chunk {chunk_count}") # Optional: very verbose
                    f.write(chunk)
                    chunk_count += 1
                print(f"--> Finished iterating content ({chunk_count} chunks).") # DEBUG
            print(f"--> Closed {download_path}.") # DEBUG

        print(f"Downloaded: {filename}")

        # Extract
        print(f"Extracting: {download_path} to {TARGET_EXTRACT_DIR}")
        with gzip.open(download_path, 'rb') as gz_file:
            with tarfile.open(fileobj=gz_file, mode='r') as tar:
                 # Need to be careful about extraction paths (TarSlip vulnerability)
                 # We trust the source here, but good practice would be to check members
                 def is_within_directory(directory, target):
                     abs_directory = os.path.abspath(directory)
                     abs_target = os.path.abspath(target)
                     prefix = os.path.commonprefix([abs_directory, abs_target])
                     return prefix == abs_directory

                 for member in tar.getmembers():
                     member_path = os.path.join(TARGET_EXTRACT_DIR, member.name)
                     if not is_within_directory(TARGET_EXTRACT_DIR, member_path):
                         raise Exception(f"Attempted Path Traversal in Tar File: {member.name}")
                 # If checks pass, extract all
                 tar.extractall(path=TARGET_EXTRACT_DIR)
        print(f"Extracted: {filename}")
        _increment_progress(location_name)
        return True

    except requests.exceptions.RequestException as e:
        print(f"--> requests.get FAILED for {url}: {e}") # DEBUG
        print(f"Error downloading {url}: {e}") # Original print
        _set_error_progress(f"Download failed: {url} ({e})")
        return False
    except (tarfile.TarError, gzip.BadGzipFile, EOFError) as e:
        print(f"Error extracting {download_path}: {e}")
        _set_error_progress(f"Extraction failed: {filename} ({e})")
        return False
    except Exception as e:
        print(f"Unexpected error processing {filename}: {e}")
        _set_error_progress(f"Unexpected error: {filename} ({e})")
        return False
    finally:
        # Clean up downloaded file regardless of success
        if os.path.exists(download_path):
            try:
                os.remove(download_path)
            except OSError as e:
                 print(f"Warning: Could not remove temp file {download_path}: {e}")


def download_bounds(bounds, location_name="CUSTOM"):
    """Downloads all map files within the specified bounding box."""
    if not bounds:
        print("Error: Invalid bounds provided.")
        _set_error_progress("Invalid download bounds.")
        return False

    print(f"Downloading Bounds for {location_name}: {bounds}")
    min_lat, min_lon, max_lat, max_lon = _calculate_adjusted_bounds(bounds)
    print(f"Adjusted Grid: Lat ({min_lat} to {max_lat}), Lon ({min_lon} to {max_lon})")

    total_success = True
    for i in range(min_lat, max_lat, GROUP_AREA_BOX_DEGREES):
        for j in range(min_lon, max_lon, GROUP_AREA_BOX_DEGREES):
             # --- Cancellation Check --- Start (Inside inner loop)
            if _check_cancel_requested():
                print("Cancellation requested, stopping download bounds.")
                _set_error_progress("Download cancelled by user.")
                return False # Indicate failure due to cancellation
            # --- Cancellation Check --- End

            if not _download_and_extract_file(i, j, location_name):
                total_success = False
                # Check if failure was due to cancellation
                if _check_cancel_requested():
                    return False # Propagate cancellation failure immediately
                # Decide whether to continue or stop on other errors
                # Current logic continues but reports first error.

    print(f"Finished downloading for {location_name}")
    return total_success

def run_downloader():
    """Main function to check params and trigger downloads."""
    # --- Ensure Cancel Param is Clear at Start --- Start
    remove_param(OSM_CANCEL_DOWNLOAD, persistent=False)
    # --- Ensure Cancel Param is Clear at Start --- End

    print("Map Downloader Started")
    load_locations() # Ensure locations are loaded

    locations_data = get_param_json(DOWNLOAD_LOCATIONS, persistent=False, default=None)
    bounds_data = get_param_json(DOWNLOAD_BOUNDS, persistent=False, default=None)

    locations_to_process = []
    bounds_to_process = []
    all_location_names = []
    total_files_to_download = 0
    location_details = {} # Recalculate based on current request

    if locations_data and isinstance(locations_data, dict):
        nations = locations_data.get("nations", [])
        states = locations_data.get("states", [])
        locations_to_process.extend([("nation", n) for n in nations])
        locations_to_process.extend([("state", s) for s in states])
        all_location_names = nations + states

        for loc_type, loc_name in locations_to_process:
            boxes = NATION_BOXES if loc_type == "nation" else STATE_BOXES
            loc_data = boxes.get(loc_name)
            if loc_data and isinstance(loc_data, dict):
                 bounds = loc_data.get("bounding_box")
                 if bounds:
                     count = _count_files_for_bounds(bounds)
                     total_files_to_download += count
                     location_details[loc_name] = {
                         "location_total_files": count,
                         "location_downloaded_files": 0
                     }
                 else:
                      print(f"Warning: No bounding_box found for {loc_type} '{loc_name}'")
            else:
                 print(f"Warning: Could not find data for {loc_type} '{loc_name}'")

    if bounds_data and isinstance(bounds_data, dict):
        # Expecting bounds_data to be a single bounds dict like {"min_lat": ..., ...}
        bounds_to_process.append(bounds_data)
        all_location_names.append("CUSTOM")
        count = _count_files_for_bounds(bounds_data)
        total_files_to_download += count
        location_details["CUSTOM"] = {
             "location_total_files": count,
             "location_downloaded_files": 0
        }


    if not locations_to_process and not bounds_to_process:
        print("No download locations or bounds specified.")
        _reset_progress([], 0, {}) # Reset progress to idle/empty state
        return

    # --- Check for Cancellation Before Starting Actual Downloads --- Start
    if _check_cancel_requested():
        print("Cancellation requested before downloads started.")
        _reset_progress([], 0, {}) # Reset to idle
        # Clean up the cancel flag since we are exiting
        remove_param(OSM_CANCEL_DOWNLOAD, persistent=False)
        return
    # --- Check for Cancellation Before Starting Actual Downloads --- End

    _reset_progress(all_location_names, total_files_to_download, location_details)
    print(f"Starting download. Total files: {total_files_to_download}")

    download_successful = True
    explicit_cancel = False # Flag to track if we stopped due to cancellation

    # Process named locations
    for loc_type, loc_name in locations_to_process:
        # --- Cancellation Check --- Start (Outer loop)
        if _check_cancel_requested():
            print("Cancellation requested during location processing.")
            explicit_cancel = True
            download_successful = False
            break # Exit outer loop
        # --- Cancellation Check --- End
        print(f"Processing {loc_type}: {loc_name}")
        boxes = NATION_BOXES if loc_type == "nation" else STATE_BOXES
        loc_data = boxes.get(loc_name)
        if loc_data and isinstance(loc_data, dict):
            bounds = loc_data.get("bounding_box")
            full_name = loc_data.get("full_name", loc_name)
            if bounds:
                if not download_bounds(bounds, loc_name):
                    download_successful = False
                    # Check if download_bounds returned false due to cancellation
                    if _check_cancel_requested():
                        explicit_cancel = True
                        break # Exit outer loop if cancelled within download_bounds
                    print(f"Download failed for {full_name}")
                    # Continue with others unless cancelled
            else:
                 print(f"Warning: No bounding box for {full_name}")
                 _set_error_progress(f"Missing bounds for {loc_name}")
                 download_successful = False # Mark as failure if data is missing
        else:
            print(f"Warning: Could not find data for {loc_type} '{loc_name}'")
            _set_error_progress(f"Missing location data for {loc_name}")
            download_successful = False # Mark as failure if data is missing


    # Process custom bounds only if not cancelled
    if not explicit_cancel:
        for bounds in bounds_to_process:
             # --- Cancellation Check --- Start (Bounds loop)
            if _check_cancel_requested():
                print("Cancellation requested during custom bounds processing.")
                explicit_cancel = True
                download_successful = False
                break # Exit bounds loop
            # --- Cancellation Check --- End
            print("Processing custom bounds")
            if not download_bounds(bounds, "CUSTOM"):
                 download_successful = False
                 # Check if download_bounds returned false due to cancellation
                 if _check_cancel_requested():
                    explicit_cancel = True
                    break # Exit bounds loop if cancelled within download_bounds
                 print("Download failed for custom bounds")
                 # Continue unless cancelled

    # Cleanup
    print("Cleaning up temporary download directory...")
    try:
        tmp_base_dir = os.path.join(get_base_path(), "tmp")
        if os.path.exists(tmp_base_dir):
            shutil.rmtree(tmp_base_dir)
        print("Cleanup complete.")
    except OSError as e:
        print(f"Error removing temporary directory {tmp_base_dir}: {e}")
        _set_error_progress(f"Cleanup failed: {e}")
        download_successful = False

    # Determine final state based on success and cancellation
    final_action = "Complete"
    if explicit_cancel:
        final_action = "Cancelled"
        # Ensure error message reflects cancellation if not already set
        with progress_lock:
             if not current_progress["error_message"]:
                 current_progress["error_message"] = "Download cancelled by user."
             current_progress["current_action"] = "Error" # Treat cancel as an error state for UI
        _update_progress_param()
        download_successful = False # Ensure it's marked as unsuccessful overall
    elif not download_successful:
        # An error occurred that wasn't cancellation
        # _set_error_progress should have been called already
        final_action = "Error"

    # Clear trigger params only on success or explicit cancel (error state handled)
    # Don't clear triggers if an unexpected error occurred without cancel
    if download_successful or explicit_cancel:
        print("Clearing download trigger parameters.")
        remove_param(DOWNLOAD_LOCATIONS, persistent=True) # Read from persistent, clear persistent
        remove_param(DOWNLOAD_BOUNDS, persistent=False) # Read from non-persistent, clear non-persistent
        # Clear cancel flag on exit
        remove_param(OSM_CANCEL_DOWNLOAD, persistent=False)

        if download_successful and not explicit_cancel:
             with progress_lock:
                 current_progress["current_action"] = "Complete"
             _update_progress_param()
    else:
         print("Download trigger parameters NOT cleared due to incomplete status without explicit cancel/error.")
         # Consider clearing cancel flag even on failure if not explicit cancel?
         remove_param(OSM_CANCEL_DOWNLOAD, persistent=False)


    print(f"Map Downloader Finished - State: {final_action}")


if __name__ == "__main__":
    # This allows running the script directly for testing
    # Example: Set params manually and run this script
    # Example Test Setup:
    # 1. Manually create /dev/shm/params/d/OSMDownloadLocations
    #    echo '{"nations": ["us"], "states": ["us-ca"]}' > /dev/shm/params/d/OSMDownloadLocations
    # 2. Run: python -m selfdrive.frogpilot.navigation.mapd_py.downloader.downloader

    # Or for bounds:
    # 1. echo '{"min_lat": 34.0, "min_lon": -118.0, "max_lat": 35.0, "max_lon": -117.0}' > /dev/shm/params/d/OSMDownloadBounds
    # 2. Run script.
    run_downloader()