#!/usr/bin/env python3
"""
live_location_diagnosis.py
==========================
Diagnose why liveLocationKalman never transitions to Status.valid.

It watches location-related services for a short window (default 45 s)
and produces an actionable report:
  • Is locationd running?  (managerState)
  • Are we receiving GNSS data? (ubloxGnss, qcomGnss, gpsNMEA)
  • Are inertial sensors publishing? (sensorEvents / accelerometer / gyroscope)
  • What exact status/sub-flags does liveLocationKalman report over time?

Usage:
  ./tools/debug/live_location_diagnosis.py [duration_s]

Example output:
  liveLocationKalman timeline
    00:00  status=init gpsOK=False sensorsOK=False posenetOK=False
    00:12  status=valid gpsOK=True  ...

At the end the script prints explicit blockers (e.g. "No GNSS messages at
all", "IMU stream missing", "gpsOK never True", ...).
"""
import sys
import time
from collections import defaultdict, Counter

import cereal.messaging as messaging
from cereal import log

# Observation parameters
RUN_SEC_DEFAULT = 45
SERVICES = [
    'liveLocationKalman',
    'ubloxGnss', 'qcomGnss', 'gpsNMEA', 'gpsLocationExternal',
    'sensorEvents', 'accelerometer', 'gyroscope',
    'managerState',
]

# Helper to readable enum
_loc_status_names = {
    int(log.LiveLocationKalman.Status.init): 'init',
    int(log.LiveLocationKalman.Status.valid): 'valid',
    int(log.LiveLocationKalman.Status.invalid): 'invalid',
}

def main():
    run_sec = int(sys.argv[1]) if len(sys.argv) > 1 else RUN_SEC_DEFAULT
    print(f"[live_location_diagnosis] Watching for {run_sec}s…")

    sm = messaging.SubMaster(SERVICES)

    # Counters & samples
    svc_counts = Counter()
    imu_counts = Counter()
    gnss_counts = Counter()

    loc_timeline = []  # (t_offset, status, gpsOK, sensorsOK, posenetOK)

    start = time.monotonic()
    try:
        while time.monotonic() - start < run_sec:
            sm.update(100)
            now = time.monotonic()
            t_off = now - start

            # count service updates
            for s in SERVICES:
                if sm.updated[s]:
                    svc_counts[s] += 1

            # record GNSS/IMU granular counts
            if sm.updated['ubloxGnss']:
                gnss_counts['ubloxGnss'] += 1
            if sm.updated['qcomGnss']:
                gnss_counts['qcomGnss'] += 1
            if sm.updated['gpsNMEA']:
                gnss_counts['gpsNMEA'] += 1
            if sm.updated['gpsLocationExternal']:
                gnss_counts['gpsLocationExternal'] += 1

            if sm.updated['sensorEvents']:
                imu_counts['sensorEvents'] += 1
            if sm.updated['accelerometer']:
                imu_counts['accelerometer'] += 1
            if sm.updated['gyroscope']:
                imu_counts['gyroscope'] += 1

            # log every 1s the location status
            if sm.updated['liveLocationKalman']:
                msg = sm['liveLocationKalman']
                status = _loc_status_names.get(int(msg.status), str(msg.status))
                loc_timeline.append((t_off, status, msg.gpsOK, msg.sensorsOK, msg.posenetOK))

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("Interrupted, summarizing…")

    # ---------------- Summary -------------
    print("\n========= LOCATION DIAGNOSTIC SUMMARY =========")
    # Process health
    if sm.updated['managerState']:
        procs = {p.name: p for p in sm['managerState'].processes}
        loc_proc = procs.get('locationd')
        if loc_proc is None:
            print("locationd process NOT present in managerState ❌")
        else:
            running = loc_proc.running and loc_proc.shouldBeRunning and loc_proc.exitCode == 0
            txt = "running" if running else f"NOT running (running={loc_proc.running}, exitCode={loc_proc.exitCode})"
            print(f"locationd process state: {txt}")
    else:
        print("managerState not received – can't verify locationd process")

    # GNSS feeds
    total_gnss = sum(gnss_counts.values())
    if total_gnss == 0:
        print("No GNSS messages received at all (ubloxGnss/qcomGnss/gpsNMEA/gpsLocationExternal) ❌")
    else:
        for k, v in gnss_counts.items():
            print(f"{k}: {v} msgs")

    # IMU feeds
    total_imu = sum(imu_counts.values())
    if total_imu == 0:
        print("No IMU / sensorEvents messages received ❌ – check loggerd/ sensors")
    else:
        for k, v in imu_counts.items():
            print(f"{k}: {v} msgs")

    # liveLocationKalman stats
    if svc_counts['liveLocationKalman'] == 0:
        print("liveLocationKalman never published any message ❌")
    else:
        statuses = Counter([s for _, s, *_ in loc_timeline])
        print("liveLocationKalman message count:", svc_counts['liveLocationKalman'])
        print("Status counts:")
        for st, cnt in statuses.items():
            print(f"  {st}: {cnt}")
        if 'valid' in statuses:
            print("→ liveLocationKalman DID reach valid ✅")
        else:
            print("→ liveLocationKalman never reached valid ❌")

    # Print short timeline
    print("\nTimeline (first 30 samples):")
    for t_off, st, gps, sens, pose in loc_timeline[:30]:
        print(f" +{t_off:5.1f}s  status={st:<6} gpsOK={gps} sensorsOK={sens} posenetOK={pose}")

    print("\nEnd of report – use the above to pinpoint missing inputs.")

if __name__ == '__main__':
    main()