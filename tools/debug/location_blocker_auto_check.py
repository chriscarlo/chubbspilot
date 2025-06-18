#!/usr/bin/env python3
"""
location_blocker_auto_check.py
==============================
End-to-end diagnostic for the prerequisites that must be satisfied for
liveLocationKalman → Status.VALID.

It observes the data bus for a short window (default 30 s) and prints
PASS / FAIL for:
  1. At least one GNSS source publishes and has a valid fix.
  2. IMU data (accelerometer & gyroscope) is flowing.
  3. liveCalibration reaches Status.CALIBRATED.
  4. locationd process is running & healthy per managerState.

The script dynamically removes any topic that does not exist in the
current log schema so it cannot crash on missing union fields.

Usage:
  ./tools/debug/location_blocker_auto_check.py  [duration_sec]
"""
import sys
import time
from collections import Counter, defaultdict
from types import SimpleNamespace

import cereal.messaging as messaging
from cereal import log

# ---------------------------------------------------------------------------
# Helper: probe whether a cap'n proto union member exists in log.Event
# ---------------------------------------------------------------------------

def topic_exists(topic: str) -> bool:
    """Return True if `topic` is present as a union member in log.Event."""
    try:
        messaging.new_message(topic)
        return True
    except Exception:
        pass
    try:
        messaging.new_message(topic, 0)  # list fields need size
        return True
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Decide which GNSS topics are available in THIS build
# ---------------------------------------------------------------------------

GNSS_TOPICS = [t for t in ("gpsLocationExternal", "gpsLocation") if topic_exists(t)]
IMU_TOPICS  = [t for t in ("accelerometer", "gyroscope") if topic_exists(t)]

BASE_TOPICS = ["liveCalibration", "managerState"]
ALL_TOPICS  = GNSS_TOPICS + IMU_TOPICS + BASE_TOPICS

# ---------------------------------------------------------------------------
# Observation window
# ---------------------------------------------------------------------------
RUN_SEC = int(sys.argv[1]) if len(sys.argv) > 1 else 30
print("[location_blocker_auto_check] observing for", RUN_SEC, "s …")
print("  GNSS topics :", GNSS_TOPICS or "<none>")
print("  IMU topics  :", IMU_TOPICS  or "<none>")

# ---------------------------------------------------------------------------
# SubMaster setup
# ---------------------------------------------------------------------------
sm = messaging.SubMaster(ALL_TOPICS)

# Counters
c_gnss_total  = Counter()   # msgs per GNSS socket
c_gnss_good   = Counter()   # msgs with hasFix & sane accuracy
c_imu         = Counter()   # msgs per IMU topic
calib_ok      = 0           # liveCalibration CALIBRATED count
locationd_ok  = None        # None=unknown, bool otherwise

# Sane-accuracy thresholds (same as locationd)
ACC_HORZ_MAX = 1500.0  # metres

start_t = time.monotonic()
while time.monotonic() - start_t < RUN_SEC:
    sm.update(100)  # 100-ms timeout

    # GNSS handling
    for g in GNSS_TOPICS:
        if sm.updated.get(g):
            msg = sm[g]
            c_gnss_total[g] += 1
            if msg.hasFix and msg.horizontalAccuracy < ACC_HORZ_MAX and msg.verticalAccuracy > 0:
                c_gnss_good[g] += 1

    # IMU handling
    for imu in IMU_TOPICS:
        if sm.updated.get(imu):
            c_imu[imu] += 1

    # Calibration status
    if "liveCalibration" in sm.updated and sm.updated["liveCalibration"]:
        if sm["liveCalibration"].calStatus == log.LiveCalibrationData.Status.calibrated:
            calib_ok += 1

    # locationd process health
    if "managerState" in sm.updated and sm.updated["managerState"]:
        for p in sm["managerState"].processes:
            if p.name == "locationd":
                locationd_ok = bool(p.running and p.shouldBeRunning and p.exitCode == 0)
                break

    time.sleep(0.05)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n========= LOCATION INPUT AUTO-CHECK =========")

# 1. GNSS
if not GNSS_TOPICS:
    print("GNSS feed :  topic absent from schema ❌")
else:
    any_good = False
    for g in GNSS_TOPICS:
        tot  = c_gnss_total[g]
        good = c_gnss_good[g]
        ratio = (good / tot * 100) if tot else 0
        status = "PASS ✅" if good else "FAIL ❌"
        print(f"{g:<22}: {tot:4d} msgs   good_fix {good:4d}  ({ratio:3.0f}%)  {status}")
        any_good |= bool(good)
    if not any_good:
        print("→ Overall GNSS check:  FAIL ❌  (no valid fixes)")

# 2. IMU
if not IMU_TOPICS:
    print("IMU feed  :  topics absent from schema ❌")
else:
    imu_total = sum(c_imu.values())
    status = "PASS ✅" if imu_total > 0 else "FAIL ❌"
    details = ", ".join(f"{k}:{c_imu[k]}" for k in IMU_TOPICS)
    print(f"IMU msgs  : {imu_total:4d}  ({details})  {status}")

# 3. Calibration
if "liveCalibration" not in ALL_TOPICS:
    print("liveCalibration topic missing → cannot check calibration ❓")
else:
    status = "PASS ✅" if calib_ok else "FAIL ❌"
    print(f"liveCalibration CALIBRATED msgs: {calib_ok}  {status}")

# 4. locationd process
if locationd_ok is None:
    print("managerState not received → locationd state unknown ❓")
else:
    print("locationd process running & healthy:", locationd_ok, "PASS ✅" if locationd_ok else "FAIL ❌")

print("\nDone.")