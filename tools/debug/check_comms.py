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
    # Get all service names directly from services.SERVICE_LIST
    # SubMaster will handle which ones it can actually subscribe to.
    all_service_names = list(services.SERVICE_LIST.keys())

    # We are interested in services that SubMaster can actually poll and get updates for.
    # SubMaster itself will only connect to services that are actually publishing.
    # So, we pass all known service names to SubMaster.
    # Our subsequent checks (sm.valid[s], sm.alive[s], sm.freq_ok[s])
    # will rely on SubMaster's state for these services.
    sm = messaging.SubMaster(all_service_names, ignore_alive=[]) # monitor all services, poll default (all)

    print("Starting openpilot communication health monitor...")
    print("This script monitors services for the first signs of trouble:")
    print("  - INVALID_MSG: Service published a message with 'valid=False'. Content shown.")
    print("  - NOT_ALIVE: Service stopped sending messages (based on SubMaster's alive check).")
    print("  - BAD_FREQ: Service message frequency is outside expected bounds (based on SubMaster's freq_ok check).")
    print("  - NO_MESSAGES: Service is expected to run (via managerState) but SubMaster hasn't received messages.")
    print("  - CRASHED_EXITED: Process associated with service isn't running as expected or exited with error.")
    print("  - UNEXPECTEDLY_RUN: Process is running but managerState indicates it shouldn't be.")
    print("\nTimestamps indicate the *first* time an issue is detected. This helps trace cascading failures.")
    print("Watching for issues... Press Ctrl+C to stop.\n")
    print("Timestamp   | Service Name        | Problem Type     | Details")
    print("------------|---------------------|------------------|----------------------------------------------------")
    sys.stdout.flush() # Ensure header prints immediately

    first_detected_issues = {}
    # Store last known status for each check type to detect transitions
    last_known_ok_state = defaultdict(lambda: {
        'valid': True,
        'alive': True,
        'freq_ok': True,
        'crashed_exited': False,
        'unexpectedly_run': False,
        'no_messages_reported': False # Specific for NO_MESSAGES to avoid re-reporting if it never starts
    })

    manager_state_sock = messaging.sub_sock('managerState', timeout=0.005)
    running_processes_info = {}

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

            # Check process states first
            for proc_name, proc_data in running_processes_info.items():
                is_crashed_or_exited_unexpectedly = proc_data['shouldBeRunning'] and not proc_data['running'] and proc_data['exitCode'] != 0
                is_unexpectedly_running = not proc_data['shouldBeRunning'] and proc_data['running']

                # Check for processes that don't have associated services in SERVICE_LIST's .process field
                # This is for processes like 'manage_athenad' or others not directly publishing to a known service endpoint name.
                # We can still report if they crash.
                service_display_name_for_proc = f"PROC:{proc_name}"

                if is_crashed_or_exited_unexpectedly:
                    if not last_known_ok_state[service_display_name_for_proc]['crashed_exited']:
                        issue_key = (service_display_name_for_proc, "CRASHED_EXITED")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            details = f"Process expected but not running. Exit code: {proc_data['exitCode']}."
                            print(f"{timestamp_str} | {service_display_name_for_proc:<20} | CRASHED_EXITED   | {details}")
                            sys.stdout.flush()
                        last_known_ok_state[service_display_name_for_proc]['crashed_exited'] = True
                elif last_known_ok_state[service_display_name_for_proc]['crashed_exited']: # Resolved
                    issue_key = (service_display_name_for_proc, "CRASHED_EXITED")
                    if issue_key in first_detected_issues:
                        print(f"{timestamp_str} | {service_display_name_for_proc:<20} | CRASHED_EXITED   | RESOLVED (Process running or correctly stopped/exited cleanly)")
                        sys.stdout.flush()
                        del first_detected_issues[issue_key]
                    last_known_ok_state[service_display_name_for_proc]['crashed_exited'] = False

                # Check services tied to this process
                for s in all_service_names:
                    service_spec = services.SERVICE_LIST[s]
                    if service_spec.process == proc_name: # Link service to its managing process
                        if is_crashed_or_exited_unexpectedly:
                            if not last_known_ok_state[s]['crashed_exited']:
                                issue_key = (s, "CRASHED_EXITED")
                                if issue_key not in first_detected_issues:
                                    first_detected_issues[issue_key] = current_time
                                    details = f"Process {proc_name} for service {s} expected but not running. Exit code: {proc_data['exitCode']}."
                                    print(f"{timestamp_str} | {s:<20} | CRASHED_EXITED   | {details}")
                                    sys.stdout.flush()
                                last_known_ok_state[s]['crashed_exited'] = True
                        elif last_known_ok_state[s]['crashed_exited']: # Resolved
                             issue_key = (s, "CRASHED_EXITED")
                             if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | CRASHED_EXITED   | RESOLVED (Process {proc_name} running or correctly stopped)")
                                sys.stdout.flush()
                                del first_detected_issues[issue_key]
                             last_known_ok_state[s]['crashed_exited'] = False

                        if is_unexpectedly_running:
                            if not last_known_ok_state[s]['unexpectedly_run']:
                                issue_key = (s, "UNEXPECTEDLY_RUN")
                                if issue_key not in first_detected_issues:
                                    first_detected_issues[issue_key] = current_time
                                    details = f"Process {proc_name} for service {s} is running but should not be."
                                    print(f"{timestamp_str} | {s:<20} | UNEXPECTEDLY_RUN | {details}")
                                    sys.stdout.flush()
                                last_known_ok_state[s]['unexpectedly_run'] = True
                        elif last_known_ok_state[s]['unexpectedly_run']: # Resolved
                            issue_key = (s, "UNEXPECTEDLY_RUN")
                            if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | UNEXPECTEDLY_RUN | RESOLVED (Process {proc_name} stopped)")
                                sys.stdout.flush()
                                del first_detected_issues[issue_key]
                            last_known_ok_state[s]['unexpectedly_run'] = False

            # Now iterate through all services for message-based checks
            for s in all_service_names:
                service_spec = services.SERVICE_LIST[s]
                proc_name = service_spec.process
                proc_data = running_processes_info.get(proc_name)

                # Determine if the service's process should be running
                # Some services might not have a managing process listed (e.g. 'thermal'), assume they should be publishing if so.
                should_be_publishing_based_on_manager = proc_data['shouldBeRunning'] if proc_data else (True if not proc_name else False)


                # 1. NO_MESSAGES Check
                # Only flag if it should be publishing and we've never seen a message (recv_frame == 0)
                # AND SubMaster hasn't updated it in this cycle (sm.updated[s] is False).
                # This avoids flagging services that are correctly off.
                if should_be_publishing_based_on_manager and sm.recv_frame[s] == 0 and not sm.updated[s]:
                    if not last_known_ok_state[s]['no_messages_reported']:
                        issue_key = (s, "NO_MESSAGES")
                        if issue_key not in first_detected_issues: # Check if already reported and not resolved
                            first_detected_issues[issue_key] = current_time
                            details = "Process should be running, but no messages received yet by SubMaster."
                            print(f"{timestamp_str} | {s:<20} | NO_MESSAGES      | {details}")
                            sys.stdout.flush()
                        last_known_ok_state[s]['no_messages_reported'] = True
                elif last_known_ok_state[s]['no_messages_reported'] and (sm.recv_frame[s] > 0 or not should_be_publishing_based_on_manager):
                    # Resolved if messages start appearing OR if the process is now correctly not running
                    issue_key = (s, "NO_MESSAGES")
                    if issue_key in first_detected_issues:
                        details_resolved = "Messages now being received." if sm.recv_frame[s] > 0 else "Correctly not running."
                        print(f"{timestamp_str} | {s:<20} | NO_MESSAGES      | RESOLVED ({details_resolved})")
                        sys.stdout.flush()
                        del first_detected_issues[issue_key]
                    last_known_ok_state[s]['no_messages_reported'] = False

                # For other checks, only proceed if the service is one SubMaster is actively getting data for,
                # or if it's a service that has a defined frequency (implying it should publish)
                if sm.recv_frame[s] > 0 or service_spec.frequency > 1e-5:
                    # 2. Validity Check (using sm.valid)
                    current_valid_status = sm.valid[s]
                    if not current_valid_status and last_known_ok_state[s]['valid']: # Transition to invalid
                        issue_key = (s, "INVALID_MSG")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            msg_content_str = "Not available or not updated this cycle"
                            if sm.updated[s] and hasattr(sm[s], 'to_dict'): # Check if we can get content
                                try:
                                    msg_content_str = pretty_print_cereal(sm[s])
                                except Exception:
                                    msg_content_str = str(sm[s])

                            details = f"Msg invalid (sm.valid=False). Content: {str(msg_content_str)[:200]}"
                            print(f"{timestamp_str} | {s:<20} | INVALID_MSG      | {details}")
                            sys.stdout.flush()
                        last_known_ok_state[s]['valid'] = False # Mark as invalid
                    elif current_valid_status and not last_known_ok_state[s]['valid']: # Transition back to valid
                        issue_key = (s, "INVALID_MSG")
                        if issue_key in first_detected_issues:
                            print(f"{timestamp_str} | {s:<20} | INVALID_MSG      | RESOLVED (sm.valid=True)")
                            sys.stdout.flush()
                            del first_detected_issues[issue_key]
                        last_known_ok_state[s]['valid'] = True


                    # 3. Alive Check (using sm.alive)
                    # Only for services that are expected to have a frequency and should be publishing
                    if service_spec.frequency > 1e-5 and should_be_publishing_based_on_manager:
                        current_alive_status = sm.alive[s]
                        if not current_alive_status and last_known_ok_state[s]['alive']: # Transition to not alive
                            issue_key = (s, "NOT_ALIVE")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                time_since_last = current_time - sm.recv_time[s] if sm.recv_time[s] > 0 else float('inf')
                                details = f"Not alive (sm.alive=False). Last recv: {time_since_last:.2f}s ago."
                                if sm.recv_time[s] == 0:
                                     details = "Not alive (sm.alive=False). No messages ever received by SubMaster."
                                print(f"{timestamp_str} | {s:<20} | NOT_ALIVE        | {details}")
                                sys.stdout.flush()
                            last_known_ok_state[s]['alive'] = False # Mark as not alive
                        elif current_alive_status and not last_known_ok_state[s]['alive']: # Transition back to alive
                            issue_key = (s, "NOT_ALIVE")
                            if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | NOT_ALIVE        | RESOLVED (sm.alive=True)")
                                sys.stdout.flush()
                                del first_detected_issues[issue_key]
                            last_known_ok_state[s]['alive'] = True

                    # 4. Frequency Check (using sm.freq_ok)
                    # Only for services that are expected to have a frequency and should be publishing
                    if service_spec.frequency > 1e-5 and should_be_publishing_based_on_manager and len(sm.recv_dts[s]) > max(1, int(service_spec.frequency * 0.5)):
                        current_freq_ok_status = sm.freq_ok[s]
                        if not current_freq_ok_status and last_known_ok_state[s]['freq_ok']: # Transition to bad freq
                            issue_key = (s, "BAD_FREQ")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                dts = sm.recv_dts[s]
                                avg_freq = 1.0 / (sum(dts) / len(dts)) if dts and sum(dts) > 0 else 0
                                details = (f"Freq issue (sm.freq_ok=False). Expected: {service_spec.frequency:.1f}Hz. Actual avg: {avg_freq:.1f}Hz. "
                                           f"(Range: {sm.min_freq[s]:.1f}-{sm.max_freq[s]:.1f}Hz). Samples: {len(dts)}")
                                print(f"{timestamp_str} | {s:<20} | BAD_FREQ         | {details}")
                                sys.stdout.flush()
                            last_known_ok_state[s]['freq_ok'] = False # Mark as bad freq
                        elif current_freq_ok_status and not last_known_ok_state[s]['freq_ok']: # Transition back to good freq
                            issue_key = (s, "BAD_FREQ")
                            if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | BAD_FREQ         | RESOLVED (sm.freq_ok=True)")
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