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
except ImportError:
  cloudlog.exception("Azure storage fileshare SDK not installed! Please `pip install azure-storage-file-share`.")
  ShareFileClient = None
  ShareDirectoryClient = None

# Constants
HANDLER_THREADS = 1
MAX_RETRY_COUNT = 30     # Try re-upload at most 30 times
RETRY_DELAY = 10         # seconds to wait after a failed attempt
MAX_AGE = 31 * 24 * 3600 # 31 days in seconds

# Azure File Share config
AZURE_SHARE_NAME = "test-rlog-1"
AZURE_BASE_DIR   = "rlogs"

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
      return f.read().strip()
  except Exception:
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
    raise Exception("Azure upload not configured (missing connection string or azure-storage-file-share).")

  subdir_name = upload_item.azure_subdir if upload_item.azure_subdir else "default"
  local_path = upload_item.path
  if not os.path.isfile(local_path):
    raise FileNotFoundError(f"Local file not found: {local_path}")

  dir_client = ShareDirectoryClient.from_connection_string(
    conn_str=conn_str,
    share_name=AZURE_SHARE_NAME,
    directory_path=f"{AZURE_BASE_DIR}/{subdir_name}"
  )
  try:
    # Create subdir if it doesn't exist
    dir_client.create_directory()
  except Exception as e:
    # If it already exists, that's fine. Otherwise, log it.
    if "ResourceAlreadyExists" not in str(e):
      cloudlog.exception("Azure create_directory error", exc_info=e)

  # Upload the file
  filename = os.path.basename(local_path)
  file_client = dir_client.get_file_client(filename)
  with open(local_path, "rb") as f:
    # Add a reasonable timeout to prevent indefinite hangs
    file_client.upload_file(f, timeout=300)  # 5 minute timeout

  cloudlog.event("azure._do_upload_azure.success", subdir=subdir_name, local_path=local_path)


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
    item = replace(item, retry_count=new_retry_count, progress=0.0, current=False)
    upload_queue.put_nowait(item)
    UploadQueueCache.cache(upload_queue)

    cur_upload_items[tid] = None

    for _ in range(RETRY_DELAY):
      time.sleep(1)
      if end_event.is_set():
        break


def upload_handler(end_event: threading.Event) -> None:
  """
  Thread that pulls items off `upload_queue` and uploads them to Azure.
  Retries if needed, or if the connection is metered but not allowed, it defers.
  """
  sm = messaging.SubMaster(['deviceState'])
  tid = threading.get_ident()

  while not end_event.is_set():
    cur_upload_items[tid] = None
    try:
      item = upload_queue.get(timeout=1)
      cur_upload_items[tid] = replace(item, current=True)

      if item.id in cancelled_uploads:
        cancelled_uploads.remove(item.id)
        continue

      # If it's too old, skip
      age = datetime.now() - datetime.fromtimestamp(item.created_at / 1000)
      if age.total_seconds() > MAX_AGE:
        cloudlog.event("azure.upload_handler.expired", item=item, error=True)
        continue

      # Check if uploading over metered connection is allowed
      sm.update(0)
      metered = sm['deviceState'].networkMetered
      network_type = sm['deviceState'].networkType.raw

      if metered and (not item.allow_cellular):
        retry_upload(tid, end_event, increase_count=False)
        continue

      try:
        fn = item.path
        file_size = 0
        try:
          file_size = os.path.getsize(fn)
        except OSError:
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
        cloudlog.event("azure.upload_handler.success", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered)

        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)

      except FileNotFoundError:
        # The local file was missing
        cloudlog.event("azure.upload_handler.not_found", fn=fn)
        item = replace(item, progress=1.0)
        cur_upload_items[tid] = item

        upload_queue.task_done()
        UploadQueueCache.cache(upload_queue)
        # No retry, just skip it.

      except AbortTransferException:
        # If we had a partial/cancel upload
        cloudlog.event("azure.upload_handler.abort", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered)
        retry_upload(tid, end_event, increase_count=False)

      except Exception:
        # Any other error, we can try again
        cloudlog.exception("azure.upload_handler.azure_upload_fail")
        retry_upload(tid, end_event)

    except queue.Empty:
      pass
    except Exception:
      cloudlog.exception("azure.upload_handler.exception")


# ------------------------------------------------------------------------------
# Automatic RLog Finder (realdata_handler)
# ------------------------------------------------------------------------------
def realdata_handler(end_event: threading.Event) -> None:
  """
  Scans /data/media/0/realdata/, finds subdirectories that contain an 'rlog'
  file, and enqueues them for upload (unless they're already queued).
  """
  while not end_event.is_set():
    try:
      base_path = "/data/media/0/realdata"
      if os.path.isdir(base_path):
        for d in os.listdir(base_path):
          sub_dir_full = os.path.join(base_path, d)
          if os.path.isdir(sub_dir_full):
            rlog_path = os.path.join(sub_dir_full, "rlog")
            if os.path.isfile(rlog_path):
              # Create a unique ID for each directory
              upload_id = f"azure|{d}"

              # Check if it's already in the queue or uploading
              queued_items = list(upload_queue.queue) + list(cur_upload_items.values())
              if any((qi is not None and qi.id == upload_id) for qi in queued_items):
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

      # Sleep for a bit before scanning again
      time.sleep(60)

    except Exception:
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
  try:
    set_core_affinity([0, 1, 2, 3])
  except Exception:
    cloudlog.exception("failed to set core affinity")

  # Initialize from stored queue
  UploadQueueCache.initialize(upload_queue)

  end_event = threading.Event()

  # Start threads
  upload_thread = threading.Thread(target=upload_handler, args=(end_event,), name='upload_handler')
  realdata_thread = threading.Thread(target=realdata_handler, args=(end_event,), name='realdata_handler')

  upload_thread.start()
  realdata_thread.start()

  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    pass
  finally:
    end_event.set()
    upload_thread.join()
    realdata_thread.join()


if __name__ == "__main__":
  main()
