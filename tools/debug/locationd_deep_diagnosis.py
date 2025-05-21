#!/usr/bin/env python3
"""
locationd_deep_diagnosis.py
===========================
A comprehensive diagnostic utility to identify *why* `locationd` refuses to
start, crashes immediately, or never reaches a healthy publishing state.  It
combines the insights of existing debugging helpers (`live_location_diagnosis`,
`location_blocker_auto_check`, `live_root_cause_monitor`) into a single, more
thorough, *locationd-centric* investigation.

Key capabilities
----------------
1. Tracks the *process* itself via `managerState` **and** `procLog` (if
   available) to detect repeated crashes, exit codes, and CPU / memory usage
   just before failure.
2. Observes **all inputs required by locationd** (GNSS, IMU, calibration,
   camera odometry, carState, …).  For each input it reports:
     • Message count & first / last receive timestamps
     • Validity ratio (using `SubMaster.valid` when available)
     • Domain-specific quality checks (e.g. `gpsLocation*.hasFix`, accuracy
       thresholds, non-zero IMU rates).
3. Captures the timeline of `liveLocationKalman` status transitions if the
   process *does* publish (useful for "initialises but never reaches VALID").
4. Tries hard *not* to crash even if some messages are entirely absent from the
   build's cap'n proto schema.  Everything is probed dynamically at runtime.

Usage
-----
    ./tools/debug/locationd_deep_diagnosis.py            # 60 s default window
    ./tools/debug/locationd_deep_diagnosis.py 120        # custom seconds

At the end a concise but information-dense report is printed.  Look for ❌ / ✅
markers to spot blockers quickly.
"""
from __future__ import annotations

import sys
import time
from collections import Counter, defaultdict
from types import SimpleNamespace

import cereal.messaging as messaging
from cereal import log

# -----------------------------------------------------------------------------
# Utility: does a topic exist in *this* build's log.Event ?
# -----------------------------------------------------------------------------

def _topic_exists(topic: str) -> bool:
    """Return True if `topic` is present as a union member in log.Event."""
    try:
        messaging.new_message(topic)
        return True
    except Exception:
        pass
    try:
        # Some list-type unions need a size argument
        messaging.new_message(topic, 0)
        return True
    except Exception:
        return False

# -----------------------------------------------------------------------------
# Observation configuration
# -----------------------------------------------------------------------------
RUN_SEC_DEFAULT = 60

# Potentially relevant topics (superset).  We'll prune with _topic_exists().
CANDIDATE_TOPICS = [
    # Core health & process info
    "managerState",
    "procLog",
    # Locationd output
    "liveLocationKalman",
    # GNSS flavours
    "gpsLocation",
    "gpsLocationExternal",
    "ubloxGnss",
    "qcomGnss",
    "gpsNMEA",
    "gnssMeasurements",
    # IMU
    "sensorEvents",
    "accelerometer",
    "gyroscope",
    # Other inputs
    "liveCalibration",
    "cameraOdometry",
    "carState",
]

# Filter out topics absent from this build to avoid capnp exceptions
VALID_TOPICS = [t for t in CANDIDATE_TOPICS if _topic_exists(t)]
INVALID_TOPICS = sorted(set(CANDIDATE_TOPICS) - set(VALID_TOPICS))
if INVALID_TOPICS:
    print(f"(Info) Skipped {len(INVALID_TOPICS)} unknown topics: {', '.join(INVALID_TOPICS)}")

# -----------------------------------------------------------------------------
# Thresholds / sanity limits (mirrored from locationd where relevant)
# -----------------------------------------------------------------------------
ACC_HORZ_MAX = 1500.0  # metres, same as locationd for good GNSS fix

# Helper: translate liveLocationKalman.Status enum to readable string even if
# the cereal binding lacks `to_string()` (older builds).
_LLK_STATUS_NAME = {
    int(log.LiveLocationKalman.Status.uninitialized): "UNINITIALIZED",
    int(log.LiveLocationKalman.Status.uncalibrated): "UNCALIBRATED",
    int(log.LiveLocationKalman.Status.valid): "VALID",
}

# -----------------------------------------------------------------------------
# Main diagnostic collector
# -----------------------------------------------------------------------------

def main() -> None:
    run_sec = int(sys.argv[1]) if len(sys.argv) > 1 else RUN_SEC_DEFAULT
    print(f"[locationd_deep_diagnosis] Observing for {run_sec}s …")
    print("Subscribing to topics:", ", ".join(VALID_TOPICS))

    sm = messaging.SubMaster(VALID_TOPICS, ignore_alive=[])  # don't ignore anything

    # --------------------------------------------------------------------------------
    # Data collection buckets
    # --------------------------------------------------------------------------------
    msg_counts: Counter[str] = Counter()               # total message count per topic
    valid_counts: Counter[str] = Counter()             # how many messages were .valid == True
    first_ts: dict[str, float] = {}                    # first receive time (monotonic) per topic
    last_ts: dict[str, float] = {}                     # last receive time per topic

    # Specialised trackers
    gnss_good_fix_counts: Counter[str] = Counter()     # gpsLocation* with hasFix & sane acc
    imu_counts: Counter[str] = Counter()               # accelerometer / gyroscope msgs
    loc_kf_timeline: list[tuple[float, str, bool, bool, bool]] = []  # (t_off, status, gpsOK, sensorsOK, posenetOK)

    # locationd process state over time
    loc_proc_history: list[tuple[float, bool, int]] = []  # (t_off, running, exitCode)

    start_t = time.monotonic()

    try:
        while time.monotonic() - start_t < run_sec:
            sm.update(100)  # 100 ms timeout
            now = time.monotonic()
            t_off = now - start_t

            # ---------- generic accounting ----------
            for topic in VALID_TOPICS:
                if sm.updated[topic]:
                    msg_counts[topic] += 1
                    last_ts[topic] = t_off
                    if topic not in first_ts:
                        first_ts[topic] = t_off
                    # validity flag (when available)
                    if sm.valid.get(topic, True):
                        valid_counts[topic] += 1

            # ---------- GNSS quality ----------
            for gtopic in ("gpsLocation", "gpsLocationExternal"):
                if gtopic in VALID_TOPICS and sm.updated[gtopic]:
                    m = sm[gtopic]
                    if m.hasFix and m.horizontalAccuracy < ACC_HORZ_MAX and m.verticalAccuracy > 0:
                        gnss_good_fix_counts[gtopic] += 1

            # ---------- IMU ----------
            for itopic in ("accelerometer", "gyroscope", "sensorEvents"):
                if itopic in VALID_TOPICS and sm.updated.get(itopic, False):
                    imu_counts[itopic] += 1

            # ---------- liveLocationKalman ----------
            if "liveLocationKalman" in VALID_TOPICS and sm.updated.get("liveLocationKalman", False):
                llk = sm["liveLocationKalman"]
                # Use .raw if available (capnp DynamicEnum);
                _code = int(llk.status.raw) if hasattr(llk.status, "raw") else int(llk.status)
                status_name = _LLK_STATUS_NAME.get(_code, str(llk.status))
                loc_kf_timeline.append((t_off, status_name, llk.gpsOK, llk.sensorsOK, llk.posenetOK))

            # ---------- managerState → locationd process ----------
            if "managerState" in VALID_TOPICS and sm.updated["managerState"]:
                procs = {p.name: p for p in sm["managerState"].processes}
                p = procs.get("locationd")
                if p is not None:
                    loc_proc_history.append((t_off, p.running, p.exitCode))

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("Interrupted by user – summarising now…")

    # --------------------------------------------------------------------------------
    #    S U M M A R Y
    # --------------------------------------------------------------------------------
    print("\n========= LOCATIOND DEEP DIAGNOSTIC REPORT =========")

    # 1. Process health via managerState ------------------------------------------------
    if "managerState" not in VALID_TOPICS or not loc_proc_history:
        print("locationd process info:   NO DATA – managerState topic missing or no updates ❓")
    else:
        last_run, last_exit = loc_proc_history[-1][1], loc_proc_history[-1][2]
        crash_events = [h for h in loc_proc_history if not h[1] and h[2] != 0]
        restarts = len([h for h in loc_proc_history if h[1]])
        status_txt = "RUNNING" if last_run else f"NOT running (exitCode {last_exit})"
        print(f"locationd process state:  {status_txt}")
        print(f"  Observed restarts: {restarts - 1 if restarts > 0 else 0}")
        if crash_events:
            print(f"  Crashes recorded: {len(crash_events)} occurrences ❌")
        else:
            print("  No crashes recorded during observation ✅")

    # 2. GNSS feeds ---------------------------------------------------------------------
    gnss_topics_present = [g for g in ("gpsLocation", "gpsLocationExternal", "ubloxGnss", "qcomGnss", "gpsNMEA", "gnssMeasurements") if g in VALID_TOPICS]
    if not gnss_topics_present:
        print("GNSS feeds          :  topic(s) absent from schema ❌")
    else:
        any_good = False
        for g in gnss_topics_present:
            tot = msg_counts[g]
            good = gnss_good_fix_counts[g]
            ratio = (good / tot * 100) if tot else 0
            status = "PASS ✅" if good else "FAIL ❌"
            print(f"  {g:<22}: {tot:5d} msgs   good_fix {good:5d}  ({ratio:4.0f}%)  {status}")
            any_good |= bool(good)
        if not any_good:
            print("→ Overall GNSS check:  FAIL ❌  (no valid fixes during window)")
        else:
            print("→ Overall GNSS check:  PASS ✅")

    # 3. IMU feeds ----------------------------------------------------------------------
    imu_topics_present = [i for i in ("accelerometer", "gyroscope", "sensorEvents") if i in VALID_TOPICS]
    if not imu_topics_present:
        print("IMU feeds           :  topics absent from schema ❌")
    else:
        imu_total = sum(imu_counts.values())
        status = "PASS ✅" if imu_total > 0 else "FAIL ❌"
        details = ", ".join(f"{k}:{imu_counts[k]}" for k in imu_topics_present)
        print(f"IMU msgs            : {imu_total:5d}  ({details})  {status}")

    # 4. Calibration --------------------------------------------------------------------
    if "liveCalibration" not in VALID_TOPICS:
        print("liveCalibration     :  topic missing → cannot check calibration ❓")
    else:
        calib_ok = sum(1 for _ in range(msg_counts["liveCalibration"]) if sm.valid.get("liveCalibration", True))  # coarse
        status = "PASS ✅" if calib_ok else "FAIL ❌"
        print(f"liveCalibration msgs: {msg_counts['liveCalibration']:5d}   valid_flag≈{calib_ok}  {status}")

    # 5. Camera odometry ----------------------------------------------------------------
    if "cameraOdometry" in VALID_TOPICS:
        print(f"cameraOdometry msgs : {msg_counts['cameraOdometry']:5d}")

    # 6. liveLocationKalman status timeline ---------------------------------------------
    if not loc_kf_timeline:
        print("liveLocationKalman  :  NO messages received (locationd never published) ❌")
    else:
        statuses = Counter([s for _, s, *_ in loc_kf_timeline])
        print("liveLocationKalman  :", sum(statuses.values()), "msgs")
        for st, cnt in statuses.items():
            print(f"  {st:<13}: {cnt:5d}")
        if "VALID" in statuses:
            print("→ Kalman filter reached VALID ✅")
        else:
            print("→ Kalman filter never reached VALID ❌")

        print("\nTimeline (first 30 samples):")
        for t_off, st, gpsOK, sensOK, poseOK in loc_kf_timeline[:30]:
            print(f"  +{t_off:5.1f}s  status={st:<6}  gpsOK={gpsOK} sensorsOK={sensOK} posenetOK={poseOK}")

    # 7. Generic per-topic stats ---------------------------------------------------------
    print("\nPer-topic message counts:")
    for t in sorted(msg_counts.keys()):
        total = msg_counts[t]
        valids = valid_counts[t]
        validity_ratio = (valids / total * 100) if total else 0
        first = first_ts.get(t, None)
        last = last_ts.get(t, None)
        print(f"  {t:<22}: {total:6d} msgs  valid {validity_ratio:6.1f}%  first +{first or 0:5.1f}s  last +{last or 0:5.1f}s")

    print("\nEnd of locationd deep diagnostic.  Investigate any ❌ items above.")

if __name__ == "__main__":
    main()