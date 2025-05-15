#!/usr/bin/env python3
import argparse
import time
import sys
import traceback
from collections import defaultdict

print(">>> [DEBUG] Starting health monitor script...", file=sys.stderr)
try:
    import cereal.messaging as messaging
    print(">>> [DEBUG] cereal.messaging imported.", file=sys.stderr)
    from cereal import services
    print(">>> [DEBUG] cereal.services imported.", file=sys.stderr)
    from openpilot.common.params import Params
    print(">>> [DEBUG] openpilot.common.params.Params imported.", file=sys.stderr)
except Exception as e:
    print("!!! [ERROR] Exception during import:", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

THRESH_FACTOR = 0.66
ALIVE_FACTOR = 5.0

LOCATIOND_INPUTS = ["cameraOdometry", "liveCalibration", "accelerometer", "gyroscope"]
PARAMSD_INPUTS = ["carState", "liveCalibration", "controlsState"]

def get_nominal_freq(service_name):
    spec = services.SERVICE_LIST[service_name]
    freq = spec.frequency if spec.frequency > 0 else 1.0
    print(f">>> [DEBUG] get_nominal_freq({service_name}) = {freq}", file=sys.stderr)
    return freq

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
    if freq_low and sm.frame > 100:
        health_str.append(f"FREQ_LOW({avg_freq:.1f}<{nominal_freq*THRESH_FACTOR:.1f})")
        ok = False
    print(f">>> [DEBUG] get_status_flags({service_name}): valid={is_valid}, alive={is_alive}, freq_low={freq_low}, status={'OK' if ok else ', '.join(health_str)}", file=sys.stderr)
    return (", ".join(health_str) if not ok else "OK", ok)

def main():
    print(">>> [DEBUG] Entering main()", file=sys.stderr)
    parser = argparse.ArgumentParser(description="Real-time health monitor for Cereal services.")
    parser.add_argument("-d", "--duration", type=float, default=0,
                        help="How many seconds to run (default: 0, for indefinite)")
    parser.add_argument("-r", "--refresh", type=float, default=0.5,
                        help="How often to print status in seconds (default: 0.5)")
    args = parser.parse_args()
    print(f">>> [DEBUG] Parsed args: duration={args.duration}, refresh={args.refresh}", file=sys.stderr)

    try:
        params = Params()
        print(">>> [DEBUG] Params() instantiated.", file=sys.stderr)
        ublox = params.get_bool("UbloxAvailable")
        print(f">>> [DEBUG] UbloxAvailable: {ublox}", file=sys.stderr)
        gps_service = "gpsLocationExternal" if ublox else "gpsLocation"
    except Exception as e:
        print("!!! [ERROR] Exception fetching Params or UbloxAvailable:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)

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
        "pandaStates",
        "managerState",
    ]
    monitored_services = sorted(set(core_services))
    print(f">>> [DEBUG] Monitored services: {monitored_services}", file=sys.stderr)

    try:
        sm = messaging.SubMaster(monitored_services)
        print(">>> [DEBUG] SubMaster initialized.", file=sys.stderr)
    except Exception as e:
        print("!!! [ERROR] Exception initializing SubMaster:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)

    counters = defaultdict(int)
    first_rx_times = defaultdict(float)
    last_rx_times = defaultdict(float)

    start_time = time.monotonic()
    next_print_time = start_time

    print(">>> [DEBUG] Entering main monitoring loop...", file=sys.stderr)

    try:
        while True:
            loop_start_time = time.monotonic()
            print(f">>> [DEBUG] Main loop, elapsed={loop_start_time-start_time:.2f}s", file=sys.stderr)
            if args.duration > 0 and (loop_start_time - start_time) >= args.duration:
                print(f">>> [DEBUG] Duration reached ({args.duration}s), breaking loop.", file=sys.stderr)
                break

            print(">>> [DEBUG] Calling sm.update(0)...", file=sys.stderr)
            try:
                sm.update(0)
            except Exception as e:
                print("!!! [ERROR] Exception during sm.update:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                raise

            print(">>> [DEBUG] Processing received messages...", file=sys.stderr)
            for service in monitored_services:
                if sm.updated[service]:
                    print(f">>> [DEBUG] sm.updated[{service}] is True", file=sys.stderr)
                    counters[service] += 1
                    if first_rx_times[service] == 0:
                        first_rx_times[service] = loop_start_time
                        print(f">>> [DEBUG] First rx for {service} at {loop_start_time}", file=sys.stderr)
                    last_rx_times[service] = loop_start_time

            if loop_start_time >= next_print_time:
                print("\033c", end="")
                print(f"--- Real-time Cereal Health Monitor (Ctrl+C to exit) --- {time.strftime('%H:%M:%S')} ---")
                print(f"{'Service':<25} {'Freq (Hz)':<10} {'Status':<30}")
                print("-" * 70)
                for service in monitored_services:
                    elapsed_service_time = max(last_rx_times[service] - first_rx_times[service], 1e-6) if first_rx_times[service] > 0 else 0
                    avg_freq = counters[service] / elapsed_service_time if elapsed_service_time > 0 else 0.0
                    print(f">>> [DEBUG] {service}: count={counters[service]}, elapsed={elapsed_service_time:.3f}, avg_freq={avg_freq:.3f}", file=sys.stderr)
                    status_str, is_ok = get_status_flags(sm, service, avg_freq, last_rx_times[service])
                    prefix = "  " if is_ok else "[!] "
                    print(f"{prefix}{service:<23} {avg_freq:<10.1f} {status_str:<30}")

                print("-" * 70)
                # Special checks
                try:
                    llk_msg = sm['liveLocationKalman']
                    print(">>> [DEBUG] Checking liveLocationKalman.inputsOK", file=sys.stderr)
                    if sm.recv_frame['liveLocationKalman'] > 0:
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
                                    print(f"    {dep_service:<23} NOT MONITORED")
                except Exception as e:
                    print("!!! [ERROR] Exception in liveLocationKalman check:", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)

                try:
                    lp_msg = sm['liveParameters']
                    if sm.recv_frame['liveParameters'] > 0:
                        if not lp_msg.valid:
                            print("\n[!!!] liveParameters.valid is FALSE.")
                except Exception as e:
                    print("!!! [ERROR] Exception in liveParameters check:", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)

                try:
                    manager_msg = sm['managerState']
                    if sm.recv_frame['managerState'] > 0:
                        not_running = [p.name for p in manager_msg.processes if not p.running and p.shouldBeRunning]
                        if not_running:
                            print(f"\n[!!!] Processes not running: {', '.join(not_running)}")
                except Exception as e:
                    print("!!! [ERROR] Exception in managerState check:", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)

                next_print_time = loop_start_time + args.refresh

            processing_time = time.monotonic() - loop_start_time
            sleep_time = max(0, (1.0 / (1.0/args.refresh if args.refresh > 0 else 10.0)) - processing_time)
            print(f">>> [DEBUG] Loop sleep_time={sleep_time:.3f}s (processing_time={processing_time:.3f}s)", file=sys.stderr)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
    except Exception as e:
        print("!!! [ERROR] Exception in main loop:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    finally:
        print("Exiting health monitor.", file=sys.stderr)

if __name__ == "__main__":
    main()