#!/usr/bin/env python3
"""
Test script to verify mapd integration with openpilot.
This tests that mapd can read GPS data and produce map outputs.
"""

import json
import time
import sys
from pathlib import Path

from openpilot.common.params import Params


def test_mapd_params():
    """Test mapd parameter reading and writing."""
    print("Testing mapd parameter integration...")
    
    # Create params instances
    params_mem = Params("/dev/shm/params")
    params_persist = Params()
    
    # Test GPS position
    test_position = {
        "latitude": 37.7749,   # San Francisco
        "longitude": -122.4194,
        "bearing": 45.0
    }
    
    print(f"Writing test GPS position: {test_position}")
    params_mem.put("LastGPSPosition", json.dumps(test_position).encode())
    
    # Verify write
    read_back = params_mem.get("LastGPSPosition")
    if read_back:
        parsed = json.loads(read_back)
        print(f"Successfully wrote and read GPS position: {parsed}")
    else:
        print("ERROR: Failed to read back GPS position")
        return False
    
    # Check if mapd output params exist
    print("\nChecking mapd output parameters...")
    mapd_outputs = [
        "RoadName",
        "MapSpeedLimit", 
        "MapCurvatures",
        "MapTargetVelocities",
        "MapHazard",
        "NextMapSpeedLimit"
    ]
    
    for param in mapd_outputs:
        value = params_mem.get(param)
        if value is not None:
            print(f"  {param}: {value.decode() if value else 'empty'}")
        else:
            print(f"  {param}: not set")
    
    return True


def check_mapd_binary():
    """Check if mapd binary exists."""
    binary_path = Path(__file__).parent / "mapd"
    
    if binary_path.exists():
        print(f"✓ mapd binary found at: {binary_path}")
        print(f"  Size: {binary_path.stat().st_size} bytes")
        print(f"  Executable: {binary_path.is_file() and binary_path.stat().st_mode & 0o111}")
        return True
    else:
        print(f"✗ mapd binary NOT found at: {binary_path}")
        print("  Run build_mapd.sh to build the binary")
        return False


def main():
    """Main test function."""
    print("mapd Integration Test")
    print("=" * 50)
    
    # Check binary
    if not check_mapd_binary():
        print("\nPlease build mapd binary first:")
        print("  cd /data/openpilot/selfdrive/frogpilot/navigation")
        print("  ./build_mapd.sh")
        sys.exit(1)
    
    print()
    
    # Test params
    if test_mapd_params():
        print("\n✓ Parameter integration test passed")
    else:
        print("\n✗ Parameter integration test failed")
        sys.exit(1)
    
    print("\nNOTE: To fully test mapd:")
    print("1. Ensure mapd process is running")
    print("2. Provide real GPS updates via locationd")
    print("3. Monitor MapTargetVelocities output for MTSC")


if __name__ == "__main__":
    main()