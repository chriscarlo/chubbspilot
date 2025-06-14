#!/usr/bin/env python3
"""
Performance monitoring script for mapd and turn speed controllers.
Monitors CPU, memory, message rates, and system health.
"""

import time
import json
import subprocess
import threading
import queue
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

import cereal.messaging as messaging
from openpilot.common.params import Params
from openpilot.system.swaglog import cloudlog


class PerformanceMonitor:
    """Monitor performance metrics of mapd and related processes."""
    
    def __init__(self, duration_seconds: int = 300):
        self.duration = duration_seconds
        self.params = Params()
        self.metrics_queue = queue.Queue()
        self.running = False
        self.start_time = None
        
        # Process names to monitor
        self.processes_to_monitor = [
            "mapd",
            "controlsd",
            "modeld",
            "locationd"
        ]
        
        # Message streams to monitor
        self.message_streams = [
            "liveMapData",
            "modelV2",
            "carControl",
            "gpsLocationExternal"
        ]
        
        # Metrics storage
        self.cpu_samples = {proc: [] for proc in self.processes_to_monitor}
        self.memory_samples = {proc: [] for proc in self.processes_to_monitor}
        self.message_counts = {stream: 0 for stream in self.message_streams}
        self.message_latencies = {stream: [] for stream in self.message_streams}
        
    def get_process_stats(self, process_name: str) -> Optional[Dict]:
        """Get CPU and memory stats for a process."""
        try:
            # Use ps command for compatibility
            cmd = f"ps aux | grep {process_name} | grep -v grep | head -1"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout:
                parts = result.stdout.split()
                if len(parts) >= 11:
                    return {
                        "cpu_percent": float(parts[2]),
                        "memory_percent": float(parts[3]),
                        "vsz_kb": int(parts[4]),
                        "rss_kb": int(parts[5]),
                        "command": ' '.join(parts[10:])
                    }
        except Exception as e:
            cloudlog.error(f"Error getting stats for {process_name}: {e}")
        
        return None
    
    def monitor_processes(self):
        """Monitor process CPU and memory usage."""
        while self.running:
            timestamp = time.time()
            
            for process_name in self.processes_to_monitor:
                stats = self.get_process_stats(process_name)
                if stats:
                    self.cpu_samples[process_name].append({
                        "timestamp": timestamp,
                        "value": stats["cpu_percent"]
                    })
                    self.memory_samples[process_name].append({
                        "timestamp": timestamp,
                        "value": stats["rss_kb"] / 1024.0  # Convert to MB
                    })
                    
                    # Queue metrics for logging
                    self.metrics_queue.put({
                        "type": "process",
                        "name": process_name,
                        "cpu": stats["cpu_percent"],
                        "memory_mb": stats["rss_kb"] / 1024.0,
                        "timestamp": timestamp
                    })
            
            time.sleep(1.0)  # Sample every second
    
    def monitor_messages(self):
        """Monitor message rates and latencies."""
        sm = messaging.SubMaster(self.message_streams)
        last_count_time = time.time()
        
        while self.running:
            sm.update(100)  # 100ms timeout
            current_time = time.time()
            
            for stream in self.message_streams:
                if sm.updated[stream]:
                    self.message_counts[stream] += 1
                    
                    # Calculate latency if message has logMonoTime
                    if hasattr(sm[stream], 'logMonoTime'):
                        latency = (current_time * 1e9 - sm[stream].logMonoTime) / 1e6  # ms
                        self.message_latencies[stream].append(latency)
            
            # Log message rates every 10 seconds
            if current_time - last_count_time >= 10.0:
                for stream in self.message_streams:
                    rate = self.message_counts[stream] / 10.0
                    self.metrics_queue.put({
                        "type": "message_rate",
                        "stream": stream,
                        "rate_hz": rate,
                        "timestamp": current_time
                    })
                    self.message_counts[stream] = 0
                
                last_count_time = current_time
    
    def monitor_mapd_params(self):
        """Monitor mapd-specific parameters."""
        while self.running:
            timestamp = time.time()
            
            # Check MapTargetVelocities
            velocities_raw = self.params.get("MapTargetVelocities")
            if velocities_raw:
                try:
                    velocities = json.loads(velocities_raw)
                    self.metrics_queue.put({
                        "type": "map_data",
                        "num_points": len(velocities),
                        "timestamp": timestamp
                    })
                except json.JSONDecodeError:
                    pass
            
            # Check GPS position updates
            gps_raw = self.params.get("LastGPSPosition")
            if gps_raw:
                try:
                    gps = json.loads(gps_raw)
                    self.metrics_queue.put({
                        "type": "gps_update",
                        "accuracy": gps.get("verticalAccuracy", -1),
                        "timestamp": timestamp
                    })
                except json.JSONDecodeError:
                    pass
            
            time.sleep(5.0)  # Check every 5 seconds
    
    def start_monitoring(self):
        """Start all monitoring threads."""
        self.running = True
        self.start_time = time.time()
        
        print(f"Starting performance monitoring for {self.duration} seconds...")
        print(f"Monitoring processes: {', '.join(self.processes_to_monitor)}")
        print(f"Monitoring messages: {', '.join(self.message_streams)}")
        print("-" * 60)
        
        # Start monitoring threads
        threads = [
            threading.Thread(target=self.monitor_processes, name="process_monitor"),
            threading.Thread(target=self.monitor_messages, name="message_monitor"),
            threading.Thread(target=self.monitor_mapd_params, name="param_monitor"),
            threading.Thread(target=self.log_metrics, name="metric_logger")
        ]
        
        for thread in threads:
            thread.daemon = True
            thread.start()
        
        # Wait for duration
        try:
            time.sleep(self.duration)
        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user")
        
        # Stop monitoring
        self.running = False
        time.sleep(2)  # Give threads time to finish
        
        # Generate report
        self.generate_report()
    
    def log_metrics(self):
        """Log metrics from queue."""
        while self.running:
            try:
                metric = self.metrics_queue.get(timeout=1.0)
                
                # Console output for key metrics
                if metric["type"] == "process" and metric["name"] == "mapd":
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"mapd: CPU={metric['cpu']:.1f}%, "
                          f"Memory={metric['memory_mb']:.1f}MB")
                
                elif metric["type"] == "message_rate" and metric["stream"] == "liveMapData":
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"liveMapData rate: {metric['rate_hz']:.1f} Hz")
                
            except queue.Empty:
                continue
    
    def generate_report(self):
        """Generate performance report."""
        print("\n" + "="*60)
        print("PERFORMANCE MONITORING REPORT")
        print("="*60)
        print(f"Duration: {time.time() - self.start_time:.1f} seconds")
        print(f"Report generated: {datetime.now()}")
        
        # Process statistics
        print("\n--- Process Statistics ---")
        for process in self.processes_to_monitor:
            if self.cpu_samples[process]:
                cpu_values = [s["value"] for s in self.cpu_samples[process]]
                memory_values = [s["value"] for s in self.memory_samples[process]]
                
                print(f"\n{process}:")
                print(f"  CPU: avg={sum(cpu_values)/len(cpu_values):.1f}%, "
                      f"max={max(cpu_values):.1f}%, "
                      f"min={min(cpu_values):.1f}%")
                print(f"  Memory: avg={sum(memory_values)/len(memory_values):.1f}MB, "
                      f"max={max(memory_values):.1f}MB, "
                      f"min={min(memory_values):.1f}MB")
            else:
                print(f"\n{process}: Not running")
        
        # Message statistics
        print("\n--- Message Statistics ---")
        for stream in self.message_streams:
            if self.message_latencies[stream]:
                latencies = self.message_latencies[stream]
                print(f"\n{stream}:")
                print(f"  Latency: avg={sum(latencies)/len(latencies):.1f}ms, "
                      f"max={max(latencies):.1f}ms, "
                      f"min={min(latencies):.1f}ms")
        
        # Health checks
        print("\n--- Health Checks ---")
        issues = []
        
        # Check mapd CPU usage
        if self.cpu_samples.get("mapd"):
            avg_cpu = sum(s["value"] for s in self.cpu_samples["mapd"]) / len(self.cpu_samples["mapd"])
            if avg_cpu > 10.0:
                issues.append(f"mapd high CPU usage: {avg_cpu:.1f}%")
        
        # Check memory growth
        for process in self.processes_to_monitor:
            if len(self.memory_samples[process]) > 10:
                early_samples = self.memory_samples[process][:10]
                late_samples = self.memory_samples[process][-10:]
                
                early_avg = sum(s["value"] for s in early_samples) / len(early_samples)
                late_avg = sum(s["value"] for s in late_samples) / len(late_samples)
                
                growth = late_avg - early_avg
                if growth > 10.0:  # 10MB growth
                    issues.append(f"{process} memory growth: +{growth:.1f}MB")
        
        if issues:
            print("Issues detected:")
            for issue in issues:
                print(f"  ⚠️  {issue}")
        else:
            print("✓ All systems healthy")
        
        # Save detailed report
        report_file = Path("/tmp/mapd_performance_report.json")
        report_data = {
            "duration": time.time() - self.start_time,
            "timestamp": datetime.now().isoformat(),
            "cpu_samples": self.cpu_samples,
            "memory_samples": self.memory_samples,
            "message_latencies": self.message_latencies,
            "issues": issues
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_file}")


def main():
    """Run performance monitoring."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitor mapd and controller performance")
    parser.add_argument("--duration", type=int, default=300,
                        help="Monitoring duration in seconds (default: 300)")
    parser.add_argument("--process", action="append",
                        help="Additional process to monitor")
    
    args = parser.parse_args()
    
    monitor = PerformanceMonitor(duration_seconds=args.duration)
    
    # Add any additional processes
    if args.process:
        monitor.processes_to_monitor.extend(args.process)
    
    # Start monitoring
    monitor.start_monitoring()


if __name__ == "__main__":
    main()