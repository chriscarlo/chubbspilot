#!/usr/bin/env python3
"""
Test script for the unified turn speed controller.
Tests map-only, vision-only, and combined modes.
"""

import json
import numpy as np
import time
from pathlib import Path

from common.params import Params
from selfdrive.frogpilot.controls.lib.unified_turn_controller import UnifiedTurnController
from selfdrive.frogpilot.controls.lib.turn_speed_common import (
    curvature_to_safe_speed,
    calculate_curvature_from_points,
    TurnSpeedProfile
)


def create_test_map_data():
    """Create test map data simulating a road with curves."""
    params = Params("/dev/shm/params")
    
    # GPS position
    test_position = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "bearing": 0.0
    }
    params.put("LastGPSPosition", json.dumps(test_position).encode())
    
    # Create velocity data with varying speeds for curves
    velocities = []
    base_lat = 37.7749
    base_lon = -122.4194
    
    # Straight section, then curve, then straight
    points = [
        (0, 30.0),    # Straight
        (50, 30.0),   # Straight
        (100, 25.0),  # Entering curve
        (150, 20.0),  # In curve
        (200, 15.0),  # Tight part
        (250, 20.0),  # Exiting curve
        (300, 25.0),  # Exiting
        (350, 30.0),  # Straight again
    ]
    
    for dist, velocity in points:
        lat_offset = dist / 111000.0  # Approximate conversion
        velocities.append({
            "latitude": base_lat + lat_offset,
            "longitude": base_lon,
            "velocity": velocity
        })
    
    params.put("MapTargetVelocities", json.dumps(velocities).encode())
    params.put("RoadName", b"Test Road")
    params.put("MapSpeedLimit", b"30.0")
    
    return velocities


def create_test_model_data():
    """Create mock model data for vision testing."""
    class MockModelData:
        def __init__(self):
            # Simulate vision seeing a curve ahead
            self.orientationRate = MockOrientationRate()
            self.velocity = MockVelocity()
            self.position = MockPosition()
    
    class MockOrientationRate:
        def __init__(self):
            # Curvature profile: straight, then curve, then straight
            self.z = [0.001, 0.002, 0.005, 0.01, 0.015, 0.01, 0.005, 0.002, 0.001]
    
    class MockVelocity:
        def __init__(self):
            # Predicted velocities
            self.x = [30.0, 28.0, 25.0, 20.0, 18.0, 20.0, 25.0, 28.0, 30.0]
    
    class MockPosition:
        def __init__(self):
            # Time points
            self.t = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    
    return MockModelData()


def test_unified_controller():
    """Test the unified controller in different modes."""
    print("Testing Unified Turn Speed Controller")
    print("=" * 60)
    
    # Create test data
    print("\n1. Creating test data...")
    map_velocities = create_test_map_data()
    model_data = create_test_model_data()
    print(f"  Created {len(map_velocities)} map points")
    print(f"  Created vision data with {len(model_data.velocity.x)} points")
    
    # Initialize controller
    controller = UnifiedTurnController()
    
    # Test parameters
    v_ego = 25.0  # m/s (90 km/h)
    a_ego = 0.0
    v_cruise = 30.0  # m/s (108 km/h)
    frogpilot_toggles = {
        'turn_aggressiveness': 1.0,
        'map_turn_speed_controller': True,
        'vision_turn_speed_controller': True
    }
    
    # Test different modes
    modes = ["map_only", "vision_only", "combined", "legacy"]
    
    for mode in modes:
        print(f"\n2. Testing {mode} mode...")
        controller.set_mode(mode)
        
        # Ensure mapd is running for map modes
        if mode in ["map_only", "combined", "legacy"]:
            print("  Waiting for mapd data...")
            time.sleep(0.5)  # Give mapd time to process
        
        # Run update
        target_speed, profile = controller.update(
            v_ego, a_ego, v_cruise, model_data, frogpilot_toggles
        )
        
        print(f"  Target speed: {target_speed:.1f} m/s ({target_speed * 3.6:.1f} km/h)")
        
        if profile:
            min_speed, min_dist = profile.get_min_speed_ahead(200.0)
            print(f"  Profile source: {profile.source}")
            print(f"  Profile points: {len(profile.distances)}")
            print(f"  Min speed ahead: {min_speed:.1f} m/s at {min_dist:.1f} m")
        else:
            print("  No profile available")
        
        # Get diagnostics
        diag = controller.get_diagnostics()
        print(f"  Map available: {diag['map_available']}")
        print(f"  Vision available: {diag['vision_available']}")
        print(f"  Map min speed: {diag['min_speed_map']:.1f} m/s")
        print(f"  Vision min speed: {diag['min_speed_vision']:.1f} m/s")
    
    # Test blend modes
    print("\n3. Testing blend modes in combined mode...")
    controller.set_mode("combined")
    
    for blend_mode in ["minimum", "weighted", "adaptive"]:
        controller.set_blend_mode(blend_mode)
        target_speed, profile = controller.update(
            v_ego, a_ego, v_cruise, model_data, frogpilot_toggles
        )
        print(f"  {blend_mode}: {target_speed:.1f} m/s")
    
    # Test aggressiveness
    print("\n4. Testing aggressiveness levels...")
    controller.set_mode("combined")
    controller.set_blend_mode("minimum")
    
    for aggr in [0.5, 1.0, 1.5, 2.0]:
        frogpilot_toggles['turn_aggressiveness'] = aggr
        target_speed, profile = controller.update(
            v_ego, a_ego, v_cruise, model_data, frogpilot_toggles
        )
        print(f"  Aggressiveness {aggr}: {target_speed:.1f} m/s")
    
    # Cleanup
    controller.shutdown()
    print("\n✓ All tests completed")


def test_curvature_calculations():
    """Test curvature calculation functions."""
    print("\nTesting Curvature Calculations")
    print("=" * 60)
    
    # Test three points forming a curve
    lat1, lon1 = 37.7749, -122.4194
    lat2, lon2 = 37.7759, -122.4194  # ~111m north
    lat3, lon3 = 37.7769, -122.4184  # ~111m north, ~111m east
    
    curvature = calculate_curvature_from_points(lat1, lon1, lat2, lon2, lat3, lon3)
    print(f"Curvature from 3 points: {curvature:.6f} (1/m)")
    
    if curvature > 0:
        radius = 1.0 / curvature
        print(f"Turn radius: {radius:.1f} m")
    
    # Test curvature to speed conversion
    curvatures = [0.001, 0.005, 0.01, 0.02, 0.05]
    print("\nCurvature to safe speed:")
    for curv in curvatures:
        for aggr in [0.5, 1.0, 2.0]:
            speed = curvature_to_safe_speed(curv, aggr)
            print(f"  Curv={curv:.3f}, Aggr={aggr}: {speed:.1f} m/s ({speed*3.6:.1f} km/h)")


def test_migration():
    """Test migration controller."""
    print("\nTesting Migration Controller")
    print("=" * 60)
    
    from selfdrive.frogpilot.controls.lib.migrate_to_unified_controller import (
        MigrationController,
        create_migration_params
    )
    
    # Set up migration params
    create_migration_params()
    
    # Create migration controller
    controller = MigrationController()
    print(f"Migration mode: {controller.migration_mode}")
    
    # Test MTSC-style update
    v_ego = 25.0
    a_ego = 0.0
    v_cruise = 30.0
    toggles = {'turn_aggressiveness': 1.0}
    
    dist, speeds = controller.update_mtsc(v_ego, a_ego, v_cruise, toggles)
    print(f"MTSC update: Got profile with {len(dist) if dist is not None else 0} points")
    
    # Test VTSC-style update
    target = controller.update_vtsc(v_ego, v_cruise, turn_aggressiveness=1.0)
    print(f"VTSC update: Target speed = {target:.1f} m/s")
    
    controller.shutdown()


if __name__ == "__main__":
    # Check if mapd is running
    mapd_path = Path("/data/openpilot/selfdrive/frogpilot/navigation/mapd")
    if not mapd_path.exists():
        print("WARNING: mapd binary not found. Map-based tests may not work.")
        print("Run download_mapd.sh or build_mapd.sh first.")
    
    # Run all tests
    test_curvature_calculations()
    test_unified_controller()
    test_migration()
    
    print("\n✓ All tests completed successfully!")