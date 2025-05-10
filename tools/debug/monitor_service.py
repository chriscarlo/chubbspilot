#!/usr/bin/env python3
"""
monitor_service.py – small CLI helper to watch the update rate and validity of one
or more cereal/messaging services in real-time.  This is useful when you're
getting the 'Communication Issue Between Processes' alert and need to verify
whether a particular pub/sub stream is alive and running at the expected
frequency.

Example – watch `frogpilotPlan` for 60 seconds:

    ./tools/debug/monitor_service.py frogpilotPlan -d 60

You can also monitor multiple services at once:

    ./tools/debug/monitor_service.py frogpilotPlan controlsState modelV2
"""
from __future__ import annotations

import argparse
import time
import sys
from typing import List

import cereal.messaging as messaging


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Monitor messaging update rates for given services")
    p.add_argument("service", nargs="+", help="Name(s) of the service(s) to monitor (e.g. frogpilotPlan)")
    p.add_argument("-d", "--duration", type=float, default=30.0,
                   help="How many seconds to run (default: 30)")
    p.add_argument("-r", "--refresh", type=float, default=0.5,
                   help="How often to print status rows in seconds (default: 0.5)")
    return p


def monitor(services: List[str], duration: float, refresh: float) -> None:
    sm = messaging.SubMaster(services)
    counters = {s: 0 for s in services}
    start_ts = time.monotonic()
    next_print = start_ts

    try:
        while True:
            sm.update(0)
            now = time.monotonic()

            # increment counters for any service that was updated this cycle
            for s in services:
                if sm.updated[s]:
                    counters[s] += 1

            # time to print a status line?
            if now >= next_print:
                elapsed = max(now - start_ts, 1e-3)
                status_parts = []
                for s in services:
                    freq = counters[s] / elapsed
                    status_parts.append(f"{s:20s} | {freq:6.1f} Hz | valid={sm.valid[s]} | alive={sm.alive[s]}")
                print(" \t".join(status_parts))
                next_print = now + refresh

            if duration > 0 and (now - start_ts) >= duration:
                break
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(0)


if __name__ == "__main__":
    args = build_argparser().parse_args()
    monitor(args.service, args.duration, args.refresh)