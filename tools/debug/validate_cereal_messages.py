#!/usr/bin/env python3
"""
Validate cereal message configuration and detect common PMS mistakes.
This tool checks for configuration errors that can cause communication issues.
"""

import os
import sys
import importlib
import inspect
from typing import Dict, List, Set, Tuple

# Add openpilot to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from cereal.services import SERVICE_LIST
import cereal.messaging as messaging
from common.params import Params


class CerealMessageValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        
        # Expected service configuration
        self.expected_config = {
            # service_name: (should_log, frequency, decimation)
            'frogpilotCarControl': (True, 100., 10),
            'frogpilotCarState': (True, 100., 10),
            'frogpilotDeviceState': (True, 2., 1),
            'frogpilotNavigation': (True, 1., 10),
            'frogpilotPlan': (True, 20., 5),
            'chauffeurHKGTuning': (True, 100., 10),
            'chauffeurTurnSpeedControl': (True, 20., 5),
        }
        
    def validate_service_registration(self):
        """Check if all custom services are properly registered."""
        print("\n1. VALIDATING SERVICE REGISTRATION")
        print("-" * 50)
        
        for service, expected in self.expected_config.items():
            if service in SERVICE_LIST:
                actual = SERVICE_LIST[service]
                if actual != expected:
                    self.errors.append(f"{service}: Config mismatch - Expected {expected}, got {actual}")
                else:
                    self.info.append(f"{service}: ✓ Properly registered")
            else:
                self.errors.append(f"{service}: NOT registered in SERVICE_LIST!")
    
    def check_publisher_conflicts(self):
        """Check for multiple publishers to the same service."""
        print("\n2. CHECKING FOR PUBLISHER CONFLICTS")
        print("-" * 50)
        
        # Search for PubMaster usage
        publisher_map = {}
        
        # Common files that might publish messages
        files_to_check = [
            'selfdrive/controls/controlsd.py',
            'selfdrive/controls/plannerd.py',
            'selfdrive/frogpilot/frogpilot_process.py',
            'selfdrive/frogpilot/frogpilot_planner.py',
            'system/hardware/hardwared.py',
            'selfdrive/navd/navd.py',
        ]
        
        for file_path in files_to_check:
            full_path = os.path.join('/data/openpilot', file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r') as f:
                        content = f.read()
                        
                    # Look for pm.send patterns
                    import re
                    send_patterns = re.findall(r'pm\.send\(["\'](\w+)["\']', content)
                    
                    for service in send_patterns:
                        if service not in publisher_map:
                            publisher_map[service] = []
                        publisher_map[service].append(file_path)
                        
                except Exception as e:
                    self.warnings.append(f"Could not analyze {file_path}: {e}")
        
        # Check for conflicts
        for service, publishers in publisher_map.items():
            if len(publishers) > 1:
                self.errors.append(f"{service}: Multiple publishers detected: {publishers}")
            else:
                self.info.append(f"{service}: Single publisher in {publishers[0]}")
    
    def validate_message_frequencies(self):
        """Check if message frequencies make sense."""
        print("\n3. VALIDATING MESSAGE FREQUENCIES")
        print("-" * 50)
        
        frequency_groups = {
            100: ['carState', 'controlsState', 'carControl', 'frogpilotCarControl', 'frogpilotCarState'],
            20: ['modelV2', 'longitudinalPlan', 'frogpilotPlan', 'chauffeurTurnSpeedControl'],
            10: ['pandaStates'],
            2: ['deviceState', 'frogpilotDeviceState'],
            1: ['frogpilotNavigation'],
        }
        
        for freq, services in frequency_groups.items():
            for service in services:
                if service in SERVICE_LIST:
                    actual_freq = SERVICE_LIST[service][1]
                    if actual_freq != freq:
                        self.warnings.append(f"{service}: Frequency mismatch - Expected {freq}Hz, got {actual_freq}Hz")
    
    def check_subscriber_publisher_mismatch(self):
        """Check for services that are subscribed to but never published."""
        print("\n4. CHECKING SUBSCRIBER/PUBLISHER MISMATCHES")
        print("-" * 50)
        
        # Try to create a SubMaster with all services
        try:
            all_services = list(SERVICE_LIST.keys())
            sm = messaging.SubMaster(all_services, poll='carState')
            
            # Wait a bit to see what's actually publishing
            import time
            print("Monitoring for 3 seconds to detect active publishers...")
            start_time = time.time()
            never_updated = set(all_services)
            
            while time.time() - start_time < 3.0:
                sm.update(100)
                for service in list(never_updated):
                    if sm.updated[service]:
                        never_updated.remove(service)
            
            # Check custom services
            for service in self.expected_config.keys():
                if service in never_updated:
                    self.warnings.append(f"{service}: Registered but never published (in 3s test)")
                    
        except Exception as e:
            self.errors.append(f"Could not create SubMaster: {e}")
    
    def check_message_dependencies(self):
        """Check if message dependencies are satisfied."""
        print("\n5. CHECKING MESSAGE DEPENDENCIES")
        print("-" * 50)
        
        dependencies = {
            'frogpilotPlan': ['carState', 'modelV2'],
            'frogpilotCarControl': ['frogpilotPlan', 'controlsState'],
            'longitudinalPlan': ['carState', 'modelV2', 'radarState'],
        }
        
        for service, deps in dependencies.items():
            if service in SERVICE_LIST:
                missing_deps = [d for d in deps if d not in SERVICE_LIST]
                if missing_deps:
                    self.errors.append(f"{service}: Missing dependencies: {missing_deps}")
                else:
                    self.info.append(f"{service}: All dependencies present")
    
    def check_common_mistakes(self):
        """Check for common cereal/PMS mistakes."""
        print("\n6. CHECKING COMMON MISTAKES")
        print("-" * 50)
        
        # Check 1: Services with same frequency that might interfere
        freq_map = {}
        for service, config in SERVICE_LIST.items():
            freq = config[1]
            if freq not in freq_map:
                freq_map[freq] = []
            freq_map[freq].append(service)
        
        # Look for potential conflicts
        conflict_pairs = [
            ('carState', 'frogpilotCarState'),
            ('carControl', 'frogpilotCarControl'),
            ('deviceState', 'frogpilotDeviceState'),
            ('longitudinalPlan', 'frogpilotPlan'),
        ]
        
        for svc1, svc2 in conflict_pairs:
            if svc1 in SERVICE_LIST and svc2 in SERVICE_LIST:
                freq1 = SERVICE_LIST[svc1][1]
                freq2 = SERVICE_LIST[svc2][1]
                if freq1 == freq2:
                    self.warnings.append(f"{svc1} and {svc2} have same frequency ({freq1}Hz) - potential timing conflicts")
        
        # Check 2: Services that might need synchronization
        if 'frogpilotPlan' in SERVICE_LIST and 'longitudinalPlan' in SERVICE_LIST:
            self.warnings.append("Both frogpilotPlan and longitudinalPlan exist - ensure proper coordination")
    
    def generate_report(self):
        """Generate validation report."""
        print("\n" + "="*70)
        print("VALIDATION REPORT")
        print("="*70)
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if self.info:
            print(f"\n✓ INFO ({len(self.info)}):")
            for info in self.info[:5]:  # Show first 5
                print(f"  - {info}")
            if len(self.info) > 5:
                print(f"  ... and {len(self.info) - 5} more")
        
        print("\n" + "="*70)
        
        # Recommendations
        if self.errors or self.warnings:
            print("\nRECOMMENDATIONS:")
            print("1. Check that PubMaster is created with all needed services")
            print("2. Ensure only one publisher per service")
            print("3. Verify service frequencies match expected rates")
            print("4. Check for race conditions between similar services")
            print("5. Make sure custom services don't interfere with standard ones")
            
            if any("Multiple publishers" in e for e in self.errors):
                print("\n⚠️  CRITICAL: Multiple publishers detected!")
                print("   This is likely causing your communication issues.")
                print("   Each service should have exactly ONE publisher.")
    
    def run(self):
        """Run all validations."""
        print("CEREAL MESSAGE CONFIGURATION VALIDATOR")
        print("=" * 70)
        
        self.validate_service_registration()
        self.check_publisher_conflicts()
        self.validate_message_frequencies()
        self.check_subscriber_publisher_mismatch()
        self.check_message_dependencies()
        self.check_common_mistakes()
        
        self.generate_report()
        
        # Save report
        report_file = f"/data/cereal_validation_{os.getpid()}.txt"
        with open(report_file, 'w') as f:
            f.write("CEREAL MESSAGE VALIDATION REPORT\n")
            f.write("=" * 70 + "\n\n")
            
            if self.errors:
                f.write(f"ERRORS ({len(self.errors)}):\n")
                for error in self.errors:
                    f.write(f"  - {error}\n")
                f.write("\n")
            
            if self.warnings:
                f.write(f"WARNINGS ({len(self.warnings)}):\n")
                for warning in self.warnings:
                    f.write(f"  - {warning}\n")
        
        print(f"\nReport saved to: {report_file}")
        
        return len(self.errors) == 0


if __name__ == "__main__":
    validator = CerealMessageValidator()
    success = validator.run()
    sys.exit(0 if success else 1)