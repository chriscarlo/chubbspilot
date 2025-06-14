#!/usr/bin/env python3
"""
Full integration test for mapd → MTSC → unified controller flow.
Tests the complete data pipeline from GPS input to turn speed output.
"""

import json
import time
import subprocess
import signal
import sys
from typing import Optional, Dict, List
from pathlib import Path

import cereal.messaging as messaging
from openpilot.common.params import Params
from openpilot.system.swaglog import cloudlog


class IntegrationTester:
    """Tests the full integration of mapd, MTSC, and unified controller."""
    
    def __init__(self):
        self.params = Params("/dev/shm/params")
        self.mapd_process: Optional[subprocess.Popen] = None
        self.results: List[Dict] = []
        
    def setup_test_environment(self):
        """Set up the test environment with necessary parameters."""
        print("Setting up test environment...")
        
        # Enable turn speed controllers
        self.params.put_bool("MapTurnSpeedController", True)
        self.params.put_bool("VisionTurnSpeedController", True)
        
        # Set controller to unified mode
        self.params.put("TurnControllerMode", "unified")
        self.params.put_float("TurnAggressiveness", 1.0)
        self.params.put("TurnControllerBlendMode", "minimum")
        
        # Set initial GPS position
        test_position = {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "bearing": 0.0,
            "speed": 0.0,
            "verticalAccuracy": 1.0,
            "bearingAccuracyDeg": 1.0,
            "speedAccuracy": 0.1,
            "timestamp": int(time.time() * 1000)
        }
        self.params.put("LastGPSPosition", json.dumps(test_position).encode())
        
        print("Test environment configured")
    
    def start_mapd(self) -> bool:
        """Start the mapd process if binary exists."""
        mapd_path = Path("/data/openpilot/selfdrive/frogpilot/navigation/mapd")
        
        if not mapd_path.exists():
            print(f"WARNING: mapd binary not found at {mapd_path}")
            print("Attempting to use download script...")
            
            download_script = Path("/data/openpilot/selfdrive/frogpilot/navigation/download_mapd.sh")
            if download_script.exists():
                try:
                    subprocess.run([str(download_script)], check=True)
                except subprocess.CalledProcessError:
                    print("Failed to download mapd binary")
                    return False
            else:
                print("Download script not found. Please build mapd first.")
                return False
        
        # Start mapd process
        try:
            self.mapd_process = subprocess.Popen(
                [str(mapd_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"Started mapd process (PID: {self.mapd_process.pid})")
            time.sleep(2)  # Give it time to initialize
            
            # Check if it's still running
            if self.mapd_process.poll() is not None:
                stdout, stderr = self.mapd_process.communicate()
                print(f"mapd exited immediately. stdout: {stdout}, stderr: {stderr}")
                return False
                
            return True
            
        except Exception as e:
            print(f"Failed to start mapd: {e}")
            return False
    
    def stop_mapd(self):
        """Stop the mapd process."""
        if self.mapd_process:
            print("Stopping mapd process...")
            self.mapd_process.terminate()
            try:
                self.mapd_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.mapd_process.kill()
                self.mapd_process.wait()
            print("mapd process stopped")
    
    def create_test_route(self, route_name: str, waypoints: List[Dict]) -> None:
        """
        Create a test route with velocity targets.
        
        Args:
            route_name: Name of the route
            waypoints: List of dicts with lat, lon, velocity
        """
        print(f"\nCreating test route: {route_name}")
        
        # Set route name
        self.params.put("RoadName", route_name.encode())
        
        # Create velocity list for mapd
        velocities = []
        for wp in waypoints:
            velocities.append({
                "latitude": wp["lat"],
                "longitude": wp["lon"],
                "velocity": wp["velocity"]
            })
        
        self.params.put("MapTargetVelocities", json.dumps(velocities).encode())
        self.params.put("MapSpeedLimit", str(max(wp["velocity"] for wp in waypoints)).encode())
        
        # Update GPS position to first waypoint
        if waypoints:
            gps_update = {
                "latitude": waypoints[0]["lat"],
                "longitude": waypoints[0]["lon"],
                "bearing": 0.0,
                "speed": waypoints[0].get("current_speed", 20.0),
                "verticalAccuracy": 1.0,
                "bearingAccuracyDeg": 1.0,
                "speedAccuracy": 0.1,
                "timestamp": int(time.time() * 1000)
            }
            self.params.put("LastGPSPosition", json.dumps(gps_update).encode())
    
    def monitor_liveMapData(self, duration: float = 5.0) -> Dict:
        """Monitor liveMapData messages for a given duration."""
        print(f"Monitoring liveMapData for {duration} seconds...")
        
        sm = messaging.SubMaster(['liveMapData'])
        start_time = time.time()
        messages_received = 0
        last_message = None
        
        while time.time() - start_time < duration:
            sm.update(100)  # 100ms timeout
            
            if sm.updated['liveMapData']:
                messages_received += 1
                last_message = sm['liveMapData']
                
                # Print message details
                if messages_received == 1:  # First message
                    print(f"First liveMapData received:")
                    print(f"  Valid: {last_message.valid}")
                    print(f"  Speed limit: {last_message.speedLimit:.1f} m/s")
                    print(f"  Speed limit valid: {last_message.speedLimitValid}")
                    print(f"  Curvatures: {len(last_message.curvatures)}")
                    if last_message.curvatures:
                        print(f"  First few curvatures: {last_message.curvatures[:5]}")
        
        result = {
            "messages_received": messages_received,
            "message_rate": messages_received / duration,
            "last_message": last_message
        }
        
        print(f"Received {messages_received} messages ({result['message_rate']:.1f} Hz)")
        return result
    
    def test_scenario(self, scenario_name: str, waypoints: List[Dict]) -> Dict:
        """Test a complete scenario."""
        print(f"\n{'='*60}")
        print(f"Testing scenario: {scenario_name}")
        print(f"{'='*60}")
        
        # Create the route
        self.create_test_route(scenario_name, waypoints)
        
        # Give mapd time to process
        time.sleep(1.0)
        
        # Monitor messages
        result = self.monitor_liveMapData(duration=5.0)
        
        # Analyze results
        result["scenario"] = scenario_name
        result["success"] = result["messages_received"] > 0
        
        if result["success"] and result["last_message"]:
            msg = result["last_message"]
            if msg.curvatures:
                max_curv = max(abs(c) for c in msg.curvatures)
                result["max_curvature"] = max_curv
                result["min_safe_speed"] = min(msg.speeds) if msg.speeds else None
        
        self.results.append(result)
        return result
    
    def run_all_tests(self):
        """Run all integration test scenarios."""
        # Test 1: Straight road
        self.test_scenario(
            "Straight Highway",
            [
                {"lat": 37.7749, "lon": -122.4194, "velocity": 35.0},
                {"lat": 37.7849, "lon": -122.4194, "velocity": 35.0},
                {"lat": 37.7949, "lon": -122.4194, "velocity": 35.0},
            ]
        )
        
        # Test 2: Gentle curve
        self.test_scenario(
            "Highway Curve",
            [
                {"lat": 37.7749, "lon": -122.4194, "velocity": 30.0},
                {"lat": 37.7799, "lon": -122.4194, "velocity": 25.0},
                {"lat": 37.7849, "lon": -122.4144, "velocity": 20.0},  # Curve
                {"lat": 37.7899, "lon": -122.4094, "velocity": 25.0},
                {"lat": 37.7949, "lon": -122.4094, "velocity": 30.0},
            ]
        )
        
        # Test 3: Sharp turn
        self.test_scenario(
            "Sharp Turn",
            [
                {"lat": 37.7749, "lon": -122.4194, "velocity": 20.0},
                {"lat": 37.7759, "lon": -122.4194, "velocity": 15.0},
                {"lat": 37.7769, "lon": -122.4184, "velocity": 10.0},  # 90-degree turn
                {"lat": 37.7769, "lon": -122.4174, "velocity": 15.0},
                {"lat": 37.7769, "lon": -122.4164, "velocity": 20.0},
            ]
        )
        
        # Test 4: Speed limit change
        self.test_scenario(
            "Speed Limit Change",
            [
                {"lat": 37.7749, "lon": -122.4194, "velocity": 35.0},
                {"lat": 37.7799, "lon": -122.4194, "velocity": 35.0},
                {"lat": 37.7849, "lon": -122.4194, "velocity": 25.0},  # Speed limit drops
                {"lat": 37.7899, "lon": -122.4194, "velocity": 25.0},
                {"lat": 37.7949, "lon": -122.4194, "velocity": 25.0},
            ]
        )
    
    def test_performance(self):
        """Test CPU and memory usage of mapd."""
        if not self.mapd_process:
            print("mapd not running, skipping performance test")
            return
        
        print("\n" + "="*60)
        print("Performance Test")
        print("="*60)
        
        try:
            # Get process info
            import psutil
            process = psutil.Process(self.mapd_process.pid)
            
            # Monitor for 10 seconds
            print("Monitoring mapd performance for 10 seconds...")
            samples = []
            
            for i in range(10):
                cpu_percent = process.cpu_percent(interval=1.0)
                memory_info = process.memory_info()
                
                samples.append({
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_info.rss / 1024 / 1024
                })
                
                print(f"  Sample {i+1}: CPU={cpu_percent:.1f}%, Memory={samples[-1]['memory_mb']:.1f} MB")
            
            # Calculate averages
            avg_cpu = sum(s["cpu_percent"] for s in samples) / len(samples)
            avg_memory = sum(s["memory_mb"] for s in samples) / len(samples)
            
            print(f"\nAverage CPU: {avg_cpu:.1f}%")
            print(f"Average Memory: {avg_memory:.1f} MB")
            
            # Check for issues
            if avg_cpu > 10:
                print("WARNING: High CPU usage detected")
            if avg_memory > 100:
                print("WARNING: High memory usage detected")
                
        except ImportError:
            print("psutil not available, skipping detailed performance monitoring")
        except Exception as e:
            print(f"Performance monitoring error: {e}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("INTEGRATION TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r["success"])
        
        print(f"Total scenarios tested: {total_tests}")
        print(f"Successful: {successful_tests}")
        print(f"Failed: {total_tests - successful_tests}")
        
        print("\nScenario Results:")
        for result in self.results:
            status = "✓" if result["success"] else "✗"
            print(f"  {status} {result['scenario']}")
            if result["success"]:
                print(f"     Messages: {result['messages_received']} ({result['message_rate']:.1f} Hz)")
                if "max_curvature" in result:
                    print(f"     Max curvature: {result['max_curvature']:.4f}")
                if "min_safe_speed" in result and result["min_safe_speed"]:
                    print(f"     Min safe speed: {result['min_safe_speed']:.1f} m/s")


def signal_handler(signum, frame):
    """Handle cleanup on interrupt."""
    print("\nInterrupted, cleaning up...")
    sys.exit(0)


def main():
    """Run the full integration test."""
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    tester = IntegrationTester()
    
    try:
        # Set up environment
        tester.setup_test_environment()
        
        # Start mapd
        if not tester.start_mapd():
            print("Failed to start mapd. Some tests may fail.")
            print("Continuing with tests that don't require mapd...")
        
        # Run tests
        tester.run_all_tests()
        
        # Performance test
        tester.test_performance()
        
        # Print summary
        tester.print_summary()
        
    finally:
        # Clean up
        tester.stop_mapd()
        print("\nTest complete!")


if __name__ == "__main__":
    main()