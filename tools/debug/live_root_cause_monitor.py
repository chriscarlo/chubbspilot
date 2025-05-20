#!/usr/bin/env python3
import cereal.messaging as messaging
from cereal import log, services
import time
import json
import os
import capnp
from collections import defaultdict
import sys

# Path to the service graph file
GRAPH_INPUT_FILE = "tools/debug/service_graph.json"
OPENPILOT_ROOT = os.path.join(os.path.dirname(__file__), "../..")

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

class LiveRootCauseMonitor:
    def __init__(self, service_graph):
        self.service_graph = service_graph # { proc: {"publishes": [], "subscribes": []} }
        self.process_to_services_published = service_graph # alias for clarity in some contexts

        self.services_to_process_publisher = {}
        for proc, data in service_graph.items():
            for s_pub in data.get("publishes", []):
                self.services_to_process_publisher[s_pub] = proc

        # ------------------------------------------------------------------
        # We want full coverage, so subscribe to *all* defined services plus
        # managerState.  This guarantees we see validity transitions for
        # services whose publisher we might not know yet.
        # ------------------------------------------------------------------
        self.monitored_services = list(services.SERVICE_LIST.keys())
        if 'managerState' not in self.monitored_services:
            self.monitored_services.append('managerState')

        unknown_pubs = []
        for svc in self.monitored_services:
            if svc not in self.services_to_process_publisher and svc != 'managerState':
                self.services_to_process_publisher[svc] = None  # Unknown publisher
                unknown_pubs.append(svc)

        print(f"Monitoring {len(self.monitored_services) -1 } total services (+ managerState)")
        if unknown_pubs:
            print(f"  (Info) {len(unknown_pubs)} services have unknown publisher mapping and will be tracked generically.")

        self.sm = messaging.SubMaster(self.monitored_services, ignore_alive=[])

        self.service_current_valid = {s: True for s in self.monitored_services}
        self.service_last_msg_content = {s: "" for s in self.monitored_services}
        self.process_current_running = {proc: True for proc in self.service_graph.keys()}
        self.process_current_should_run = {proc: True for proc in self.service_graph.keys()}
        self.process_last_exit_code = {proc: 0 for proc in self.service_graph.keys()}

        # Tracks the timestamp when a root cause was first identified for an issue
        # {(item_name, issue_type): timestamp}
        self.active_root_causes = {}

    def _log_issue(self, item_name, issue_type, details, is_root_cause=False):
        current_time = time.monotonic()
        timestamp_str = f"{time.strftime('%H:%M:%S')}.{int((current_time - int(current_time)) * 1000):03d}"

        issue_key = (item_name, issue_type)
        status_prefix = "ROOT-CAUSE" if is_root_cause else "INFO"

        if issue_key not in self.active_root_causes or is_root_cause: # Always print root causes
            if is_root_cause:
                 self.active_root_causes[issue_key] = current_time # Mark as active root cause
            print(f"{timestamp_str} | {status_prefix:<10} | {item_name:<25} | {issue_type:<20} | {details}")
            sys.stdout.flush()

    def _log_resolved(self, item_name, issue_type):
        current_time = time.monotonic()
        timestamp_str = f"{time.strftime('%H:%M:%S')}.{int((current_time - int(current_time)) * 1000):03d}"
        issue_key = (item_name, issue_type)
        if issue_key in self.active_root_causes: # Only log resolution for active root causes
            print(f"{timestamp_str} | RESOLVED   | {item_name:<25} | {issue_type:<20} | Issue resolved or no longer considered root.")
            sys.stdout.flush()
            del self.active_root_causes[issue_key]

    def run(self):
        print("\nTimestamp   | Status     | Item (Service/Process)        | Issue Type           | Details")
        print("------------|------------|-------------------------------|----------------------|-------------------------------------------------")
        sys.stdout.flush()

        while True:
            self.sm.update(0) # Poll with minimal timeout, effectively non-blocking for non-polled
            cur_time = time.monotonic()

            # 1. Check managerState for process health
            if self.sm.updated['managerState'] and self.sm['managerState'] is not None:
                current_managed_procs = {p.name for p in self.sm['managerState'].processes}
                for p_log in self.sm['managerState'].processes:
                    proc_name = p_log.name
                    if proc_name not in self.service_graph: # Only care about procs in our graph
                        continue

                    prev_running = self.process_current_running.get(proc_name, True)
                    prev_should_run = self.process_current_should_run.get(proc_name, True)

                    self.process_current_running[proc_name] = p_log.running
                    self.process_current_should_run[proc_name] = p_log.shouldBeRunning
                    self.process_last_exit_code[proc_name] = p_log.exitCode

                    is_crashed = p_log.shouldBeRunning and not p_log.running and p_log.exitCode != 0
                    was_crashed_and_now_ok = not is_crashed and (not prev_should_run or prev_running)

                    if is_crashed and not (self.active_root_causes.get((proc_name, "PROC_CRASHED"))):
                        details = f"Process crashed or exited with error. Exit code: {p_log.exitCode}."
                        self._log_issue(proc_name, "PROC_CRASHED", details, is_root_cause=True)
                        # When a process crashes, services it publishes might become stale/invalid
                        for s_pub in self.process_to_services_published.get(proc_name, {}).get("publishes", []):
                            if self.service_current_valid.get(s_pub, True):
                                self._log_issue(s_pub, "IMPLICIT_INVALID", f"Publisher process {proc_name} crashed.", is_root_cause=False)
                                self.service_current_valid[s_pub] = False # Mark as invalid due to crash
                    elif was_crashed_and_now_ok:
                         self._log_resolved(proc_name, "PROC_CRASHED")

                # Check for processes that disappeared from managerState but were in graph
                for known_proc in self.service_graph.keys():
                    if known_proc not in current_managed_procs and self.process_current_running.get(known_proc, False):
                        details = "Process disappeared from managerState but was previously running."
                        self._log_issue(known_proc, "PROC_MISSING", details, is_root_cause=True)
                        self.process_current_running[known_proc] = False # Mark as not running
                        for s_pub in self.process_to_services_published.get(known_proc, {}).get("publishes", []):
                             if self.service_current_valid.get(s_pub, True):
                                self._log_issue(s_pub, "IMPLICIT_INVALID", f"Publisher process {known_proc} missing.", is_root_cause=False)
                                self.service_current_valid[s_pub] = False
                    elif known_proc in current_managed_procs and not self.process_current_running.get(known_proc, True) and not self.active_root_causes.get((known_proc, "PROC_MISSING")):
                        pass # It's correctly reported by managerState, handled above
                    elif known_proc not in current_managed_procs and self.active_root_causes.get((known_proc, "PROC_MISSING")):
                         self._log_resolved(known_proc, "PROC_MISSING")

            # 2. Check service message validity
            for s_name in self.monitored_services:
                if s_name == 'managerState': continue # Handled above

                publisher_proc = self.services_to_process_publisher.get(s_name)
                # allow None publisher, we still monitor

                # If we know a publisher and it is not running, mark implicit invalid
                if publisher_proc is not None and not self.process_current_running.get(publisher_proc, True):
                    if self.service_current_valid.get(s_name, True): # If it was previously considered valid
                        self.service_current_valid[s_name] = False
                        # No need to log issue here, PROC_CRASHED/PROC_MISSING for publisher is the root
                    continue # Skip further checks for this service

                # Handle case where it recovers from a process crash
                if not self.service_current_valid.get(s_name, True) and self.process_current_running.get(publisher_proc, True) and (self.active_root_causes.get((publisher_proc, "PROC_CRASHED")) is None and self.active_root_causes.get((publisher_proc, "PROC_MISSING")) is None):
                    is_implicitly_invalid_due_to_publisher_crash = any(
                        msg == f"Publisher process {publisher_proc} crashed." or msg == f"Publisher process {publisher_proc} missing."
                        for msg in [self.service_last_msg_content.get(s_name, "")]
                    )
                    if is_implicitly_invalid_due_to_publisher_crash and self.sm.updated[s_name] and self.sm.valid[s_name]:
                        self._log_resolved(s_name, "IMPLICIT_INVALID")
                        self.service_current_valid[s_name] = True # Allow re-evaluation

                if self.sm.updated[s_name]:
                    current_s_valid = self.sm.valid[s_name]
                    prev_s_valid = self.service_current_valid.get(s_name, True)
                    msg_content = None

                    try:
                        # Access message content for logging, even if invalid (to see what's wrong)
                        # This might raise KjException if the message is truly malformed beyond recovery by cereal
                        if self.sm[s_name] is not None: # Check if sm[s_name] itself is None
                             msg_content = pretty_print_cereal(self.sm[s_name])
                             self.service_last_msg_content[s_name] = msg_content
                    except capnp.KjException as e:
                        if prev_s_valid: # Only log if it just transitioned
                            details = f"Capnproto KjException during message decode: {e}"
                            self._log_issue(s_name, "DECODE_ERROR", details, is_root_cause=True)
                        self.service_current_valid[s_name] = False
                        continue # This is a root cause, skip other checks for this service
                    except Exception as e:
                        # General error accessing message content, less specific than KjException
                        if prev_s_valid:
                            details = f"Error accessing message content for {s_name}: {e}"
                            self._log_issue(s_name, "MSG_ACCESS_ERR", details, is_root_cause=True) # Treat as potential root
                        self.service_current_valid[s_name] = False
                        continue

                    if not current_s_valid and prev_s_valid: # Transition to invalid
                        self.service_current_valid[s_name] = False

                        # Check if this is a root cause
                        is_root = True
                        root_cause_detail = "All subscribed inputs are currently valid."
                        subscribed_services = []
                        if publisher_proc is not None:
                            subscribed_services = self.process_to_services_published.get(publisher_proc, {}).get("subscribes", [])

                        if not subscribed_services:
                            root_cause_detail = "Process publishes this service but subscribes to no known (Python) services."
                        else:
                            inputs_details = []
                            for sub_s_name in subscribed_services:
                                input_publisher_proc = self.services_to_process_publisher.get(sub_s_name)
                                if not input_publisher_proc: # Input service not in our Python-parsed graph publishers
                                    inputs_details.append(f"{sub_s_name}(Unknown Publisher: Not in py-graph or Native)")
                                    continue # Cannot verify validity of this input's publisher

                                if not self.process_current_running.get(input_publisher_proc, True):
                                    is_root = False
                                    root_cause_detail = f"Input service '{sub_s_name}' publisher '{input_publisher_proc}' is not running."
                                    inputs_details.append(f"{sub_s_name}(FAIL:PubProcess '{input_publisher_proc}' DOWN)")
                                    break
                                if not self.service_current_valid.get(sub_s_name, True): # Check our tracked validity
                                    is_root = False
                                    root_cause_detail = f"Input service '{sub_s_name}' is currently invalid."
                                    inputs_details.append(f"{sub_s_name}(FAIL:Invalid)")
                                    break
                                inputs_details.append(f"{sub_s_name}(OK)")
                            if is_root:
                                root_cause_detail = f"All inputs valid: [{', '.join(inputs_details)}]"

                        details_origin = "Unknown publisher" if publisher_proc is None else f"Publisher: {publisher_proc}"
                        details = f"{details_origin}. Message invalid. Content: {str(msg_content)[:200]}. {root_cause_detail}"
                        self._log_issue(s_name, "INVALID_MSG", details, is_root_cause=is_root)

                    elif current_s_valid and not prev_s_valid:
                        # Transition back to valid
                        self.service_current_valid[s_name] = True
                        self._log_resolved(s_name, "INVALID_MSG")
                        self._log_resolved(s_name, "DECODE_ERROR") # Also clear if it was a decode error
                        self._log_resolved(s_name, "IMPLICIT_INVALID")
                        self._log_resolved(s_name, "MSG_ACCESS_ERR")

            time.sleep(0.05) # Poll frequency

def main():
    graph_abs_path = os.path.normpath(os.path.join(OPENPILOT_ROOT, GRAPH_INPUT_FILE))
    if not os.path.exists(graph_abs_path):
        print(f"Error: Service graph file not found at {graph_abs_path}", file=sys.stderr)
        print("Please run 'tools/debug/build_service_graph.py' first.", file=sys.stderr)
        sys.exit(1)

    with open(graph_abs_path, 'r') as f:
        service_graph = json.load(f)

    if not service_graph:
        print(f"Error: Service graph at {graph_abs_path} is empty or invalid.", file=sys.stderr)
        print("Please re-run 'tools/debug/build_service_graph.py'.", file=sys.stderr)
        sys.exit(1)

    monitor = LiveRootCauseMonitor(service_graph)
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nMonitor stopped by user.")
    finally:
        print("Exiting live root cause monitor.")

if __name__ == "__main__":
    main()
