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

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from functools import partial
from queue import Queue
from typing import cast

# OpenPilot / system imports
import cereal.messaging as messaging
from cereal import log               # Ensure log is imported for log.DeviceState.NetworkType
from openpilot.common.file_helpers import CallbackReader
from openpilot.common.params import Params
from openpilot.common.realtime import set_core_affinity
# from openpilot.system.hardware import HARDWARE, PC # Not used directly
# from openpilot.system.loggerd.xattr_cache import getxattr, setxattr # Not used directly
from openpilot.common.swaglog import cloudlog
# from openpilot.system.version import get_build_metadata # Not used directly
# from openpilot.system.hardware.hw import Paths # Not used directly

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
MAX_RETRY_COUNT = 5
RETRY_DELAY = 10
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
  # Use mutex for safe access to internal queue list size check
  with upload_queue.mutex:
      queue_size = upload_queue.qsize() # qsize is thread-safe
  print("\n[DEBUG] === Queue Status ===")
  print(f"Active uploads: {active_count}")
  print(f"Queue size: {queue_size}")
  print("Active upload items:")
  # Copy items to avoid issues if dict changes during iteration
  current_items_copy = dict(cur_upload_items)
  for tid, item in current_items_copy.items():
    if item is not None:
      print(f"  Thread {tid}: {item.path} -> {item.azure_subdir} (progress: {item.progress}, retries: {item.retry_count})")
  print("Next 3 queued items:")
  # Use mutex for safe access to internal queue list iteration
  with upload_queue.mutex:
    items = list(upload_queue.queue)[:3]
  for item in items:
    print(f"  {item.path} -> {item.azure_subdir} (retries: {item.retry_count})")
  print("========================\n")


# -------------------------------------------------------------------------------
# Azure Connection / Upload (Keeping previous corrected version)
# -------------------------------------------------------------------------------
def get_azure_connection_string() -> str:
  """ Reads the Azure connection string from /persist/azure_conn_string """
  try:
    if not hasattr(get_azure_connection_string, "conn_str_cache"):
      with open("/persist/azure_conn_string", "r") as f:
        conn_str = f.read().strip()
        get_azure_connection_string.conn_str_cache = conn_str # Cache it
        debug_print(f"Successfully read Azure connection string (length: {len(conn_str)})")
    return get_azure_connection_string.conn_str_cache
  except Exception as e:
    debug_print(f"Failed to read Azure connection string: {str(e)}")
    cloudlog.exception("azure.get_azure_connection_string.exception")
    get_azure_connection_string.conn_str_cache = "" # Cache empty string on error
    return ""

def azure_file_exists(conn_str, share_name, dir_path, filename):
    if ShareDirectoryClient is None or ResourceNotFoundError is None:
        raise Exception("Azure SDK not available for file existence check.")
    try:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, dir_path)
        file_client = dir_client.get_file_client(filename)
        file_client.get_file_properties()
        debug_print(f"Azure file check: EXISTS - {dir_path}/{filename}")
        return True
    except ResourceNotFoundError:
        debug_print(f"Azure file check: NOT FOUND - {dir_path}/{filename}")
        return False
    except Exception as e:
        debug_print(f"Azure file check: Error checking {dir_path}/{filename} - {str(e)}")
        cloudlog.warning(f"Azure file existence check failed for {dir_path}/{filename}: {str(e)}")
        raise # Propagate other errors like connection issues

def ensure_azure_directory_exists(conn_str, share_name, azure_path):
    if ShareDirectoryClient is None or ResourceExistsError is None:
        raise Exception("Azure SDK not available for directory creation.")
    parts = azure_path.strip('/').split('/')
    current_path = ""
    dir_client = None # Define outside loop for clarity
    for part in parts:
        if not part: continue
        current_path = f"{current_path}/{part}" if current_path else part
        try:
            # Optimization: Only create client once per part
            dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, current_path)
            dir_client.create_directory()
            debug_print(f"Ensured Azure directory exists: {current_path}")
        except ResourceExistsError:
            pass # Already exists, fine
        except Exception as e:
            debug_print(f"Error creating/checking directory {current_path}: {str(e)}")
            cloudlog.exception(f"Azure ensure_azure_directory_exists error for {current_path}", exc_info=e)
            raise

def list_azure_directories(conn_str, share_name, dir_path):
    """ Lists directories within a specified Azure File Share path. """
    if ShareDirectoryClient is None:
        raise Exception("Azure SDK not available for listing directories.")
    try:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, dir_path)
        # list_directories_and_files returns an iterator of dicts {'name': '...', 'is_directory': True/False}
        return [item['name'] for item in dir_client.list_directories_and_files() if item['is_directory']]
    except ResourceNotFoundError:
        debug_print(f"Azure list directories: Path not found - {dir_path}")
        return [] # Path doesn't exist, so no directories within it
    except Exception as e:
        debug_print(f"Azure list directories: Error listing {dir_path} - {str(e)}")
        cloudlog.warning(f"Azure directory listing failed for {dir_path}: {str(e)}")
        raise # Propagate other errors

def rename_azure_directory(conn_str, share_name, old_dir_path, new_dir_path):
    """ Renames a directory in Azure File Share. """
    if ShareDirectoryClient is None:
        raise Exception("Azure SDK not available for renaming directories.")
    try:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, old_dir_path)
        # Ensure the new parent directory exists (rename requires it)
        new_parent_path = os.path.dirname(new_dir_path)
        if new_parent_path and new_parent_path != '.': # Handle case where new path is in root
             ensure_azure_directory_exists(conn_str, share_name, new_parent_path)

        debug_print(f"Attempting to rename Azure directory from '{old_dir_path}' to '{new_dir_path}'")
        # The destination path for rename_directory is the *full new path*
        dir_client.rename_directory(new_dir_path)
        debug_print(f"Successfully renamed Azure directory: '{old_dir_path}' -> '{new_dir_path}'")
        return True
    except ResourceNotFoundError:
        debug_print(f"Azure rename directory: Source directory not found - {old_dir_path}")
        return False # Source doesn't exist, cannot rename
    except ResourceExistsError:
        debug_print(f"Azure rename directory: Target directory already exists - {new_dir_path}")
        # This could happen if rename was interrupted or run twice. Treat as success?
        # Let's return True, assuming the desired state is achieved.
        return True
    except Exception as e:
        debug_print(f"Azure rename directory: Error renaming {old_dir_path} to {new_dir_path} - {str(e)}")
        cloudlog.warning(f"Azure directory rename failed for {old_dir_path} -> {new_dir_path}: {str(e)}")
        raise # Propagate other errors

def _do_upload_azure(upload_item: UploadItem):
  """ Upload a file to Azure File Share. Creates target directory. Skips if exists. """
  conn_str = get_azure_connection_string()
  if not conn_str or ShareDirectoryClient is None or ShareFileClient is None:
    debug_print("Azure upload not configured - missing connection string or SDK")
    raise Exception("Azure upload not configured (missing connection string or azure-storage-file-share).")

  if not upload_item.azure_subdir:
      cloudlog.error(f"Azure upload item missing azure_subdir: {upload_item.path}")
      raise ValueError("UploadItem missing required azure_subdir for Azure upload")

  local_path = upload_item.path
  filename = os.path.basename(local_path)
  azure_target_dir = f"{AZURE_BASE_DIR}/{upload_item.azure_subdir}"

  debug_print(f"\n[DEBUG] === Starting Azure Upload Attempt ===")
  debug_print(f"Local path: {local_path}")
  debug_print(f"Target Azure directory: {azure_target_dir}")
  debug_print(f"Target Azure filename: {filename}")

  # Check local file existence right before operations
  try:
    file_size = os.path.getsize(local_path)
    debug_print(f"Local file size: {file_size} bytes")
  except FileNotFoundError:
    debug_print(f"File not found locally: {local_path}")
    raise # Propagate to handler
  except OSError as e:
    debug_print(f"Error stating local file {local_path}: {e}")
    raise # Propagate other OS errors

  try:
    debug_print("Ensuring Azure directory exists...")
    ensure_azure_directory_exists(conn_str, AZURE_SHARE_NAME, azure_target_dir)

    # Check if file already exists on Azure *in the target directory*
    if azure_file_exists(conn_str, AZURE_SHARE_NAME, azure_target_dir, filename):
      debug_print(f"File already exists on Azure, skipping upload: {azure_target_dir}/{filename}")
      return # Return successfully as the file is already there

    debug_print("Creating Azure file client for upload...")
    # Use the specific target directory client - reuse if possible? No, path is specific.
    dir_client = ShareDirectoryClient.from_connection_string(
      conn_str, AZURE_SHARE_NAME, azure_target_dir
    )
    file_client = dir_client.get_file_client(filename)

    debug_print("Starting file upload...")
    with open(local_path, "rb") as f:
        # Use overwrite=True? Default is False, fails if exists. We check above, but maybe safer?
        # Let's keep default False as we explicitly check.
        file_client.upload_file(f, timeout=600) # 10 minute overall timeout
    debug_print(f"File upload completed successfully: {azure_target_dir}/{filename}")
    debug_print("=== Azure Upload Attempt Complete ===\n")

    cloudlog.event("azure._do_upload_azure.success", subdir=upload_item.azure_subdir, local_path=local_path, azure_path=f"{azure_target_dir}/{filename}")

  except (ResourceNotFoundError, FileNotFoundError) as e:
      # Re-raise FileNotFoundError specifically if local file vanished
      if isinstance(e, FileNotFoundError):
          raise e
      debug_print(f"Azure resource not found during upload op for {azure_target_dir}/{filename}: {str(e)}")
      cloudlog.warning(f"Azure ResourceNotFoundError during upload op for {azure_target_dir}/{filename}: {e}")
      raise # Let retry handler decide
  except ServiceResponseError as e:
      debug_print(f"Azure ServiceResponseError during upload for {azure_target_dir}/{filename}: {str(e)}")
      cloudlog.warning(f"Azure ServiceResponseError for {azure_target_dir}/{filename}: {e}")
      raise # Let retry handler decide
  except Exception as e:
    debug_print(f"Error during Azure upload process for {azure_target_dir}/{filename}: {str(e)}")
    cloudlog.exception(f"azure._do_upload_azure exception for {azure_target_dir}/{filename}", exc_info=e)
    raise


# -------------------------------------------------------------------------------
# Upload Items/Queue (Keeping previous corrected version)
# -------------------------------------------------------------------------------
@dataclass
class UploadItem:
  path: str
  created_at: int  # required
  id: str | None   # required
  url: str = ""
  headers: dict[str, str] = field(default_factory=dict)
  retry_count: int = 0
  current: bool = False
  progress: float = 0.0
  allow_cellular: bool = True
  azure_subdir: str | None = None

  @classmethod
  def from_dict(cls, d: dict) -> UploadItem:
    return cls(
      path=d.get("path", ""),
      url=d.get("url", ""),
      headers=d.get("headers", {}),
      created_at=d.get("created_at", 0),
      id=d.get("id"),
      retry_count=d.get("retry_count", 0),
      current=d.get("current", False),
      progress=d.get("progress", 0.0),
      allow_cellular=d.get("allow_cellular", True),
      azure_subdir=d.get("azure_subdir"),
    )

class AbortTransferException(Exception):
  pass

cur_upload_items: dict[int, UploadItem | None] = {}
cancelled_uploads: set[str] = set()
upload_queue: Queue[UploadItem] = queue.Queue()

class UploadQueueCache:
  """ Persists the upload queue in param "AzureUploadQueue". """
  PARAM_NAME = "AzureUploadQueue"

  @staticmethod
  def initialize(upload_queue_instance: Queue[UploadItem]) -> None:
    """ Load previously queued items from the param store. """
    global last_clear_time
    params = Params()
    try:
      upload_queue_json = params.get(UploadQueueCache.PARAM_NAME, encoding='utf-8') # Specify encoding
      if upload_queue_json is not None:
        loaded_count = 0
        items_data = json.loads(upload_queue_json)
        for item_dict in items_data:
          try:
              item = UploadItem.from_dict(item_dict)
              # Basic validation and reset state
              if item.path and item.id and item.azure_subdir:
                  item = replace(item, progress=0.0, current=False, retry_count=item.retry_count) # Keep retry count
                  upload_queue_instance.put(item)
                  loaded_count += 1
              else:
                  debug_print(f"Skipping invalid item from cache: {item_dict}")
          except (TypeError, KeyError) as e:
              debug_print(f"Error parsing item from cache: {item_dict}, Error: {e}")
              cloudlog.warning("Failed to parse item from AzureUploadQueue cache", item_dict=item_dict, error=str(e))

        debug_print(f"Initialized queue with {loaded_count} items from cache.")
      else:
        debug_print("No cached queue found.")
      last_clear_time = time.time()
    except json.JSONDecodeError:
      cloudlog.error("Failed to decode AzureUploadQueue JSON, clearing cache.")
      params.remove(UploadQueueCache.PARAM_NAME)
      last_clear_time = time.time() # Treat as cleared
    except Exception as e:
      cloudlog.exception("azure.UploadQueueCache.initialize.exception")
      params.remove(UploadQueueCache.PARAM_NAME) # Clear cache on generic init error too? Safer.
      last_clear_time = time.time() # Treat as cleared

  @staticmethod
  def cache(upload_queue_instance: Queue[UploadItem]) -> None:
    """ Save non-completed items back to the param store. """
    params = Params()
    items_to_cache = []
    try:
      # Add items currently being processed (if not finished/failed permanently)
      current_items_copy = dict(cur_upload_items) # Thread safe copy
      for item in current_items_copy.values():
          # Only cache if actively being processed or pending retry (progress != 1.0)
          if item is not None and item.progress < 1.0:
              items_to_cache.append(asdict(item))

      # Add items waiting in the queue
      with upload_queue_instance.mutex:
          queued_items = list(upload_queue_instance.queue)
      for item in queued_items:
          if item is not None and item.progress < 1.0:
              # Ensure it's not already added from cur_upload_items (by id)
              if not any(cached_item['id'] == item.id for cached_item in items_to_cache):
                  items_to_cache.append(asdict(item))

      if items_to_cache:
          debug_print(f"Caching {len(items_to_cache)} items to {UploadQueueCache.PARAM_NAME}")
          params.put(UploadQueueCache.PARAM_NAME, json.dumps(items_to_cache))
      else:
          # If nothing to cache, remove the param
          if params.check(UploadQueueCache.PARAM_NAME): # Check if param exists before removing
              debug_print(f"Queue and active uploads are empty/completed, removing {UploadQueueCache.PARAM_NAME}")
              params.remove(UploadQueueCache.PARAM_NAME)
          else:
              debug_print(f"Queue empty, cache param already removed or never existed.")

    except Exception:
      cloudlog.exception("azure.UploadQueueCache.cache.exception")

  @staticmethod
  def clear_cache() -> None:
    """ Explicitly remove the queue from the param store. """
    try:
        Params().remove(UploadQueueCache.PARAM_NAME)
        debug_print(f"Cleared cached queue param: {UploadQueueCache.PARAM_NAME}")
    except Exception:
        cloudlog.exception("azure.UploadQueueCache.clear_cache.exception")


# -------------------------------------------------------------------------------
# Upload Handler Thread - Using .raw as in original code
# -------------------------------------------------------------------------------
# --- Using the improved retry_upload from previous correction ---
def retry_upload(tid: int, end_event: threading.Event, increase_count: bool = True) -> None:
  """
  If an upload fails or is aborted, re-queue it (unless we've exceeded retry limits).
  Ensures task_done() is called for the failed/aborted attempt.
  """
  item = cur_upload_items.get(tid)
  if item is None:
    debug_print(f"Thread {tid}: No item found to retry (item might have been cleared).")
    return

  new_retry_count = item.retry_count + 1 if increase_count else item.retry_count

  # Mark task done for the failed attempt *before* requeue/max_retry logic
  try:
    upload_queue.task_done()
    debug_print(f"Thread {tid}: Marked task done for failed attempt of {item.id}")
  except ValueError:
    debug_print(f"Warning: task_done() called too many times before retry/max_retry for item {item.id}")
  except Exception as e:
      debug_print(f"Error calling task_done() before retry for {item.id}: {e}")
      cloudlog.exception("azure.upload_handler.retry.task_done_error")

  if new_retry_count > MAX_RETRY_COUNT:
    debug_print(f"\n[DEBUG] === Max Retries Reached (Thread {tid}) ===")
    debug_print(f"File: {item.path}")
    debug_print(f"Azure Subdir: {item.azure_subdir}")
    debug_print(f"Giving up after {item.retry_count} retries.")
    debug_print("=== Retry Aborted ===\n")
    cloudlog.event("azure.upload_handler.max_retries", item=asdict(item), error=True)
    # Mark as logically done for cache removal
    cur_upload_items[tid] = replace(item, progress=1.0, current=False)
    UploadQueueCache.cache(upload_queue)
    cur_upload_items[tid] = None
    return

  # Requeue the item
  debug_print(f"\n[DEBUG] === Retrying Upload (Thread {tid}) ===")
  debug_print(f"File: {item.path}")
  debug_print(f"Azure Subdir: {item.azure_subdir}")
  debug_print(f"Next retry count: {new_retry_count}")
  debug_print(f"Increase count: {increase_count}")

  requeued_item = replace(item, retry_count=new_retry_count, progress=0.0, current=False)
  upload_queue.put_nowait(requeued_item)
  UploadQueueCache.cache(upload_queue) # Update cache after requeue
  debug_print(f"Item {item.id} requeued successfully.")
  debug_print("=== Retry Queued ===\n")

  cur_upload_items[tid] = None # Clear current item *after* requeue

  debug_print(f"Thread {tid} waiting {RETRY_DELAY}s before next attempt...")
  interrupted = end_event.wait(RETRY_DELAY)
  if interrupted:
      debug_print(f"Thread {tid}: Retry delay interrupted by shutdown.")


def upload_handler(end_event: threading.Event) -> None:
  """
  Thread that pulls items off `upload_queue` and uploads them to Azure.
  Uses deviceState.networkType.raw for network type.
  """
  sm = messaging.SubMaster(['deviceState'])
  tid = threading.get_ident()
  debug_print(f"\n[DEBUG] === Upload Handler Started (Thread {tid}) ===")

  while not end_event.is_set():
    cur_upload_items[tid] = None # Clean state before getting item
    item = None # Define for finally block scope
    try:
      item = upload_queue.get(timeout=1)

      cur_upload_items[tid] = replace(item, current=True)
      debug_print(f"\n[DEBUG] === Processing Upload Item (Thread {tid}) ===")
      debug_print(f"Item ID: {item.id}")
      debug_print(f"File: {item.path}")
      # debug_print(f"Azure Subdir: {item.azure_subdir}") # Already logged in _do_upload
      debug_print(f"Retry count: {item.retry_count}")
      # debug_print(f"Allow cellular: {item.allow_cellular}") # Logged below if relevant
      # debug_queue_status() # Can be noisy

      if item.id in cancelled_uploads: # Should be empty normally
        debug_print(f"Item {item.id} was cancelled, skipping")
        cancelled_uploads.remove(item.id)
        cur_upload_items[tid] = replace(item, progress=1.0, current=False)
        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)
        continue

      # --- Network Check using .raw ---
      sm.update(0)
      if not sm.valid['deviceState']:
          debug_print(f"No valid deviceState message yet, deferring upload (Thread {tid})")
          retry_upload(tid, end_event, increase_count=False)
          continue

      metered = sm['deviceState'].networkMetered
      # --- Using .raw as in the original code ---
      network_type = sm['deviceState'].networkType.raw
      # --- End .raw usage ---

      debug_print(f"\n[DEBUG] === Network Status (Thread {tid}) ===")
      # log.capnp defines: none @0; wifi @1; cell* @2-5; ethernet @6; unknown @7;
      is_connected = network_type != 0 # 0 corresponds to 'none'
      debug_print(f"Connected: {is_connected} (Type: {network_type})") # Log the raw integer
      debug_print(f"Metered connection: {metered}")

      if not is_connected:
          debug_print("Network type is 'none' (0), deferring upload.")
          retry_upload(tid, end_event, increase_count=False)
          continue

      if metered and not item.allow_cellular:
        debug_print(f"Metered connection ({network_type=}, {metered=}) detected and cellular not allowed ({item.allow_cellular=}), deferring upload")
        retry_upload(tid, end_event, increase_count=False)
        continue
      # --- End Network Check ---

      # --- Upload Attempt ---
      try:
        fn = item.path
        file_size = 0
        # Get size just before logging/upload, handle if file vanished since queueing
        try:
          if not os.path.isfile(fn): # Re-check existence
               raise FileNotFoundError(f"Local file disappeared before upload: {fn}")
          file_size = os.path.getsize(fn)
          # debug_print(f"Local file size: {file_size} bytes") # Already logged in _do_upload
        except OSError as e:
          debug_print(f"Error getting file size for {fn} just before upload: {str(e)}")
          # If it's gone, FileNotFoundError will be raised above or by _do_upload_azure below
          pass # Size is just for logging, try upload anyway if error is not FileNotFoundError

        cloudlog.event("azure.upload_handler.upload_start",
                       fn=fn, sz=file_size, azure_subdir=item.azure_subdir,
                       network_type=network_type, # Log the raw integer
                       metered=metered,
                       retry_count=item.retry_count)

        _do_upload_azure(item) # This function now handles FileNotFoundError internally too

        # Mark success (progress 1.0)
        cur_upload_items[tid] = replace(item, progress=1.0, current=False) # Update state before logging/cache
        debug_print(f"\n[DEBUG] === Upload Success/Skipped (Thread {tid}) ===")
        debug_print(f"File: {fn}")
        # debug_print(f"Azure Subdir: {item.azure_subdir}") # Logged in _do_upload
        debug_print("=== Upload Complete ===\n")
        cloudlog.event("azure.upload_handler.success", fn=fn, sz=file_size, azure_subdir=item.azure_subdir,
                       network_type=network_type, # Log the raw integer
                       metered=metered)

        upload_queue.task_done() # Signal completion *after* success
        UploadQueueCache.cache(upload_queue) # Update cache on success

      except FileNotFoundError:
        # Handled if _do_upload_azure raises it, or if getsize failed above
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
        debug_print(f"Error Type: {type(e).__name__} - Details: {str(e)}")
        debug_print("Attempting retry...")
        debug_print("=== Error Complete ===\n")
        log_level = cloudlog.warning # Treat these as potentially transient
        log_level(f"azure.upload_handler.network_error", fn=fn, azure_subdir=item.azure_subdir,
                  network_type=network_type, error_type=type(e).__name__, error=str(e), exc_info=DEBUG)
        retry_upload(tid, end_event) # Handles task_done for failed attempt

      except AbortTransferException: # Placeholder
        debug_print(f"\n[DEBUG] === Upload Aborted by Request (Thread {tid}) ===")
        cloudlog.event("azure.upload_handler.abort", fn=item.path, azure_subdir=item.azure_subdir,
                       network_type=network_type, metered=metered)
        retry_upload(tid, end_event, increase_count=False) # Handles task_done

      except Exception as e:
        # Unexpected errors during upload process
        debug_print(f"\n[DEBUG] === Unexpected Upload Error (Thread {tid}) ===")
        debug_print(f"File: {item.path if item else 'N/A'}")
        debug_print(f"Error Type: {type(e).__name__} - Details: {str(e)}")
        debug_print("Attempting retry...")
        debug_print("=== Error Complete ===\n")
        cloudlog.exception(f"azure.upload_handler.azure_upload_fail for {item.azure_subdir if item else 'N/A'}/{os.path.basename(item.path if item else 'N/A')}",
                           network_type=network_type if 'network_type' in locals() else 'unknown')
        retry_upload(tid, end_event) # Handles task_done

    except queue.Empty:
      continue # Loop and wait again

    except Exception as e:
      # Error in the handler loop itself (e.g., queue.get, sm update)
      debug_print(f"\n[DEBUG] === Handler Loop Error (Thread {tid}) ===")
      debug_print(f"Error Type: {type(e).__name__} - Details: {str(e)}")
      debug_print("=== Error Complete ===\n")
      cloudlog.exception("azure.upload_handler.outer_exception")
      # If item was fetched but error occurred before try-block for upload:
      if item is not None and cur_upload_items.get(tid) is not None:
           debug_print(f"Error occurred after fetching item {item.id} but before upload block. Attempting auto-retry.")
           # Need to call task_done for the fetched item before retrying
           retry_upload(tid, end_event, increase_count=False) # Retry without increment count
      else:
          # Error likely before item fetch, just wait
          interrupted = end_event.wait(5)
          if interrupted:
              debug_print(f"Thread {tid}: Outer loop wait interrupted by shutdown.")
    finally:
      # Ensure thread state is cleared if not processing an item,
      # especially if an exception happened that wasn't caught by retry_upload.
      if cur_upload_items.get(tid) is not None:
          # This case should be rare now with retry_upload handling task_done and state clearing.
          # It might occur if AbortTransferException happened outside the inner try block.
          debug_print(f"Thread {tid}: Clearing potentially stale item state in finally block.")
          active_item = cur_upload_items.get(tid)
          if active_item: # Check again before using item id
             try:
                 # Try to mark task done, might fail if already done by retry_upload
                 upload_queue.task_done()
                 debug_print(f"Thread {tid}: Called task_done in final cleanup for {active_item.id}")
             except ValueError:
                 pass # Expected if already done
             except Exception as final_e:
                 debug_print(f"Error during final task_done cleanup for {active_item.id}: {final_e}")
                 cloudlog.exception("azure.upload_handler.finally.task_done_error")
          cur_upload_items[tid] = None


  debug_print(f"Upload handler thread {tid} exiting.")


# -------------------------------------------------------------------------------
# Automatic RLog Finder (realdata_handler - keeping previous corrected version)
# -------------------------------------------------------------------------------
def _scan_and_queue_realdata(base_path: str, age_limit_seconds: float, processed_dirs: set[str]) -> int:
  """
  Scans the base_path for recent directories and queues relevant log files.
  Updates processed_dirs with the directories processed in this scan.
  Returns the number of new files queued.
  """
  current_time = time.time()
  debug_print(f"Scanning {base_path} for directories created within the last {age_limit_seconds / 3600:.1f} hours...")
  one_day_ago_ts = current_time - age_limit_seconds
  found_count = 0
  queued_count = 0
  # Note: processed_dirs is passed by reference (mutable set) and updated directly

  if not os.path.isdir(base_path):
      debug_print(f"Base path {base_path} not found, skipping scan.")
      cloudlog.error(f"Realdata base path not found: {base_path}")
      return 0 # Return 0 queued

  try:
    for subdir in os.listdir(base_path):
      subdir_path = os.path.join(base_path, subdir)
      if not os.path.isdir(subdir_path):
        continue
      if subdir in processed_dirs: # Avoid processing same dir multiple times
          continue

      try:
        stat_info = os.stat(subdir_path)
        creation_time_ts = stat_info.st_ctime
      except OSError as e:
        debug_print(f"Could not stat directory {subdir_path}: {e}")
        continue

      # Filter by CREATION time
      if creation_time_ts < one_day_ago_ts:
        continue

      # --- Start processing this directory ---
      found_count += 1
      creation_dt = datetime.fromtimestamp(creation_time_ts)
      formatted_date_time = creation_dt.strftime("%m%d%y_%H%M")
      azure_target_subdir_new_format = f"{formatted_date_time}--{subdir}"
      segment_name = subdir

      # --- Check and Rename Logic ---
      conn_str = get_azure_connection_string()
      rename_performed_or_exists = False
      if conn_str:
          try:
              azure_base_log_path = AZURE_BASE_DIR
              existing_azure_dirs = list_azure_directories(conn_str, AZURE_SHARE_NAME, azure_base_log_path)
              old_format_dir_to_rename = None
              for azure_dir in existing_azure_dirs:
                  if '--' in azure_dir:
                      _, existing_segment = azure_dir.split('--', 1)
                      if existing_segment == segment_name:
                          full_old_path = f"{azure_base_log_path}/{azure_dir}"
                          full_new_path = f"{azure_base_log_path}/{azure_target_subdir_new_format}"
                          if full_old_path != full_new_path:
                              old_format_dir_to_rename = full_old_path
                              break
                          else:
                              debug_print(f"Directory {full_new_path} already exists with new format, skipping.")
                              rename_performed_or_exists = True
                              break
              if old_format_dir_to_rename and not rename_performed_or_exists:
                  full_new_path = f"{azure_base_log_path}/{azure_target_subdir_new_format}"
                  debug_print(f"Found old format directory '{old_format_dir_to_rename}', attempting rename to '{full_new_path}'")
                  if rename_azure_directory(conn_str, AZURE_SHARE_NAME, old_format_dir_to_rename, full_new_path):
                      cloudlog.event("azure.realdata_handler.renamed", old_dir=old_format_dir_to_rename, new_dir=full_new_path)
                      rename_performed_or_exists = True
                  else:
                      cloudlog.warning("azure.realdata_handler.rename_failed", old_dir=old_format_dir_to_rename, new_dir=full_new_path)
          except Exception as e:
              cloudlog.exception("azure.realdata_handler.rename_check_exception", segment=segment_name)
              debug_print(f"Error during Azure rename check for {segment_name}: {e}")
      # --- End Check and Rename Logic ---

      # Mark directory as processed regardless of rename outcome to avoid re-processing locally
      processed_dirs.add(subdir)


      if rename_performed_or_exists:
          continue # Skip queueing if renamed or already exists remotely

      # --- Original Queueing Logic ---
      files_to_upload = ['rlog', 'qlog', 'qcamera.ts']
      for filename in files_to_upload:
          local_path = os.path.join(subdir_path, filename)
          if not os.path.isfile(local_path):
              continue

          upload_id = f"azure|{subdir}|{filename}"
          is_active_or_queued = False
          current_items_copy = dict(cur_upload_items)
          if any(ci and ci.id == upload_id for ci in current_items_copy.values()):
              is_active_or_queued = True
          if not is_active_or_queued:
              with upload_queue.mutex:
                  if any(qi and qi.id == upload_id for qi in list(upload_queue.queue)):
                      is_active_or_queued = True

          if is_active_or_queued:
              continue

          item = UploadItem(
              path=local_path,
              created_at=int(creation_time_ts * 1000),
              id=upload_id,
              azure_subdir=azure_target_subdir_new_format,
              allow_cellular=True
          )
          debug_print(f"Queueing item: {item.id} -> Azure: {azure_target_subdir_new_format}/{filename}")
          upload_queue.put_nowait(item)
          queued_count += 1

    debug_print(f"Scan complete. Found {found_count} recent directories locally, queued {queued_count} new file uploads.")
    # Cache once after a full scan cycle if items were added
    if queued_count > 0:
         UploadQueueCache.cache(upload_queue)

  except Exception as e:
    cloudlog.exception("azure.realdata_handler.scan_exception")
    debug_print(f"Error during realdata scan: {e}")

  return queued_count


def realdata_handler(end_event: threading.Event) -> None:
  """
  Scans /data/media/0/realdata/ for subdirectories CREATED within 24 hours.
  Queues 'rlog', 'qlog', 'qcamera.ts'. Performs hourly clear/re-scan.
  Performs an initial scan immediately on startup.
  """
  global last_clear_time
  base_path = "/data/media/0/realdata"
  age_limit_seconds = 24 * 3600
  scan_interval = 300 # Scan every 5 minutes
  processed_dirs = set() # Keep track of dirs processed across scans

  # --- Perform initial scan ---
  cloudlog.info("Performing initial realdata scan...")
  debug_print("Performing initial realdata scan...")
  try:
    initial_queued_count = _scan_and_queue_realdata(base_path, age_limit_seconds, processed_dirs)
    cloudlog.info(f"Initial scan queued {initial_queued_count} files.")
    debug_print(f"Initial scan queued {initial_queued_count} files.")
    UploadQueueCache.cache(upload_queue) # Cache after initial scan
  except Exception as e:
    cloudlog.exception("azure.realdata_handler.initial_scan_exception")
    debug_print(f"Error during initial realdata scan: {e}")
  # --- End initial scan ---

  while not end_event.is_set():
    current_time = time.time()

    # --- Hourly Queue Clear ---
    if current_time - last_clear_time >= HOURLY_CLEAR_INTERVAL:
      cloudlog.info("Performing hourly Azure queue clear and preparing for re-scan.")
      debug_print("Performing hourly Azure queue clear and preparing for re-scan.")
      try:
        UploadQueueCache.clear_cache()
        drained_count = 0
        with upload_queue.mutex:
            while not upload_queue.empty():
                try:
                    item = upload_queue.get_nowait()
                    upload_queue.task_done()
                    drained_count += 1
                except queue.Empty:
                    break
        processed_dirs = set() # Reset processed dirs after clear
        debug_print(f"Cleared in-memory upload_queue (drained {drained_count} items) and reset processed_dirs set.")
        last_clear_time = current_time
        cloudlog.info("Hourly Azure queue clear complete. Starting re-scan.")
        debug_print("Hourly Azure queue clear complete. Starting re-scan.")
      except Exception as e:
        cloudlog.exception("azure.realdata_handler.hourly_clear.exception")
        debug_print(f"Hourly clear failed: {e}. Retrying next cycle.")

    # --- Periodic Scan for Recent Directories ---
    # The scan function now handles its own try/except block and logging
    _scan_and_queue_realdata(base_path, age_limit_seconds, processed_dirs)

    # Wait before next scan or clear check
    end_event.wait(scan_interval)

  debug_print("Realdata handler thread exiting.")


# -------------------------------------------------------------------------------
# Entry Point (Keeping previous corrected version)
# -------------------------------------------------------------------------------
def main():
  """ Initializes queue, starts upload and scanner threads, waits for termination. """
  cloudlog.info("Starting Azure upload service")
  debug_print("Starting Azure upload service")
  try:
    pass # Affinity setting depends on system resources/policy
  except Exception:
    cloudlog.exception("failed to set core affinity")
    debug_print("Failed to set core affinity")

  if ShareFileClient is None or ShareDirectoryClient is None:
      cloudlog.error("Azure SDK not found. Service cannot run.")
      print("Azure SDK not found. Service cannot run. Please `pip install azure-storage-file-share`", file=sys.stderr)

      return

  # Initialize queue from stored cache
  UploadQueueCache.initialize(upload_queue)
  debug_print(f"Initial queue size after load: {upload_queue.qsize()}")
  debug_queue_status()

  end_event = threading.Event()
  threads = []

  for i in range(HANDLER_THREADS):
      t = threading.Thread(target=upload_handler, args=(end_event,), name=f'upload_handler_{i}')
      # Make threads daemons so they exit automatically if main thread exits unexpectedly
      # Although we do explicit join later, this is a safety measure.
      t.daemon = True
      t.start()
      threads.append(t)
      cur_upload_items[t.ident] = None # Initialize state

  realdata_thread = threading.Thread(target=realdata_handler, args=(end_event,), name='realdata_handler')
  realdata_thread.daemon = True
  realdata_thread.start()
  threads.append(realdata_thread)

  cloudlog.info(f"Azure upload service started with {HANDLER_THREADS} upload thread(s).")
  debug_print(f"Started {len(threads)} threads.")

  try:
    # Keep main thread alive while workers run
    while not end_event.is_set():
        # Check if worker threads are alive periodically?
        all_alive = all(t.is_alive() for t in threads)
        if not all_alive:
            cloudlog.error("One or more Azure worker threads have died unexpectedly.")
            debug_print("Error: One or more worker threads have died!")
            # Decide on action: restart threads? exit?
            end_event.set() # Signal shutdown
            break
        time.sleep(10) # Check thread health every 10s

  except KeyboardInterrupt:
    cloudlog.info("Keyboard interrupt received, shutting down Azure service.")
    debug_print("Received keyboard interrupt, shutting down...")
    end_event.set() # Signal threads first
  finally:
    if not end_event.is_set(): # Ensure event is set if loop exited for other reasons
        end_event.set()
    cloudlog.info("Waiting for threads to finish...")
    debug_print("Waiting for threads to join...")
    shutdown_timeout = RETRY_DELAY + 5 # Give threads time to finish current task + retry delay
    for t in threads:
      try:
          t.join(timeout=shutdown_timeout)
          if t.is_alive():
              cloudlog.warning(f"Thread {t.name} did not exit cleanly after {shutdown_timeout}s.")
              debug_print(f"Warning: Thread {t.name} did not join!")
      except Exception as e:
          cloudlog.error(f"Error joining thread {t.name}: {e}")
          debug_print(f"Error joining thread {t.name}: {e}")

    debug_print("Performing final queue cache before exit.")
    UploadQueueCache.cache(upload_queue)

    cloudlog.info("Azure upload service shutdown complete.")
    debug_print("Service shutdown complete")

if __name__ == "__main__":
  # Add necessary imports if missing at top-level for dataclasses field
  from dataclasses import field
  main()
