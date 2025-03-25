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
from collections.abc import Callable

import requests
from jsonrpc import JSONRPCResponseManager, dispatcher
from websocket import (ABNF, WebSocket, WebSocketException, WebSocketTimeoutException,
                       create_connection)

import cereal.messaging as messaging
from cereal import log
from cereal.services import SERVICE_LIST
from openpilot.common.api import Api
from openpilot.common.file_helpers import CallbackReader
from openpilot.common.params import Params
from openpilot.common.realtime import set_core_affinity
from openpilot.system.hardware import HARDWARE, PC
from openpilot.system.loggerd.xattr_cache import getxattr, setxattr
from openpilot.common.swaglog import cloudlog
from openpilot.system.version import get_build_metadata
from openpilot.system.hardware.hw import Paths

# ---- NEW IMPORTS FOR AZURE FILE SHARE ----
try:
  from azure.storage.fileshare import ShareFileClient, ShareDirectoryClient
except ImportError:
  cloudlog.exception("Azure storage fileshare SDK not installed! Please pip install azure-storage-file-share.")
  ShareFileClient = None
  ShareDirectoryClient = None
# ------------------------------------------

ATHENA_HOST = os.getenv('ATHENA_HOST', 'wss://athena.comma.ai')
HANDLER_THREADS = int(os.getenv('HANDLER_THREADS', "4"))
LOCAL_PORT_WHITELIST = {8022}

LOG_ATTR_NAME = 'user.upload'
LOG_ATTR_VALUE_MAX_UNIX_TIME = int.to_bytes(2147483647, 4, sys.byteorder)
RECONNECT_TIMEOUT_S = 70

RETRY_DELAY = 10  # seconds
MAX_RETRY_COUNT = 30  # Try for at most 5 minutes if upload fails immediately
MAX_AGE = 31 * 24 * 3600  # seconds
WS_FRAME_SIZE = 4096

NetworkType = log.DeviceState.NetworkType

UploadFileDict = dict[str, str | int | float | bool]
UploadItemDict = dict[str, str | bool | int | float | dict[str, str]]

UploadFilesToUrlResponse = dict[str, int | list[UploadItemDict] | list[str]]

dispatcher["echo"] = lambda s: s
recv_queue: Queue[str] = queue.Queue()
send_queue: Queue[str] = queue.Queue()
upload_queue: Queue[UploadItem] = queue.Queue()
low_priority_send_queue: Queue[str] = queue.Queue()
log_recv_queue: Queue[str] = queue.Queue()
cancelled_uploads: set[str] = set()

cur_upload_items: dict[int, UploadItem | None] = {}

def strip_bz2_extension(fn: str) -> str:
  if fn.endswith('.bz2'):
    return fn[:-4]
  return fn

class AbortTransferException(Exception):
  pass

class UploadQueueCache:
  @staticmethod
  def initialize(upload_queue: Queue[UploadItem]) -> None:
    try:
      upload_queue_json = Params().get("AthenadUploadQueue")
      if upload_queue_json is not None:
        for item in json.loads(upload_queue_json):
          upload_queue.put(UploadItem.from_dict(item))
    except Exception:
      cloudlog.exception("athena.UploadQueueCache.initialize.exception")

  @staticmethod
  def cache(upload_queue: Queue[UploadItem]) -> None:
    try:
      queue_list: list[UploadItem | None] = list(upload_queue.queue)
      items = [asdict(i) for i in queue_list if i is not None and (i.id not in cancelled_uploads)]
      Params().put("AthenadUploadQueue", json.dumps(items))
    except Exception:
      cloudlog.exception("athena.UploadQueueCache.cache.exception")


def handle_long_poll(ws: WebSocket, exit_event: threading.Event | None) -> None:
  end_event = threading.Event()

  threads = [
    threading.Thread(target=ws_manage, args=(ws, end_event), name='ws_manage'),
    threading.Thread(target=ws_recv, args=(ws, end_event), name='ws_recv'),
    threading.Thread(target=ws_send, args=(ws, end_event), name='ws_send'),
    threading.Thread(target=upload_handler, args=(end_event,), name='upload_handler'),
    threading.Thread(target=log_handler, args=(end_event,), name='log_handler'),
    threading.Thread(target=stat_handler, args=(end_event,), name='stat_handler'),
    # ---- NEW: We'll spawn the realdata_handler to poll /data/media/0/realdata ----
    threading.Thread(target=realdata_handler, args=(end_event,), name='realdata_handler'),
  ] + [
    threading.Thread(target=jsonrpc_handler, args=(end_event,), name=f'worker_{x}')
    for x in range(HANDLER_THREADS)
  ]

  for thread in threads:
    thread.start()

  try:
    while not end_event.wait(0.1):
      if exit_event is not None and exit_event.is_set():
        end_event.set()
  except (KeyboardInterrupt, SystemExit):
    end_event.set()
    raise
  finally:
    for thread in threads:
      cloudlog.debug(f"athena.joining {thread.name}")
      thread.join()


def jsonrpc_handler(end_event: threading.Event) -> None:
  dispatcher["startLocalProxy"] = partial(startLocalProxy, end_event)
  while not end_event.is_set():
    try:
      data = recv_queue.get(timeout=1)
      if "method" in data:
        cloudlog.event("athena.jsonrpc_handler.call_method", data=data)
        response = JSONRPCResponseManager.handle(data, dispatcher)
        send_queue.put_nowait(response.json)
      elif "id" in data and ("result" in data or "error" in data):
        log_recv_queue.put_nowait(data)
      else:
        raise Exception("not a valid request or response")
    except queue.Empty:
      pass
    except Exception as e:
      cloudlog.exception("athena jsonrpc handler failed")
      send_queue.put_nowait(json.dumps({"error": str(e)}))


def retry_upload(tid: int, end_event: threading.Event, increase_count: bool = True) -> None:
  item = cur_upload_items[tid]
  if item is not None and item.retry_count < MAX_RETRY_COUNT:
    new_retry_count = item.retry_count + 1 if increase_count else item.retry_count

    item = replace(
      item,
      retry_count=new_retry_count,
      progress=0,
      current=False
    )
    upload_queue.put_nowait(item)
    UploadQueueCache.cache(upload_queue)

    cur_upload_items[tid] = None

    for _ in range(RETRY_DELAY):
      time.sleep(1)
      if end_event.is_set():
        break


def cb(sm, item, tid, end_event: threading.Event, sz: int, cur: int) -> None:
  # This callback was used for the old approach to track upload progress,
  # can still use it if you want, or ignore for Azure.
  sm.update(0)
  metered = sm['deviceState'].networkMetered
  if metered and (not item.allow_cellular):
    raise AbortTransferException

  if end_event.is_set():
    raise AbortTransferException

  cur_upload_items[tid] = replace(item, progress=cur / sz if sz else 1)


# ---- (LEGACY) _do_upload() was the old Comma/Athena upload. We keep it for reference if needed. ----
def _do_upload(upload_item, callback: Callable = None) -> requests.Response:
  """
  Original method for uploading to Comma's endpoints with a PUT to a presigned URL.
  We'll leave it here, but not actually call it if we've moved to Azure.
  """
  path = upload_item.path
  compress = False

  # If file does not exist, but does exist without the .bz2 extension we will compress on the fly
  if not os.path.exists(path) and os.path.exists(strip_bz2_extension(path)):
    path = strip_bz2_extension(path)
    compress = True

  with open(path, "rb") as f:
    content = f.read()
    if compress:
      cloudlog.event("athena.upload_handler.compress", fn=path, fn_orig=upload_item.path)
      content = bz2.compress(content)

  with io.BytesIO(content) as data:
    return requests.put(
      upload_item.url,
      data=CallbackReader(data, callback, len(content)) if callback else data,
      headers={**upload_item.headers, 'Content-Length': str(len(content))},
      timeout=30
    )
# --------------------------------------------------------------------------------------------

# ---- NEW: Azure-based upload logic ----
AZURE_SHARE_NAME = "test-rlog-1"
AZURE_BASE_DIR   = "rlogs"

def get_azure_connection_string() -> str:
  """
  Reads the Azure connection string from /data/persist/azure_conn_string.
  """
  try:
    with open("/data/persist/azure_conn_string", "r") as f:
      return f.read().strip()
  except Exception:
    cloudlog.exception("athena.get_azure_connection_string.exception")
    return ""


def _do_upload_azure(upload_item: UploadItem, callback: Callable = None):
  """
  Upload a file to Azure File Share.
  We'll create a sub-directory named upload_item.azure_subdir (if provided),
  within AZURE_BASE_DIR, then upload the local 'rlog' file.

  If you want progress tracking, you can adapt the 'callback' like in the old code.
  """
  conn_str = get_azure_connection_string()
  if not conn_str or (ShareDirectoryClient is None):
    cloudlog.error("Azure connection string not found or azure-storage-file-share not installed")
    raise Exception("Azure upload not configured")

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

  # The actual file in that subdir. We'll call it "rlog" or the local file's name:
  filename = os.path.basename(local_path)  # e.g. "rlog"
  file_client = dir_client.get_file_client(filename)

  # If we want to forcibly overwrite, that's the default behavior of upload_file().
  with open(local_path, "rb") as f:
    # We can do chunked uploads automatically
    file_client.upload_file(f)

  # No explicit return needed; if we get here, success
  cloudlog.event("athena._do_upload_azure.success", subdir=subdir_name, local_path=local_path)

# --------------------------------------------------------------------------------------------

@dataclass
class UploadFile:
  fn: str
  url: str
  headers: dict[str, str]
  allow_cellular: bool

  @classmethod
  def from_dict(cls, d: dict) -> UploadFile:
    return cls(d.get("fn", ""), d.get("url", ""), d.get("headers", {}), d.get("allow_cellular", False))

@dataclass
class UploadItem:
  path: str
  url: str
  headers: dict[str, str]
  created_at: int
  id: str | None
  retry_count: int = 0
  current: bool = False
  progress: float = 0
  allow_cellular: bool = False

  # ---- NEW: store the name of the subdirectory on Azure, if any
  azure_subdir: str | None = None

  @classmethod
  def from_dict(cls, d: dict) -> UploadItem:
    return cls(
      d["path"],
      d["url"],
      d["headers"],
      d["created_at"],
      d["id"],
      d.get("retry_count", 0),
      d.get("current", False),
      d.get("progress", 0),
      d.get("allow_cellular", False),
      d.get("azure_subdir", None),
    )


def upload_handler(end_event: threading.Event) -> None:
  sm = messaging.SubMaster(['deviceState'])
  tid = threading.get_ident()

  while not end_event.is_set():
    cur_upload_items[tid] = None
    try:
      cur_upload_items[tid] = item = replace(upload_queue.get(timeout=1), current=True)

      if item.id in cancelled_uploads:
        cancelled_uploads.remove(item.id)
        continue

      # Remove item if too old
      age = datetime.now() - datetime.fromtimestamp(item.created_at / 1000)
      if age.total_seconds() > MAX_AGE:
        cloudlog.event("athena.upload_handler.expired", item=item, error=True)
        continue

      # Check if uploading over metered connection is allowed
      sm.update(0)
      metered = sm['deviceState'].networkMetered
      network_type = sm['deviceState'].networkType.raw
      if metered and (not item.allow_cellular):
        retry_upload(tid, end_event, False)
        continue

      try:
        fn = item.path
        file_size = 0
        try:
          file_size = os.path.getsize(fn)
        except OSError:
          pass

        cloudlog.event("athena.upload_handler.upload_start", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered, retry_count=item.retry_count)

        # ---- REPLACE with Azure Upload ----
        _do_upload_azure(item, partial(cb, sm, item, tid, end_event, file_size))

        cloudlog.event("athena.upload_handler.success", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered)

        UploadQueueCache.cache(upload_queue)

      except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.SSLError):
        cloudlog.event("athena.upload_handler.timeout", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered)
        retry_upload(tid, end_event)

      except AbortTransferException:
        cloudlog.event("athena.upload_handler.abort", fn=fn, sz=file_size,
                       network_type=network_type, metered=metered)
        retry_upload(tid, end_event, False)

      except Exception:
        cloudlog.exception("athena.upload_handler.azure_upload_fail")
        retry_upload(tid, end_event)

    except queue.Empty:
      pass
    except Exception:
      cloudlog.exception("athena.upload_handler.exception")


@dispatcher.add_method
def getMessage(service: str, timeout: int = 1000) -> dict:
  if service is None or service not in SERVICE_LIST:
    raise Exception("invalid service")

  socket_ = messaging.sub_sock(service, timeout=timeout)
  ret = messaging.recv_one(socket_)

  if ret is None:
    raise TimeoutError

  return cast(dict, ret.to_dict())


@dispatcher.add_method
def getVersion() -> dict[str, str]:
  build_metadata = get_build_metadata()
  return {
    "version": build_metadata.openpilot.version,
    "remote": build_metadata.openpilot.git_normalized_origin,
    "branch": build_metadata.channel,
    "commit": build_metadata.openpilot.git_commit,
  }


@dispatcher.add_method
def setNavDestination(latitude: int = 0, longitude: int = 0, place_name: str = None, place_details: str = None) -> dict[str, int]:
  destination = {
    "latitude": latitude,
    "longitude": longitude,
    "place_name": place_name,
    "place_details": place_details,
  }
  Params().put("NavDestination", json.dumps(destination))
  return {"success": 1}


def scan_dir(path: str, prefix: str) -> list[str]:
  files = []
  with os.scandir(path) as i:
    for e in i:
      rel_path = os.path.relpath(e.path, Paths.log_root())
      if e.is_dir(follow_symlinks=False):
        rel_path = os.path.join(rel_path, '')
        if rel_path.startswith(prefix) or prefix.startswith(rel_path):
          files.extend(scan_dir(e.path, prefix))
      else:
        if rel_path.startswith(prefix):
          files.append(rel_path)
  return files

@dispatcher.add_method
def listDataDirectory(prefix='') -> list[str]:
  return scan_dir(Paths.log_root(), prefix)


@dispatcher.add_method
def uploadFileToUrl(fn: str, url: str, headers: dict[str, str]) -> UploadFilesToUrlResponse:
  """
  Legacy JSON-RPC method. Not really used if you’re purely on Azure now,
  but we keep it for completeness.
  """
  response: UploadFilesToUrlResponse = uploadFilesToUrls([{
    "fn": fn,
    "url": url,
    "headers": headers,
  }])
  return response


@dispatcher.add_method
def uploadFilesToUrls(files_data: list[UploadFileDict]) -> UploadFilesToUrlResponse:
  """
  Another legacy method. If you want to adapt it to queue Azure uploads,
  you could do so. Right now it queues items with the old structure.
  """
  files = map(UploadFile.from_dict, files_data)
  items: list[UploadItemDict] = []
  failed: list[str] = []

  for file in files:
    if len(file.fn) == 0 or file.fn[0] == '/' or '..' in file.fn or len(file.url) == 0:
      failed.append(file.fn)
      continue

    path = os.path.join(Paths.log_root(), file.fn)
    if not os.path.exists(path) and not os.path.exists(strip_bz2_extension(path)):
      failed.append(file.fn)
      continue

    url = file.url.split('?')[0]
    if any(url == item['url'].split('?')[0] for item in listUploadQueue()):
      continue

    item = UploadItem(
      path=path,
      url=file.url,
      headers=file.headers,
      created_at=int(time.time() * 1000),
      id=None,
      allow_cellular=file.allow_cellular,
    )
    upload_id = hashlib.sha1(str(item).encode()).hexdigest()
    item = replace(item, id=upload_id)
    upload_queue.put_nowait(item)
    items.append(asdict(item))

  UploadQueueCache.cache(upload_queue)
  resp: UploadFilesToUrlResponse = {"enqueued": len(items), "items": items}
  if failed:
    resp["failed"] = failed

  return resp


@dispatcher.add_method
def listUploadQueue() -> list[UploadItemDict]:
  items = list(upload_queue.queue) + list(cur_upload_items.values())
  return [asdict(i) for i in items if (i is not None) and (i.id not in cancelled_uploads)]


@dispatcher.add_method
def cancelUpload(upload_id: str | list[str]) -> dict[str, int | str]:
  if not isinstance(upload_id, list):
    upload_id = [upload_id]

  uploading_ids = {item.id for item in list(upload_queue.queue)}
  cancelled_ids = uploading_ids.intersection(upload_id)
  if len(cancelled_ids) == 0:
    return {"success": 0, "error": "not found"}

  cancelled_uploads.update(cancelled_ids)
  return {"success": 1}


@dispatcher.add_method
def setRouteViewed(route: str) -> dict[str, int | str]:
  params = Params()
  r = params.get("AthenadRecentlyViewedRoutes", encoding="utf8")
  routes = [] if r is None else r.split(",")
  routes.append(route)
  routes = list(dict.fromkeys(routes))
  params.put("AthenadRecentlyViewedRoutes", ",".join(routes[-10:]))
  return {"success": 1}


def startLocalProxy(global_end_event: threading.Event, remote_ws_uri: str, local_port: int) -> dict[str, int]:
  if local_port not in LOCAL_PORT_WHITELIST:
    raise Exception("Requested local port not whitelisted")

  cloudlog.debug("athena.startLocalProxy.starting")

  dongle_id = Params().get("DongleId").decode('utf8')
  identity_token = Api(dongle_id).get_token()
  ws = create_connection(remote_ws_uri,
                         cookie="jwt=" + identity_token,
                         enable_multithread=True)

  ws.sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x90)
  ssock, csock = socket.socketpair()
  local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  local_sock.connect(('127.0.0.1', local_port))
  local_sock.setblocking(False)

  proxy_end_event = threading.Event()
  threads = [
    threading.Thread(target=ws_proxy_recv, args=(ws, local_sock, ssock, proxy_end_event, global_end_event)),
    threading.Thread(target=ws_proxy_send, args=(ws, local_sock, csock, proxy_end_event))
  ]
  for thread in threads:
    thread.start()

  cloudlog.debug("athena.startLocalProxy.started")
  return {"success": 1}


@dispatcher.add_method
def getPublicKey() -> str | None:
  if not os.path.isfile(Paths.persist_root() + '/comma/id_rsa.pub'):
    return None
  with open(Paths.persist_root() + '/comma/id_rsa.pub') as f:
    return f.read()


@dispatcher.add_method
def getSshAuthorizedKeys() -> str:
  return Params().get("GithubSshKeys", encoding='utf8') or ''


@dispatcher.add_method
def getGithubUsername() -> str:
  return Params().get("GithubUsername", encoding='utf8') or ''


@dispatcher.add_method
def getSimInfo():
  return HARDWARE.get_sim_info()


@dispatcher.add_method
def getNetworkType():
  return HARDWARE.get_network_type()


@dispatcher.add_method
def getNetworkMetered() -> bool:
  network_type = HARDWARE.get_network_type()
  return HARDWARE.get_network_metered(network_type)


@dispatcher.add_method
def getNetworks():
  return HARDWARE.get_networks()


@dispatcher.add_method
def takeSnapshot() -> str | dict[str, str] | None:
  from openpilot.system.camerad.snapshot.snapshot import jpeg_write, snapshot
  ret = snapshot()
  if ret is not None:
    def b64jpeg(x):
      if x is not None:
        f = io.BytesIO()
        jpeg_write(f, x)
        return base64.b64encode(f.getvalue()).decode("utf-8")
      else:
        return None
    return {'jpegBack': b64jpeg(ret[0]),
            'jpegFront': b64jpeg(ret[1])}
  else:
    raise Exception("not available while camerad is started")


def get_logs_to_send_sorted() -> list[str]:
  curr_time = int(time.time())
  logs = []
  for log_entry in os.listdir(Paths.swaglog_root()):
    log_path = os.path.join(Paths.swaglog_root(), log_entry)
    time_sent = 0
    try:
      value = getxattr(log_path, LOG_ATTR_NAME)
      if value is not None:
        time_sent = int.from_bytes(value, sys.byteorder)
    except (ValueError, TypeError):
      pass
    if not time_sent or curr_time - time_sent > 3600:
      logs.append(log_entry)
  return sorted(logs)[:-1]


def log_handler(end_event: threading.Event) -> None:
  if PC:
    return

  log_files = []
  last_scan = 0.
  while not end_event.is_set():
    try:
      curr_scan = time.monotonic()
      if curr_scan - last_scan > 10:
        log_files = get_logs_to_send_sorted()
        last_scan = curr_scan

      curr_log = None
      if len(log_files) > 0:
        log_entry = log_files.pop()
        cloudlog.debug(f"athena.log_handler.forward_request {log_entry}")
        try:
          curr_time = int(time.time())
          log_path = os.path.join(Paths.swaglog_root(), log_entry)
          setxattr(log_path, LOG_ATTR_NAME, int.to_bytes(curr_time, 4, sys.byteorder))
          with open(log_path) as f:
            jsonrpc = {
              "method": "forwardLogs",
              "params": {
                "logs": f.read()
              },
              "jsonrpc": "2.0",
              "id": log_entry
            }
            low_priority_send_queue.put_nowait(json.dumps(jsonrpc))
            curr_log = log_entry
        except OSError:
          pass

      for _ in range(100):
        if end_event.is_set():
          break
        try:
          log_resp = json.loads(log_recv_queue.get(timeout=1))
          log_entry = log_resp.get("id")
          log_success = "result" in log_resp and log_resp["result"].get("success")
          cloudlog.debug(f"athena.log_handler.forward_response {log_entry} {log_success}")
          if log_entry and log_success:
            log_path = os.path.join(Paths.swaglog_root(), log_entry)
            try:
              setxattr(log_path, LOG_ATTR_NAME, LOG_ATTR_VALUE_MAX_UNIX_TIME)
            except OSError:
              pass
          if curr_log == log_entry:
            break
        except queue.Empty:
          if curr_log is None:
            break

    except Exception:
      cloudlog.exception("athena.log_handler.exception")


def stat_handler(end_event: threading.Event) -> None:
  STATS_DIR = Paths.stats_root()
  while not end_event.is_set():
    last_scan = 0.
    curr_scan = time.monotonic()
    try:
      if curr_scan - last_scan > 10:
        stat_filenames = list(filter(lambda name: not name.startswith(tempfile.gettempprefix()), os.listdir(STATS_DIR)))
        if len(stat_filenames) > 0:
          stat_path = os.path.join(STATS_DIR, stat_filenames[0])
          with open(stat_path) as f:
            jsonrpc = {
              "method": "storeStats",
              "params": {
                "stats": f.read()
              },
              "jsonrpc": "2.0",
              "id": stat_filenames[0]
            }
            low_priority_send_queue.put_nowait(json.dumps(jsonrpc))
          os.remove(stat_path)
        last_scan = curr_scan
    except Exception:
      cloudlog.exception("athena.stat_handler.exception")
    time.sleep(0.1)


# ---- NEW: realdata_handler: scans /data/media/0/realdata/ for subdirectories,
# finds "rlog" file, queues an UploadItem pointing to Azure.
def realdata_handler(end_event: threading.Event) -> None:
  while not end_event.is_set():
    try:
      base_path = "/data/media/0/realdata"
      if os.path.isdir(base_path):
        for d in os.listdir(base_path):
          sub_dir_full = os.path.join(base_path, d)
          if os.path.isdir(sub_dir_full):
            # Check if there's a file named "rlog"
            rlog_path = os.path.join(sub_dir_full, "rlog")
            if os.path.isfile(rlog_path):
              # Create a unique ID so we don't double-queue
              upload_id = f"azure|{d}"
              # Check if it's already in the queue or uploading
              queued_items = list(upload_queue.queue) + list(cur_upload_items.values())
              if any((qi is not None and qi.id == upload_id) for qi in queued_items):
                continue

              # Create new item and push to queue
              item = UploadItem(
                path=rlog_path,
                url="",  # not used for Azure
                headers={},
                created_at=int(time.time() * 1000),
                id=upload_id,
                azure_subdir=d
              )
              upload_queue.put_nowait(item)
              UploadQueueCache.cache(upload_queue)
      time.sleep(60)
    except Exception:
      cloudlog.exception("athena.realdata_handler.exception")


def ws_proxy_recv(ws: WebSocket, local_sock: socket.socket, ssock: socket.socket,
                  end_event: threading.Event, global_end_event: threading.Event) -> None:
  while not (end_event.is_set() or global_end_event.is_set()):
    try:
      r = select.select((ws.sock,), (), (), 30)
      if r[0]:
        data = ws.recv()
        if isinstance(data, str):
          data = data.encode("utf-8")
        local_sock.sendall(data)
    except WebSocketTimeoutException:
      pass
    except Exception:
      cloudlog.exception("athenad.ws_proxy_recv.exception")
      break

  cloudlog.debug("athena.ws_proxy_recv closing sockets")
  ssock.close()
  local_sock.close()
  ws.close()
  cloudlog.debug("athena.ws_proxy_recv done closing sockets")
  end_event.set()


def ws_proxy_send(ws: WebSocket, local_sock: socket.socket, signal_sock: socket.socket, end_event: threading.Event) -> None:
  while not end_event.is_set():
    try:
      r, _, _ = select.select((local_sock, signal_sock), (), ())
      if r:
        if r[0].fileno() == signal_sock.fileno():
          end_event.set()
          break
        data = local_sock.recv(4096)
        if not data:
          end_event.set()
          break
        ws.send(data, ABNF.OPCODE_BINARY)
    except Exception:
      cloudlog.exception("athenad.ws_proxy_send.exception")
      end_event.set()

  cloudlog.debug("athena.ws_proxy_send closing sockets")
  signal_sock.close()
  cloudlog.debug("athena.ws_proxy_send done closing sockets")


def ws_recv(ws: WebSocket, end_event: threading.Event) -> None:
  last_ping = int(time.monotonic() * 1e9)
  while not end_event.is_set():
    try:
      opcode, data = ws.recv_data(control_frame=True)
      if opcode in (ABNF.OPCODE_TEXT, ABNF.OPCODE_BINARY):
        if opcode == ABNF.OPCODE_TEXT:
          data = data.decode("utf-8")
        recv_queue.put_nowait(data)
      elif opcode == ABNF.OPCODE_PING:
        last_ping = int(time.monotonic() * 1e9)
        Params().put("LastAthenaPingTime", str(last_ping))
    except WebSocketTimeoutException:
      ns_since_last_ping = int(time.monotonic() * 1e9) - last_ping
      if ns_since_last_ping > RECONNECT_TIMEOUT_S * 1e9:
        cloudlog.exception("athenad.ws_recv.timeout")
        end_event.set()
    except Exception:
      cloudlog.exception("athenad.ws_recv.exception")
      end_event.set()


def ws_send(ws: WebSocket, end_event: threading.Event) -> None:
  while not end_event.is_set():
    try:
      try:
        data = send_queue.get_nowait()
      except queue.Empty:
        data = low_priority_send_queue.get(timeout=1)

      for i in range(0, len(data), WS_FRAME_SIZE):
        frame = data[i:i+WS_FRAME_SIZE]
        last = i + WS_FRAME_SIZE >= len(data)
        opcode = ABNF.OPCODE_TEXT if i == 0 else ABNF.OPCODE_CONT
        ws.send_frame(ABNF.create_frame(frame, opcode, last))

    except queue.Empty:
      pass
    except Exception:
      cloudlog.exception("athenad.ws_send.exception")
      end_event.set()


def ws_manage(ws: WebSocket, end_event: threading.Event) -> None:
  params = Params()
  onroad_prev = None
  sock = ws.sock

  while True:
    onroad = params.get_bool("IsOnroad")
    if onroad != onroad_prev:
      onroad_prev = onroad

      if sock is not None:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT, 16000 if onroad else 0)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 7 if onroad else 30)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 7 if onroad else 10)
        sock.setsockopt(socket.TCP_KEEPIDLE, socket.TCP_KEEPCNT, 2 if onroad else 3)  # sometimes needed

    if end_event.wait(5):
      break


def backoff(retries: int) -> int:
  return random.randrange(0, min(128, int(2 ** retries)))


def main(exit_event: threading.Event = None):
  try:
    set_core_affinity([0, 1, 2, 3])
  except Exception:
    cloudlog.exception("failed to set core affinity")

  params = Params()
  dongle_id = params.get("DongleId", encoding='utf-8')
  UploadQueueCache.initialize(upload_queue)

  ws_uri = ATHENA_HOST + "/ws/v2/" + dongle_id
  api = Api(dongle_id)

  conn_start = None
  conn_retries = 0
  while exit_event is None or not exit_event.is_set():
    try:
      if conn_start is None:
        conn_start = time.monotonic()

      cloudlog.event("athenad.main.connecting_ws", ws_uri=ws_uri, retries=conn_retries)
      ws = create_connection(ws_uri,
                             cookie="jwt=" + api.get_token(),
                             enable_multithread=True,
                             timeout=30.0)
      cloudlog.event("athenad.main.connected_ws", ws_uri=ws_uri, retries=conn_retries,
                     duration=time.monotonic() - conn_start)
      conn_start = None

      conn_retries = 0
      cur_upload_items.clear()

      handle_long_poll(ws, exit_event)

    except (KeyboardInterrupt, SystemExit):
      break
    except (ConnectionError, TimeoutError, WebSocketException):
      conn_retries += 1
      params.remove("LastAthenaPingTime")
    except Exception:
      cloudlog.exception("athenad.main.exception")
      conn_retries += 1
      params.remove("LastAthenaPingTime")

    time.sleep(backoff(conn_retries))


if __name__ == "__main__":
  main()
