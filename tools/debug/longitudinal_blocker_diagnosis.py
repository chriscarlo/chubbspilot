#!/usr/bin/env python3
"""
longitudinal_blocker_diagnosis.py
================================
Runtime diagnostic tool that gathers definitive evidence for the common
root-causes preventing longitudinal control engagement:

H1  controlsState.valid toggles False (usually CAN drop-outs)
H2  CAN service not alive / wrong frequency
H3  liveLocationKalman never reaches Status.valid, keeping related
    messages invalid
H4  longitudinalPlan.valid remains False even though inputs are healthy

The script subscribes to a focused set of services, tracks their validity /
alive / frequency status for *N* seconds (default 120) and prints an easily
interpretable report proving or disproving every hypothesis above.

Usage:
  ./tools/debug/longitudinal_blocker_diagnosis.py [duration_sec]

Press Ctrl-C to stop early; the script will still output the collected
summary.
"""
import sys
import time
from collections import defaultdict

import cereal.messaging as messaging
from cereal import log, services

# ---------------------------- CONFIG -----------------------------------
DEFAULT_RUN_SEC = 120  # default observation window
SERVICES = [
    'carState',
    'controlsState',
    'liveLocationKalman',
    'longitudinalPlan',
    'can',
]

# ---------------------- DATA COLLECTION STRUCTS ------------------------
class Tracker:
    def __init__(self):
        self.reset()

    def reset(self):
        # Counters
        self.count_msgs = defaultdict(int)
        self.invalid_controlsState = 0
        self.controlsState_invalid_timestamps = []
        self.controlsState_valid_transitions = 0

        self.can_freq_bad = 0
        self.can_alive_bad = 0

        self.liveLoc_not_valid_counter = 0
        self.liveLoc_valid_counter = 0

        self.longPlan_invalid_counter = 0
        self.longPlan_valid_counter = 0

    # ------------------------------------------------------------------
    # Update helpers called per message or per-cycle
    # ------------------------------------------------------------------
    def handle_controlsState(self, is_valid, sm_time):
        if not is_valid:
            self.invalid_controlsState += 1
            self.controlsState_invalid_timestamps.append(sm_time)
        else:
            self.controlsState_valid_transitions += 1

    def handle_liveLocationKalman(self, msg):
        if msg.status == log.LiveLocationKalman.Status.valid:
            self.liveLoc_valid_counter += 1
        else:
            self.liveLoc_not_valid_counter += 1

    def handle_longitudinalPlan(self, is_valid):
        if is_valid:
            self.longPlan_valid_counter += 1
        else:
            self.longPlan_invalid_counter += 1

    def handle_can_health(self, sm):
        # Use SubMaster bookkeeping for alive/freq
        if not sm.alive['can']:
            self.can_alive_bad += 1
        if not sm.freq_ok['can']:
            self.can_freq_bad += 1

    # ------------------------------------------------------------------
    # Evaluation section
    # ------------------------------------------------------------------
    def evaluate(self):
        res = {}
        # H1: controlsState.valid toggles false
        res['H1_controlsState_invalid'] = self.invalid_controlsState > 0

        # H2: CAN service unhealthy
        res['H2_can_alive_bad'] = self.can_alive_bad > 0 or self.can_freq_bad > 0

        # H3: liveLocationKalman never valid
        res['H3_liveLoc_never_valid'] = self.liveLoc_valid_counter == 0

        # H4: longitudinalPlan still invalid with healthy inputs (approx)
        res['H4_longPlan_invalid_seen'] = self.longPlan_invalid_counter > 0

        return res

    def summary(self):
        res = self.evaluate()
        lines = []
        lines.append("\n========= DIAGNOSTIC SUMMARY =========")
        lines.append(f"Observed {sum(self.count_msgs.values())} total messages across {len(self.count_msgs)} services.")
        lines.append("")
        # H1
        if res['H1_controlsState_invalid']:
            lines.append(f"H1: controlsState.valid dropped FALSE {self.invalid_controlsState} times (CAN glitches suspected) ✅")
        else:
            lines.append("H1: controlsState.valid never dropped FALSE ❌")

        # H2
        if res['H2_can_alive_bad']:
            lines.append(f"H2: CAN service had {self.can_alive_bad} alive failures and {self.can_freq_bad} freq violations ✅")
        else:
            lines.append("H2: CAN service stayed alive & within expected frequency ❌")

        # H3
        if res['H3_liveLoc_never_valid']:
            lines.append("H3: liveLocationKalman NEVER reported Status.valid ✅")
        else:
            lines.append("H3: liveLocationKalman reached Status.valid at least once ❌")

        # H4
        lines.append(f"H4: longitudinalPlan.valid true {self.longPlan_valid_counter} times / false {self.longPlan_invalid_counter} times")
        return "\n".join(lines)

# ----------------------------- MAIN ------------------------------------

def main():
    run_sec = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RUN_SEC
    print(f"Running longitudinal blocker diagnosis for {run_sec} seconds...")

    sm = messaging.SubMaster(SERVICES, ignore_alive=[], ignore_valid=[])
    tracker = Tracker()

    start_t = time.monotonic()
    try:
        while time.monotonic() - start_t < run_sec:
            sm.update(100)
            cur_time = time.strftime('%H:%M:%S')

            # Process each service if updated
            if sm.updated['controlsState']:
                tracker.count_msgs['controlsState'] += 1
                tracker.handle_controlsState(sm.valid['controlsState'], cur_time)

            if sm.updated['liveLocationKalman']:
                tracker.count_msgs['liveLocationKalman'] += 1
                tracker.handle_liveLocationKalman(sm['liveLocationKalman'])

            if sm.updated['longitudinalPlan']:
                tracker.count_msgs['longitudinalPlan'] += 1
                tracker.handle_longitudinalPlan(sm.valid['longitudinalPlan'])

            if sm.updated['carState']:
                tracker.count_msgs['carState'] += 1

            if sm.updated['can']:
                tracker.count_msgs['can'] += 1

            # Even when not updated, check can health each cycle
            tracker.handle_can_health(sm)

            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nUser interrupted. Generating report...")
    finally:
        print(tracker.summary())

        # Detailed timestamps for controlsState invalid drops
        if tracker.controlsState_invalid_timestamps:
            print("\ncontrolsState.valid FALSE observed at:")
            for ts in tracker.controlsState_invalid_timestamps:
                print(f"  {ts}")

if __name__ == "__main__":
    main()