"""
Trigger service for Azure Protobuf map downloader.
Responds to manual trigger param. Automatic checks are disabled.
"""

import time
from datetime import datetime

from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
import openpilot.system.sentry as sentry
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.frogpilot.frogpilot_utilities import update_maps

# Automatic check interval is defined but not used
UPDATE_CHECK_INTERVAL_SECONDS = 60 * 60 * 24 * 30  # 30 days

def main():
  """Main loop for map downloader trigger service."""
  cloudlog.info("Starting map downloader trigger service (mapd_py.downloader) - MANUAL TRIGGER ONLY")
  sentry.init(sentry.SentryProject.SELFDRIVE)

  params = Params()
  # Ratekeeper initialized but not used for scheduling checks
  rk = Ratekeeper(1.0 / UPDATE_CHECK_INTERVAL_SECONDS, print_delay_threshold=None)

  while True:
    check_triggered = False
    try:
      # Check for manual trigger
      if params.get_bool("TriggerMapDownloadCheck"):
        cloudlog.info("Map download manually triggered.")
        params.put_bool("TriggerMapDownloadCheck", False)
        check_triggered = True
        update_maps(datetime.now())
        # Reset ratekeeper time even on manual trigger to potentially allow
        # re-enabling scheduled checks later without immediate trigger.
        rk._last_monitor_time = time.monotonic()
        rk._next_frame_time = rk._last_monitor_time + rk._interval

      # Keep the scheduled check commented out
      # if rk.keep_time() and not check_triggered:
      #  cloudlog.info(f"Scheduled map download check at {datetime.now()}")
      #  update_maps(datetime.now())

      # Sleep only if no manual trigger happened in this iteration
      if not check_triggered:
        time.sleep(1)

    except Exception as e:
      cloudlog.exception("mapd_py.downloader.service_loop_exception")
      sentry.capture_exception(e)
      # Longer sleep on exception
      time.sleep(60)


if __name__ == "__main__":
  main()
