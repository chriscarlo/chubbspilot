#!/usr/bin/env python3
import cereal.messaging as messaging
from cereal import services
import time
from collections import defaultdict
import sys

# Helper to pretty print cereal messages
def pretty_print_cereal(msg):
    if msg is None:
        return "None"
    if hasattr(msg, 'to_dict'):
        try:
            return msg.to_dict()
        except Exception:
            return str(msg)
    return str(msg)

def main():
    print("[DEBUG] Entered main()", file=sys.stderr)
    sys.stderr.flush()

    print("[DEBUG] About to get all_service_names...", file=sys.stderr)
    sys.stderr.flush()
    all_service_names = list(services.SERVICE_LIST.keys())
    print(f"[DEBUG] Got {len(all_service_names)} service names.", file=sys.stderr)
    sys.stderr.flush()

    # TEMPORARY DEBUG: Exclude sensorEvents to see if it's the sole Cap'n Proto issue
    print("[DEBUG] Checking for sensorEvents exclusion...", file=sys.stderr)
    sys.stderr.flush()
    if 'sensorEvents' in all_service_names:
        print("Temporarily excluding 'sensorEvents' from SubMaster subscription for debugging capnp error...", file=sys.stderr)
        sys.stderr.flush()
        all_service_names.remove('sensorEvents')
        print(f"[DEBUG] Service names count after sensorEvents exclusion: {len(all_service_names)}", file=sys.stderr)
        sys.stderr.flush()

    # Create a reverse map from process name to a list of services it *might* be associated with.
    # This is an approximation if service_spec.process doesn't exist or is unreliable.
    # We can look at which services are conventionally run by which processes based on common knowledge
    # or by parsing process_config.py (which is too complex for this script).
    # For now, we'll focus on direct process health and direct service health.

    print("[DEBUG] About to initialize SubMaster...", file=sys.stderr)
    sys.stderr.flush()
    sm = messaging.SubMaster(all_service_names, ignore_alive=[])
    print("[DEBUG] SubMaster initialized.", file=sys.stderr)
    sys.stderr.flush()

    print("Starting openpilot communication health monitor...")
    print("This script monitors services for the first signs of trouble:")
    print("  - INVALID_MSG: Service published a message with 'valid=False'. Content shown.")
    print("  - NOT_ALIVE: Service stopped sending messages (based on SubMaster's alive check).")
    print("  - BAD_FREQ: Service message frequency is outside expected bounds (based on SubMaster's freq_ok check).")
    print("  - NO_MESSAGES: Service SubMaster is subscribed to hasn't received messages (especially if it has a defined frequency).")
    print("  - PROC_CRASHED_EXITED: OS Process (from managerState) expected to run but isn't, or exited with error.")
    print("  - PROC_UNEXPECTEDLY_RUN: OS Process (from managerState) is running but managerState indicates it shouldn't be.")
    print("\nTimestamps indicate the *first* time an issue is detected. This helps trace cascading failures.")
    print("Watching for issues... Press Ctrl+C to stop.\n")
    print("Timestamp   | Service/Process Name| Problem Type          | Details")
    print("------------|---------------------|-----------------------|----------------------------------------------------")
    sys.stdout.flush()

    first_detected_issues = {}
    last_known_ok_state = defaultdict(lambda: {
        'valid': True, 'alive': True, 'freq_ok': True,
        'proc_crashed_exited': False, 'proc_unexpectedly_run': False,
        'no_messages_reported': False
    })

    print("[DEBUG] About to initialize manager_state_sock...", file=sys.stderr)
    sys.stderr.flush()
    manager_state_sock = messaging.sub_sock('managerState', timeout=0.005)
    print("[DEBUG] manager_state_sock initialized.", file=sys.stderr)
    sys.stderr.flush()
    running_processes_info = {}

    print("[DEBUG] Entering main monitoring loop...", file=sys.stderr)
    sys.stderr.flush()
    try:
        while True:
            manager_msg = messaging.recv_one_or_none(manager_state_sock)
            if manager_msg and manager_msg.managerState:
                current_running_processes_info = {}
                for p_log in manager_msg.managerState.processes:
                    current_running_processes_info[p_log.name] = {
                        'running': p_log.running,
                        'shouldBeRunning': p_log.shouldBeRunning,
                        'pid': p_log.pid,
                        'exitCode': p_log.exitCode,
                    }
                running_processes_info = current_running_processes_info

            sm.update(0)
            current_time = time.monotonic()
            timestamp_str = f"{time.strftime('%H:%M:%S')}.{int((current_time - int(current_time)) * 1000):03d}"

            # Check OS process states directly from managerState
            for proc_name, proc_data in running_processes_info.items():
                display_name = f"PROC:{proc_name}"

                # Check PROC_CRASHED_EXITED
                is_crashed = proc_data['shouldBeRunning'] and not proc_data['running'] and proc_data['exitCode'] != 0
                if is_crashed:
                    if not last_known_ok_state[display_name]['proc_crashed_exited']:
                        issue_key = (display_name, "PROC_CRASHED_EXITED")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            details = f"Process expected but not running. Exit code: {proc_data['exitCode']}."
                            print(f"{timestamp_str} | {display_name:<20} | PROC_CRASHED_EXITED   | {details}")
                            sys.stdout.flush()
                        last_known_ok_state[display_name]['proc_crashed_exited'] = True
                elif last_known_ok_state[display_name]['proc_crashed_exited']: # Resolved
                    issue_key = (display_name, "PROC_CRASHED_EXITED")
                    if issue_key in first_detected_issues:
                        print(f"{timestamp_str} | {display_name:<20} | PROC_CRASHED_EXITED   | RESOLVED (Running or correctly stopped/exited cleanly)")
                        sys.stdout.flush()
                        del first_detected_issues[issue_key]
                    last_known_ok_state[display_name]['proc_crashed_exited'] = False

                # Check PROC_UNEXPECTEDLY_RUN
                is_unexpectedly_running = not proc_data['shouldBeRunning'] and proc_data['running']
                if is_unexpectedly_running:
                    if not last_known_ok_state[display_name]['proc_unexpectedly_run']:
                        issue_key = (display_name, "PROC_UNEXPECTEDLY_RUN")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            details = "Process is running but managerState indicates it should not be."
                            print(f"{timestamp_str} | {display_name:<20} | PROC_UNEXPECTEDLY_RUN | {details}")
                            sys.stdout.flush()
                        last_known_ok_state[display_name]['proc_unexpectedly_run'] = True
                elif last_known_ok_state[display_name]['proc_unexpectedly_run']: # Resolved
                    issue_key = (display_name, "PROC_UNEXPECTEDLY_RUN")
                    if issue_key in first_detected_issues:
                        print(f"{timestamp_str} | {display_name:<20} | PROC_UNEXPECTEDLY_RUN | RESOLVED (Process stopped)")
                        sys.stdout.flush()
                        del first_detected_issues[issue_key]
                    last_known_ok_state[display_name]['proc_unexpectedly_run'] = False

            # Now iterate through Cereal services for message-based checks
            for s in all_service_names:
                service_spec = services.SERVICE_LIST[s] # Still useful for frequency

                # NO_MESSAGES Check: Flag if SubMaster hasn't received anything for this service,
                # especially if it has a non-zero frequency suggesting it should be active.
                # We can't reliably link to managerState.shouldBeRunning without service_spec.process
                if sm.recv_frame[s] == 0 and not sm.updated[s] and service_spec.frequency > 1e-5 :
                    if not last_known_ok_state[s]['no_messages_reported']:
                        issue_key = (s, "NO_MESSAGES")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            details = "No messages received by SubMaster for this active-frequency service."
                            print(f"{timestamp_str} | {s:<20} | NO_MESSAGES           | {details}")
                            sys.stdout.flush()
                        last_known_ok_state[s]['no_messages_reported'] = True
                elif last_known_ok_state[s]['no_messages_reported'] and sm.recv_frame[s] > 0:
                    issue_key = (s, "NO_MESSAGES")
                    if issue_key in first_detected_issues:
                        print(f"{timestamp_str} | {s:<20} | NO_MESSAGES           | RESOLVED (Messages now being received)")
                        sys.stdout.flush()
                        del first_detected_issues[issue_key]
                    last_known_ok_state[s]['no_messages_reported'] = False

                if sm.recv_frame[s] > 0 or service_spec.frequency > 1e-5:
                    # VALID_MSG Check
                    current_valid_status = sm.valid[s]
                    if not current_valid_status and last_known_ok_state[s]['valid']:
                        issue_key = (s, "INVALID_MSG")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            msg_content_str = "Not available or not updated this cycle"
                            if sm.updated[s] and hasattr(sm[s], 'to_dict'):
                                try:
                                    msg_content_str = pretty_print_cereal(sm[s])
                                except Exception:
                                    msg_content_str = str(sm[s])
                            details = f"Msg invalid (sm.valid=False). Content: {str(msg_content_str)[:200]}"
                            print(f"{timestamp_str} | {s:<20} | INVALID_MSG         | {details}")
                            sys.stdout.flush()
                        last_known_ok_state[s]['valid'] = False
                    elif current_valid_status and not last_known_ok_state[s]['valid']:
                        issue_key = (s, "INVALID_MSG")
                        if issue_key in first_detected_issues:
                            print(f"{timestamp_str} | {s:<20} | INVALID_MSG         | RESOLVED (sm.valid=True)")
                            sys.stdout.flush()
                            del first_detected_issues[issue_key]
                        last_known_ok_state[s]['valid'] = True

                    # NOT_ALIVE Check
                    if service_spec.frequency > 1e-5: # Only for services expected to be periodic
                        current_alive_status = sm.alive[s]
                        if not current_alive_status and last_known_ok_state[s]['alive']:
                            issue_key = (s, "NOT_ALIVE")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                time_since_last = current_time - sm.recv_time[s] if sm.recv_time[s] > 0 else float('inf')
                                details = f"Not alive (sm.alive=False). Last recv: {time_since_last:.2f}s ago."
                                if sm.recv_time[s] == 0:
                                     details = "Not alive (sm.alive=False). No messages ever received by SubMaster."
                                print(f"{timestamp_str} | {s:<20} | NOT_ALIVE           | {details}")
                                sys.stdout.flush()
                            last_known_ok_state[s]['alive'] = False
                        elif current_alive_status and not last_known_ok_state[s]['alive']:
                            issue_key = (s, "NOT_ALIVE")
                            if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | NOT_ALIVE           | RESOLVED (sm.alive=True)")
                                sys.stdout.flush()
                                del first_detected_issues[issue_key]
                            last_known_ok_state[s]['alive'] = True

                    # BAD_FREQ Check
                    if service_spec.frequency > 1e-5 and len(sm.recv_dts[s]) > max(1, int(service_spec.frequency * 0.5)):
                        current_freq_ok_status = sm.freq_ok[s]
                        if not current_freq_ok_status and last_known_ok_state[s]['freq_ok']:
                            issue_key = (s, "BAD_FREQ")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                dts = sm.recv_dts[s]
                                avg_freq = 1.0 / (sum(dts) / len(dts)) if dts and sum(dts) > 0 else 0
                                details = (f"Freq issue (sm.freq_ok=False). Expected: {service_spec.frequency:.1f}Hz. Actual avg: {avg_freq:.1f}Hz. "
                                           f"(Range: {sm.min_freq[s]:.1f}-{sm.max_freq[s]:.1f}Hz). Samples: {len(dts)})")
                                print(f"{timestamp_str} | {s:<20} | BAD_FREQ            | {details}")
                                sys.stdout.flush()
                            last_known_ok_state[s]['freq_ok'] = False
                        elif current_freq_ok_status and not last_known_ok_state[s]['freq_ok']:
                            issue_key = (s, "BAD_FREQ")
                            if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | BAD_FREQ            | RESOLVED (sm.freq_ok=True)")
                                sys.stdout.flush()
                                del first_detected_issues[issue_key]
                            last_known_ok_state[s]['freq_ok'] = True

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
    finally:
        print("Exiting communication monitor.")

if __name__ == "__main__":
    main()