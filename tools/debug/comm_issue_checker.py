#!/usr/bin/env python3
"""
comm_issue_checker.py – run from an SSH shell when the HUD shows
"Communication Issue Between Processes".  It subscribes to (almost) every
cereal service, watches them for a short period, and prints the services that
would cause `SubMaster.all_checks()` to fail:

• not_valid   – haven't seen a message yet
• not_alive   – last message older than expected (5× period)
• freq_low    – average frequency lower than service spec (66 % threshold)

Example:
    ./tools/debug/comm_issue_checker.py -t 15
"""
from __future__ import annotations

import argparse
import time
from typing import Dict, List

import cereal.messaging as messaging
from cereal import services

THRESH_FACTOR = 0.66  # below 66 % of nominal freq counts as too slow
ALIVE_FACTOR = 5.0    # consider dead if last packet older than 5× period


def build_argparser():
    p = argparse.ArgumentParser(description="Diagnose services causing commIssue")
    p.add_argument("-t", "--time", type=float, default=10.0, help="Seconds to sample (default: 10)")
    p.add_argument("-f", "--filter", nargs="*", help="If given, only monitor these services")
    return p


def main(duration: float, filter_services: List[str] | None):
    monitored = filter_services or list(services.SERVICE_LIST.keys())
    sm = messaging.SubMaster(monitored)
    counters: Dict[str, int] = {s: 0 for s in monitored}
    first_ts: Dict[str, float] = {s: 0.0 for s in monitored}
    last_ts: Dict[str, float] = {s: 0.0 for s in monitored}

    start = time.monotonic()
    while time.monotonic() - start < duration:
        sm.update(0)
        now = time.monotonic()
        for s in monitored:
            if sm.updated[s]:
                counters[s] += 1
                if first_ts[s] == 0.0:
                    first_ts[s] = now
                last_ts[s] = now

    # analyse
    offenders = []
    for s in monitored:
        spec = services.SERVICE_LIST[s]
        exp_freq = spec.frequency if spec.frequency > 0 else 1.0  # treat 0-Hz streams as 1Hz
        run_time = max(last_ts[s] - first_ts[s], 1e-6)
        avg_freq = counters[s] / run_time if run_time > 0 else 0.0
        alive_age = time.monotonic() - last_ts[s]
        valid = sm.valid[s]

        not_valid = not valid
        not_alive = alive_age > ALIVE_FACTOR * (1.0 / exp_freq)
        freq_low = avg_freq < THRESH_FACTOR * exp_freq

        if not_valid or not_alive or freq_low:
            offenders.append((s, avg_freq, not_valid, not_alive, freq_low))

    if not offenders:
        print("All monitored services look healthy – no obvious culprit in the sample window.")
        return

    print("\nPossible problematic services (sorted by worst average freq):")
    offenders.sort(key=lambda x: x[1])
    print(f"{'service':25s}  avgHz   not_valid  not_alive  freq_low")
    for s, f, nv, na, fl in offenders:
        print(f"{s:25s}  {f:6.1f}   {str(nv):9s}  {str(na):9s}  {str(fl):8s}")


if __name__ == "__main__":
    args = build_argparser().parse_args()
    main(args.time, args.filter)