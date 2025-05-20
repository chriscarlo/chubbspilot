#!/usr/bin/env python3
"""
location_blocker_auto_check.py
=============================
Automated detector for the root-cause preventing liveLocationKalman from
reaching VALID.  Runs ~30 s and prints explicit PASS / FAIL for each of
these prerequisites:

 1. GNSS feed (gpsLocationExternal or gpsLocation) publishes and hasFix.
 2. IMU feed (accelerometer + gyroscope) publishes.
 3. liveCalibration reaches CALIBRATED.
 4. locationd process is running and healthy in managerState.

Usage:
  ./tools/debug/location_blocker_auto_check.py [duration_s]
"""
import sys
import time
from collections import Counter
from pathlib import Path

import cereal.messaging as messaging
from cereal import log
from openpilot.common.params import Params

RUN_SEC_DEFAULT = 30

# --- Determine available GNSS sockets -------------------------------------
GNSS_SOCKETS = [s for s in ("gpsLocationExternal", "gpsLocation") if messaging.topic_contains(s)]

CANDIDATE_TOPICS = [
    *GNSS_SOCKETS,
    "accelerometer", "gyroscope",
    "liveCalibration",
    "managerState",
]

# Filter for schema existence ------------------------------------------------
valid_topics = []
for t in CANDIDATE_TOPICS:
    try:
        messaging.new_message(t)
        valid_topics.append(t)
    except Exception:
        try:
            messaging.new_message(t, 0)
            valid_topics.append(t)
        except Exception:
            print(f"(info) topic '{t}' absent from schema – skipped")

sm = messaging.SubMaster(valid_topics)

# --- Counters --------------------------------------------------------------
counts = Counter()
gnss_fix_ok = Counter()
gnss_msgs = Counter()
imu_msgs = Counter()
calib_calibrated = 0
locationd_running = None

RUN_SEC = int(sys.argv[1]) if len(sys.argv) > 1 else RUN_SEC_DEFAULT
print(f"[location_blocker_auto_check] observing for {RUN_SEC}s (GNSS sockets: {GNSS_SOCKETS})…")

start = time.monotonic()
while time.monotonic() - start < RUN_SEC:
    sm.update(100)
    # GNSS
    for sock in GNSS_SOCKETS:
        if sock in sm.updated and sm.updated[sock]:
            gnss_msgs[sock] += 1
            msg = sm[sock]
            if msg.hasFix and msg.horizontalAccuracy < 1500 and msg.verticalAccuracy > 0:
                gnss_fix_ok[sock] += 1
    # IMU
    for imu in ("accelerometer", "gyroscope"):
        if imu in sm.updated and sm.updated[imu]:
            imu_msgs[imu] += 1
    # Calibration
    if "liveCalibration" in sm.updated and sm.updated["liveCalibration"]:
        if sm["liveCalibration"].calStatus == log.LiveCalibrationData.Status.calibrated:
            calib_calibrated += 1
    # locationd process
    if "managerState" in sm.updated and sm.updated["managerState"]:
        for p in sm["managerState"].processes:
            if p.name == "locationd":
                locationd_running = p.running and p.shouldBeRunning and p.exitCode == 0
    time.sleep(0.05)

# --- Summary ---------------------------------------------------------------
print("\n========= AUTO-CHECK SUMMARY =========")
# 1 GNSS
if sum(gnss_msgs.values()) == 0:
    print("GNSS feeds: NO messages ❌")
else:
    for sock in GNSS_SOCKETS:
        msgs = gnss_msgs[sock]
        good = gnss_fix_ok[sock]
        if msgs:
            ratio = good / msgs
            print(f"{sock}: {msgs} msgs, good fix {good} ({ratio:.0%})  →", "PASS" if good>0 else "FAIL")
# 2 IMU
imu_total = sum(imu_msgs.values())
print(f"IMU messages: {imu_total}  (accel {imu_msgs['accelerometer']} / gyro {imu_msgs['gyroscope']})")
print("→", "PASS ✅" if imu_total > 0 else "FAIL ❌ (no IMU)")
# 3 Calibration
if "liveCalibration" in valid_topics:
    print("liveCalibration CALIBRATED messages:", calib_calibrated)
    print("→", "PASS ✅" if calib_calibrated > 0 else "FAIL ❌ (never calibrated)")
else:
    print("liveCalibration topic absent from schema – skipped")
# 4 locationd process
if locationd_running is None:
    print("managerState not received – cannot verify locationd process ❓")
else:
    print("locationd running & healthy:", locationd_running)
    print("→", "PASS ✅" if locationd_running else "FAIL ❌ (locationd not running)")

print("\nDone.")