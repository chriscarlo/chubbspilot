#!/usr/bin/env python3
import argparse
import time
from collections import defaultdict

import cereal.messaging as messaging
from cereal import services
from openpilot.common.params import Params

# Thresholds from comm_issue_checker.py
THRESH_FACTOR = 0.66  # below 66 % of nominal freq counts as too slow
ALIVE_FACTOR = 5.0    # consider dead if last packet older than 5× period

# Services that locationd depends on (directly for its inputsOK check)
LOCATIOND_INPUTS = ["cameraOdometry", "liveCalibration", "accelerometer", "gyroscope"]
# Add GPS service dynamically

PARAMSD_INPUTS = ["carState", "liveCalibration", "controlsState"]


def get_nominal_freq(service_name):
    spec = services.SERVICE_LIST[service_name]
    return spec.frequency if spec.frequency > 0 else 1.0 # Treat 0Hz as 1Hz for checks

def get_status_flags(sm, service_name, avg_freq, last_rx_time):
    nominal_freq = get_nominal_freq(service_name)

    is_valid = sm.valid[service_name]

    time_since_last_rx = time.monotonic() - last_rx_time if last_rx_time > 0 else float('inf')
    is_alive = time_since_last_rx <= ALIVE_FACTOR * (1.0 / nominal_freq if nominal_freq > 0 else float('inf'))

    freq_low = avg_freq < THRESH_FACTOR * nominal_freq

    health_str = []
    ok = True

    if not is_valid:
        health_str.append("NOT_VALID")
        ok = False
    if not is_alive:
        health_str.append("NOT_ALIVE")
        ok = False
    if freq_low and sm.frame > 100: # Give some time for freq to stabilize
        health_str.append(f"FREQ_LOW({avg_freq:.1f}<{nominal_freq*THRESH_FACTOR:.1f})")
        ok = False

    return (", ".join(health_str) if not ok else "OK", ok)

def main():
    parser = argparse.ArgumentParser(description="Real-time health monitor for Cereal services.")
    parser.add_argument("-d", "--duration", type=float, default=0,
                        help="How many seconds to run (default: 0, for indefinite)")
    parser.add_argument("-r", "--refresh", type=float, default=0.5,
                        help="How often to print status in seconds (default: 0.5)")
    args = parser.parse_args()

    params = Params()
    gps_service = "gpsLocationExternal" if params.get_bool("UbloxAvailable") else "gpsLocation"

    locationd_inputs_with_gps = LOCATIOND_INPUTS + [gps_service]

    core_services = [
        "liveLocationKalman",
        "liveParameters",
        "cameraOdometry",
        "liveCalibration",
        "accelerometer",
        "gyroscope",
        gps_service,
        "carState",
        "controlsState",
        "modelV2",
        "pandaStates", # Good for general CAN health
        "managerState", # To see if processes are running
    ]
    # Ensure no duplicates if gps_service was already in a list by chance
    monitored_services = sorted(set(core_services))

    sm = messaging.SubMaster(monitored_services)

    counters = defaultdict(int)
    first_rx_times = defaultdict(float)
    last_rx_times = defaultdict(float)

    start_time = time.monotonic()
    next_print_time = start_time

    try:
        while True:
            loop_start_time = time.monotonic()
            if args.duration > 0 and (loop_start_time - start_time) >= args.duration:
                break

            sm.update(0)

            for service in monitored_services:
                if sm.updated[service]:
                    counters[service] += 1
                    if first_rx_times[service] == 0:
                        first_rx_times[service] = loop_start_time
                    last_rx_times[service] = loop_start_time

            if loop_start_time >= next_print_time:
                print("\033c", end="") # Clear screen
                print(f"--- Real-time Cereal Health Monitor (Ctrl+C to exit) --- {time.strftime('%H:%M:%S')} ---")
                print(f"{'Service':<25} {'Freq (Hz)':<10} {'Status':<30}")
                print("-" * 70)

                for service in monitored_services:
                    elapsed_service_time = max(last_rx_times[service] - first_rx_times[service], 1e-6) if first_rx_times[service] > 0 else 0
                    avg_freq = counters[service] / elapsed_service_time if elapsed_service_time > 0 else 0.0

                    status_str, is_ok = get_status_flags(sm, service, avg_freq, last_rx_times[service])
                    prefix = "  " if is_ok else "[!] "
                    print(f"{prefix}{service:<23} {avg_freq:<10.1f} {status_str:<30}")

                print("-" * 70)
                # Special checks
                llk_msg = sm['liveLocationKalman']
                if sm.recv_frame['liveLocationKalman'] > 0: # Check if we have received it at least once
                    if not llk_msg.inputsOK:
                        print("\n[!!!] liveLocationKalman.inputsOK is FALSE. Checking dependencies:")
                        print(f"  {'Dependency':<25} {'Freq (Hz)':<10} {'Status':<30}")
                        print("  " + "-" * 67)
                        for dep_service in locationd_inputs_with_gps:
                            if dep_service in monitored_services:
                                dep_elapsed = max(last_rx_times[dep_service] - first_rx_times[dep_service], 1e-6) if first_rx_times[dep_service] > 0 else 0
                                dep_avg_freq = counters[dep_service] / dep_elapsed if dep_elapsed > 0 else 0.0
                                dep_status_str, dep_is_ok = get_status_flags(sm, dep_service, dep_avg_freq, last_rx_times[dep_service])
                                dep_prefix = "    " if dep_is_ok else "  [!] "
                                print(f"{dep_prefix}{dep_service:<23} {dep_avg_freq:<10.1f} {dep_status_str:<30}")
                            else:
                                print(f"    {dep_service:<23} NOT MONITORED") # Should not happen with current setup

                lp_msg = sm['liveParameters']
                if sm.recv_frame['liveParameters'] > 0:
                    if not lp_msg.valid:
                        print("\n[!!!] liveParameters.valid is FALSE.")

                manager_msg = sm['managerState']
                if sm.recv_frame['managerState'] > 0:
                    not_running = [p.name for p in manager_msg.processes if not p.running and p.shouldBeRunning]
                    if not_running:
                        print(f"\n[!!!] Processes not running: {', '.join(not_running)}")


                next_print_time = loop_start_time + args.refresh

            # Calculate sleep time to maintain refresh rate, ensuring it's not negative
            processing_time = time.monotonic() - loop_start_time
            sleep_time = max(0, (1.0 / (1.0/args.refresh if args.refresh > 0 else 10.0)) - processing_time) # Avoid division by zero for refresh
            time.sleep(sleep_time)


    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        print("Exiting health monitor.")

if __name__ == "__main__":
    main()