#!/usr/bin/env python3
from __future__ import annotations

import base64
import bz2
import hashlib
import io
import json
import os
import queue
import random
import select
import socket
import stat # <-- Import stat for ctime
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from functools import partial
from queue import Queue
from typing import cast

# OpenPilot / system imports
import cereal.messaging as messaging
from cereal import log
# from openpilot.common.file_helpers import CallbackReader # Removed as not used directly here
from openpilot.common.params import Params
from openpilot.common.realtime import set_core_affinity
# from openpilot.system.hardware import HARDWARE, PC # Removed as not used directly here
# from openpilot.system.loggerd.xattr_cache import getxattr, setxattr # Removed as not used directly here
from openpilot.common.swaglog import cloudlog
# from openpilot.system.version import get_build_metadata # Removed as not used directly here
# from openpilot.system.hardware.hw import Paths # Removed as not used directly here

# ---- Azure imports ----
try:
  from azure.storage.fileshare import ShareFileClient, ShareDirectoryClient
  from azure.core.exceptions import ServiceResponseError, ResourceNotFoundError, ResourceExistsError
except ImportError:
  cloudlog.exception("Azure storage fileshare SDK not installed! Please `pip install azure-storage-file-share`.")
  ShareFileClient = None
  ShareDirectoryClient = None
  ServiceResponseError = None
  ResourceNotFoundError = None
  ResourceExistsError = None

# Constants
HANDLER_THREADS = 1 # Increased threads might speed up uploads if network isn't the bottleneck
MAX_RETRY_COUNT = 5 # Reduced retries to avoid getting stuck on persistent errors
RETRY_DELAY = 30    # Increased delay between retries
# MAX_AGE = 31 * 24 * 3600 # Removed MAX_AGE check in handler, handled by realdata_handler filter

# Azure File Share config
AZURE_SHARE_NAME = "chauffeurlogs"
AZURE_BASE_DIR   = "rlogs" # Base directory within the Azure share

# Source Data Directory
SOURCE_DATA_DIR = "/data/media/0/realdata" # Base directory to scan on the device

# Age limit for directories to consider for upload
DIRECTORY_AGE_LIMIT = timedelta(hours=24)

# Files within each directory to upload
TARGET_FILES = ['rlog', 'qlog', 'qcamera.ts']

# Debug flag - only True when running directly
DEBUG = __name__ == "__main__"

def debug_print(*args, **kwargs):
  if DEBUG:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG]", *args, **kwargs)

def debug_queue_status():
  """Print current status of upload queue and active uploads"""
  if not DEBUG:
    return
  active_uploads = [item for item in cur_upload_items.values() if item is not None]
  queued_items = list(upload_queue.queue)

  print("\n[DEBUG] === Queue Status ===")
  print(f"Active uploads: {len(active_uploads)}")
  print(f"Queue size: {len(queued_items)}")
  if active_uploads:
    print("Active upload items:")
    for tid, item in cur_upload_items.items():
      if item is not None:
        print(f"  Thread {tid}: {item.path} -> {item.azure_subdir} (progress: {item.progress:.1f}, retries: {item.retry_count})")
  if queued_items:
    print("Next 5 queued items:")
    for item in queued_items[:5]:
      print(f"  {item.path} -> {item.azure_subdir} (retries: {item.retry_count})")
  print("========================\n")

# -------------------------------------------------------------------------------
# Azure Connection / Helpers
# -------------------------------------------------------------------------------

_AZURE_CONN_STR = None
_AZURE_CONN_STR_LOCK = threading.Lock()

def get_azure_connection_string() -> str | None:
  """
  Reads the Azure connection string from /persist/azure_conn_string, caches it.
  """
  global _AZURE_CONN_STR
  if _AZURE_CONN_STR is None:
      with _AZURE_CONN_STR_LOCK:
          if _AZURE_CONN_STR is None: # Double check after acquiring lock
              try:
                  with open("/persist/azure_conn_string", "r") as f:
                      conn_str = f.read().strip()
                      if conn_str:
                         _AZURE_CONN_STR = conn_str
                         debug_print(f"Successfully read and cached Azure connection string (length: {len(conn_str)})")
                      else:
                         debug_print("Azure connection string file is empty.")
                         cloudlog.warning("azure.get_azure_connection_string.empty_file")
              except FileNotFoundError:
                  debug_print("Azure connection string file not found: /persist/azure_conn_string")
                  cloudlog.error("azure.get_azure_connection_string.not_found")
              except Exception as e:
                  debug_print(f"Failed to read Azure connection string: {str(e)}")
                  cloudlog.exception("azure.get_azure_connection_string.exception")
  return _AZURE_CONN_STR

def check_azure_file_exists(conn_str: str, share_name: str, directory_path: str, filename: str) -> bool:
    """Checks if a specific file exists in an Azure File Share directory."""
    if ShareDirectoryClient is None or ResourceNotFoundError is None:
        return False # SDK not available
    try:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, directory_path)
        file_client = dir_client.get_file_client(filename)
        file_client.get_file_properties()
        debug_print(f"Azure file exists: {share_name}/{directory_path}/{filename}")
        return True
    except ResourceNotFoundError:
        debug_print(f"Azure file NOT found: {share_name}/{directory_path}/{filename}")
        return False
    except Exception as e:
        debug_print(f"Error checking Azure file existence for {filename} in {directory_path}: {e}")
        cloudlog.warning("azure.check_azure_file_exists.error", directory=directory_path, file=filename, error=str(e))
        # Decide: Assume it doesn't exist on error to allow upload attempt? Or assume it does to prevent retries?
        # Let's assume it doesn't exist to potentially fix incomplete uploads.
        return False

def ensure_azure_directory_exists(conn_str: str, share_name: str, azure_full_dir_path: str) -> bool:
    """Ensures the Azure directory exists. Returns True if successful or already exists, False otherwise."""
    if ShareDirectoryClient is None or ResourceExistsError is None:
        return False # SDK not available
    try:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, azure_full_dir_path)
        dir_client.create_directory()
        debug_print(f"Azure directory created or already exists: {share_name}/{azure_full_dir_path}")
        return True
    except ResourceExistsError:
        debug_print(f"Azure directory already exists: {share_name}/{azure_full_dir_path}")
        return True # Already exists is considered success
    except Exception as e:
        debug_print(f"Error creating/checking Azure directory {azure_full_dir_path}: {e}")
        cloudlog.exception("azure.ensure_azure_directory_exists.error", directory=azure_full_dir_path, error=str(e))
        return False

# -------------------------------------------------------------------------------
# Upload Item DataClass
# -------------------------------------------------------------------------------
@dataclass
class UploadItem:
  path: str                # Full local path to the file
  azure_subdir: str        # Formatted target subdirectory name in Azure (e.g., "040325--...")
  id: str                  # Unique identifier (e.g., "azure|040325--...|rlog")
  created_at: int          # Timestamp when the item was queued (ms)
  retry_count: int = 0
  current: bool = False    # Is it currently being processed by a handler thread?
  progress: float = 0.0    # Progress (0.0 to 1.0)
  allow_cellular: bool = False # Currently unused, default False

  # --- Fields not strictly needed for Azure file share but kept for compatibility ---
  url: str = ""
  headers: dict[str, str] = field(default_factory=dict)
  # ---

  @classmethod
  def from_dict(cls, d: dict) -> UploadItem | None:
    # Provide default values for potentially missing keys if restoring from older cache format
    required_keys = {"path", "azure_subdir", "id", "created_at"}
    if not required_keys.issubset(d.keys()):
        cloudlog.warning("UploadItem.from_dict missing required keys, skipping.", data=d)
        return None

    return cls(
      path=d["path"],
      azure_subdir=d["azure_subdir"],
      id=d["id"],
      created_at=d["created_at"],
      retry_count=d.get("retry_count", 0),
      current=d.get("current", False), # Should always be false when loading from cache
      progress=d.get("progress", 0.0),
      allow_cellular=d.get("allow_cellular", False),
      url=d.get("url", ""),
      headers=d.get("headers", {}),
    )

# -------------------------------------------------------------------------------
# Upload Queue and Cache
# -------------------------------------------------------------------------------
class AbortTransferException(Exception):
  pass

cur_upload_items: dict[int, UploadItem | None] = {} # Holds item currently processed by each thread_id
cancelled_uploads: set[str] = set() # Set of upload IDs that were cancelled
upload_queue: Queue[UploadItem] = queue.Queue()

class UploadQueueCache:
  PARAM_NAME = "AzureUploadQueueV2" # Changed name to avoid conflicts with old format

  @staticmethod
  def initialize(upload_queue_instance: Queue[UploadItem]) -> None:
    """Load previously queued items from the param store."""
    params = Params()
    upload_queue_json = params.get(UploadQueueCache.PARAM_NAME)
    if upload_queue_json is not None:
      try:
        items_list = json.loads(upload_queue_json)
        count = 0
        for item_dict in items_list:
            item = UploadItem.from_dict(item_dict)
            if item:
                # Reset transient state
                item.current = False
                item.progress = 0.0 # Assume restart means progress reset
                upload_queue_instance.put_nowait(item)
                count += 1
        debug_print(f"Initialized queue with {count} items from param '{UploadQueueCache.PARAM_NAME}'")
      except json.JSONDecodeError:
        cloudlog.exception(f"azure.UploadQueueCache.initialize: Invalid JSON in param '{UploadQueueCache.PARAM_NAME}'")
        params.remove(UploadQueueCache.PARAM_NAME)
      except Exception:
        cloudlog.exception("azure.UploadQueueCache.initialize.exception")
        params.remove(UploadQueueCache.PARAM_NAME) # Clear potentially corrupt data
    else:
        debug_print(f"No existing queue found in param '{UploadQueueCache.PARAM_NAME}'")


  @staticmethod
  def cache(upload_queue_instance: Queue[UploadItem]) -> None:
    """Save items back to the param store."""
    try:
      # Combine items currently in queue and items being processed (that might need retry)
      items_to_cache = list(upload_queue_instance.queue)
      for item in cur_upload_items.values():
          if item is not None and item.id not in cancelled_uploads and item.progress < 1.0:
              # Only cache items being processed if they aren't finished or cancelled
              # Reset 'current' flag as it's transient state for the running process
              items_to_cache.append(replace(item, current=False))

      # Filter out any cancelled items explicitly
      items_data = [asdict(i) for i in items_to_cache if i and i.id not in cancelled_uploads]

      if items_data:
        Params().put(UploadQueueCache.PARAM_NAME, json.dumps(items_data))
        # debug_print(f"Cached {len(items_data)} items to param '{UploadQueueCache.PARAM_NAME}'")
      else:
        Params().remove(UploadQueueCache.PARAM_NAME)
        # debug_print(f"Queue empty, removed param '{UploadQueueCache.PARAM_NAME}'")

    except Exception:
      cloudlog.exception("azure.UploadQueueCache.cache.exception")

# -------------------------------------------------------------------------------
# Upload Handler Thread Logic
# -------------------------------------------------------------------------------
def _do_upload_azure(upload_item: UploadItem):
  """
  Performs the actual file upload to Azure File Share.
  Assumes the connection string is valid and SDK is installed.
  Handles directory creation implicitly via ShareDirectoryClient.
  """
  conn_str = get_azure_connection_string()
  if not conn_str or ShareFileClient is None or ShareDirectoryClient is None:
    raise Exception("Azure upload prerequisites not met (conn_str/SDK).")

  local_path = upload_item.path
  filename = os.path.basename(local_path)
  # Construct the full path within the share: AZURE_BASE_DIR / azure_subdir
  azure_full_dir_path = f"{AZURE_BASE_DIR}/{upload_item.azure_subdir}"

  debug_print(f"Attempting upload: {local_path} -> {AZURE_SHARE_NAME}/{azure_full_dir_path}/{filename}")

  if not os.path.isfile(local_path):
    debug_print(f"Local file not found: {local_path}")
    raise FileNotFoundError(f"Local file not found: {local_path}")

  file_size = os.path.getsize(local_path)
  debug_print(f"Local file size: {file_size} bytes")

  # 1. Ensure directory exists (SDK handles 'already exists' gracefully)
  if not ensure_azure_directory_exists(conn_str, AZURE_SHARE_NAME, azure_full_dir_path):
       raise Exception(f"Failed to ensure Azure directory exists: {azure_full_dir_path}")

  # 2. Check if file already exists on Azure (redundant check, realdata_handler should prevent this, but good safety measure)
  if check_azure_file_exists(conn_str, AZURE_SHARE_NAME, azure_full_dir_path, filename):
      debug_print(f"File already exists on Azure, skipping upload: {filename}")
      # If we reach here, it means realdata_handler might have added it erroneously,
      # or it was uploaded by another process between queuing and now. Mark as success.
      return # Treat as success

  # 3. Get file client and upload
  try:
    dir_client = ShareDirectoryClient.from_connection_string(conn_str, AZURE_SHARE_NAME, azure_full_dir_path)
    file_client = dir_client.get_file_client(filename)

    debug_print(f"Starting upload of {filename} to {azure_full_dir_path}...")
    with open(local_path, "rb") as f:
      # Consider using `overwrite=True` if you want to force overwrite, but based on checks, it shouldn't be needed.
      # Added timeout for the whole upload operation. Chunk timeouts are handled internally by SDK default.
      file_client.upload_file(f, timeout=600) # 10 minute overall timeout

    debug_print(f"Successfully uploaded {filename} ({file_size} bytes)")
    cloudlog.event("azure._do_upload_azure.success", subdir=upload_item.azure_subdir, filename=filename, size=file_size)

  except ServiceResponseError as e:
      debug_print(f"Azure Service Error during upload of {filename}: {e}")
      cloudlog.exception("azure._do_upload_azure.service_error", subdir=upload_item.azure_subdir, filename=filename, error=str(e))
      raise # Re-raise to trigger retry logic
  except TimeoutError as e:
      debug_print(f"Timeout during upload of {filename}: {e}")
      cloudlog.exception("azure._do_upload_azure.timeout", subdir=upload_item.azure_subdir, filename=filename, error=str(e))
      raise # Re-raise to trigger retry logic
  except Exception as e:
    debug_print(f"Unexpected error during upload of {filename}: {e}")
    cloudlog.exception("azure._do_upload_azure.exception", subdir=upload_item.azure_subdir, filename=filename, error=str(e))
    raise # Re-raise to trigger retry logic

def retry_upload(tid: int, end_event: threading.Event, increase_count: bool = True) -> None:
  """Re-queues the item associated with thread `tid` for another attempt."""
  item = cur_upload_items.get(tid) # Use get for safety
  if item is None:
      debug_print(f"[Thread {tid}] No item found to retry.")
      return

  if item.id in cancelled_uploads:
      debug_print(f"[Thread {tid}] Item {item.id} was cancelled, not retrying.")
      cur_upload_items[tid] = None
      UploadQueueCache.cache(upload_queue) # Update cache since item is removed
      return

  new_retry_count = item.retry_count + 1 if increase_count else item.retry_count

  if new_retry_count > MAX_RETRY_COUNT:
      debug_print(f"[Thread {tid}] Max retries ({MAX_RETRY_COUNT}) exceeded for {item.path}. Giving up.")
      cloudlog.error("azure.retry_upload.max_retries", item_id=item.id, path=item.path, retries=item.retry_count)
      # Mark as failed/done so it's removed from queue cache
      cur_upload_items[tid] = replace(item, progress=1.0, current=False) # Treat max retries as 'done' for queue management
      upload_queue.task_done() # Signal task completion even on failure
      UploadQueueCache.cache(upload_queue)
      cur_upload_items[tid] = None # Clear current item for the thread
      return

  debug_print(f"[Thread {tid}] Retrying upload for {item.path} (Attempt {new_retry_count}/{MAX_RETRY_COUNT})")
  # Reset progress and current status for re-queuing
  requeued_item = replace(item, retry_count=new_retry_count, progress=0.0, current=False)
  upload_queue.put(requeued_item) # Use put instead of put_nowait to handle full queue if needed
  cur_upload_items[tid] = None # Clear current item for the thread before cache/sleep
  UploadQueueCache.cache(upload_queue) # Cache the updated queue with the re-added item

  # Wait before the thread picks up a new item
  debug_print(f"[Thread {tid}] Waiting {RETRY_DELAY}s before next attempt...")
  end_event.wait(RETRY_DELAY) # Wait for the delay or until shutdown is requested
  debug_print(f"[Thread {tid}] Finished retry delay.")


def upload_handler(end_event: threading.Event) -> None:
  """Thread worker function to process items from the upload queue."""
  sm = messaging.SubMaster(['deviceState'])
  tid = threading.get_ident()
  debug_print(f"[Thread {tid}] Upload handler started.")

  while not end_event.is_set():
    item = None # Ensure item is reset each loop
    try:
      item = upload_queue.get(timeout=1)
      cur_upload_items[tid] = replace(item, current=True) # Mark as currently processing
      debug_print(f"[Thread {tid}] Processing item: {item.id} ({item.path})")
      # debug_queue_status() # Optional: Can be noisy

      if item.id in cancelled_uploads:
        debug_print(f"[Thread {tid}] Item {item.id} was cancelled, removing.")
        cancelled_uploads.remove(item.id)
        upload_queue.task_done()
        cur_upload_items[tid] = None
        UploadQueueCache.cache(upload_queue)
        continue

      # --- Network Metered Check ---
      # Allow cellular check removed as per original script structure, assume wifi only unless specified
      # sm.update(0)
      # is_metered = sm['deviceState'].networkMetered
      # network_type = sm['deviceState'].networkType.raw
      # if is_metered and not item.allow_cellular:
      #   debug_print(f"[Thread {tid}] Metered network ({network_type}) and cellular not allowed, deferring {item.id}")
      #   cloudlog.info("azure.upload_handler.defer_metered", item_id=item.id, network=str(network_type))
      #   retry_upload(tid, end_event, increase_count=False) # Requeue without increasing retry count
      #   continue # Skip to next queue item check

      # --- Perform Upload ---
      try:
        _do_upload_azure(item)
        # Mark as success
        debug_print(f"[Thread {tid}] Successfully processed item: {item.id}")
        cur_upload_items[tid] = replace(item, progress=1.0, current=False)
        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue) # Update cache after success
        cur_upload_items[tid] = None # Clear current item

      # --- Handle Specific Upload Errors ---
      except FileNotFoundError:
        debug_print(f"[Thread {tid}] File not found for item {item.id}: {item.path}. Removing from queue.")
        cloudlog.warning("azure.upload_handler.file_not_found", item_id=item.id, path=item.path)
        cur_upload_items[tid] = replace(item, progress=1.0, current=False) # Mark done
        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)
        cur_upload_items[tid] = None

      except (ConnectionError, TimeoutError, ServiceResponseError) as e:
        debug_print(f"[Thread {tid}] Network/Service error for item {item.id}: {type(e).__name__}. Retrying.")
        cloudlog.warning("azure.upload_handler.network_error", item_id=item.id, error=str(e), type=type(e).__name__)
        retry_upload(tid, end_event, increase_count=True) # Retry with increased count

      except AbortTransferException: # Should not happen with current setup, but keep for structure
        debug_print(f"[Thread {tid}] Transfer aborted for item {item.id}. Re-queuing.")
        cloudlog.warning("azure.upload_handler.abort", item_id=item.id)
        retry_upload(tid, end_event, increase_count=False) # Requeue without increasing count

      except Exception as e:
        # Catch-all for unexpected errors during _do_upload_azure or other logic
        debug_print(f"[Thread {tid}] Unexpected error processing item {item.id}: {e}. Retrying.")
        cloudlog.exception("azure.upload_handler.unexpected_error", item_id=item.id)
        retry_upload(tid, end_event, increase_count=True) # Retry with increased count

    except queue.Empty:
      # Queue is empty, just loop again
      cur_upload_items[tid] = None # Ensure state is clear if queue was empty
      pass
    except Exception as e:
      # Error getting from queue or other unexpected handler loop error
      debug_print(f"[Thread {tid}] CRITICAL ERROR in upload handler loop: {e}")
      cloudlog.exception("azure.upload_handler.critical_loop_error")
      cur_upload_items[tid] = None # Clear current item state
      time.sleep(5) # Avoid fast spinning on critical errors

  debug_print(f"[Thread {tid}] Upload handler stopped.")


# -------------------------------------------------------------------------------
# Directory Scanner (realdata_handler)
# -------------------------------------------------------------------------------
def realdata_handler(end_event: threading.Event) -> None:
  """
  Scans SOURCE_DATA_DIR for subdirectories created within DIRECTORY_AGE_LIMIT.
  For qualifying directories, queues uploads for TARGET_FILES if they exist locally
  and do not already exist on Azure.
  """
  debug_print("Realdata handler started.")
  conn_str = None # Initialize connection string

  while not end_event.is_set():
    scan_start_time = time.monotonic()
    added_count = 0
    skipped_exist_count = 0
    skipped_old_count = 0
    skipped_queued_count = 0
    error_count = 0

    # --- Ensure Azure Connection ---
    if conn_str is None:
        conn_str = get_azure_connection_string()
        if not conn_str:
            debug_print("Realdata handler: Azure connection string not available. Sleeping for 60s.")
            cloudlog.warning("azure.realdata_handler.no_conn_str")
            end_event.wait(60)
            continue # Retry getting connection string in the next iteration

    if ShareDirectoryClient is None or ShareFileClient is None:
        debug_print("Realdata handler: Azure SDK not available. Sleeping for 60s.")
        cloudlog.error("azure.realdata_handler.sdk_missing")
        end_event.wait(60)
        continue

    # --- Scan Local Directories ---
    try:
      now = datetime.now()
      queued_items_ids = {qi.id for qi in list(upload_queue.queue) + list(cur_upload_items.values()) if qi is not None}
      debug_print(f"Scanning {SOURCE_DATA_DIR} for directories created within {DIRECTORY_AGE_LIMIT}...")
      debug_print(f"Currently {len(queued_items_ids)} items in queue/active.")

      # Check if base directory exists
      if not os.path.isdir(SOURCE_DATA_DIR):
          debug_print(f"Source directory {SOURCE_DATA_DIR} not found. Sleeping.")
          cloudlog.error("azure.realdata_handler.source_dir_missing", dir=SOURCE_DATA_DIR)
          end_event.wait(300) # Wait 5 minutes before checking again
          continue

      for subdir_name in os.listdir(SOURCE_DATA_DIR):
        if end_event.is_set(): break # Exit loop early if shutdown requested

        source_subdir_path = os.path.join(SOURCE_DATA_DIR, subdir_name)
        try:
          if not os.path.isdir(source_subdir_path):
            continue

          # 1. Get Creation Time (using ctime)
          stat_result = os.stat(source_subdir_path)
          # On Unix, ctime is often the metadata change time, but it's typically the
          # closest timestamp to the actual creation time available via standard os.stat.
          # It's better than mtime for "new directory" detection.
          creation_timestamp = stat_result.st_ctime
          creation_dt = datetime.fromtimestamp(creation_timestamp)

          # 2. Check Age
          if (now - creation_dt) > DIRECTORY_AGE_LIMIT:
            # debug_print(f"Skipping {subdir_name}: too old (created {creation_dt})")
            skipped_old_count += 1
            continue

          # 3. Format Azure Directory Name
          azure_subdir_prefix = creation_dt.strftime("%m%d%y--")
          azure_subdir_formatted = f"{azure_subdir_prefix}{subdir_name}"
          azure_full_dir_path = f"{AZURE_BASE_DIR}/{azure_subdir_formatted}" # Path relative to share root

          # debug_print(f"Checking recent directory: {subdir_name} (created {creation_dt}), Target Azure Dir: {azure_subdir_formatted}")

          # 4. Check Local Files and Queue if Needed
          for filename in TARGET_FILES:
            if end_event.is_set(): break # Exit inner loop early

            local_file_path = os.path.join(source_subdir_path, filename)
            upload_id = f"azure|{azure_subdir_formatted}|{filename}" # Unique ID

            # Check if already queued or being processed
            if upload_id in queued_items_ids:
                # debug_print(f"Skipping {filename} for {azure_subdir_formatted}: Already in queue/active.")
                skipped_queued_count += 1
                continue

            if os.path.isfile(local_file_path):
              # File exists locally, now check Azure
              if check_azure_file_exists(conn_str, AZURE_SHARE_NAME, azure_full_dir_path, filename):
                # debug_print(f"Skipping {filename} for {azure_subdir_formatted}: Already exists on Azure.")
                skipped_exist_count += 1
                continue
              else:
                # File exists locally, not queued, and not found on Azure -> Queue it!
                debug_print(f"Queueing upload for {local_file_path} -> {azure_full_dir_path}/{filename}")
                item = UploadItem(
                  path=local_file_path,
                  azure_subdir=azure_subdir_formatted,
                  id=upload_id,
                  created_at=int(time.time() * 1000), # Time it was queued
                  # allow_cellular=False # Default
                )
                upload_queue.put_nowait(item)
                queued_items_ids.add(upload_id) # Add to set to prevent queuing duplicates in same scan cycle
                added_count += 1
                # No need to cache queue here, cache happens in handler or periodically

            # else: File doesn't exist locally, do nothing.

        except FileNotFoundError:
            debug_print(f"Directory {source_subdir_path} likely removed during scan.")
            cloudlog.warning("azure.realdata_handler.subdir_disappeared", path=source_subdir_path)
            error_count += 1
            continue # Skip to next directory
        except Exception as e:
            debug_print(f"Error processing directory {source_subdir_path}: {e}")
            cloudlog.exception("azure.realdata_handler.subdir_error", path=source_subdir_path)
            error_count += 1
            continue # Skip to next directory

      # Cache the queue state after a full scan cycle
      UploadQueueCache.cache(upload_queue)
      scan_duration = time.monotonic() - scan_start_time
      debug_print(f"Scan finished in {scan_duration:.2f}s. Added: {added_count}, Skipped (Old/Queued/Exists): {skipped_old_count}/{skipped_queued_count}/{skipped_exist_count}, Errors: {error_count}")
      debug_queue_status()

    except OSError as e:
        debug_print(f"OS Error during scan of {SOURCE_DATA_DIR}: {e}")
        cloudlog.exception("azure.realdata_handler.os_error", dir=SOURCE_DATA_DIR)
        error_count += 1
    except Exception as e:
      # Catch errors related to listdir or other unexpected issues in the main loop
      debug_print(f"CRITICAL ERROR in realdata handler loop: {e}")
      cloudlog.exception("azure.realdata_handler.critical_loop_error")
      error_count += 1

    # Wait before next scan cycle
    wait_time = 300 # 5 minutes
    # debug_print(f"Realdata handler sleeping for {wait_time} seconds...")
    end_event.wait(wait_time)

  debug_print("Realdata handler stopped.")

# -------------------------------------------------------------------------------
# Main Entry Point
# -------------------------------------------------------------------------------
def main():
  """
  Initializes and runs the Azure upload service.
  """
  cloudlog.info("Starting Azure upload service")
  debug_print("Starting Azure upload service...") # Also print for local debug

  # --- Set Core Affinity ---
  try:
    # Restrict to fewer cores potentially, depending on device resources
    cores = [0, 1] if not PC else [0, 1, 2, 3]
    set_core_affinity(cores)
    debug_print(f"Set core affinity to: {cores}")
  except Exception:
    cloudlog.exception("failed to set core affinity")
    debug_print("Failed to set core affinity")


  # --- Initialize Queue from Cache ---
  UploadQueueCache.initialize(upload_queue)
  debug_print(f"Initial queue size: {upload_queue.qsize()}")
  debug_queue_status()

  end_event = threading.Event()
  threads = []

  # --- Start Upload Handlers ---
  for i in range(HANDLER_THREADS):
      t = threading.Thread(target=upload_handler, args=(end_event,), name=f'upload_handler_{i}')
      t.start()
      threads.append(t)
      cur_upload_items[t.ident] = None # Initialize state for this thread ID
  debug_print(f"Started {HANDLER_THREADS} upload handler thread(s)")


  # --- Start Directory Scanner ---
  realdata_thread = threading.Thread(target=realdata_handler, args=(end_event,), name='realdata_handler')
  realdata_thread.start()
  threads.append(realdata_thread)
  debug_print("Started realdata handler thread")

  # --- Keep Main Thread Alive & Handle Shutdown ---
  try:
    while not end_event.is_set():
      # Optional: Add main thread checks or tasks here if needed
      time.sleep(1) # Keep main thread alive
  except KeyboardInterrupt:
    debug_print("KeyboardInterrupt received, shutting down...")
    cloudlog.info("Azure upload service shutting down")
  finally:
    if not end_event.is_set():
        end_event.set() # Signal threads to exit

    debug_print("Waiting for threads to finish...")
    for t in threads:
      try:
        t.join(timeout=10) # Wait max 10 seconds per thread
        if t.is_alive():
             debug_print(f"Thread {t.name} did not finish cleanly.")
             cloudlog.warning(f"Thread {t.name} did not finish cleanly on shutdown.")
      except Exception as e:
         debug_print(f"Error joining thread {t.name}: {e}")
         cloudlog.exception("azure.main.join_error", thread_name=t.name)

    # Final cache before exiting? Might not capture everything if threads were killed.
    # UploadQueueCache.cache(upload_queue)
    debug_print("Azure upload service shutdown complete.")
    cloudlog.info("Azure upload service stopped")

if __name__ == "__main__":
  # Ensure necessary directories exist if running locally for testing
  if DEBUG and not os.path.exists(SOURCE_DATA_DIR):
      os.makedirs(SOURCE_DATA_DIR)
      print(f"[DEBUG] Created test directory {SOURCE_DATA_DIR}")
  if DEBUG and not os.path.exists("/persist"):
       os.makedirs("/persist")
       print("[DEBUG] Created test directory /persist")
       # Create a dummy connection string file for local testing
       dummy_conn_str = "DefaultEndpointsProtocol=https;AccountName=youraccount;AccountKey=yourkey;EndpointSuffix=core.windows.net"
       if not os.path.exists("/persist/azure_conn_string"):
           with open("/persist/azure_conn_string", "w") as f:
               f.write(dummy_conn_str)
           print("[DEBUG] Created dummy /persist/azure_conn_string file.")


  main()
