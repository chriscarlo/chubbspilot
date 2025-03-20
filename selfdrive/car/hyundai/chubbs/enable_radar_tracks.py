from openpilot.selfdrive.car.isotp_parallel_query import IsoTpParallelQuery
from openpilot.common.swaglog import cloudlog


EXT_DIAG_REQUEST = b'\x10\x07'
EXT_DIAG_RESPONSE = b'\x50\x07'

WRITE_DATA_REQUEST = b'\x2e'
WRITE_DATA_RESPONSE = b'\x68'

RADAR_TRACKS_CONFIG = b"\x00\x00\x00\x01\x00\x01"


def enable_radar_tracks(logcan, sendcan, bus=0, addr=0x7d0, config_data_id=b'\x01\x42', timeout=0.1, retry=10, debug=False):
  cloudlog.warning("radar_tracks: enabling ...")

  for i in range(retry):
    try:
      cloudlog.info(f"radar_tracks: attempt {i+1}/{retry} to enter extended diagnostic mode")
      query = IsoTpParallelQuery(sendcan, logcan, bus, [addr], [EXT_DIAG_REQUEST], [EXT_DIAG_RESPONSE], debug=debug)

      for _, _ in query.get_data(timeout).items():
        cloudlog.warning("radar_tracks: reconfigure radar to output radar points ...")

        try:
          query = IsoTpParallelQuery(sendcan, logcan, bus, [addr],
                                   [WRITE_DATA_REQUEST + config_data_id + RADAR_TRACKS_CONFIG],
                                   [WRITE_DATA_RESPONSE], debug=debug)
          query.get_data(timeout)

          cloudlog.warning("radar_tracks: successfully enabled")
          return True
        except Exception as e:
          cloudlog.error(f"radar_tracks: error during write data: {e}")
          # Continue to next retry iteration

    except Exception as e:
      cloudlog.error(f"radar_tracks exception: {e}")

    cloudlog.error(f"radar_tracks retry ({i + 1}) ...")
    # Add a small delay between retries to give the system time to recover
    import time
    time.sleep(0.5)

  cloudlog.error(f"radar_tracks: failed after {retry} attempts")
  return False


if __name__ == "__main__":
  import time
  import cereal.messaging as messaging
  sendcan = messaging.pub_sock('sendcan')
  logcan = messaging.sub_sock('can')
  time.sleep(1)

  enabled = enable_radar_tracks(logcan, sendcan, bus=0, addr=0x7d0, config_data_id=b'\x01\x42', timeout=0.1, debug=False)
  print(f"enabled: {enabled}")

