#!/usr/bin/env python3
"""
Real-time communication issue diagnostics for longitudinal control engagement.
This tool monitors all critical services and provides detailed diagnostics when
communication issues occur during longitudinal control engagement.
"""

import time
import json
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Tuple

import cereal.messaging as messaging
from cereal.services import SERVICE_LIST
from common.params import Params
from selfdrive.controls.lib.events import Events, EventName, ET
from openpilot.selfdrive.controls.lib.longcontrol import LongCtrlState


# Critical services for longitudinal control
LONGITUDINAL_SERVICES = [
    'carState', 'controlsState', 'modelV2', 'longitudinalPlan',
    'liveLocationKalman', 'liveParameters', 'radarState',
    'pandaStates', 'deviceState', 'managerState', 'carOutput'
]

# Expected frequencies (Hz)
SERVICE_FREQUENCIES = {
    'carState': 100,
    'controlsState': 100,
    'modelV2': 20,
    'longitudinalPlan': 20,
    'liveLocationKalman': 20,
    'liveParameters': 20,
    'radarState': 20,
    'pandaStates': 10,
    'deviceState': 2,
    'managerState': 2,
    'carOutput': 100,
}


class CommunicationDiagnostics:
    def __init__(self):
        self.sm = messaging.SubMaster(LONGITUDINAL_SERVICES)
        self.params = Params()
        
        # State tracking
        self.service_stats = defaultdict(lambda: {
            'alive': False,
            'freq_ok': False,
            'valid': False,
            'last_update': 0,
            'update_times': [],
            'frequency': 0,
            'issues': []
        })
        
        self.longitudinal_engaged = False
        self.last_longitudinal_state = None
        self.issue_log = []
        self.start_time = time.time()
        
    def update_service_stats(self):
        """Update statistics for all monitored services."""
        current_time = time.time()
        
        for service in LONGITUDINAL_SERVICES:
            stats = self.service_stats[service]
            
            # Check if service is alive
            stats['alive'] = self.sm.alive[service]
            
            # Check frequency
            stats['freq_ok'] = self.sm.freq_ok[service]
            
            # Check validity
            if hasattr(self.sm, service):
                msg = getattr(self.sm, service)
                stats['valid'] = self.sm.valid[service]
                
                # Track update times for frequency calculation
                if self.sm.updated[service]:
                    stats['last_update'] = current_time
                    stats['update_times'].append(current_time)
                    
                    # Keep only last 100 updates
                    if len(stats['update_times']) > 100:
                        stats['update_times'] = stats['update_times'][-100:]
                    
                    # Calculate actual frequency
                    if len(stats['update_times']) > 10:
                        time_span = stats['update_times'][-1] - stats['update_times'][-10]
                        stats['frequency'] = 9.0 / time_span if time_span > 0 else 0
            
            # Detect issues
            stats['issues'] = []
            if not stats['alive']:
                stats['issues'].append('NOT_ALIVE')
            if not stats['freq_ok']:
                stats['issues'].append('FREQ_ISSUE')
            if not stats['valid']:
                stats['issues'].append('INVALID_DATA')
            
            # Check for stale data
            if current_time - stats['last_update'] > 1.0:
                stats['issues'].append('STALE_DATA')
    
    def check_longitudinal_state(self):
        """Check if longitudinal control is engaged or attempting to engage."""
        if self.sm.updated['controlsState']:
            cs = self.sm['controlsState']
            self.longitudinal_engaged = cs.longActive if hasattr(cs, 'longActive') else False
            
            # Check for state transitions
            if hasattr(cs, 'longControlState'):
                new_state = cs.longControlState
                if new_state != self.last_longitudinal_state:
                    self.log_event(f"Longitudinal state transition: {self.last_longitudinal_state} -> {new_state}")
                    self.last_longitudinal_state = new_state
    
    def detect_communication_issues(self) -> List[Dict]:
        """Detect and categorize communication issues."""
        issues = []
        
        # Check for services with issues
        for service, stats in self.service_stats.items():
            if stats['issues']:
                issue = {
                    'service': service,
                    'issues': stats['issues'],
                    'frequency': stats['frequency'],
                    'expected_freq': SERVICE_FREQUENCIES.get(service, 0),
                    'last_update': time.time() - stats['last_update']
                }
                issues.append(issue)
        
        # Check for specific longitudinal control blockers
        if not self.sm.all_checks():
            if not self.sm.all_alive():
                issues.append({
                    'type': 'COMM_ISSUE',
                    'reason': 'Not all services alive',
                    'dead_services': [s for s in LONGITUDINAL_SERVICES if not self.sm.alive[s]]
                })
            elif not self.sm.all_freq_ok():
                issues.append({
                    'type': 'COMM_ISSUE_AVG_FREQ',
                    'reason': 'Service frequency issues',
                    'low_freq_services': [s for s in LONGITUDINAL_SERVICES if not self.sm.freq_ok[s]]
                })
        
        return issues
    
    def log_event(self, message: str):
        """Log an event with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.issue_log.append(log_entry)
        print(log_entry)
    
    def print_status(self):
        """Print current status dashboard."""
        print("\n" + "="*80)
        print(f"LONGITUDINAL CONTROL COMMUNICATION DIAGNOSTICS - {datetime.now().strftime('%H:%M:%S')}")
        print("="*80)
        
        # Longitudinal state
        print(f"\nLongitudinal Control: {'ENGAGED' if self.longitudinal_engaged else 'DISENGAGED'}")
        print(f"Control State: {self.last_longitudinal_state}")
        
        # Service status table
        print("\nSERVICE STATUS:")
        print(f"{'Service':<20} {'Alive':<8} {'Freq OK':<10} {'Valid':<8} {'Actual Hz':<12} {'Expected Hz':<12} {'Issues':<30}")
        print("-" * 100)
        
        for service in LONGITUDINAL_SERVICES:
            stats = self.service_stats[service]
            alive_str = "✓" if stats['alive'] else "✗"
            freq_ok_str = "✓" if stats['freq_ok'] else "✗"
            valid_str = "✓" if stats['valid'] else "✗"
            actual_freq = f"{stats['frequency']:.1f}" if stats['frequency'] > 0 else "N/A"
            expected_freq = f"{SERVICE_FREQUENCIES.get(service, 0)}"
            issues_str = ", ".join(stats['issues']) if stats['issues'] else "None"
            
            # Color coding for terminal
            if stats['issues']:
                print(f"\033[91m{service:<20} {alive_str:<8} {freq_ok_str:<10} {valid_str:<8} {actual_freq:<12} {expected_freq:<12} {issues_str:<30}\033[0m")
            else:
                print(f"{service:<20} {alive_str:<8} {freq_ok_str:<10} {valid_str:<8} {actual_freq:<12} {expected_freq:<12} {issues_str:<30}")
        
        # Current issues
        issues = self.detect_communication_issues()
        if issues:
            print("\n\033[93mACTIVE ISSUES:\033[0m")
            for i, issue in enumerate(issues, 1):
                print(f"\n{i}. {json.dumps(issue, indent=2)}")
        
        # Recent events
        if self.issue_log:
            print("\n\033[94mRECENT EVENTS (last 10):\033[0m")
            for event in self.issue_log[-10:]:
                print(event)
    
    def save_diagnostic_report(self):
        """Save detailed diagnostic report to file."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'runtime_seconds': time.time() - self.start_time,
            'longitudinal_engaged': self.longitudinal_engaged,
            'last_longitudinal_state': self.last_longitudinal_state,
            'service_stats': dict(self.service_stats),
            'active_issues': self.detect_communication_issues(),
            'event_log': self.issue_log
        }
        
        filename = f"/data/longitudinal_comm_diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return filename
    
    def run(self):
        """Main diagnostic loop."""
        print("Starting Longitudinal Control Communication Diagnostics...")
        print("Press Ctrl+C to stop and save diagnostic report.")
        print("\nMonitoring will begin when you attempt to engage longitudinal control...")
        
        try:
            while True:
                self.sm.update(0)
                
                self.update_service_stats()
                self.check_longitudinal_state()
                
                # Log any new issues
                issues = self.detect_communication_issues()
                for issue in issues:
                    issue_str = json.dumps(issue)
                    if issue_str not in [json.dumps(i) for i in self.issue_log[-10:]]:
                        self.log_event(f"ISSUE DETECTED: {issue_str}")
                
                # Clear screen and print status
                print("\033[2J\033[H")  # Clear screen and move cursor to top
                self.print_status()
                
                time.sleep(0.1)  # 10Hz update rate
                
        except KeyboardInterrupt:
            print("\n\nStopping diagnostics...")
            filename = self.save_diagnostic_report()
            print(f"Diagnostic report saved to: {filename}")
            print("\nTo analyze the report, run:")
            print(f"  python3 -m json.tool {filename} | less")


if __name__ == "__main__":
    diag = CommunicationDiagnostics()
    diag.run()