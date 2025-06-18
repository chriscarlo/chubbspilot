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
import tarfile
import shutil
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from functools import partial
from queue import Queue
from typing import cast
import concurrent.futures

# OpenPilot / system imports
import cereal.messaging as messaging
from cereal import log               # Ensure log is imported for log.DeviceState.NetworkType
from common.file_helpers import CallbackReader
from common.params import Params
from common.realtime import set_core_affinity
from common.swaglog import cloudlog

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

try:
    import zstandard as zstd
except ImportError:
    zstd = None
    cloudlog.error(
        "zstandard library not found – cannot create .tar.zst archives. "
        "Run  `pip install zstandard`  or archives will fail."
    )

# Constants
HANDLER_THREADS = 1
MAX_RETRY_COUNT = 5
RETRY_DELAY = 10
HOURLY_CLEAR_INTERVAL = 3600  # 1 hour in seconds

# Azure File Share config
AZURE_SHARE_NAME = "chauffeurlogs"
AZURE_BASE_DIR   = "rlogs"
BASE_REALDATA_PATH = "/data/media/0/realdata"
STAGING_ARCHIVE_DIR = os.path.join(BASE_REALDATA_PATH, "..", "rlog_staging_archives") # e.g., /data/media/0/rlog_staging_archives

# Debug flag - only True when running directly
DEBUG = __name__ == "__main__"

# Global state
last_clear_time = 0  # Timestamp of the last queue clear

def debug_print(*args, **kwargs):
  if DEBUG:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [DEBUG]", *args, **kwargs)

def debug_queue_status():
  """Print current status of upload queue and active uploads"""
  if not DEBUG:
    return
  active_count = len([x for x in cur_upload_items.values() if x is not None])
  with upload_queue.mutex:
      queue_size = upload_queue.qsize()
  print("\n[DEBUG] === Queue Status ===")
  print(f"Active uploads: {active_count}")
  print(f"Queue size: {queue_size}")
  current_items_copy = dict(cur_upload_items)
  for tid, item in current_items_copy.items():
    if item is not None:
      print(f"  Thread {tid}: {item.path} -> {item.azure_subdir} (progress: {item.progress}, retries: {item.retry_count})")
  print("Next 3 queued items:")
  with upload_queue.mutex:
    items = list(upload_queue.queue)[:3]
  for item in items:
    print(f"  {item.path} -> {item.azure_subdir} (retries: {item.retry_count})")
  print("========================\n")


# -------------------------------------------------------------------------------
# Azure Connection / Upload
# -------------------------------------------------------------------------------
def get_azure_connection_string() -> str:
  """ Reads the Azure connection string from /persist/azure_conn_string """
  try:
    if not hasattr(get_azure_connection_string, "conn_str_cache"):
      with open("/persist/azure_conn_string", "r") as f:
        conn_str = f.read().strip()
        get_azure_connection_string.conn_str_cache = conn_str
        debug_print(f"Successfully read Azure connection string (length: {len(conn_str)})")
    return get_azure_connection_string.conn_str_cache
  except Exception as e:
    debug_print(f"Failed to read Azure connection string: {str(e)}")
    cloudlog.exception("azure.get_azure_connection_string.exception")
    get_azure_connection_string.conn_str_cache = ""
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
        raise

def ensure_azure_directory_exists(conn_str, share_name, azure_path):
    if ShareDirectoryClient is None or ResourceExistsError is None:
        raise Exception("Azure SDK not available for directory creation.")
    parts = azure_path.strip('/').split('/')
    current_path = ""
    for part in parts:
        if not part: continue
        current_path = f"{current_path}/{part}" if current_path else part
        try:
            dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, current_path)
            dir_client.create_directory()
            debug_print(f"Ensured Azure directory exists: {current_path}")
        except ResourceExistsError:
            pass
        except Exception as e:
            debug_print(f"Error creating/checking directory {current_path}: {str(e)}")
            cloudlog.exception(f"Azure ensure_azure_directory_exists error for {current_path}", exc_info=e)
            raise

def list_azure_directories(conn_str, share_name, dir_path):
    if ShareDirectoryClient is None:
        raise Exception("Azure SDK not available for listing directories.")
    try:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, dir_path)
        return [item['name'] for item in dir_client.list_directories_and_files() if item['is_directory']]
    except ResourceNotFoundError:
        debug_print(f"Azure list directories: Path not found - {dir_path}")
        return []
    except Exception as e:
        debug_print(f"Azure list directories: Error listing {dir_path} - {str(e)}")
        cloudlog.warning(f"Azure directory listing failed for {dir_path}: {str(e)}")
        raise

def rename_azure_directory(conn_str, share_name, old_dir_path, new_dir_path):
    if ShareDirectoryClient is None:
        raise Exception("Azure SDK not available for renaming directories.")
    try:
        dir_client = ShareDirectoryClient.from_connection_string(conn_str, share_name, old_dir_path)
        new_parent_path = os.path.dirname(new_dir_path)
        if new_parent_path and new_parent_path != '.':
             ensure_azure_directory_exists(conn_str, share_name, new_parent_path)
        debug_print(f"Attempting to rename Azure directory from '{old_dir_path}' to '{new_dir_path}'")
        dir_client.rename_directory(new_dir_path)
        debug_print(f"Successfully renamed Azure directory: '{old_dir_path}' -> '{new_dir_path}'")
        return True
    except ResourceNotFoundError:
        debug_print(f"Azure rename directory: Source directory not found - {old_dir_path}")
        return False
    except ResourceExistsError:
        debug_print(f"Azure rename directory: Target directory already exists - {new_dir_path}")
        return True
    except Exception as e:
        debug_print(f"Azure rename directory: Error renaming {old_dir_path} to {new_dir_path} - {str(e)}")
        cloudlog.warning(f"Azure directory rename failed for {old_dir_path} -> {new_dir_path}: {str(e)}")
        raise

def _do_upload_azure(upload_item: UploadItem):
  """ Upload a file to Azure File Share. Creates target directory. Skips if exists. """
  conn_str = get_azure_connection_string()
  if not conn_str or ShareDirectoryClient is None or ShareFileClient is None:
    debug_print("Azure upload not configured - missing connection string or SDK")
    raise Exception("Azure upload not configured (missing connection string or azure-storage-file-share).")

  local_path = upload_item.path
  filename = os.path.basename(local_path)
  # Determine target directory on Azure; if azure_subdir given, nest it, otherwise root under base
  if upload_item.azure_subdir:
      azure_target_dir = f"{AZURE_BASE_DIR}/{upload_item.azure_subdir}"
  else:
      azure_target_dir = AZURE_BASE_DIR

  debug_print(f"\n[DEBUG] === Starting Azure Upload Attempt ===")
  debug_print(f"Local path: {local_path}")
  debug_print(f"Target Azure directory: {azure_target_dir}")
  debug_print(f"Target Azure filename: {filename}")

  try:
    file_size = os.path.getsize(local_path)
    debug_print(f"Local file size: {file_size} bytes")
  except FileNotFoundError:
    debug_print(f"File not found locally: {local_path}")
    raise
  except OSError as e:
    debug_print(f"Error stating local file {local_path}: {e}")
    raise

  try:
    debug_print("Ensuring Azure directory exists...")
    ensure_azure_directory_exists(conn_str, AZURE_SHARE_NAME, azure_target_dir)

    if azure_file_exists(conn_str, AZURE_SHARE_NAME, azure_target_dir, filename):
      debug_print(f"File already exists on Azure, skipping upload: {azure_target_dir}/{filename}")
      return

    debug_print("Creating Azure file client for upload...")
    dir_client = ShareDirectoryClient.from_connection_string(
      conn_str, AZURE_SHARE_NAME, azure_target_dir
    )
    file_client = dir_client.get_file_client(filename)

    debug_print("Starting file upload...")
    with open(local_path, "rb") as f:
        file_client.upload_file(f, timeout=600)
    debug_print(f"File upload completed successfully: {azure_target_dir}/{filename}")
    debug_print("=== Azure Upload Attempt Complete ===\n")

    cloudlog.event("azure._do_upload_azure.success",
                   subdir=upload_item.azure_subdir or "",
                   local_path=local_path,
                   azure_path=f"{azure_target_dir}/{filename}")
  except (ResourceNotFoundError, FileNotFoundError) as e:
      if isinstance(e, FileNotFoundError):
          raise
      debug_print(f"Azure resource not found during upload op for {azure_target_dir}/{filename}: {str(e)}")
      cloudlog.warning(f"Azure ResourceNotFoundError during upload op for {azure_target_dir}/{filename}: {e}")
      raise
  except ServiceResponseError as e:
      debug_print(f"Azure ServiceResponseError during upload for {azure_target_dir}/{filename}: {str(e)}")
      cloudlog.warning(f"Azure ServiceResponseError for {azure_target_dir}/{filename}: {e}")
      raise
  except Exception as e:
    debug_print(f"Error during Azure upload process for {azure_target_dir}/{filename}: {str(e)}")
    cloudlog.exception(f"azure._do_upload_azure exception for {azure_target_dir}/{filename}", exc_info=e)
    raise


# -------------------------------------------------------------------------------
# Upload Items/Queue
# -------------------------------------------------------------------------------
@dataclass
class UploadItem:
  path: str
  created_at: int
  id: str | None
  url: str = ""
  headers: dict[str, str] = field(default_factory=dict)
  retry_count: int = 0
  current: bool = False
  progress: float = 0.0
  allow_cellular: bool = True
  azure_subdir: str | None = None
  original_segment_to_delete: str | None = None # Path to the original segment dir to delete after archive upload

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
      original_segment_to_delete=d.get("original_segment_to_delete"),
    )

class AbortTransferException(Exception):
  pass

cur_upload_items: dict[int, UploadItem | None] = {}
cancelled_uploads: set[str] = set()
upload_queue: Queue[UploadItem] = queue.Queue()

class UploadQueueCache:
  PARAM_NAME = "AzureUploadQueue"

  @staticmethod
  def initialize(upload_queue_instance: Queue[UploadItem]) -> None:
    global last_clear_time
    params = Params()
    try:
      upload_queue_json = params.get(UploadQueueCache.PARAM_NAME, encoding='utf-8')
      if upload_queue_json is not None:
        loaded_count = 0
        items_data = json.loads(upload_queue_json)
        for item_dict in items_data:
          try:
              item = UploadItem.from_dict(item_dict)
              if item.path and item.id:
                  item = replace(item, progress=0.0, current=False, retry_count=item.retry_count)
                  upload_queue_instance.put(item)
                  loaded_count += 1
          except (TypeError, KeyError) as e:
              debug_print(f"Error parsing item from cache: {item_dict}, Error: {e}")
              cloudlog.warning("Failed to parse item from AzureUploadQueue cache",
                               item_dict=item_dict, error=str(e))
        debug_print(f"Initialized queue with {loaded_count} items from cache.")
      else:
        debug_print("No cached queue found.")
      last_clear_time = time.time()
    except json.JSONDecodeError:
      cloudlog.error("Failed to decode AzureUploadQueue JSON, clearing cache.")
      params.remove(UploadQueueCache.PARAM_NAME)
      last_clear_time = time.time()
    except Exception as e:
      cloudlog.exception("azure.UploadQueueCache.initialize.exception")
      params.remove(UploadQueueCache.PARAM_NAME)
      last_clear_time = time.time()

  @staticmethod
  def cache(upload_queue_instance: Queue[UploadItem]) -> None:
    params = Params()
    items_to_cache = []
    try:
      current_items_copy = dict(cur_upload_items)
      for item in current_items_copy.values():
          if item is not None and item.progress < 1.0:
              items_to_cache.append(asdict(item))

      with upload_queue_instance.mutex:
          queued_items = list(upload_queue_instance.queue)
      for item in queued_items:
          if item is not None and item.progress < 1.0:
              if not any(cached_item['id'] == item.id for cached_item in items_to_cache):
                  items_to_cache.append(asdict(item))

      if items_to_cache:
          debug_print(f"Caching {len(items_to_cache)} items to {UploadQueueCache.PARAM_NAME}")
          params.put(UploadQueueCache.PARAM_NAME, json.dumps(items_to_cache))
      else:
          if params.check(UploadQueueCache.PARAM_NAME):
              debug_print(f"Queue empty/completed, removing {UploadQueueCache.PARAM_NAME}")
              params.remove(UploadQueueCache.PARAM_NAME)
          else:
              debug_print("Queue empty, no cache to remove.")
    except Exception:
      cloudlog.exception("azure.UploadQueueCache.cache.exception")

  @staticmethod
  def clear_cache() -> None:
    try:
        Params().remove(UploadQueueCache.PARAM_NAME)
        debug_print(f"Cleared cached queue param: {UploadQueueCache.PARAM_NAME}")
    except Exception:
        cloudlog.exception("azure.UploadQueueCache.clear_cache.exception")


# -------------------------------------------------------------------------------
# Upload Handler Thread
# -------------------------------------------------------------------------------
def retry_upload(tid: int, end_event: threading.Event, increase_count: bool = True) -> None:
  item = cur_upload_items.get(tid)
  if item is None:
    debug_print(f"Thread {tid}: No item found to retry.")
    return

  new_retry_count = item.retry_count + 1 if increase_count else item.retry_count

  try:
    upload_queue.task_done()
    debug_print(f"Thread {tid}: Marked task done for retry of {item.id}")
  except Exception as e:
    debug_print(f"Warning calling task_done before retry: {e}")

  if new_retry_count > MAX_RETRY_COUNT:
    debug_print(f"Thread {tid}: Max retries reached for {item.path}. Giving up.")
    cloudlog.event("azure.upload_handler.max_retries", item=asdict(item), error=True)
    cur_upload_items[tid] = replace(item, progress=1.0, current=False)
    UploadQueueCache.cache(upload_queue)
    cur_upload_items[tid] = None
    return

  debug_print(f"Thread {tid}: Retrying upload for {item.path} (retry {new_retry_count})")
  requeued_item = replace(item, retry_count=new_retry_count, progress=0.0, current=False)
  upload_queue.put_nowait(requeued_item)
  UploadQueueCache.cache(upload_queue)
  cur_upload_items[tid] = None

  interrupted = end_event.wait(RETRY_DELAY)
  if interrupted:
      debug_print(f"Thread {tid}: Retry delayed interrupted by shutdown.")

def upload_handler(end_event: threading.Event) -> None:
  sm = messaging.SubMaster(['deviceState'])
  tid = threading.get_ident()
  debug_print(f"Upload handler started (Thread {tid})")

  while not end_event.is_set():
    cur_upload_items[tid] = None
    item = None
    try:
      item = upload_queue.get(timeout=1)
      cur_upload_items[tid] = replace(item, current=True)
      debug_print(f"Processing upload item: {item.id} -> {item.path}")

      if item.id in cancelled_uploads:
        cancelled_uploads.remove(item.id)
        cur_upload_items[tid] = replace(item, progress=1.0, current=False)
        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)
        continue

      sm.update(0)
      if not sm.valid['deviceState']:
        retry_upload(tid, end_event, increase_count=False)
        continue

      metered = sm['deviceState'].networkMetered
      network_type = sm['deviceState'].networkType.raw

      is_connected = network_type != 0
      if not is_connected or (metered and not item.allow_cellular):
        retry_upload(tid, end_event, increase_count=False)
        continue

      try:
        fn = item.path
        try:
          if not os.path.isfile(fn):
             raise FileNotFoundError(f"{fn} disappeared")
          file_size = os.path.getsize(fn)
        except:
          file_size = 0

        cloudlog.event("azure.upload_handler.upload_start",
                       fn=fn, sz=file_size,
                       azure_subdir=item.azure_subdir or "",
                       network_type=network_type, metered=metered,
                       retry_count=item.retry_count)

        _do_upload_azure(item)

        cur_upload_items[tid] = replace(item, progress=1.0, current=False)
        cloudlog.event("azure.upload_handler.success",
                       fn=fn, sz=file_size,
                       azure_subdir=item.azure_subdir or "",
                       network_type=network_type, metered=metered)

        # --- Start Deletion Logic ---
        try:
          debug_print(f"Attempting to delete uploaded archive file: {item.path}")
          os.remove(item.path) # Delete the archive from staging/temp location
          debug_print(f"Deleted archive file: {item.path}")

          if item.original_segment_to_delete:
            # Ensure the path is a directory and exists before attempting to delete
            if os.path.isdir(item.original_segment_to_delete):
              debug_print(f"Attempting to delete original segment directory: {item.original_segment_to_delete}")
              shutil.rmtree(item.original_segment_to_delete)
              debug_print(f"Deleted original segment directory: {item.original_segment_to_delete}")
              cloudlog.event("azure.upload_handler.cleanup_success",
                             archive_path=item.path, source_dir=item.original_segment_to_delete)
            else:
              debug_print(f"Original segment directory not found or already deleted: {item.original_segment_to_delete}")
              cloudlog.warning("azure.upload_handler.cleanup_skip_source_dir_not_found",
                               archive_path=item.path, source_dir=item.original_segment_to_delete)
          elif item.id and "archive" in item.id: # Heuristic for archive items that might be missing the new field (e.g. from old cache)
            cloudlog.warning("azure.upload_handler.cleanup_missing_original_segment_path",
                             item_id=item.id, archive_path=item.path)
            debug_print(f"No original_segment_to_delete path for item: {item.id}, archive: {item.path}")

        except OSError as e:
          debug_print(f"Error deleting local files after upload: {e}")
          cloudlog.exception("azure.upload_handler.cleanup_error",
                             archive_path=item.path,
                             source_dir=item.original_segment_to_delete or "N/A",
                             error=str(e))
        # --- End Deletion Logic ---

        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)

      except FileNotFoundError:
        cloudlog.event("azure.upload_handler.not_found",
                       fn=item.path, azure_subdir=item.azure_subdir or "")
        cur_upload_items[tid] = replace(item, progress=1.0, current=False)
        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)

      except (ConnectionError, TimeoutError, ServiceResponseError,
              socket.timeout, ResourceNotFoundError) as e:
        cloudlog.warning("azure.upload_handler.network_error",
                         fn=item.path, azure_subdir=item.azure_subdir or "",
                         network_type=network_type, error=str(e))
        retry_upload(tid, end_event)

      except AbortTransferException:
        cloudlog.event("azure.upload_handler.abort",
                       fn=item.path, azure_subdir=item.azure_subdir or "",
                       network_type=network_type, metered=metered)
        retry_upload(tid, end_event, increase_count=False)

      except Exception as e:
        cloudlog.exception("azure.upload_handler.azure_upload_fail",
                           network_type=network_type)
        retry_upload(tid, end_event)

    except queue.Empty:
      continue

    except Exception:
      cloudlog.exception("azure.upload_handler.outer_exception")
      if item is not None and cur_upload_items.get(tid) is not None:
        retry_upload(tid, end_event, increase_count=False)
      else:
        end_event.wait(5)

    finally:
      if cur_upload_items.get(tid) is not None:
        try:
          upload_queue.task_done()
        except:
          pass
        cur_upload_items[tid] = None

  debug_print(f"Upload handler thread {tid} exiting.")


# -------------------------------------------------------------------------------
# Automatic RLog Finder (realdata_handler)
# -------------------------------------------------------------------------------
def _compress_segment_and_queue_on_cpu3(subdir_path: str, segment_name: str, formatted_date_time: str, creation_time_ts: float):
    """
    Compresses a single segment to .tar.zst, pins to CPU3, and queues for upload.
    """
    try:
        os.sched_setaffinity(0, {3})  # Pin this thread to CPU core 3
        debug_print(f"Compression thread for {segment_name} now running on CPU {os.sched_getaffinity(0)}")
    except Exception as e:
        cloudlog.warning(f"Failed to set CPU affinity for compression of {segment_name}: {e}")
        debug_print(f"Warning: Failed to set CPU affinity for {segment_name}: {e}")

    if zstd is None:
        debug_print(f"zstandard library not found, cannot create archive for {segment_name}. Skipping.")
        cloudlog.warning(f"zstd not found, skipping archive creation for {segment_name}")
        return

    archive_name = f"{formatted_date_time}--{segment_name}.tar.zst"
    archive_filepath_in_staging = os.path.join(STAGING_ARCHIVE_DIR, archive_name)

    try:
        files_added_count = 0
        with open(archive_filepath_in_staging, "wb") as raw_f:
            cctx = zstd.ZstdCompressor(level=3)
            with cctx.stream_writer(raw_f) as zstd_f:
                with tarfile.open(fileobj=zstd_f, mode="w|") as tar:
                    for fname in ['rlog', 'qlog', 'qcamera.ts']:
                        fpath = os.path.join(subdir_path, fname)
                        if os.path.isfile(fpath):
                            tar.add(fpath, arcname=fname)
                            files_added_count += 1

        if files_added_count == 0:
            debug_print(f"No files found for archive {archive_filepath_in_staging}, removing empty archive.")
            if os.path.exists(archive_filepath_in_staging):
                os.remove(archive_filepath_in_staging)
            return

        debug_print(f"Created archive for upload: {archive_filepath_in_staging} (processed by thread {threading.get_ident()})")

        upload_id = f"azure|{segment_name}|archive"
        item = UploadItem(
            path=archive_filepath_in_staging,
            created_at=int(creation_time_ts * 1000),
            id=upload_id,
            azure_subdir=None,
            allow_cellular=True,
            original_segment_to_delete=subdir_path
        )
        debug_print(f"Queueing archive item from compression thread: {item.id} (Path: {item.path}) -> Azure: {AZURE_BASE_DIR}/{archive_name}")
        upload_queue.put_nowait(item)
        # Note: UploadQueueCache.cache() is called by the main realdata_handler loop

    except (tarfile.TarError, zstd.ZstdError, OSError) as e:
        debug_print(f"Failed to create archive {archive_filepath_in_staging} in compression thread: {e}")
        cloudlog.exception(f"Failed to create archive {archive_name} in {STAGING_ARCHIVE_DIR} (compression_thread)", error=str(e))
        try:
            if os.path.exists(archive_filepath_in_staging):
                os.remove(archive_filepath_in_staging)
        except OSError:
            pass # Ignore cleanup error
    except Exception as e:
        debug_print(f"Unexpected error in compression thread for {segment_name}: {e}")
        cloudlog.exception(f"Unexpected error in _compress_segment_and_queue_on_cpu3 for {segment_name}", error=str(e))

def _scan_and_queue_realdata(base_path: str, age_limit_seconds: float, processed_dirs: set[str], sm: messaging.SubMaster, compression_executor: concurrent.futures.ThreadPoolExecutor) -> None:
  current_time = time.time()
  one_day_ago_ts = current_time - age_limit_seconds
  found_count = 0

  if not os.path.isdir(base_path):
      cloudlog.error(f"Realdata base path not found: {base_path}")
      return

  try:
    os.makedirs(STAGING_ARCHIVE_DIR, exist_ok=True)
    debug_print(f"Ensured staging directory exists: {STAGING_ARCHIVE_DIR}")
  except OSError as e:
    cloudlog.error(f"Could not create or access staging directory {STAGING_ARCHIVE_DIR}: {e}")
    debug_print(f"Fatal: Could not create/access staging dir {STAGING_ARCHIVE_DIR}: {e}. Archiving cannot proceed.")
    return

  try:
    for subdir in os.listdir(base_path):
      subdir_path = os.path.join(base_path, subdir)
      if not os.path.isdir(subdir_path) or subdir_path == STAGING_ARCHIVE_DIR or subdir in processed_dirs:
        continue

      try:
        creation_time_ts = os.stat(subdir_path).st_ctime
      except OSError:
        continue

      if creation_time_ts < one_day_ago_ts:
        continue

      found_count += 1
      creation_dt = datetime.fromtimestamp(creation_time_ts)
      formatted_date_time = creation_dt.strftime("%m%d%y_%H%M")
      segment_name = subdir

      # --- Check if device is offroad before attempting compression ---
      sm.update(0) # Get fresh status for this specific segment
      if not sm.valid['deviceState'] or sm['deviceState'].started:
          debug_print(f"Device onroad or deviceState invalid. Skipping compression for {segment_name} ({subdir_path}).")
          continue # Skip to the next directory/segment

      # Submit compression and queuing to the dedicated executor
      debug_print(f"Submitting compression task for {segment_name} ({subdir_path}) to executor.")
      compression_executor.submit(
          _compress_segment_and_queue_on_cpu3,
          subdir_path,
          segment_name,
          formatted_date_time,
          creation_time_ts
      )
      processed_dirs.add(subdir) # Mark as processed for this scan iteration only after successful queuing

    UploadQueueCache.cache(upload_queue) # Cache after scan pass, queued items are added by worker
    debug_print(f"Scan complete. Found {found_count} potential dirs for processing.")
  except Exception:
    cloudlog.exception("azure.realdata_handler.scan_exception")

def realdata_handler(end_event: threading.Event) -> None:
  global last_clear_time
  # base_path = "/data/media/0/realdata" # Now uses BASE_REALDATA_PATH constant
  age_limit_seconds = 24 * 3600
  scan_interval = 300
  processed_dirs: set[str] = set()

  sm = messaging.SubMaster(['deviceState'])

  cloudlog.info("Performing initial realdata scan...")
  debug_print("Performing initial realdata scan...")

  # Thread pool for compression tasks, pinned to CPU 3
  compression_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='azure_compress')

  try:
    try:
      # Ensure staging directory exists before first scan.
      os.makedirs(STAGING_ARCHIVE_DIR, exist_ok=True)
      sm.update(0) # Initial update for the first scan
      _scan_and_queue_realdata(BASE_REALDATA_PATH, age_limit_seconds, processed_dirs, sm, compression_executor)
      cloudlog.info(f"Initial scan for realdata started. Items will be queued by compression workers.")
      debug_print(f"Initial scan for realdata started. Items will be queued by compression workers.")
      UploadQueueCache.cache(upload_queue) # Cache after initial scan submission pass
    except Exception:
      cloudlog.exception("azure.realdata_handler.initial_scan_exception")

    while not end_event.is_set():
      current_time = time.time()
      if current_time - last_clear_time >= HOURLY_CLEAR_INTERVAL:
        cloudlog.info("Hourly Azure queue clear, resetting scan state.")
        debug_print("Hourly Azure queue clear, resetting scan state.")
        try:
          UploadQueueCache.clear_cache()
          with upload_queue.mutex:
            # Clear the Python queue. Submitted compression tasks might still run and re-add.
            # This primarily clears items that were persisted and reloaded.
            temp_list = []
            while not upload_queue.empty():
                try:
                    temp_list.append(upload_queue.get_nowait())
                except queue.Empty:
                    break
            # For tasks already done from queue perspective but part of this clear
            for _ in temp_list:
                try:
                    upload_queue.task_done()
                except ValueError: # if task_done() called too many times
                    pass
            # Re-add items not yet fully processed by uploader but might be from old cache.
            # The goal is to clear the *persisted* cache and reset processed_dirs.
            # Active items in cur_upload_items or newly compressed items will repopulate.
          processed_dirs.clear()
          last_clear_time = current_time
          debug_print("Cleared processed_dirs and ParamStore cache for hourly reset.")
        except Exception:
          cloudlog.exception("azure.realdata_handler.hourly_clear.exception")

      sm.update(0) # Update device state before passing to scan function
      _scan_and_queue_realdata(BASE_REALDATA_PATH, age_limit_seconds, processed_dirs, sm, compression_executor)
      end_event.wait(scan_interval)
  finally:
    debug_print("Shutting down compression executor...")
    compression_executor.shutdown(wait=True)
    debug_print("Compression executor shutdown complete. Realdata handler thread exiting.")


# -------------------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------------------
def main():
  cloudlog.info("Starting Azure upload service")
  debug_print("Starting Azure upload service")
  try:
    set_core_affinity()
  except Exception:
    cloudlog.exception("failed to set core affinity")

  if ShareFileClient is None or ShareDirectoryClient is None:
      cloudlog.error("Azure SDK not found. Service cannot run.")
      print("Azure SDK not found. Service cannot run. Please `pip install azure-storage-file-share`",
            file=sys.stderr)
      return

  if zstd is None:
      cloudlog.warning("zstandard library not found. Archive creation will fail.")
      print("Warning: zstandard library not found. Archives (.tar.zst) cannot be created.", file=sys.stderr)
      # Proceeding, but archive creation will fail in the scanner

  UploadQueueCache.initialize(upload_queue)
  debug_print(f"Initial queue size after load: {upload_queue.qsize()}")
  debug_queue_status()

  end_event = threading.Event()
  threads = []
  for _ in range(HANDLER_THREADS):
      t = threading.Thread(target=upload_handler, args=(end_event,))
      t.daemon = True
      t.start()
      threads.append(t)
      cur_upload_items[t.ident] = None

  realdata_thread = threading.Thread(target=realdata_handler, args=(end_event,))
  realdata_thread.daemon = True
  realdata_thread.start()
  threads.append(realdata_thread)

  cloudlog.info(f"Azure upload service started with {HANDLER_THREADS} upload thread(s).")
  debug_print(f"Started {len(threads)} threads.")

  try:
    while not end_event.is_set():
        if not all(t.is_alive() for t in threads):
            cloudlog.error("One or more Azure worker threads died.")
            debug_print("Error: One or more worker threads died!")
            end_event.set()
            break
        time.sleep(10)
  except KeyboardInterrupt:
    cloudlog.info("Keyboard interrupt, shutting down Azure service.")
    debug_print("Received keyboard interrupt, shutting down...")
    end_event.set()
  finally:
    if not end_event.is_set():
        end_event.set()
    cloudlog.info("Waiting for threads to finish...")
    debug_print("Waiting for threads to join...")
    shutdown_timeout = RETRY_DELAY + 5
    for t in threads:
      try:
          t.join(timeout=shutdown_timeout)
          if t.is_alive():
              cloudlog.warning(f"Thread {t.name} did not exit cleanly.")
              debug_print(f"Warning: Thread {t.name} did not join!")
      except Exception as e:
          cloudlog.error(f"Error joining thread {t.name}: {e}")
          debug_print(f"Error joining thread {t.name}: {e}")

    debug_print("Performing final queue cache before exit.")
    UploadQueueCache.cache(upload_queue)
    cloudlog.info("Azure upload service shutdown complete.")
    debug_print("Service shutdown complete")

if __name__ == "__main__":
  main()
