#!/usr/bin/env python3
"""
Cereal messaging diagnostics for custom PMS issues.
Specifically designed to detect conflicts and issues with custom cereal messages
that might cause communication errors during longitudinal control engagement.
"""

import time
import json
import sys
import os
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple

import cereal.messaging as messaging
from cereal.services import SERVICE_LIST
from common.params import Params
from common.realtime import Ratekeeper


class CerealMessageDiagnostics:
    def __init__(self):
        # All services including custom ones
        self.all_services = list(SERVICE_LIST.keys())
        
        # Custom services added by FrogPilot/Chauffeur
        self.custom_services = [
            'frogpilotCarControl', 'frogpilotCarState', 'frogpilotDeviceState',
            'frogpilotNavigation', 'frogpilotPlan', 'chauffeurHKGTuning',
            'chauffeurTurnSpeedControl', 'liveMapData'
        ]
        
        # Critical services for longitudinal control
        self.critical_services = [
            'carState', 'controlsState', 'modelV2', 'longitudinalPlan',
            'liveLocationKalman', 'liveParameters', 'radarState',
            'pandaStates', 'deviceState', 'managerState', 'carOutput'
        ]
        
        # Services that might conflict with custom messages
        self.potential_conflicts = {
            'frogpilotCarControl': ['carControl'],
            'frogpilotCarState': ['carState'],
            'frogpilotPlan': ['longitudinalPlan'],
            'frogpilotDeviceState': ['deviceState'],
        }
        
        # Try to subscribe to all services
        try:
            self.sm = messaging.SubMaster(self.all_services)
        except Exception as e:
            print(f"WARNING: Could not subscribe to all services: {e}")
            # Fall back to critical services only
            self.sm = messaging.SubMaster(self.critical_services)
        
        self.params = Params()
        
        # Tracking
        self.message_counts = defaultdict(int)
        self.message_sizes = defaultdict(list)
        self.message_errors = defaultdict(list)
        self.timing_conflicts = []
        self.publishing_issues = []
        
        # Socket monitoring
        self.socket_errors = defaultdict(int)
        self.zmq_errors = []
        
        self.start_time = time.time()
        self.log_file = open(f"/data/cereal_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", 'w')
        
    def log(self, message: str, level: str = "INFO"):
        """Log message to file and console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{level}] {message}"
        print(log_line)
        self.log_file.write(log_line + "\n")
        self.log_file.flush()
    
    def check_service_conflicts(self):
        """Check for conflicts between custom and standard services."""
        current_time = time.time()
        
        for custom_service, conflicting_services in self.potential_conflicts.items():
            if custom_service in self.sm.alive and self.sm.alive[custom_service]:
                # Check if conflicting services are also active
                for conflict in conflicting_services:
                    if conflict in self.sm.alive and self.sm.alive[conflict]:
                        # Both services active - potential conflict
                        conflict_info = {
                            'time': current_time,
                            'custom': custom_service,
                            'standard': conflict,
                            'custom_freq': self.sm.freq_ok.get(custom_service, False),
                            'standard_freq': self.sm.freq_ok.get(conflict, False)
                        }
                        self.timing_conflicts.append(conflict_info)
                        self.log(f"CONFLICT: Both {custom_service} and {conflict} are active!", "WARNING")
    
    def analyze_message_sizes(self):
        """Check for unusually large messages that might cause issues."""
        for service in self.all_services:
            if service in self.sm.updated and self.sm.updated[service]:
                try:
                    # Get message size (approximate)
                    msg = getattr(self.sm, service)
                    if msg:
                        # Estimate size based on string representation
                        msg_size = len(str(msg))
                        self.message_sizes[service].append(msg_size)
                        
                        # Keep only last 100 sizes
                        if len(self.message_sizes[service]) > 100:
                            self.message_sizes[service] = self.message_sizes[service][-100:]
                        
                        # Check for unusually large messages
                        if msg_size > 10000:  # 10KB threshold
                            self.log(f"LARGE MESSAGE: {service} size={msg_size} bytes", "WARNING")
                except Exception as e:
                    self.message_errors[service].append(str(e))
    
    def check_message_publishing(self):
        """Detect issues with message publishing patterns."""
        # Check for services that should be publishing but aren't
        for service in self.custom_services:
            if service in SERVICE_LIST:
                expected_freq = SERVICE_LIST[service][1]
                if service in self.sm.alive and not self.sm.alive[service]:
                    self.publishing_issues.append({
                        'service': service,
                        'issue': 'not_alive',
                        'expected_freq': expected_freq
                    })
                    self.log(f"PUBLISHING ISSUE: {service} is registered but not alive", "ERROR")
    
    def monitor_zmq_health(self):
        """Monitor ZMQ socket health and errors."""
        try:
            # Check for socket errors by examining service health
            for service in self.all_services:
                if service in self.sm.alive:
                    # A service that was alive but suddenly isn't might indicate socket issues
                    if hasattr(self, 'last_alive_state'):
                        if self.last_alive_state.get(service, False) and not self.sm.alive[service]:
                            self.socket_errors[service] += 1
                            self.log(f"SOCKET ISSUE: {service} lost connection", "ERROR")
            
            # Update last alive state
            self.last_alive_state = dict(self.sm.alive)
            
        except Exception as e:
            self.zmq_errors.append({
                'time': time.time(),
                'error': str(e)
            })
            self.log(f"ZMQ ERROR: {e}", "ERROR")
    
    def check_longitudinal_dependencies(self):
        """Specifically check services critical for longitudinal control."""
        issues = []
        
        # Check if custom services are interfering with critical services
        for critical in self.critical_services:
            if critical in self.sm.alive:
                if not self.sm.alive[critical]:
                    issues.append(f"{critical} not alive")
                elif not self.sm.freq_ok.get(critical, False):
                    issues.append(f"{critical} frequency issues")
                elif not self.sm.valid.get(critical, False):
                    issues.append(f"{critical} invalid data")
        
        if issues:
            self.log(f"LONGITUDINAL DEPS: {', '.join(issues)}", "ERROR")
        
        # Check for custom service interference
        if 'frogpilotPlan' in self.sm.updated and self.sm.updated['frogpilotPlan']:
            if 'longitudinalPlan' in self.sm.updated and self.sm.updated['longitudinalPlan']:
                # Both plans updating - potential conflict
                self.log("CONFLICT: Both frogpilotPlan and longitudinalPlan updating!", "WARNING")
    
    def print_status(self):
        """Print comprehensive status dashboard."""
        print("\n" + "="*100)
        print(f"CEREAL MESSAGE DIAGNOSTICS - {datetime.now().strftime('%H:%M:%S')}")
        print("="*100)
        
        # Custom services status
        print("\nCUSTOM SERVICES STATUS:")
        print(f"{'Service':<30} {'Alive':<8} {'Freq OK':<10} {'Valid':<8} {'Msg Count':<12} {'Errors':<10}")
        print("-" * 80)
        
        for service in self.custom_services:
            if service in self.sm.alive:
                alive = "✓" if self.sm.alive[service] else "✗"
                freq_ok = "✓" if self.sm.freq_ok.get(service, False) else "✗"
                valid = "✓" if self.sm.valid.get(service, False) else "✗"
                count = self.message_counts.get(service, 0)
                errors = len(self.message_errors.get(service, []))
                
                color = "\033[91m" if not self.sm.alive[service] else ""
                print(f"{color}{service:<30} {alive:<8} {freq_ok:<10} {valid:<8} {count:<12} {errors:<10}\033[0m")
        
        # Conflicts
        if self.timing_conflicts:
            print("\n\033[93mACTIVE CONFLICTS:\033[0m")
            recent_conflicts = self.timing_conflicts[-5:]  # Last 5
            for conflict in recent_conflicts:
                print(f"  {conflict['custom']} <-> {conflict['standard']}")
        
        # Publishing issues
        if self.publishing_issues:
            print("\n\033[91mPUBLISHING ISSUES:\033[0m")
            for issue in self.publishing_issues[-5:]:
                print(f"  {issue['service']}: {issue['issue']}")
        
        # Socket errors
        if self.socket_errors:
            print("\n\033[91mSOCKET ERRORS:\033[0m")
            for service, count in list(self.socket_errors.items())[:5]:
                print(f"  {service}: {count} disconnections")
        
        # Message size analysis
        print("\nMESSAGE SIZE ANALYSIS:")
        for service in self.custom_services:
            if service in self.message_sizes and self.message_sizes[service]:
                avg_size = sum(self.message_sizes[service]) / len(self.message_sizes[service])
                max_size = max(self.message_sizes[service])
                print(f"  {service}: avg={avg_size:.0f} bytes, max={max_size} bytes")
    
    def generate_report(self):
        """Generate detailed diagnostic report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'runtime_seconds': time.time() - self.start_time,
            'custom_services_status': {},
            'timing_conflicts': self.timing_conflicts,
            'publishing_issues': self.publishing_issues,
            'socket_errors': dict(self.socket_errors),
            'zmq_errors': self.zmq_errors,
            'message_errors': dict(self.message_errors),
            'message_statistics': {}
        }
        
        # Add service status
        for service in self.custom_services:
            if service in self.sm.alive:
                report['custom_services_status'][service] = {
                    'alive': self.sm.alive[service],
                    'freq_ok': self.sm.freq_ok.get(service, False),
                    'valid': self.sm.valid.get(service, False),
                    'message_count': self.message_counts.get(service, 0),
                    'errors': self.message_errors.get(service, [])
                }
        
        # Add message statistics
        for service, sizes in self.message_sizes.items():
            if sizes:
                report['message_statistics'][service] = {
                    'avg_size': sum(sizes) / len(sizes),
                    'max_size': max(sizes),
                    'min_size': min(sizes)
                }
        
        filename = f"/data/cereal_diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return filename
    
    def run(self):
        """Main diagnostic loop."""
        self.log("Starting Cereal Message Diagnostics...", "INFO")
        self.log("Monitoring custom message services and potential conflicts", "INFO")
        self.log("Press Ctrl+C to stop and generate report\n", "INFO")
        
        rk = Ratekeeper(10)  # 10Hz monitoring
        
        try:
            while True:
                self.sm.update(0)
                
                # Update message counts
                for service in self.all_services:
                    if service in self.sm.updated and self.sm.updated[service]:
                        self.message_counts[service] += 1
                
                # Run diagnostics
                self.check_service_conflicts()
                self.analyze_message_sizes()
                self.check_message_publishing()
                self.monitor_zmq_health()
                self.check_longitudinal_dependencies()
                
                # Clear screen and print status
                if rk.frame % 10 == 0:  # Every second
                    print("\033[2J\033[H")  # Clear screen
                    self.print_status()
                
                rk.keep_time()
                
        except KeyboardInterrupt:
            print("\n\nStopping diagnostics...")
            filename = self.generate_report()
            self.log_file.close()
            print(f"\nDiagnostic report saved to: {filename}")
            print(f"Log file saved to: {self.log_file.name}")


if __name__ == "__main__":
    diag = CerealMessageDiagnostics()
    diag.run()