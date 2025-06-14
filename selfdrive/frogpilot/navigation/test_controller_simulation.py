#!/usr/bin/env python3
"""
Simulation test harness for unified turn speed controller.
Tests controller behavior with synthetic data without needing actual driving.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict, Optional
from pathlib import Path

from openpilot.common.params import Params
from openpilot.selfdrive.frogpilot.controls.lib.unified_turn_controller import UnifiedTurnController
from openpilot.selfdrive.frogpilot.controls.lib.turn_speed_common import (
    curvature_to_safe_speed,
    calculate_curvature_from_points,
    AGGR_MIN, AGGR_MAX, AGGR_DEFAULT
)
from openpilot.selfdrive.frogpilot.controls.lib.migrate_to_unified_controller import MigrationController


class ControllerSimulator:
    """Simulates controller behavior with synthetic driving scenarios."""
    
    def __init__(self):
        self.params = Params("/dev/shm/params")
        self.controller = UnifiedTurnController()
        self.migration_controller = MigrationController()
        self.results = []
    
    def create_map_scenario(self, scenario_name: str, points: List[Tuple[float, float, float]]) -> None:
        """
        Create a map scenario with synthetic GPS and velocity data.
        
        Args:
            scenario_name: Name for this scenario
            points: List of (distance_m, velocity_mps, curvature) tuples
        """
        print(f"\n=== Setting up scenario: {scenario_name} ===")
        
        # Create GPS position
        base_lat, base_lon = 37.7749, -122.4194
        self.params.put("LastGPSPosition", json.dumps({
            "latitude": base_lat,
            "longitude": base_lon,
            "bearing": 0.0
        }).encode())
        
        # Create velocity points
        velocities = []
        for dist, vel, _ in points:
            lat_offset = dist / 111000.0  # Approximate conversion
            velocities.append({
                "latitude": base_lat + lat_offset,
                "longitude": base_lon,
                "velocity": vel
            })
        
        self.params.put("MapTargetVelocities", json.dumps(velocities).encode())
        self.params.put("RoadName", scenario_name.encode())
        self.params.put("MapSpeedLimit", b"30.0")
    
    def create_vision_scenario(self, curvatures: List[float], velocities: List[float]) -> 'MockModelData':
        """Create synthetic vision/model data."""
        class MockModelData:
            def __init__(self, curvatures, velocities):
                self.orientationRate = MockOrientationRate(curvatures, velocities)
                self.velocity = MockVelocity(velocities)
                self.position = MockPosition(len(velocities))
        
        class MockOrientationRate:
            def __init__(self, curvatures, velocities):
                # Convert curvatures to orientation rates
                self.z = [c * v for c, v in zip(curvatures, velocities)]
        
        class MockVelocity:
            def __init__(self, velocities):
                self.x = velocities
        
        class MockPosition:
            def __init__(self, num_points):
                self.t = list(range(num_points))  # 1 second intervals
        
        return MockModelData(curvatures, velocities)
    
    def test_scenario(self, 
                     scenario_name: str,
                     v_ego: float,
                     v_cruise: float,
                     map_points: Optional[List[Tuple[float, float, float]]] = None,
                     vision_data: Optional[Tuple[List[float], List[float]]] = None,
                     aggressiveness: float = AGGR_DEFAULT,
                     mode: str = "combined") -> Dict:
        """
        Test a specific scenario and collect results.
        
        Returns:
            Dict with test results
        """
        print(f"\n--- Testing: {scenario_name} ---")
        print(f"Mode: {mode}, Aggressiveness: {aggressiveness}")
        print(f"v_ego: {v_ego:.1f} m/s, v_cruise: {v_cruise:.1f} m/s")
        
        # Set up map data if provided
        if map_points:
            self.create_map_scenario(scenario_name, map_points)
        
        # Create vision data if provided
        model_data = None
        if vision_data:
            curvatures, velocities = vision_data
            model_data = self.create_vision_scenario(curvatures, velocities)
        
        # Configure controller
        self.controller.set_mode(mode)
        frogpilot_toggles = {'turn_aggressiveness': aggressiveness}
        
        # Run update
        target_speed, profile = self.controller.update(
            v_ego, 0.0, v_cruise, model_data, frogpilot_toggles
        )
        
        # Get diagnostics
        diag = self.controller.get_diagnostics()
        
        # Collect results
        result = {
            'scenario': scenario_name,
            'mode': mode,
            'aggressiveness': aggressiveness,
            'v_ego': v_ego,
            'v_cruise': v_cruise,
            'target_speed': target_speed,
            'profile': profile,
            'diagnostics': diag
        }
        
        # Print summary
        print(f"Target speed: {target_speed:.1f} m/s ({target_speed * 3.6:.1f} km/h)")
        if profile:
            min_speed, min_dist = profile.get_min_speed_ahead(200.0)
            print(f"Min speed ahead: {min_speed:.1f} m/s at {min_dist:.1f} m")
        print(f"Map available: {diag['map_available']}, Vision available: {diag['vision_available']}")
        
        self.results.append(result)
        return result
    
    def run_all_tests(self):
        """Run comprehensive test suite."""
        print("\n" + "="*60)
        print("UNIFIED TURN CONTROLLER SIMULATION TEST SUITE")
        print("="*60)
        
        # Test 1: Straight road (no slowdown expected)
        self.test_scenario(
            "Straight Highway",
            v_ego=30.0,
            v_cruise=35.0,
            map_points=[(0, 35.0, 0.0), (500, 35.0, 0.0), (1000, 35.0, 0.0)],
            vision_data=([0.0001] * 9, [30.0] * 9),
            mode="combined"
        )
        
        # Test 2: Map-only curve detection (far ahead)
        self.test_scenario(
            "Highway Sweeper - Map Only",
            v_ego=30.0,
            v_cruise=35.0,
            map_points=[
                (0, 35.0, 0.0),      # Straight
                (200, 35.0, 0.0),    # Straight
                (400, 25.0, 0.01),   # Entering curve
                (600, 20.0, 0.02),   # In curve
                (800, 15.0, 0.03),   # Tight part
                (1000, 20.0, 0.02),  # Exiting
            ],
            mode="map_only"
        )
        
        # Test 3: Vision-only tight turn
        self.test_scenario(
            "Parking Lot Turn - Vision Only",
            v_ego=10.0,
            v_cruise=15.0,
            vision_data=(
                [0.001, 0.005, 0.01, 0.02, 0.03, 0.02, 0.01, 0.005, 0.001],  # Curvatures
                [10.0, 9.0, 8.0, 6.0, 5.0, 6.0, 8.0, 9.0, 10.0]              # Velocities
            ),
            mode="vision_only"
        )
        
        # Test 4: Combined inputs (redundant confirmation)
        self.test_scenario(
            "Curvy Road - Combined",
            v_ego=25.0,
            v_cruise=30.0,
            map_points=[
                (0, 30.0, 0.0),
                (100, 25.0, 0.005),
                (200, 20.0, 0.01),
                (300, 18.0, 0.015),
                (400, 20.0, 0.01),
                (500, 25.0, 0.005),
            ],
            vision_data=(
                [0.001, 0.003, 0.005, 0.008, 0.012, 0.008, 0.005, 0.003, 0.001],
                [25.0, 23.0, 21.0, 19.0, 17.0, 19.0, 21.0, 23.0, 25.0]
            ),
            mode="combined"
        )
        
        # Test 5: Aggressiveness variations
        for aggr in [0.5, 1.0, 1.5, 2.0]:
            self.test_scenario(
                f"Standard Curve - Aggr {aggr}",
                v_ego=20.0,
                v_cruise=25.0,
                map_points=[(0, 25.0, 0.0), (100, 15.0, 0.02), (200, 25.0, 0.0)],
                aggressiveness=aggr,
                mode="map_only"
            )
        
        # Test 6: Blend mode variations
        for blend_mode in ["minimum", "weighted", "adaptive"]:
            self.controller.set_blend_mode(blend_mode)
            self.test_scenario(
                f"Discrepant Inputs - {blend_mode} blend",
                v_ego=25.0,
                v_cruise=30.0,
                map_points=[(0, 30.0, 0.0), (100, 20.0, 0.01), (200, 30.0, 0.0)],  # Map sees moderate curve
                vision_data=([0.001] * 9, [28.0] * 9),  # Vision sees almost straight
                mode="combined"
            )
        
        # Test 7: False positive scenario (overpass)
        self.test_scenario(
            "Highway Overpass False Positive",
            v_ego=30.0,
            v_cruise=35.0,
            map_points=[
                (0, 35.0, 0.0),
                (100, 15.0, 0.05),  # Sharp curve in map (overpass ramp)
                (200, 35.0, 0.0),
            ],
            vision_data=([0.0001] * 9, [30.0] * 9),  # Vision sees straight
            mode="combined"
        )
    
    def plot_results(self):
        """Plot simulation results for visualization."""
        if not self.results:
            print("No results to plot")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle("Turn Speed Controller Simulation Results")
        
        # Plot 1: Target speeds by scenario
        ax1 = axes[0, 0]
        scenarios = [r['scenario'] for r in self.results]
        target_speeds = [r['target_speed'] for r in self.results]
        v_cruises = [r['v_cruise'] for r in self.results]
        
        x = range(len(scenarios))
        ax1.bar(x, target_speeds, alpha=0.7, label='Target Speed')
        ax1.plot(x, v_cruises, 'r--', label='Cruise Speed')
        ax1.set_xticks(x)
        ax1.set_xticklabels(scenarios, rotation=45, ha='right')
        ax1.set_ylabel('Speed (m/s)')
        ax1.set_title('Target Speeds by Scenario')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Aggressiveness impact
        ax2 = axes[0, 1]
        aggr_results = [r for r in self.results if 'Aggr' in r['scenario']]
        if aggr_results:
            aggrs = [r['aggressiveness'] for r in aggr_results]
            speeds = [r['target_speed'] for r in aggr_results]
            ax2.plot(aggrs, speeds, 'bo-', linewidth=2, markersize=8)
            ax2.set_xlabel('Aggressiveness')
            ax2.set_ylabel('Target Speed (m/s)')
            ax2.set_title('Aggressiveness vs Target Speed')
            ax2.grid(True, alpha=0.3)
        
        # Plot 3: Map vs Vision speeds
        ax3 = axes[1, 0]
        map_speeds = []
        vision_speeds = []
        labels = []
        
        for r in self.results:
            if r['diagnostics']['map_available'] and r['diagnostics']['vision_available']:
                map_speeds.append(r['diagnostics']['min_speed_map'])
                vision_speeds.append(r['diagnostics']['min_speed_vision'])
                labels.append(r['scenario'][:20])  # Truncate long names
        
        if map_speeds:
            x = range(len(map_speeds))
            width = 0.35
            ax3.bar([i - width/2 for i in x], map_speeds, width, label='Map', alpha=0.7)
            ax3.bar([i + width/2 for i in x], vision_speeds, width, label='Vision', alpha=0.7)
            ax3.set_xticks(x)
            ax3.set_xticklabels(labels, rotation=45, ha='right')
            ax3.set_ylabel('Min Speed (m/s)')
            ax3.set_title('Map vs Vision Min Speeds')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        
        # Plot 4: Controller modes
        ax4 = axes[1, 1]
        modes = {}
        for r in self.results:
            mode = r['mode']
            modes[mode] = modes.get(mode, 0) + 1
        
        if modes:
            ax4.pie(modes.values(), labels=modes.keys(), autopct='%1.1f%%')
            ax4.set_title('Test Distribution by Mode')
        
        plt.tight_layout()
        plt.savefig('/tmp/controller_simulation_results.png')
        print("\nResults saved to /tmp/controller_simulation_results.png")
    
    def test_curvature_physics(self):
        """Test the physics calculations for curvature to speed conversion."""
        print("\n" + "="*60)
        print("CURVATURE PHYSICS VALIDATION")
        print("="*60)
        
        # Test various curvatures
        curvatures = [0.001, 0.005, 0.01, 0.02, 0.03, 0.05]
        
        print("\nCurvature to Safe Speed (various aggressiveness levels):")
        print("Curvature | Radius | Aggr=0.5 | Aggr=1.0 | Aggr=1.5 | Aggr=2.0")
        print("-" * 70)
        
        for curv in curvatures:
            radius = 1.0 / curv if curv > 0 else float('inf')
            speeds = [curvature_to_safe_speed(curv, aggr) for aggr in [0.5, 1.0, 1.5, 2.0]]
            print(f"{curv:9.3f} | {radius:6.0f}m | {speeds[0]:8.1f} | {speeds[1]:8.1f} | "
                  f"{speeds[2]:8.1f} | {speeds[3]:8.1f}")
        
        # Test three-point curvature calculation
        print("\nThree-point curvature calculation test:")
        # Create a 90-degree turn
        lat1, lon1 = 37.7749, -122.4194
        lat2, lon2 = 37.7759, -122.4194  # North
        lat3, lon3 = 37.7759, -122.4184  # East (90-degree turn)
        
        curvature = calculate_curvature_from_points(lat1, lon1, lat2, lon2, lat3, lon3)
        radius = 1.0 / curvature if curvature > 0 else float('inf')
        
        print(f"90-degree turn: Curvature = {curvature:.6f} (1/m), Radius = {radius:.1f} m")
        print(f"Safe speed at this curvature: {curvature_to_safe_speed(curvature):.1f} m/s")


def main():
    """Run the simulation test suite."""
    sim = ControllerSimulator()
    
    # Run physics validation
    sim.test_curvature_physics()
    
    # Run all test scenarios
    sim.run_all_tests()
    
    # Generate plots
    try:
        sim.plot_results()
    except ImportError:
        print("\nMatplotlib not available, skipping plots")
    
    # Summary
    print("\n" + "="*60)
    print("SIMULATION COMPLETE")
    print("="*60)
    print(f"Total scenarios tested: {len(sim.results)}")
    
    # Check for any concerning results
    concerns = []
    for r in sim.results:
        if r['target_speed'] < 5.0:
            concerns.append(f"{r['scenario']}: Very low target speed ({r['target_speed']:.1f} m/s)")
        elif r['target_speed'] >= r['v_cruise']:
            # This is fine - no slowdown needed
            pass
        
        # Check for false positives (map says slow, vision says fast)
        if (r['diagnostics']['map_available'] and r['diagnostics']['vision_available'] and
            abs(r['diagnostics']['min_speed_map'] - r['diagnostics']['min_speed_vision']) > 10.0):
            concerns.append(f"{r['scenario']}: Large discrepancy between map and vision")
    
    if concerns:
        print("\nPotential concerns:")
        for c in concerns:
            print(f"  - {c}")
    else:
        print("\nAll tests passed without concerns!")
    
    # Clean up
    sim.controller.shutdown()


if __name__ == "__main__":
    main()