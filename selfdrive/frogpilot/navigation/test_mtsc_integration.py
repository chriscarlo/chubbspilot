#!/usr/bin/env python3
"""
Test script to verify mapd → liveMapData → MTSC integration.
This tests the complete data flow from mapd params to MTSC speed profiles.
"""

import json
import time
import math
from typing import List, Dict

import cereal.messaging as messaging
from common.params import Params
from selfdrive.frogpilot.controls.lib.chauffeur_mtsc import ChauffeurMtsc


def create_test_velocities() -> List[Dict]:
    """Create test velocity data simulating a curved road."""
    velocities = []
    
    # Simulate a road with varying curvatures
    # Start with straight section (no velocity data for straight parts)
    # Then a gentle curve
    base_lat = 37.7749
    base_lon = -122.4194
    
    # Add points for a curve ahead (lower velocities = tighter curve)
    curve_points = [
        # Distance ahead (m), target velocity (m/s)
        (50, 25.0),    # 25 m/s = 90 km/h = 56 mph
        (100, 20.0),   # 20 m/s = 72 km/h = 45 mph  
        (150, 15.0),   # 15 m/s = 54 km/h = 34 mph (tight curve)
        (200, 15.0),   # maintain low speed
        (250, 20.0),   # speed up again
        (300, 25.0),   # back to normal
    ]
    
    for dist, velocity in curve_points:
        # Approximate lat/lon offset (1 degree ≈ 111km)
        lat_offset = dist / 111000.0
        velocities.append({
            "latitude": base_lat + lat_offset,
            "longitude": base_lon,
            "velocity": velocity
        })
    
    return velocities


def test_mapd_to_mtsc():
    """Test the complete mapd → MTSC data flow."""
    print("Testing mapd → MTSC integration...")
    
    # Create params instance
    params_mem = Params("/dev/shm/params")
    
    # Set test GPS position
    test_position = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "bearing": 0.0  # North
    }
    params_mem.put("LastGPSPosition", json.dumps(test_position).encode())
    
    # Create test velocity data
    test_velocities = create_test_velocities()
    params_mem.put("MapTargetVelocities", json.dumps(test_velocities).encode())
    
    # Set other mapd outputs
    params_mem.put("RoadName", b"Test Road")
    params_mem.put("MapSpeedLimit", b"30.0")  # 30 m/s = 108 km/h
    params_mem.put("MapCurvatures", b"[]")  # Not used by MTSC
    
    print(f"\nTest data written to params:")
    print(f"  Position: {test_position}")
    print(f"  Velocities: {len(test_velocities)} points")
    for i, vel in enumerate(test_velocities):
        print(f"    {i}: {vel['velocity']:.1f} m/s at ({vel['latitude']:.5f}, {vel['longitude']:.5f})")
    
    # Start monitoring liveMapData
    print("\nMonitoring liveMapData messages...")
    sm = messaging.SubMaster(['liveMapData'])
    
    # Wait for a liveMapData message
    start_time = time.monotonic()
    timeout = 5.0
    received_msg = False
    
    while time.monotonic() - start_time < timeout:
        sm.update(100)  # 100ms timeout
        
        if sm.updated['liveMapData'] and sm.valid['liveMapData']:
            lmd = sm['liveMapData']
            print("\n✓ Received liveMapData message!")
            print(f"  Map valid: {lmd.mapValid}")
            print(f"  Curvature data valid: {lmd.curvatureDataValid}")
            print(f"  Road name: {lmd.currentRoadName}")
            print(f"  Speed limit: {lmd.speedLimit} m/s (valid: {lmd.speedLimitValid})")
            
            if lmd.curvatureDataValid:
                seg = lmd.currentSegment
                print(f"\n  Current segment:")
                print(f"    ID: {seg.segmentId}")
                print(f"    Distance along: {seg.distanceAlongSegment:.1f} m")
                print(f"    Speed points: {len(seg.curvatureDerivedSpeedsMps)}")
                if seg.curvatureDerivedSpeedsMps:
                    print(f"    Speed range: {min(seg.curvatureDerivedSpeedsMps):.1f} - {max(seg.curvatureDerivedSpeedsMps):.1f} m/s")
                    print(f"    Distances: {seg.distancesForSpeeds[:3]}... (first 3)")
            
            received_msg = True
            break
    
    if not received_msg:
        print("\n✗ No liveMapData message received within timeout!")
        print("  Make sure mapd process is running:")
        print("  cd /data/openpilot && python selfdrive/frogpilot/navigation/mapd.py")
        return False
    
    # Test MTSC with the data
    print("\nTesting MTSC with received data...")
    mtsc = ChauffeurMtsc()
    
    # Simulate a few control cycles
    v_ego = 30.0  # Current speed: 30 m/s
    a_ego = 0.0
    v_cruise = 35.0  # Cruise set to 35 m/s
    frogpilot_toggles = {}  # Not used by MTSC
    
    print(f"\nSimulating MTSC with v_ego={v_ego} m/s, v_cruise={v_cruise} m/s")
    
    # Run a few update cycles
    for i in range(5):
        dist_profile, speed_profile = mtsc.update(v_ego, a_ego, v_cruise, frogpilot_toggles)
        
        if dist_profile is not None and len(dist_profile) > 0:
            print(f"\n  Cycle {i}: Got speed profile with {len(dist_profile)} points")
            print(f"    Distance range: {dist_profile[0]:.1f} - {dist_profile[-1]:.1f} m")
            print(f"    Speed range: {min(speed_profile):.1f} - {max(speed_profile):.1f} m/s")
            
            # Find minimum speed point
            min_idx = speed_profile.argmin()
            print(f"    Minimum speed: {speed_profile[min_idx]:.1f} m/s at {dist_profile[min_idx]:.1f} m ahead")
        else:
            print(f"\n  Cycle {i}: No speed profile available yet")
        
        time.sleep(0.5)
    
    # Cleanup
    mtsc.shutdown()
    print("\n✓ MTSC integration test completed")
    return True


def main():
    """Main test function."""
    print("mapd → MTSC Integration Test")
    print("=" * 50)
    
    # Run the test
    success = test_mapd_to_mtsc()
    
    if success:
        print("\n✓ All tests passed!")
    else:
        print("\n✗ Some tests failed")
        print("\nTroubleshooting:")
        print("1. Ensure mapd process is running")
        print("2. Check that mapd binary exists and is executable")
        print("3. Verify GPS data is being written to params")


if __name__ == "__main__":
    main()