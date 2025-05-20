#!/usr/bin/env python3
import cereal.messaging as messaging
from cereal.services import SERVICE_LIST
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
    # Subscribe to all services + managerState for shouldBeRunning info
    services_to_check = list(SERVICE_LIST.keys())
    if 'managerState' not in services_to_check: # Should always be there from services.py
        services_to_check.append('managerState')

    # Filter out services that don't publish, as we can't check their health directly
    # We will check the health of the *processes* that are supposed to publish them via managerState
    services_that_publish = [s for s in SERVICE_LIST.keys() if SERVICE_LIST[s].port is not None and SERVICE_LIST[s].port > 0]

    sm = messaging.SubMaster(services_that_publish, poll='*', ignore_alive=[]) # monitor all publishing services

    print("Starting openpilot communication health monitor...")
    print("This script monitors services for the first signs of trouble:")
    print("  - INVALID_MSG: Service published a message with 'valid=False'. Content shown.")
    print("  - NOT_ALIVE: Service stopped sending messages.")
    print("  - BAD_FREQ: Service message frequency is outside expected bounds.")
    print("  - NO_MESSAGES: Service is expected to run but hasn't sent any messages.")
    print("  - CRASHED_EXITED: Process associated with service isn't running as expected or exited with error.")
    print("  - UNEXPECTEDLY_RUN: Process is running but managerState indicates it shouldn't be.")
    print("\nTimestamps indicate the *first* time an issue is detected. This helps trace cascading failures.")
    print("Watching for issues... Press Ctrl+C to stop.\n")
    print("Timestamp   | Service Name        | Problem Type     | Details")
    print("------------|---------------------|------------------|----------------------------------------------------")
    sys.stdout.flush() # Ensure header prints immediately

    first_detected_issues = {}
    last_known_ok_state = defaultdict(lambda: {'valid': True, 'alive': True, 'freq_ok': True, 'crashed_exited': False, 'unexpectedly_run': False, 'no_messages': False})

    # Use a non-blocking sub socket for managerState
    manager_state_sock = messaging.sub_sock('managerState', timeout=0.005) # Short timeout, non-blocking
    running_processes_info = {}

    try:
        while True:
            # Update managerState separately and non-blockingly
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

            sm.update(0) # Non-blocking update for all other services

            current_time = time.monotonic()
            timestamp_str = f"{time.strftime('%H:%M:%S')}.{int((current_time - int(current_time)) * 1000):03d}"

            # First, check process states from managerState
            for proc_name, proc_data in running_processes_info.items():
                # Find services associated with this process
                affected_services = [s_name for s_name, s_info in SERVICE_LIST.items() if s_info.process == proc_name and s_info.publishes]
                if not affected_services: # If process doesn't publish a known service, skip (e.g. 'manage_athenad')
                    # However, we can still report if it crashed and should be running
                    if proc_data['shouldBeRunning'] and not proc_data['running'] and proc_data['exitCode'] != 0:
                        service_display_name = f"PROC:{proc_name}" # Display as a process issue
                        issue_key = (service_display_name, "CRASHED_EXITED")
                        if not last_known_ok_state[service_display_name]['crashed_exited']: # If it was previously OK or not reported
                             if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                details = f"Process expected but not running. Exit code: {proc_data['exitCode']}."
                                print(f"{timestamp_str} | {service_display_name:<20} | CRASHED_EXITED   | {details}")
                                sys.stdout.flush()
                        last_known_ok_state[service_display_name]['crashed_exited'] = True # Mark as having this issue
                    elif last_known_ok_state[service_display_name]['crashed_exited'] and (proc_data['running'] or (not proc_data['shouldBeRunning'] and not proc_data['running'])):
                        # Process is now running OR correctly not running, so it's resolved
                        issue_key = (service_display_name, "CRASHED_EXITED")
                        if issue_key in first_detected_issues:
                            print(f"{timestamp_str} | {service_display_name:<20} | CRASHED_EXITED   | RESOLVED (Running or correctly stopped)")
                            sys.stdout.flush()
                            del first_detected_issues[issue_key]
                        last_known_ok_state[service_display_name]['crashed_exited'] = False

                    continue # Move to next process if this one doesn't publish known service

                for s in affected_services:
                    service_ok_for_manager_checks = True
                    # Check CRASHED_EXITED for the service context
                    if proc_data['shouldBeRunning'] and not proc_data['running'] and proc_data['exitCode'] != 0:
                        service_ok_for_manager_checks = False
                        if not last_known_ok_state[s]['crashed_exited']:
                            issue_key = (s, "CRASHED_EXITED")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                details = f"Process {proc_name} expected but not running. Exit code: {proc_data['exitCode']}."
                                print(f"{timestamp_str} | {s:<20} | CRASHED_EXITED   | {details}")
                                sys.stdout.flush()
                        last_known_ok_state[s]['crashed_exited'] = True
                    elif last_known_ok_state[s]['crashed_exited'] and (proc_data['running'] or (not proc_data['shouldBeRunning'] and not proc_data['running'])):
                        issue_key = (s, "CRASHED_EXITED")
                        if issue_key in first_detected_issues:
                            print(f"{timestamp_str} | {s:<20} | CRASHED_EXITED   | RESOLVED (Process running or correctly stopped)")
                            sys.stdout.flush()
                            del first_detected_issues[issue_key]
                        last_known_ok_state[s]['crashed_exited'] = False

                    # Check UNEXPECTEDLY_RUNNING
                    if not proc_data['shouldBeRunning'] and proc_data['running']:
                        service_ok_for_manager_checks = False
                        if not last_known_ok_state[s]['unexpectedly_run']:
                            issue_key = (s, "UNEXPECTEDLY_RUN")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                details = f"Process {proc_name} is running but should not be."
                                print(f"{timestamp_str} | {s:<20} | UNEXPECTEDLY_RUN | {details}")
                                sys.stdout.flush()
                        last_known_ok_state[s]['unexpectedly_run'] = True
                    elif last_known_ok_state[s]['unexpectedly_run'] and not proc_data['running']: # It stopped, so resolved
                        issue_key = (s, "UNEXPECTEDLY_RUN")
                        if issue_key in first_detected_issues:
                            print(f"{timestamp_str} | {s:<20} | UNEXPECTEDLY_RUN | RESOLVED (Process stopped)")
                            sys.stdout.flush()
                            del first_detected_issues[issue_key]
                        last_known_ok_state[s]['unexpectedly_run'] = False


            # Now iterate through services that are supposed to publish for message-based checks
            for s in services_that_publish:
                service_info = SERVICE_LIST[s]
                proc_name = service_info.process
                proc_data = running_processes_info.get(proc_name)

                should_be_publishing = proc_data['shouldBeRunning'] if proc_data else True # Assume should if process info missing

                # If a service is correctly not publishing, clear its potential 'NO_MESSAGES' or other issues
                if not should_be_publishing:
                    if last_known_ok_state[s]['no_messages'] : # Was previously considered missing
                        issue_key = (s, "NO_MESSAGES")
                        if issue_key in first_detected_issues:
                            print(f"{timestamp_str} | {s:<20} | NO_MESSAGES      | RESOLVED (Correctly not running)")
                            sys.stdout.flush()
                            del first_detected_issues[issue_key]
                        last_known_ok_state[s]['no_messages'] = False
                    # Potentially other states could be reset here if they depend on the service being active
                    continue # Skip message content checks for services that shouldn't be running


                service_ok_this_cycle = True

                # 1. NO_MESSAGES Check (if it should be running but we've never received anything)
                # sm.recv_frame is 0 if no messages ever, sm.updated is false if no message in this frame
                if should_be_publishing and sm.recv_frame[s] == 0 and not sm.updated[s]:
                    service_ok_this_cycle = False
                    if not last_known_ok_state[s]['no_messages']: # First time seeing it as not having sent messages
                        issue_key = (s, "NO_MESSAGES")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            details = "Expected to publish, but no messages received yet."
                            print(f"{timestamp_str} | {s:<20} | NO_MESSAGES      | {details}")
                            sys.stdout.flush()
                    last_known_ok_state[s]['no_messages'] = True # Mark as having this issue
                elif last_known_ok_state[s]['no_messages'] and (sm.updated[s] or sm.recv_frame[s] > 0): # It has sent a message
                    issue_key = (s, "NO_MESSAGES")
                    if issue_key in first_detected_issues:
                        print(f"{timestamp_str} | {s:<20} | NO_MESSAGES      | RESOLVED (Messages now being received)")
                        sys.stdout.flush()
                        del first_detected_issues[issue_key]
                    last_known_ok_state[s]['no_messages'] = False


                # Proceed with other checks only if messages have been received at some point or are being received now
                if sm.recv_frame[s] > 0 or sm.updated[s]:
                    # 2. Validity Check
                    current_valid_status = sm.valid[s] if sm.updated[s] else last_known_ok_state[s]['valid'] # Use last known if not updated this cycle
                    if not sm.updated[s] and not current_valid_status : # If not updated and was already invalid, it's still invalid
                        pass # Don't re-flag, wait for NOT_ALIVE
                    elif not current_valid_status and last_known_ok_state[s]['valid']: # Transition to invalid
                        service_ok_this_cycle = False
                        issue_key = (s, "INVALID_MSG")
                        if issue_key not in first_detected_issues:
                            first_detected_issues[issue_key] = current_time
                            msg_content_str = "Not available this cycle"
                            if sm.updated[s] and sm[s] is not None: # Make sure we have the actual invalid message
                                msg_content_str = pretty_print_cereal(sm[s])
                            details = f"Msg invalid. Content snapshot: {str(msg_content_str)[:200]}"
                            print(f"{timestamp_str} | {s:<20} | INVALID_MSG      | {details}")
                            sys.stdout.flush()
                    last_known_ok_state[s]['valid'] = current_valid_status
                    if current_valid_status and not last_known_ok_state[s]['valid']: # Transition to valid
                         issue_key = (s, "INVALID_MSG")
                         if issue_key in first_detected_issues:
                            print(f"{timestamp_str} | {s:<20} | INVALID_MSG      | RESOLVED")
                            sys.stdout.flush()
                            del first_detected_issues[issue_key]
                         last_known_ok_state[s]['valid'] = True


                    expected_freq = service_info.frequency
                    # 3. Alive Check
                    if expected_freq > 1e-5: # Only for services with defined frequency
                        # Generous threshold: 10 times the expected interval, or minimum 2s, max 60s
                        alive_threshold = max(2.0, min(60.0, (10.0 / expected_freq if expected_freq > 0 else 60.0)))
                        time_since_last_recv = current_time - sm.recv_time[s]

                        current_alive_status = time_since_last_recv < alive_threshold if sm.recv_time[s] > 0 else False # False if never received
                        if sm.recv_time[s] == 0 and should_be_publishing: # If never received but should be, it's not alive effectively
                            current_alive_status = False

                        if not current_alive_status and last_known_ok_state[s]['alive'] and should_be_publishing:
                            service_ok_this_cycle = False
                            issue_key = (s, "NOT_ALIVE")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                details = f"Stalled. Last recv: {time_since_last_recv:.2f}s ago (thresh: {alive_threshold:.2f}s)."
                                if sm.recv_time[s] == 0:
                                    details = "Stalled. No messages ever received."
                                print(f"{timestamp_str} | {s:<20} | NOT_ALIVE        | {details}")
                                sys.stdout.flush()
                        last_known_ok_state[s]['alive'] = current_alive_status
                        if current_alive_status and not last_known_ok_state[s]['alive']:
                            issue_key = (s, "NOT_ALIVE")
                            if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | NOT_ALIVE        | RESOLVED")
                                sys.stdout.flush()
                                del first_detected_issues[issue_key]
                            last_known_ok_state[s]['alive'] = True


                    # 4. Frequency Check
                    if expected_freq > 1e-5 and len(sm.recv_dts[s]) > max(1, int(expected_freq * 0.5)) : # Need some samples, e.g., 0.5s worth
                        current_freq_ok_status = sm.freq_ok[s]
                        if not current_freq_ok_status and last_known_ok_state[s]['freq_ok']:
                            service_ok_this_cycle = False
                            issue_key = (s, "BAD_FREQ")
                            if issue_key not in first_detected_issues:
                                first_detected_issues[issue_key] = current_time
                                dts = sm.recv_dts[s]
                                avg_freq = 1.0 / (sum(dts) / len(dts)) if dts and sum(dts) > 0 else 0
                                recent_dts_len = max(1, int(len(dts) * 0.2)) # Check last 20% of samples
                                recent_dts = list(dts)[-recent_dts_len:]
                                avg_freq_recent = 1.0 / (sum(recent_dts) / len(recent_dts)) if recent_dts and sum(recent_dts) > 0 else 0
                                details = (f"Expected: {expected_freq:.1f}Hz. Avg: {avg_freq:.1f}Hz, Recent: {avg_freq_recent:.1f}Hz. "
                                           f"(Range: {sm.min_freq[s]:.1f}-{sm.max_freq[s]:.1f}Hz). Samples: {len(dts)}")
                                print(f"{timestamp_str} | {s:<20} | BAD_FREQ         | {details}")
                                sys.stdout.flush()
                        last_known_ok_state[s]['freq_ok'] = current_freq_ok_status
                        if current_freq_ok_status and not last_known_ok_state[s]['freq_ok']:
                            issue_key = (s, "BAD_FREQ")
                            if issue_key in first_detected_issues:
                                print(f"{timestamp_str} | {s:<20} | BAD_FREQ         | RESOLVED")
                                sys.stdout.flush()
                                del first_detected_issues[issue_key]
                            last_known_ok_state[s]['freq_ok'] = True

            time.sleep(0.05) # Loop update rate - increased frequency for faster detection

    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
    finally:
        print("Exiting communication monitor.")

if __name__ == "__main__":
    main()