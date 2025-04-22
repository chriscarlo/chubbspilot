"""
Trigger service for Azure Protobuf map downloader.
Periodically checks for updates or responds to manual trigger param.
"""

import os
import shutil
import time
from datetime import datetime

from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
import openpilot.system.sentry as sentry
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.frogpilot.frogpilot_utilities import update_maps

UPDATE_CHECK_INTERVAL_SECONDS = 60 * 15  # 15 minutes


def main():
  """Main loop for map downloader trigger service."""
  cloudlog.info("Starting map downloader trigger service (mapd_py.downloader)")
  sentry.init(sentry.SentryProject.SELFDRIVE)

  params = Params()
  rk = Ratekeeper(1.0 / UPDATE_CHECK_INTERVAL_SECONDS, print_delay_threshold=None)

  while True:
    check_triggered = False
    try:
      if params.get_bool("TriggerMapDownloadCheck"):
        cloudlog.info("Map download manually triggered.")
        params.put_bool("TriggerMapDownloadCheck", False)
        check_triggered = True
        update_maps(datetime.now())
        rk.monitor_time = time.monotonic()
        rk.last_monitor_time = rk.monitor_time

      if rk.keep_time() and not check_triggered:
        cloudlog.info(f"Scheduled map download check at {datetime.now()}")
        update_maps(datetime.now())
      elif not check_triggered:
        time.sleep(1)

    except Exception as e:
      cloudlog.exception("mapd_py.downloader.service_loop_exception")
      sentry.capture_exception(e)
      time.sleep(60)


if __name__ == "__main__":
  main()
