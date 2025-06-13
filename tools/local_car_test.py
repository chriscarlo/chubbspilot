#!/usr/bin/env python3
"""
Local car testing without comma servers
This script shows how to test openpilot with different car models locally
"""

import os
import sys
import time
import argparse
from typing import Optional

# Add openpilot to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from cereal import car, messaging
from openpilot.common.params import Params
from openpilot.selfdrive.car import gen_empty_fingerprint
from openpilot.selfdrive.car.car_helpers import get_car_interface
from openpilot.selfdrive.test.helpers import set_params_enabled

# Popular test vehicles
TEST_CARS = {
    'honda': {
        'accord': 'HONDA_ACCORD',
        'civic': 'HONDA_CIVIC_2022',
        'crv': 'HONDA_CRV_2017',
    },
    'toyota': {
        'camry': 'TOYOTA_CAMRY',
        'corolla': 'TOYOTA_COROLLA_TSS2',
        'rav4': 'TOYOTA_RAV4_TSS2',
    },
    'hyundai': {
        'sonata': 'HYUNDAI_SONATA',
        'elantra': 'HYUNDAI_ELANTRA_2021',
        'kona': 'HYUNDAI_KONA_EV_2022',
    },
    'subaru': {
        'outback': 'SUBARU_OUTBACK',
        'ascent': 'SUBARU_ASCENT',
        'crosstrek': 'SUBARU_CROSSTREK_HYBRID',
    },
    'mazda': {
        'cx5': 'MAZDA_CX5',
        'cx9': 'MAZDA_CX9',
    }
}

def setup_car_test(fingerprint: str, passive: bool = False):
    """Set up environment for testing a specific car"""
    
    # Set environment variables
    os.environ['FINGERPRINT'] = fingerprint
    os.environ['PASSIVE'] = '1' if passive else '0'
    os.environ['NOBOARD'] = '1'  # No hardware
    os.environ['SIMULATION'] = '1'
    os.environ['SKIP_FW_QUERY'] = '1'  # Don't query firmware
    
    # Block hardware processes
    os.environ['BLOCK'] = 'camerad,loggerd,encoderd,micd,logmessaged,sensord'
    
    # Enable openpilot
    set_params_enabled()
    
    print(f"Set up testing environment for: {fingerprint}")
    print(f"Passive mode: {passive}")

def test_car_interface(fingerprint: str):
    """Test basic car interface functionality"""
    
    # Create params
    params = Params()
    params.put("CarParams", car.CarParams().to_bytes())
    
    # Get car interface
    print(f"\nTesting car interface for {fingerprint}...")
    
    try:
        # Create empty fingerprint
        can_fingerprint = gen_empty_fingerprint()
        
        # Get car interface (this validates the fingerprint)
        CarInterface, _, _ = get_car_interface(can_fingerprint, fingerprint, None, False, False)
        
        print(f"✓ Successfully loaded car interface")
        print(f"  Car name: {CarInterface.CP.carName}")
        print(f"  Safety model: {CarInterface.CP.safetyModel}")
        print(f"  Steer ratio: {CarInterface.CP.steerRatio:.2f}")
        print(f"  Mass: {CarInterface.CP.mass:.0f} kg")
        
        # Test some basic car controls
        CC = car.CarControl.new_message()
        CC.enabled = True
        CC.latActive = True
        CC.longActive = True
        
        # Create car state
        CS = CarInterface.get_CS()
        print(f"  Cruise available: {CS.cruiseState.available}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error loading car interface: {e}")
        return False

def run_simulation_test(fingerprint: str):
    """Run a simulation test with the specified car"""
    
    print(f"\nTo run full simulation test:")
    print(f"# Terminal 1:")
    print(f"FINGERPRINT={fingerprint} ./tools/sim/launch_openpilot.sh")
    print(f"\n# Terminal 2:")
    print(f"./tools/sim/run_bridge.py")
    
def list_test_cars():
    """List all available test cars"""
    print("\nAvailable test cars:")
    for brand, models in TEST_CARS.items():
        print(f"\n{brand.upper()}:")
        for model, fp in models.items():
            print(f"  {model}: {fp}")

def main():
    parser = argparse.ArgumentParser(description='Test openpilot with different cars locally')
    parser.add_argument('--car', help='Car to test (e.g., honda_accord, toyota_camry)')
    parser.add_argument('--fingerprint', help='Direct fingerprint to use')
    parser.add_argument('--passive', action='store_true', help='Run in passive mode')
    parser.add_argument('--list', action='store_true', help='List available test cars')
    parser.add_argument('--interface-test', action='store_true', help='Test car interface loading')
    
    args = parser.parse_args()
    
    if args.list:
        list_test_cars()
        return
    
    # Determine fingerprint
    fingerprint = None
    if args.fingerprint:
        fingerprint = args.fingerprint
    elif args.car:
        # Parse car argument (e.g., honda_accord)
        parts = args.car.lower().split('_')
        if len(parts) >= 2:
            brand = parts[0]
            model = '_'.join(parts[1:])
            if brand in TEST_CARS and model in TEST_CARS[brand]:
                fingerprint = TEST_CARS[brand][model]
    
    if not fingerprint:
        print("Please specify --car or --fingerprint")
        list_test_cars()
        return
    
    # Set up test environment
    setup_car_test(fingerprint, args.passive)
    
    # Run tests
    if args.interface_test:
        test_car_interface(fingerprint)
    else:
        run_simulation_test(fingerprint)

if __name__ == "__main__":
    main()