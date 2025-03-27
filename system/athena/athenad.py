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
from datetime import datetime
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
  from azure.core.exceptions import ServiceResponseError  # <-- NEW import for catching timeouts
except ImportError:
  cloudlog.exception("Azure storage fileshare SDK not installed! Please `pip install azure-storage-file-share`.")
  ShareFileClient = None
  ShareDirectoryClient = None
  ServiceResponseError = None

# Constants
HANDLER_THREADS = 1
MAX_RETRY_COUNT = 30     # Try re-upload at most 30 times
RETRY_DELAY = 10         # seconds to wait after a failed attempt
MAX_AGE = 31 * 24 * 3600 # 31 days in seconds

# Azure File Share config
AZURE_SHARE_NAME = "drivelogs"
AZURE_BASE_DIR   = "chauffeurrlogs"

# Debug flag - only True when running directly
DEBUG = __name__ == "__main__"

def debug_print(*args, **kwargs):
  if DEBUG:
    print("[DEBUG]", *args, **kwargs)

def debug_queue_status():
  """Print current status of upload queue and active uploads"""
  if not DEBUG:
    return
  print("\n[DEBUG] === Queue Status ===")
  print(f"Active uploads: {len([x for x in cur_upload_items.values() if x is not None])}")
  print(f"Queue size: {upload_queue.qsize()}")
  print("Active upload items:")
  for tid, item in cur_upload_items.items():
    if item is not None:
      print(f"  Thread {tid}: {item.path} (progress: {item.progress}, retries: {item.retry_count})")
  print("Next 3 queued items:")
  for item in list(upload_queue.queue)[:3]:
    print(f"  {item.path} (retries: {item.retry_count})")
  print("========================\n")

# ------------------------------------------------------------------------------
# Azure Connection / Upload
# ------------------------------------------------------------------------------

def get_azure_connection_string() -> str:
  """
  Reads the Azure connection string from /data/persist/azure_conn_string
  (or any other path you prefer).
  """
  try:
    with open("/data/persist/azure_conn_string", "r") as f:
      conn_str = f.read().strip()
      debug_print(f"Successfully read Azure connection string (length: {len(conn_str)})")
      return conn_str
  except Exception as e:
    debug_print(f"Failed to read Azure connection string: {str(e)}")
    cloudlog.exception("azure.get_azure_connection_string.exception")
    return ""


def _do_upload_azure(upload_item: UploadItem, callback=None):
  """
  Upload a file to Azure File Share.
  Creates a sub-directory named upload_item.azure_subdir (if provided)
  within AZURE_BASE_DIR, then uploads the local file (e.g., 'rlog').
  Raises FileNotFoundError if the local file isn't found.
  """
  conn_str = get_azure_connection_string()
  if not conn_str or (ShareDirectoryClient is None):
    debug_print("Azure upload not configured - missing connection string or SDK")
    raise Exception("Azure upload not configured (missing connection string or azure-storage-file-share).")

  subdir_name = upload_item.azure_subdir if upload_item.azure_subdir else "default"
  local_path = upload_item.path
  debug_print(f"\n[DEBUG] === Starting Azure Upload ===")
  debug_print(f"Local path: {local_path}")
  debug_print(f"Target subdirectory: {subdir_name}")
  debug_print(f"File size: {os.path.getsize(local_path) if os.path.exists(local_path) else 'N/A'} bytes")

  if not os.path.isfile(local_path):
    debug_print(f"File not found: {local_path}")
    raise FileNotFoundError(f"Local file not found: {local_path}")

  try:
    debug_print("Creating Azure directory client...")
    dir_client = ShareDirectoryClient.from_connection_string(
      conn_str=conn_str,
      share_name=AZURE_SHARE_NAME,
      directory_path=f"{AZURE_BASE_DIR}/{subdir_name}"
    )
    debug_print(f"Directory client created for: {AZURE_BASE_DIR}/{subdir_name}")

    try:
      debug_print("Attempting to create directory if it doesn't exist...")
      dir_client.create_directory()
      debug_print("Directory created successfully")
    except Exception as e:
      if "ResourceAlreadyExists" not in str(e):
        debug_print(f"Error creating directory: {str(e)}")
        cloudlog.exception("Azure create_directory error", exc_info=e)
      else:
        debug_print("Directory already exists, continuing...")

    # Upload the file
    filename = os.path.basename(local_path)
    debug_print(f"Getting file client for: {filename}")
    file_client = dir_client.get_file_client(filename)

    debug_print("Starting file upload...")
    with open(local_path, "rb") as f:
      file_client.upload_file(f, timeout=300)  # 5 minute chunk-level timeout
    debug_print("File upload completed successfully")
    debug_print("=== Azure Upload Complete ===\n")

    cloudlog.event("azure._do_upload_azure.success", subdir=subdir_name, local_path=local_path)
  except Exception as e:
    debug_print(f"Error during Azure upload: {str(e)}")
    raise


# ------------------------------------------------------------------------------
# Upload Items/Queue
# ------------------------------------------------------------------------------
@dataclass
class UploadItem:
  path: str
  url: str                 # Not used for Azure; can be left blank
  headers: dict[str, str]  # Not used for Azure
  created_at: int
  id: str | None
  retry_count: int = 0
  current: bool = False
  progress: float = 0      # We'll set this to 1.0 on success
  allow_cellular: bool = False

  # Azure-specific subdirectory name
  azure_subdir: str | None = None

  @classmethod
  def from_dict(cls, d: dict) -> UploadItem:
    return cls(
      path=d["path"],
      url=d["url"],
      headers=d["headers"],
      created_at=d["created_at"],
      id=d["id"],
      retry_count=d.get("retry_count", 0),
      current=d.get("current", False),
      progress=d.get("progress", 0),
      allow_cellular=d.get("allow_cellular", False),
      azure_subdir=d.get("azure_subdir", None),
    )


class AbortTransferException(Exception):
  pass


cur_upload_items: dict[int, UploadItem | None] = {}
cancelled_uploads: set[str] = set()
upload_queue: Queue[UploadItem] = queue.Queue()


class UploadQueueCache:
  """
  Simple utility to persist the upload queue across restarts in a param named "AzureUploadQueue".
  """
  @staticmethod
  def initialize(upload_queue: Queue[UploadItem]) -> None:
    """Load any previously queued items from the param store."""
    try:
      upload_queue_json = Params().get("AzureUploadQueue")
      if upload_queue_json is not None:
        for item in json.loads(upload_queue_json):
          upload_queue.put(UploadItem.from_dict(item))
    except Exception:
      cloudlog.exception("azure.UploadQueueCache.initialize.exception")

  @staticmethod
  def cache(upload_queue: Queue[UploadItem]) -> None:
    """
    Save items back to the param store, omitting cancelled or fully completed ones.
    """
    try:
      queue_list = list(upload_queue.queue)
      # Filter out items that are fully done (progress=1.0) or in cancelled_uploads
      items = []
      for i in queue_list:
        if i is None:
          continue
        if i.id in cancelled_uploads:
          continue
        if i.progress >= 1.0:
          continue
        # otherwise, keep it
        items.append(asdict(i))

      Params().put("AzureUploadQueue", json.dumps(items))
    except Exception:
      cloudlog.exception("azure.UploadQueueCache.cache.exception")


# ------------------------------------------------------------------------------
# Upload Handler Thread
# ------------------------------------------------------------------------------
def retry_upload(tid: int, end_event: threading.Event, increase_count: bool = True) -> None:
  """
  If an upload fails or is aborted, re-queue it (unless we've exceeded retry limits).
  """
  item = cur_upload_items[tid]
  if item is not None and item.retry_count < MAX_RETRY_COUNT:
    new_retry_count = item.retry_count + 1 if increase_count else item.retry_count
    debug_print(f"\n[DEBUG] === Retrying Upload ===")
    debug_print(f"File: {item.path}")
    debug_print(f"Retry count: {new_retry_count}")
    debug_print(f"Increase count: {increase_count}")

    item = replace(item, retry_count=new_retry_count, progress=0.0, current=False)
    upload_queue.put_nowait(item)
    UploadQueueCache.cache(upload_queue)
    debug_print("Item requeued successfully")
    debug_print("=== Retry Complete ===\n")

    cur_upload_items[tid] = None

    for i in range(RETRY_DELAY):
      time.sleep(1)
      if end_event.is_set():
        debug_print(f"Retry delay interrupted after {i+1} seconds")
        break


def upload_handler(end_event: threading.Event) -> None:
  """
  Thread that pulls items off `upload_queue` and uploads them to Azure.
  Retries if needed, or if the connection is metered but not allowed, it defers.
  """
  sm = messaging.SubMaster(['deviceState'])
  tid = threading.get_ident()
  debug_print(f"\n[DEBUG] === Upload Handler Started ===")
  debug_print(f"Thread ID: {tid}")
  debug_print("=== Upload Handler Ready ===\n")

  while not end_event.is_set():
    cur_upload_items[tid] = None
    try:
      item = upload_queue.get(timeout=1)
      debug_print(f"\n[DEBUG] === Processing Upload Item ===")
      debug_print(f"File: {item.path}")
      debug_print(f"ID: {item.id}")
      debug_print(f"Retry count: {item.retry_count}")
      debug_print(f"Created at: {datetime.fromtimestamp(item.created_at / 1000)}")
      debug_print(f"Allow cellular: {item.allow_cellular}")
      debug_print("=== Item Details Complete ===\n")

      cur_upload_items[tid] = replace(item, current=True)
      debug_queue_status()

      if item.id in cancelled_uploads:
        debug_print(f"Item {item.id} was cancelled, skipping")
        cancelled_uploads.remove(item.id)
        continue

      # If it's too old, skip
      age = datetime.now() - datetime.fromtimestamp(item.created_at / 1000)
      if age.total_seconds() > MAX_AGE:
        debug_print(f"Item {item.id} is too old ({age.total_seconds()}s), skipping")
        cloudlog.event("azure.upload_handler.expired", item=item, error=True)
        continue

      # Check if uploading over metered connection is allowed
      sm.update(0)
      metered = sm['deviceState'].networkMetered
      network_type = sm['deviceState'].networkType.raw
      debug_print(f"\n[DEBUG] === Network Status ===")
      debug_print(f"Network type: {network_type}")
      debug_print(f"Metered connection: {metered}")
      debug_print("=== Network Check Complete ===\n")

      if metered and (not item.allow_cellular):
        debug_print("Metered connection detected and cellular not allowed, deferring upload")
        retry_upload(tid, end_event, increase_count=False)
        continue

      try:
        fn = item.path
        file_size = 0
        try:
          file_size = os.path.getsize(fn)
          debug_print(f"File size: {file_size} bytes")
        except OSError as e:
          debug_print(f"Error getting file size: {str(e)}")
          pass

        cloudlog.event("azure.upload_handler.upload_start",
                       fn=fn, sz=file_size,
                       network_type=network_type,
                       metered=metered,
                       retry_count=item.retry_count)

        # Perform the Azure upload
        _do_upload_azure(item)

        # Mark success
        item = replace(item, progress=1.0)
        cur_upload_items[tid] = item
        debug_print(f"\n[DEBUG] === Upload Success ===")
        debug_print(f"File: {fn}")
        debug_print(f"Size: {file_size} bytes")
        debug_print("=== Upload Complete ===\n")

        cloudlog.event("azure.upload_handler.success", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered)

        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)
        debug_queue_status()

      except FileNotFoundError:
        debug_print(f"\n[DEBUG] === File Not Found ===")
        debug_print(f"File: {fn}")
        debug_print("=== Error Complete ===\n")
        cloudlog.event("azure.upload_handler.not_found", fn=fn)
        item = replace(item, progress=1.0)
        cur_upload_items[tid] = item

        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)
        debug_queue_status()

      except (ConnectionError, TimeoutError) as e:
        debug_print(f"\n[DEBUG] === Connection Error ===")
        debug_print(f"File: {fn}")
        debug_print(f"Error: {str(e)}")
        debug_print("=== Error Complete ===\n")
        cloudlog.event("azure.upload_handler.timeout", fn=fn, error=str(e))
        retry_upload(tid, end_event)

      except ServiceResponseError as e:
        debug_print(f"\n[DEBUG] === Azure Service Error ===")
        debug_print(f"File: {fn}")
        debug_print(f"Error: {str(e)}")
        debug_print("=== Error Complete ===\n")
        cloudlog.event("azure.upload_handler.timeout", fn=fn, error=str(e))
        retry_upload(tid, end_event)

      except AbortTransferException:
        debug_print(f"\n[DEBUG] === Upload Aborted ===")
        debug_print(f"File: {fn}")
        debug_print(f"Size: {file_size} bytes")
        debug_print("=== Abort Complete ===\n")
        cloudlog.event("azure.upload_handler.abort", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered)
        retry_upload(tid, end_event, increase_count=False)

      except Exception as e:
        debug_print(f"\n[DEBUG] === Unexpected Error ===")
        debug_print(f"File: {fn}")
        debug_print(f"Error: {str(e)}")
        debug_print("=== Error Complete ===\n")
        cloudlog.exception("azure.upload_handler.azure_upload_fail")
        retry_upload(tid, end_event)

    except queue.Empty:
      pass
    except Exception as e:
      debug_print(f"\n[DEBUG] === Handler Error ===")
      debug_print(f"Error: {str(e)}")
      debug_print("=== Error Complete ===\n")
      cloudlog.exception("azure.upload_handler.exception")


# ------------------------------------------------------------------------------
# Automatic RLog Finder (realdata_handler)
# ------------------------------------------------------------------------------
def realdata_handler(end_event: threading.Event) -> None:
  """
  Scans /data/media/0/realdata/, finds subdirectories that contain an 'rlog'
  file, and enqueues them for upload (unless they're already queued).
  """
  debug_print(f"\n[DEBUG] === Realdata Handler Started ===")
  debug_print("=== Realdata Handler Ready ===\n")

  while not end_event.is_set():
    try:
      base_path = "/data/media/0/realdata"
      if os.path.isdir(base_path):
        debug_print(f"\n[DEBUG] === Scanning Directory ===")
        debug_print(f"Base path: {base_path}")

        for d in os.listdir(base_path):
          sub_dir_full = os.path.join(base_path, d)
          if os.path.isdir(sub_dir_full):
            rlog_path = os.path.join(sub_dir_full, "rlog")
            if os.path.isfile(rlog_path):
              debug_print(f"\n[DEBUG] === Found RLog File ===")
              debug_print(f"Directory: {d}")
              debug_print(f"RLog path: {rlog_path}")
              debug_print(f"File size: {os.path.getsize(rlog_path)} bytes")

              # Create a unique ID for each directory
              upload_id = f"azure|{d}"
              debug_print(f"Upload ID: {upload_id}")

              # Check if it's already in the queue or uploading
              queued_items = list(upload_queue.queue) + list(cur_upload_items.values())
              if any((qi is not None and qi.id == upload_id) for qi in queued_items):
                debug_print("File already queued or uploading, skipping")
                cloudlog.debug(f"realdata_handler: skipping {d}, already queued or uploading.")
                continue

              # Create new item and push to queue
              item = UploadItem(
                path=rlog_path,
                url="",  # not needed for Azure
                headers={},
                created_at=int(time.time() * 1000),
                id=upload_id,
                azure_subdir=d
              )
              upload_queue.put_nowait(item)
              UploadQueueCache.cache(upload_queue)
              debug_print("File queued for upload")
              debug_print("=== Queue Update Complete ===\n")
              debug_queue_status()

        debug_print("=== Directory Scan Complete ===\n")

      # Sleep for a bit before scanning again
      debug_print("Sleeping for 60 seconds before next scan...")
      time.sleep(60)

    except Exception as e:
      debug_print(f"\n[DEBUG] === Realdata Handler Error ===")
      debug_print(f"Error: {str(e)}")
      debug_print("=== Error Complete ===\n")
      cloudlog.exception("azure.realdata_handler.exception")


# ------------------------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------------------------
def main():
  """
  Minimal 'main' that:
   - Initializes the queue from storage
   - Spawns the upload handler
   - Spawns the realdata directory scanner
   - Runs indefinitely
  """
  debug_print("Starting Azure upload service")
  try:
    set_core_affinity([0, 1, 2, 3])
    debug_print("Successfully set core affinity")
  except Exception:
    debug_print("Failed to set core affinity")
    cloudlog.exception("failed to set core affinity")

  # Initialize from stored queue
  UploadQueueCache.initialize(upload_queue)
  debug_print("Initialized upload queue from storage")

  end_event = threading.Event()

  # Start threads
  upload_thread = threading.Thread(target=upload_handler, args=(end_event,), name='upload_handler')
  realdata_thread = threading.Thread(target=realdata_handler, args=(end_event,), name='realdata_handler')

  upload_thread.start()
  realdata_thread.start()
  debug_print("Started upload and realdata handler threads")

  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    debug_print("Received keyboard interrupt, shutting down...")
    pass
  finally:
    end_event.set()
    upload_thread.join()
    realdata_thread.join()
    debug_print("Service shutdown complete")


if __name__ == "__main__":
  main()
