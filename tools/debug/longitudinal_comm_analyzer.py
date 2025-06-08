#!/usr/bin/env python3
"""
Advanced analyzer for longitudinal control communication issues.
This tool provides deep analysis of timing, sequencing, and dependencies
between services during longitudinal control engagement.
"""

import time
import sys
import os
import signal
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import cereal.messaging as messaging
from cereal import car
from common.params import Params
from common.realtime import Ratekeeper
from selfdrive.controls.lib.events import Events, EventName, ET


class LongitudinalCommAnalyzer:
    def __init__(self):
        # Core services with dependencies
        self.service_dependencies = {
            'longitudinalPlan': ['carState', 'modelV2', 'radarState'],
            'controlsState': ['carState', 'modelV2', 'longitudinalPlan'],
            'carControl': ['controlsState', 'carState', 'longitudinalPlan'],
        }
        
        self.all_services = list(set(
            sum(self.service_dependencies.values(), []) + 
            list(self.service_dependencies.keys())
        ))
        
        self.sm = messaging.SubMaster(self.all_services)
        self.params = Params()
        
        # Timing analysis
        self.service_timings = defaultdict(lambda: deque(maxlen=1000))
        self.inter_service_delays = defaultdict(lambda: deque(maxlen=1000))
        self.sequence_violations = []
        
        # State tracking
        self.last_update_times = {}
        self.service_update_counts = defaultdict(int)
        self.dependency_failures = []
        
        # Longitudinal state
        self.long_active = False
        self.long_active_transitions = []
        
        # Output file
        self.log_file = open(f"/data/longitudinal_comm_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", 'w')
        
    def log(self, message: str, level: str = "INFO"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        self.log_file.write(log_line + "\n")
        self.log_file.flush()
    
    def analyze_timing(self):
        """Analyze service update timing and delays."""
        current_time = time.monotonic()
        
        for service in self.all_services:
            if self.sm.updated[service]:
                # Record update time
                self.service_timings[service].append(current_time)
                self.service_update_counts[service] += 1
                
                # Calculate inter-update delay
                if service in self.last_update_times:
                    delay = current_time - self.last_update_times[service]
                    self.inter_service_delays[service].append(delay)
                
                self.last_update_times[service] = current_time
                
                # Check dependencies
                self.check_dependencies(service, current_time)
    
    def check_dependencies(self, service: str, current_time: float):
        """Check if dependencies were updated before this service."""
        if service in self.service_dependencies:
            for dep in self.service_dependencies[service]:
                if dep not in self.last_update_times:
                    self.dependency_failures.append({
                        'time': current_time,
                        'service': service,
                        'missing_dep': dep,
                        'reason': 'never_updated'
                    })
                elif self.last_update_times[dep] > current_time - 0.1:  # 100ms window
                    # Dependency is stale
                    self.dependency_failures.append({
                        'time': current_time,
                        'service': service,
                        'missing_dep': dep,
                        'reason': 'stale',
                        'age_ms': (current_time - self.last_update_times[dep]) * 1000
                    })
    
    def check_sequence_violations(self):
        """Check for out-of-order service updates."""
        # Expected sequence: carState -> modelV2/radarState -> longitudinalPlan -> controlsState
        expected_sequence = ['carState', 'modelV2', 'longitudinalPlan', 'controlsState']
        
        recent_updates = sorted(
            [(service, self.last_update_times.get(service, 0)) for service in expected_sequence],
            key=lambda x: x[1]
        )
        
        for i in range(len(recent_updates) - 1):
            if recent_updates[i][1] > recent_updates[i+1][1]:
                self.sequence_violations.append({
                    'time': time.monotonic(),
                    'violation': f"{recent_updates[i][0]} updated after {recent_updates[i+1][0]}",
                    'time_diff_ms': (recent_updates[i][1] - recent_updates[i+1][1]) * 1000
                })
    
    def analyze_longitudinal_state(self):
        """Track longitudinal control state changes."""
        if self.sm.updated['controlsState']:
            cs = self.sm['controlsState']
            new_long_active = cs.longActive if hasattr(cs, 'longActive') else False
            
            if new_long_active != self.long_active:
                transition = {
                    'time': time.monotonic(),
                    'from': self.long_active,
                    'to': new_long_active,
                    'service_states': self.get_service_states()
                }
                self.long_active_transitions.append(transition)
                self.log(f"LONGITUDINAL STATE CHANGE: {self.long_active} -> {new_long_active}", "WARNING")
                
                # Log service states at transition
                for service, state in transition['service_states'].items():
                    self.log(f"  {service}: alive={state['alive']}, valid={state['valid']}, freq_ok={state['freq_ok']}")
                
                self.long_active = new_long_active
    
    def get_service_states(self) -> Dict:
        """Get current state of all services."""
        states = {}
        for service in self.all_services:
            states[service] = {
                'alive': self.sm.alive[service],
                'valid': self.sm.valid[service],
                'freq_ok': self.sm.freq_ok[service],
                'update_count': self.service_update_counts[service],
                'last_update_age': time.monotonic() - self.last_update_times.get(service, 0)
            }
        return states
    
    def calculate_statistics(self):
        """Calculate and log timing statistics."""
        self.log("\n=== TIMING STATISTICS ===", "INFO")
        
        for service in self.all_services:
            if service in self.inter_service_delays and len(self.inter_service_delays[service]) > 10:
                delays = np.array(self.inter_service_delays[service])
                expected_period = 1.0 / {'carState': 100, 'modelV2': 20, 'longitudinalPlan': 20}.get(service, 10)
                
                stats = {
                    'mean_ms': np.mean(delays) * 1000,
                    'std_ms': np.std(delays) * 1000,
                    'min_ms': np.min(delays) * 1000,
                    'max_ms': np.max(delays) * 1000,
                    'expected_ms': expected_period * 1000,
                    'jitter_ms': np.std(delays) * 1000
                }
                
                self.log(f"{service}: mean={stats['mean_ms']:.1f}ms, std={stats['std_ms']:.1f}ms, " +
                        f"expected={stats['expected_ms']:.1f}ms, jitter={stats['jitter_ms']:.1f}ms")
                
                # Flag high jitter
                if stats['jitter_ms'] > stats['expected_ms'] * 0.2:  # 20% jitter threshold
                    self.log(f"  WARNING: High jitter detected for {service}!", "WARNING")
    
    def print_summary(self):
        """Print analysis summary."""
        self.log("\n=== ANALYSIS SUMMARY ===", "INFO")
        
        # Dependency failures
        if self.dependency_failures:
            self.log(f"\nDependency Failures: {len(self.dependency_failures)}", "ERROR")
            for failure in self.dependency_failures[-10:]:  # Last 10
                self.log(f"  {failure['service']} missing {failure['missing_dep']} ({failure['reason']})")
        
        # Sequence violations
        if self.sequence_violations:
            self.log(f"\nSequence Violations: {len(self.sequence_violations)}", "ERROR")
            for violation in self.sequence_violations[-10:]:  # Last 10
                self.log(f"  {violation['violation']} (diff: {violation['time_diff_ms']:.1f}ms)")
        
        # Longitudinal transitions
        if self.long_active_transitions:
            self.log(f"\nLongitudinal State Transitions: {len(self.long_active_transitions)}", "INFO")
            for trans in self.long_active_transitions:
                self.log(f"  {trans['from']} -> {trans['to']} at {trans['time']:.2f}s")
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        self.log("\n\nAnalysis interrupted by user", "INFO")
        self.calculate_statistics()
        self.print_summary()
        self.log_file.close()
        print(f"\nAnalysis saved to: {self.log_file.name}")
        sys.exit(0)
    
    def run(self):
        """Main analysis loop."""
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.log("Starting Longitudinal Communication Analysis...", "INFO")
        self.log("Monitoring service timing, dependencies, and state transitions", "INFO")
        self.log("Press Ctrl+C to stop and see analysis summary\n", "INFO")
        
        rk = Ratekeeper(100)  # 100Hz analysis
        
        while True:
            self.sm.update(0)
            
            self.analyze_timing()
            self.check_sequence_violations()
            self.analyze_longitudinal_state()
            
            # Periodic statistics
            if rk.frame % 1000 == 0:  # Every 10 seconds at 100Hz
                self.calculate_statistics()
            
            rk.keep_time()


if __name__ == "__main__":
    analyzer = LongitudinalCommAnalyzer()
    analyzer.run()