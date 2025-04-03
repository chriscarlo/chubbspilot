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
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from functools import partial
from queue import Queue
from typing import cast

# OpenPilot / system imports
import cereal.messaging as messaging
from cereal import log
from openpilot.common.file_helpers import CallbackReader  # If you don't need chunk callbacks, remove it
from openpilot.common.params import Params
from openpilot.common.realtime import set_core_affinity
from openpilot.system.hardware import HARDWARE, PC
from openpilot.system.loggerd.xattr_cache import getxattr, setxattr
from openpilot.common.swaglog import cloudlog
from openpilot.system.version import get_build_metadata
from openpilot.system.hardware.hw import Paths

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
HANDLER_THREADS = 1
MAX_RETRY_COUNT = 5      # Reduced retry attempts for faster failure/skip
RETRY_DELAY = 10         # seconds to wait after a failed attempt
# MAX_AGE removed - filtering now done by creation time in realdata_handler
HOURLY_CLEAR_INTERVAL = 3600 # 1 hour in seconds

# Azure File Share config
AZURE_SHARE_NAME = "chauffeurlogs"
AZURE_BASE_DIR   = "rlogs"

# Debug flag - only True when running directly
DEBUG = __name__ == "__main__"

# Global state
last_clear_time = 0 # Timestamp of the last queue clear

def debug_print(*args, **kwargs):
  if DEBUG:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG]", *args, **kwargs)

def debug_queue_status():
  """Print current status of upload queue and active uploads"""
  if not DEBUG:
    return
  active_count = len([x for x in cur_upload_items.values() if x is not None])
  queue_size = upload_queue.qsize()
  print("\n[DEBUG] === Queue Status ===")
  print(f"Active uploads: {active_count}")
  print(f"Queue size: {queue_size}")
  print("Active upload items:")
  for tid, item in cur_upload_items.items():
    if item is not None:
      print(f"  Thread {tid}: {item.path} -> {item.azure_subdir} (progress: {item.progress}, retries: {item.retry_count})")
  print("Next 3 queued items:")
  # Use mutex for safe access to internal queue list
  with upload_queue.mutex:
    items = list(upload_queue.queue)[:3]
  for item in items:
    print(f"  {item.path} -> {item.azure_subdir} (retries: {item.retry_count})")
  print("========================\n")

# -------------------------------------------------------------------------------
# Azure Connection / Upload
# -------------------------------------------------------------------------------

def get_azure_connection_string() -> str:
  """
  Reads the Azure connection string from /persist/azure_conn_string
  """
  try:
    # Cache connection string in memory to avoid frequent file reads
    if not hasattr(get_azure_connection_string, "conn_str"):
      with open("/persist/azure_conn_string", "r") as f:
        conn_str = f.read().strip()
        get_azure_connection_string.conn_str = conn_str # Cache it
        debug_print(f"Successfully read Azure connection string (length: {len(conn_str)})")
    return get_azure_connection_string.conn_str
  except Exception as e:
    debug_print(f"Failed to read Azure connection string: {str(e)}")
    cloudlog.exception("azure.get_azure_connection_string.exception")
    return ""

def azure_file_exists(conn_str, share_name, dir_path, filename):
    if ShareDirectoryClient is None or ResourceNotFoundError is None:
        raise Exception("Azure SDK not available for file existence check.")
    dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, dir_path)
    file_client = dir_client.get_file_client(filename)
    try:
        file_client.get_file_properties()
        debug_print(f"Azure file check: EXISTS - {dir_path}/{filename}")
        return True
    except ResourceNotFoundError:
        debug_print(f"Azure file check: NOT FOUND - {dir_path}/{filename}")
        return False
    except Exception as e:
        debug_print(f"Azure file check: Error checking {dir_path}/{filename} - {str(e)}")
        cloudlog.warning(f"Azure file existence check failed: {str(e)}")
        raise # Propagate other errors

def ensure_azure_directory_exists(conn_str, share_name, azure_path):
    if ShareDirectoryClient is None or ResourceExistsError is None:
        raise Exception("Azure SDK not available for directory creation.")
    # Ensure parent directories exist first (Azure SDK might handle this, but explicit is safer)
    parts = azure_path.split('/')
    current_path = ""
    for part in parts:
        if not part: continue
        current_path = f"{current_path}/{part}" if current_path else part
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, current_path)
        try:
            dir_client.create_directory()
            debug_print(f"Ensured Azure directory exists: {current_path}")
        except ResourceExistsError:
            # Directory already exists, which is fine
            pass
        except Exception as e:
            debug_print(f"Error creating directory {current_path}: {str(e)}")
            cloudlog.exception("Azure ensure_azure_directory_exists error", exc_info=e)
            raise # Propagate error

def _do_upload_azure(upload_item: UploadItem):
  """
  Upload a file to Azure File Share.
  Creates the target directory (including prepended date) if needed.
  Skips the upload if the file already exists in the target Azure location.
  """
  conn_str = get_azure_connection_string()
  if not conn_str or (ShareDirectoryClient is None):
    debug_print("Azure upload not configured - missing connection string or SDK")
    raise Exception("Azure upload not configured (missing connection string or azure-storage-file-share).")

  if not upload_item.azure_subdir:
      cloudlog.error(f"Azure upload item missing azure_subdir: {upload_item.path}")
      raise ValueError("UploadItem missing required azure_subdir for Azure upload")

  local_path = upload_item.path
  filename = os.path.basename(local_path)
  # Construct the full target path in Azure using azure_subdir
  azure_target_dir = f"{AZURE_BASE_DIR}/{upload_item.azure_subdir}"

  debug_print(f"\n[DEBUG] === Starting Azure Upload Attempt ===")
  debug_print(f"Local path: {local_path}")
  debug_print(f"Target Azure directory: {azure_target_dir}")
  debug_print(f"Target Azure filename: {filename}")
  debug_print(f"File size: {os.path.getsize(local_path) if os.path.exists(local_path) else 'N/A'} bytes")

  if not os.path.isfile(local_path):
    debug_print(f"File not found locally: {local_path}")
    raise FileNotFoundError(f"Local file not found: {local_path}")

  try:
    debug_print("Ensuring Azure directory exists...")
    ensure_azure_directory_exists(conn_str, AZURE_SHARE_NAME, azure_target_dir)

    # Check if file already exists on Azure *in the target directory*
    if azure_file_exists(conn_str, AZURE_SHARE_NAME, azure_target_dir, filename):
      debug_print(f"File already exists on Azure, skipping upload: {azure_target_dir}/{filename}")
      return # Return successfully as the file is already there

    debug_print("Creating Azure file client for upload...")
    # Use the specific target directory client
    dir_client = ShareDirectoryClient.from_connection_string(
      conn_str, AZURE_SHARE_NAME, azure_target_dir
    )
    file_client = dir_client.get_file_client(filename)

    debug_print("Starting file upload...")
    with open(local_path, "rb") as f:
        # Using upload_file handles chunking automatically. Timeout is for the whole operation.
        # Consider adjusting timeout based on typical file sizes and network.
        file_client.upload_file(f, timeout=600) # 10 minute overall timeout
    debug_print("File upload completed successfully")
    debug_print("=== Azure Upload Attempt Complete ===\n")

    cloudlog.event("azure._do_upload_azure.success", subdir=upload_item.azure_subdir, local_path=local_path, azure_path=f"{azure_target_dir}/{filename}")
  except (ResourceNotFoundError, FileNotFoundError) as e:
      # Re-raise FileNotFoundError specifically if local file vanished
      if isinstance(e, FileNotFoundError):
          raise e
      # Treat Azure ResourceNotFoundError during upload as potentially transient? Or fail?
      debug_print(f"Azure resource not found during upload: {str(e)}")
      cloudlog.warning(f"Azure ResourceNotFoundError during upload for {azure_target_dir}/{filename}: {e}")
      raise # Let retry handler decide
  except ServiceResponseError as e:
      # Catch specific Azure service errors (like timeouts within the SDK)
      debug_print(f"Azure ServiceResponseError during upload: {str(e)}")
      cloudlog.warning(f"Azure ServiceResponseError for {azure_target_dir}/{filename}: {e}")
      raise # Let retry handler decide
  except Exception as e:
    # Catch other potential errors (network, permissions, etc.)
    debug_print(f"Error during Azure upload process: {str(e)}")
    cloudlog.exception(f"azure._do_upload_azure exception for {azure_target_dir}/{filename}", exc_info=e)
    raise # Propagate to trigger retry logic

# -------------------------------------------------------------------------------
# Upload Items/Queue
# -------------------------------------------------------------------------------
@dataclass
class UploadItem:
  path: str
  url: str                 # Not used for Azure; can be left blank
  headers: dict[str, str]  # Not used for Azure
  created_at: int          # Timestamp (ms) related to the item (e.g., source dir creation)
  id: str | None           # Unique ID for tracking (e.g., "azure|src_dir|filename")
  retry_count: int = 0
  current: bool = False
  progress: float = 0      # Set to 1.0 on success or definite skip
  allow_cellular: bool = True # Default to allowing cellular for these logs

  # Azure-specific target subdirectory name (e.g., "YYMMDD--original_dir")
  azure_subdir: str | None = None

  @classmethod
  def from_dict(cls, d: dict) -> UploadItem:
    # Handle potential missing keys gracefully during load
    return cls(
      path=d.get("path", ""),
      url=d.get("url", ""),
      headers=d.get("headers", {}),
      created_at=d.get("created_at", 0),
      id=d.get("id"), # id might be None
      retry_count=d.get("retry_count", 0),
      current=d.get("current", False),
      progress=d.get("progress", 0.0),
      allow_cellular=d.get("allow_cellular", True), # Match default
      azure_subdir=d.get("azure_subdir"), # Can be None
    )

class AbortTransferException(Exception):
  pass

cur_upload_items: dict[int, UploadItem | None] = {}
cancelled_uploads: set[str] = set() # Currently unused, keep for potential future use
upload_queue: Queue[UploadItem] = queue.Queue()

class UploadQueueCache:
  """
  Simple utility to persist the upload queue across restarts in a param named "AzureUploadQueue".
  """
  PARAM_NAME = "AzureUploadQueue"

  @staticmethod
  def initialize(upload_queue_instance: Queue[UploadItem]) -> None:
    """Load any previously queued items from the param store."""
    global last_clear_time
    params = Params()
    try:
      upload_queue_json = params.get(UploadQueueCache.PARAM_NAME)
      if upload_queue_json is not None:
        loaded_items = 0
        items_data = json.loads(upload_queue_json)
        for item_dict in items_data:
          item = UploadItem.from_dict(item_dict)
          # Basic validation
          if item.path and item.id and item.azure_subdir:
              # Reset progress and current status on load
              item = replace(item, progress=0.0, current=False)
              upload_queue_instance.put(item)
              loaded_items += 1
          else:
              debug_print(f"Skipping invalid item from cache: {item_dict}")
        debug_print(f"Initialized queue with {loaded_items} items from cache.")
      else:
        debug_print("No cached queue found.")
      # Assume cache is fresh on init, reset clear timer
      last_clear_time = time.time()
    except json.JSONDecodeError:
      cloudlog.error("Failed to decode AzureUploadQueue JSON, clearing.")
      params.remove(UploadQueueCache.PARAM_NAME)
      last_clear_time = time.time() # Treat as cleared
    except Exception:
      cloudlog.exception("azure.UploadQueueCache.initialize.exception")
      # Potentially clear cache if loading fails badly?
      # params.remove(UploadQueueCache.PARAM_NAME)
      last_clear_time = time.time() # Treat as cleared

  @staticmethod
  def cache(upload_queue_instance: Queue[UploadItem]) -> None:
    """
    Save non-completed items back to the param store.
    """
    params = Params()
    try:
      items_to_cache = []
      # Add items currently being processed (if not finished)
      for item in cur_upload_items.values():
          if item is not None and item.progress < 1.0:
              items_to_cache.append(asdict(item))

      # Add items waiting in the queue
      with upload_queue_instance.mutex:
          queued_items = list(upload_queue_instance.queue)
      for item in queued_items:
          if item is not None and item.progress < 1.0:
              # Ensure it's not already added from cur_upload_items
              if not any(i['id'] == item.id for i in items_to_cache):
                  items_to_cache.append(asdict(item))

      if items_to_cache:
          debug_print(f"Caching {len(items_to_cache)} items to {UploadQueueCache.PARAM_NAME}")
          params.put(UploadQueueCache.PARAM_NAME, json.dumps(items_to_cache))
      else:
          # If nothing to cache, remove the param
          debug_print(f"Queue and active uploads are empty, removing {UploadQueueCache.PARAM_NAME}")
          params.remove(UploadQueueCache.PARAM_NAME)

    except Exception:
      cloudlog.exception("azure.UploadQueueCache.cache.exception")

  @staticmethod
  def clear_cache() -> None:
    """Explicitly remove the queue from the param store."""
    try:
        Params().remove(UploadQueueCache.PARAM_NAME)
        debug_print(f"Cleared cached queue param: {UploadQueueCache.PARAM_NAME}")
    except Exception:
        cloudlog.exception("azure.UploadQueueCache.clear_cache.exception")


# -------------------------------------------------------------------------------
# Upload Handler Thread
# -------------------------------------------------------------------------------

# --- retry_upload function remains the same as the previous correction ---
def retry_upload(tid: int, end_event: threading.Event, increase_count: bool = True) -> None:
  """
  If an upload fails or is aborted, re-queue it (unless we've exceeded retry limits).
  Ensures task_done() is called for the failed/aborted attempt.
  """
  item = cur_upload_items.get(tid) # Use .get for safety
  if item is None:
    debug_print(f"Thread {tid}: No item found to retry (item might have been cleared).")
    return

  new_retry_count = item.retry_count + 1 if increase_count else item.retry_count

  # --- Mark the task as done *for the failed attempt* BEFORE potentially requeueing ---
  try:
    upload_queue.task_done()
    debug_print(f"Thread {tid}: Marked task done for failed attempt of {item.id}")
  except ValueError:
    debug_print(f"Warning: task_done() called too many times before retry/max_retry for item {item.id}")
  except Exception as e:
      debug_print(f"Error calling task_done() before retry for {item.id}: {e}")
      cloudlog.exception("azure.upload_handler.retry.task_done_error")


  # --- Check Max Retries ---
  if new_retry_count > MAX_RETRY_COUNT:
    debug_print(f"\n[DEBUG] === Max Retries Reached (Thread {tid}) ===")
    debug_print(f"File: {item.path}")
    debug_print(f"Azure Subdir: {item.azure_subdir}")
    debug_print(f"Giving up after {item.retry_count} retries.")
    debug_print("=== Retry Aborted ===\n")
    cloudlog.event("azure.upload_handler.max_retries", item=asdict(item), error=True)
    # Mark as done logically by setting progress=1.0 so cache knows to remove it eventually
    # Use replace on the original item state before it was cleared, if possible
    original_item_state = cur_upload_items.get(tid) # Get the state again just in case
    if original_item_state:
       cur_upload_items[tid] = replace(original_item_state, progress=1.0, current=False)
    else: # Fallback if state was already cleared somehow
       cur_upload_items[tid] = replace(item, progress=1.0, current=False) # Use item as fallback
    # Update cache after marking done
    UploadQueueCache.cache(upload_queue)
    cur_upload_items[tid] = None # Clear current item for this thread
    return # Exit retry logic

  # --- Requeue the item ---
  debug_print(f"\n[DEBUG] === Retrying Upload (Thread {tid}) ===")
  debug_print(f"File: {item.path}")
  debug_print(f"Azure Subdir: {item.azure_subdir}")
  debug_print(f"Next retry count: {new_retry_count}")
  debug_print(f"Increase count: {increase_count}")

  # Create a new item instance for requeueing
  requeued_item = replace(item, retry_count=new_retry_count, progress=0.0, current=False)
  upload_queue.put_nowait(requeued_item)
  # Update cache *after* successfully requeueing
  UploadQueueCache.cache(upload_queue)
  debug_print(f"Item {item.id} requeued successfully.")
  debug_print("=== Retry Queued ===\n")

  # Clear the current item *after* successfully requeueing
  cur_upload_items[tid] = None

  # Wait before the thread picks up a new item
  debug_print(f"Thread {tid} waiting {RETRY_DELAY}s before next attempt...")
  interrupted = end_event.wait(RETRY_DELAY) # Use event wait for faster shutdown
  if interrupted:
      debug_print(f"Thread {tid}: Retry delay interrupted by shutdown.")


def upload_handler(end_event: threading.Event) -> None:
  """
  Thread that pulls items off `upload_queue` and uploads them to Azure.
  Retries if needed. Checks metered connection status. Uses deviceState.networkType raw integer value.
  """
  sm = messaging.SubMaster(['deviceState'])
  tid = threading.get_ident()
  debug_print(f"\n[DEBUG] === Upload Handler Started (Thread {tid}) ===")

  while not end_event.is_set():
    cur_upload_items[tid] = None # Ensure state is clean before getting item
    item = None # Define item here for use in finally block
    try:
      item = upload_queue.get(timeout=1) # Wait up to 1s for an item

      cur_upload_items[tid] = replace(item, current=True)
      debug_print(f"\n[DEBUG] === Processing Upload Item (Thread {tid}) ===")
      debug_print(f"Item ID: {item.id}")
      debug_print(f"File: {item.path}")
      debug_print(f"Azure Subdir: {item.azure_subdir}")
      debug_print(f"Retry count: {item.retry_count}")
      debug_print(f"Allow cellular: {item.allow_cellular}")

      if item.id in cancelled_uploads:
        debug_print(f"Item {item.id} was cancelled, skipping")
        cancelled_uploads.remove(item.id)
        cur_upload_items[tid] = replace(item, progress=1.0, current=False) # Mark as done
        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)
        continue

      # Check network status **before** attempting upload
      sm.update(0) # Non-blocking update

      if not sm.valid['deviceState']:
          debug_print(f"No valid deviceState message yet, deferring upload (Thread {tid})")
          retry_upload(tid, end_event, increase_count=False)
          continue

      metered = sm['deviceState'].networkMetered
      # --- REVERT TO USING INTEGER VALUE ---
      network_type_enum = sm['deviceState'].networkType
      # Cast the enum directly to int to get the raw numerical value (0, 1, 4, etc.)
      network_type_int = int(network_type_enum)
      # log.capnp defines: none @0; wifi @1; cell2g @2; cell3g @3; cell4g @4; cell5g @5; ethernet @6; unknown @7;
      # --- END REVERT ---

      debug_print(f"\n[DEBUG] === Network Status (Thread {tid}) ===")
      # Check connectivity based on the integer value (0 means 'none')
      is_connected = network_type_int != 0
      # Log the integer value as it was likely done originally
      debug_print(f"Connected: {is_connected} (Type: {network_type_int})")
      debug_print(f"Metered connection: {metered}")

      if not is_connected:
          debug_print("Network type is 'none' (0), deferring upload.")
          retry_upload(tid, end_event, increase_count=False)
          continue

      if metered and not item.allow_cellular:
        debug_print("Metered connection detected and cellular not allowed, deferring upload")
        retry_upload(tid, end_event, increase_count=False)
        continue

      # --- Network conditions met, proceed with upload ---
      try:
        fn = item.path
        file_size = 0
        try:
          if not os.path.isfile(fn):
               raise FileNotFoundError(f"Local file disappeared before upload: {fn}")
          file_size = os.path.getsize(fn)
          debug_print(f"Local file size: {file_size} bytes")
        except OSError as e:
          debug_print(f"Error getting file size for {fn} just before upload: {str(e)}")
          pass # Proceed, size is mostly for logging

        # Log the integer network type
        cloudlog.event("azure.upload_handler.upload_start",
                       fn=fn, sz=file_size, azure_subdir=item.azure_subdir,
                       network_type=network_type_int, # Log integer value
                       metered=metered,
                       retry_count=item.retry_count)

        _do_upload_azure(item)

        # Mark success
        cur_upload_items[tid] = replace(item, progress=1.0, current=False)
        debug_print(f"\n[DEBUG] === Upload Success/Skipped (Thread {tid}) ===")
        debug_print(f"File: {fn}")
        debug_print(f"Azure Subdir: {item.azure_subdir}")
        debug_print("=== Upload Complete ===\n")
        # Log the integer network type
        cloudlog.event("azure.upload_handler.success", fn=fn, sz=file_size, azure_subdir=item.azure_subdir,
                       network_type=network_type_int, # Log integer value
                       metered=metered)

        upload_queue.task_done() # Signal completion *after* success
        UploadQueueCache.cache(upload_queue) # Update cache on success

      except FileNotFoundError:
        debug_print(f"\n[DEBUG] === File Not Found Locally (Thread {tid}) ===")
        debug_print(f"File: {fn}")
        debug_print("Marking as complete, won't retry.")
        debug_print("=== Error Complete ===\n")
        cloudlog.event("azure.upload_handler.not_found", fn=fn, azure_subdir=item.azure_subdir)
        cur_upload_items[tid] = replace(item, progress=1.0, current=False) # Mark as done
        upload_queue.task_done() # Signal completion for this item
        UploadQueueCache.cache(upload_queue)

      except (ConnectionError, TimeoutError, ServiceResponseError, socket.timeout, ResourceNotFoundError) as e:
        debug_print(f"\n[DEBUG] === Network/Service Error (Thread {tid}) ===")
        debug_print(f"File: {fn}")
        debug_print(f"Azure Subdir: {item.azure_subdir}")
        debug_print(f"Error Type: {type(e).__name__}")
        debug_print(f"Error Details: {str(e)}")
        debug_print("Attempting retry...")
        debug_print("=== Error Complete ===\n")
        log_level = cloudlog.warning if isinstance(e, (ResourceNotFoundError, TimeoutError, socket.timeout)) else cloudlog.error # Adjust logging level based on error type
        log_level(f"azure.upload_handler.network_error", fn=fn, azure_subdir=item.azure_subdir,
                  network_type=network_type_int, # Log integer value
                  error_type=type(e).__name__, error=str(e), exc_info=DEBUG)
        retry_upload(tid, end_event)

      except AbortTransferException:
        debug_print(f"\n[DEBUG] === Upload Aborted by Request (Thread {tid}) ===")
        # ... (logging as before) ...
        cloudlog.event("azure.upload_handler.abort", fn=fn, azure_subdir=item.azure_subdir,
                       network_type=network_type_int, # Log integer value
                       metered=metered)
        retry_upload(tid, end_event, increase_count=False)

      except Exception as e:
        debug_print(f"\n[DEBUG] === Unexpected Upload Error (Thread {tid}) ===")
        debug_print(f"File: {fn}")
        debug_print(f"Azure Subdir: {item.azure_subdir}")
        debug_print(f"Error Type: {type(e).__name__}")
        debug_print(f"Error Details: {str(e)}")
        debug_print("Attempting retry...")
        debug_print("=== Error Complete ===\n")
        cloudlog.exception(f"azure.upload_handler.azure_upload_fail for {item.azure_subdir}/{os.path.basename(fn)}",
                           network_type=network_type_int) # Log integer value
        retry_upload(tid, end_event)

    except queue.Empty:
      continue # Loop and wait again

    except Exception as e:
      debug_print(f"\n[DEBUG] === Handler Loop Error (Thread {tid}) ===")
      debug_print(f"Error Type: {type(e).__name__}")
      debug_print(f"Error Details: {str(e)}")
      debug_print("=== Error Complete ===\n")
      cloudlog.exception("azure.upload_handler.outer_exception")
      interrupted = end_event.wait(5)
      if interrupted:
          debug_print(f"Thread {tid}: Outer loop wait interrupted by shutdown.")
    finally:
        # Cleanup logic remains the same as previous version
        if item is not None and cur_upload_items.get(tid) is not None and cur_upload_items.get(tid).id == item.id:
             debug_print(f"Item {item.id} in unexpected state in finally block (Thread {tid}), clearing state.")
             try:
                 upload_queue.task_done()
                 debug_print(f"Thread {tid}: Called task_done in finally block for {item.id}")
             except ValueError:
                 debug_print(f"Thread {tid}: task_done likely already called for {item.id} (expected in some error paths).")
             except Exception as final_e:
                 debug_print(f"Error during final task_done for {item.id}: {final_e}")
                 cloudlog.exception("azure.upload_handler.finally.task_done_error")
             cur_upload_items[tid] = None

  debug_print(f"Upload handler thread {tid} exiting.")

# -------------------------------------------------------------------------------
# Automatic RLog Finder (realdata_handler)
# -------------------------------------------------------------------------------
def realdata_handler(end_event: threading.Event) -> None:
  """
  Scans /data/media/0/realdata/ for subdirectories CREATED within the last 24 hours.
  For each such directory, queues upload items for 'rlog', 'qlog', 'qcamera.ts' if they exist.
  Performs an hourly queue clear and re-scan.
  """
  global last_clear_time
  base_path = "/data/media/0/realdata"
  age_limit_seconds = 24 * 3600
  scan_interval = 300 # Scan every 5 minutes

  while not end_event.is_set():
    current_time = time.time()

    # --- Hourly Queue Clear ---
    if current_time - last_clear_time >= HOURLY_CLEAR_INTERVAL:
      cloudlog.info("Performing hourly Azure queue clear and preparing for re-scan.")
      debug_print("Performing hourly Azure queue clear and preparing for re-scan.")
      try:
        # Clear the persisted queue first
        UploadQueueCache.clear_cache()

        # Clear the in-memory queue
        drained_count = 0
        # Drain the queue safely
        while not upload_queue.empty():
          try:
            item = upload_queue.get_nowait()
            upload_queue.task_done() # Mark task as done even if we discard it
            drained_count += 1
          except queue.Empty:
            break # Queue became empty during drain

        debug_print(f"Cleared in-memory upload_queue (drained {drained_count} items).")

        # Note: Active uploads in upload_handler threads are NOT cancelled here.
        # They will complete or fail. If they succeed, the file exists check
        # in _do_upload_azure will prevent re-upload during the subsequent scan.
        # If they fail, they won't be requeued because the main queue is empty.

        last_clear_time = current_time # Update time *after* successful clear
        cloudlog.info("Hourly Azure queue clear complete. Starting re-scan.")
        debug_print("Hourly Azure queue clear complete. Starting re-scan.")

      except Exception as e:
        cloudlog.exception("azure.realdata_handler.hourly_clear.exception")
        debug_print(f"Hourly clear failed: {e}. Retrying next cycle.")
        # Don't update last_clear_time if clearing failed, try again next interval

    # --- Scan for Recent Directories ---
    try:
      debug_print(f"Scanning {base_path} for directories created within the last 24 hours...")
      one_day_ago_ts = current_time - age_limit_seconds
      found_count = 0
      queued_count = 0

      if not os.path.isdir(base_path):
          debug_print(f"Base path {base_path} not found, skipping scan.")
          cloudlog.error(f"Realdata base path not found: {base_path}")
          time.sleep(scan_interval) # Wait before retrying scan
          continue

      for subdir in os.listdir(base_path):
        subdir_path = os.path.join(base_path, subdir)
        if not os.path.isdir(subdir_path):
          continue

        try:
          # Use ctime (creation time on Unix/Linux)
          stat_info = os.stat(subdir_path)
          creation_time_ts = stat_info.st_ctime
        except OSError as e:
          debug_print(f"Could not stat directory {subdir_path}: {e}")
          continue # Skip if cannot stat

        # Filter by CREATION time (last 24 hours)
        if creation_time_ts < one_day_ago_ts:
          continue

        found_count += 1
        # Format creation time for Azure path: YYMMDD
        creation_dt = datetime.fromtimestamp(creation_time_ts)
        formatted_date = creation_dt.strftime("%y%m%d")
        # Construct Azure target subdirectory name
        azure_target_subdir = f"{formatted_date}--{subdir}"

        # Files to consider uploading from this directory
        files_to_upload = ['rlog', 'qlog', 'qcamera.ts']

        for filename in files_to_upload:
          local_path = os.path.join(subdir_path, filename)
          if not os.path.isfile(local_path):
            continue # Skip if this specific file doesn't exist

          # Unique ID based on source directory and filename
          upload_id = f"azure|{subdir}|{filename}"

          # Check if already queued or currently uploading (more robust check)
          is_active = False
          # Check current uploads
          if any(ci and ci.id == upload_id for ci in cur_upload_items.values()):
              is_active = True
          # Check queue (safely)
          if not is_active:
              with upload_queue.mutex:
                  if any(qi and qi.id == upload_id for qi in list(upload_queue.queue)):
                      is_active = True

          if is_active:
            # debug_print(f"Item {upload_id} already queued or active, skipping.")
            continue

          # Queue the upload item
          item = UploadItem(
            path=local_path,
            url="", # Not used
            headers={}, # Not used
            # Use directory ctime as the reference creation time (milliseconds)
            created_at=int(creation_time_ts * 1000),
            id=upload_id,
            azure_subdir=azure_target_subdir, # Use the formatted name
            allow_cellular=True # Default allow cellular for these logs
          )
          debug_print(f"Queueing item: {item.id} (Source: {subdir}/{filename}) -> Azure: {azure_target_subdir}/{filename}")
          upload_queue.put_nowait(item)
          queued_count += 1
          # Cache is updated periodically or on significant events (like adding)
          UploadQueueCache.cache(upload_queue)

      debug_print(f"Scan complete. Found {found_count} recent directories, queued {queued_count} new file uploads.")

    except Exception as e:
      cloudlog.exception("azure.realdata_handler.scan_exception")
      debug_print(f"Error during realdata scan: {e}")

    # Wait before next scan or clear check
    end_event.wait(scan_interval) # Use event wait for faster shutdown response

  debug_print("Realdata handler thread exiting.")

# -------------------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------------------
def main():
  """
  Initializes queue, starts upload and scanner threads, and waits for termination.
  """
  cloudlog.info("Starting Azure upload service")
  debug_print("Starting Azure upload service")
  try:
    # Lower priority threads for background uploads? Check OP conventions.
    # set_core_affinity([0, 1, 2, 3]) # Example affinity
    pass # Affinity setting depends on system resources/policy
  except Exception:
    cloudlog.exception("failed to set core affinity")
    debug_print("Failed to set core affinity")

  # Ensure Azure SDK is available
  if ShareFileClient is None or ShareDirectoryClient is None:
      cloudlog.error("Azure SDK not found. Service cannot run.")
      print("Azure SDK not found. Service cannot run. Please `pip install azure-storage-file-share`", file=sys.stderr)
      return

  # Initialize queue from stored cache
  UploadQueueCache.initialize(upload_queue)
  debug_print(f"Initial queue size: {upload_queue.qsize()}")
  debug_queue_status() # Show status after load

  end_event = threading.Event()
  threads = []

  # Start Upload Handlers
  for i in range(HANDLER_THREADS):
      t = threading.Thread(target=upload_handler, args=(end_event,), name=f'upload_handler_{i}')
      t.start()
      threads.append(t)
      # Initialize state for this thread's current item
      cur_upload_items[t.ident] = None

  # Start Realdata Scanner
  realdata_thread = threading.Thread(target=realdata_handler, args=(end_event,), name='realdata_handler')
  realdata_thread.start()
  threads.append(realdata_thread)

  cloudlog.info(f"Azure upload service started with {HANDLER_THREADS} upload thread(s).")
  debug_print(f"Started {len(threads)} threads.")

  try:
    while not end_event.is_set():
        # Keep main thread alive, maybe perform periodic health checks?
        time.sleep(5)
        # Optional: Periodically save cache state even if no new items added?
        # UploadQueueCache.cache(upload_queue) # Could add overhead

  except KeyboardInterrupt:
    cloudlog.info("Keyboard interrupt received, shutting down Azure service.")
    debug_print("Received keyboard interrupt, shutting down...")
    pass
  finally:
    end_event.set() # Signal threads to exit
    cloudlog.info("Waiting for threads to finish...")
    debug_print("Waiting for threads to join...")
    for t in threads:
      t.join(timeout=10) # Wait max 10s per thread
      if t.is_alive():
          cloudlog.warning(f"Thread {t.name} did not exit cleanly.")
          debug_print(f"Thread {t.name} did not join!")

    # Final cache save attempt on shutdown
    debug_print("Performing final queue cache before exit.")
    UploadQueueCache.cache(upload_queue)

    cloudlog.info("Azure upload service shutdown complete.")
    debug_print("Service shutdown complete")

if __name__ == "__main__":
  main()