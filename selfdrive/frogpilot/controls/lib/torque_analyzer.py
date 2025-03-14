#!/usr/bin/env python3
"""
Torque Saturation Model Analyzer

This script analyzes the collected steering torque data and helps in fine-tuning the
torque prediction model used by the Vision Turn Speed Controller.

Usage:
  python torque_analyzer.py [--days=7] [--plot] [--verbose]

Options:
  --days=N    Analyze data from the last N days (default: 7)
  --plot      Generate and save visualization plots
  --verbose   Print detailed statistics
"""

import argparse
import datetime
import json
import glob
import math
import matplotlib.pyplot as plt
import numpy as np
import os
import pickle
import sys
from collections import defaultdict

# Add openpilot directory to import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
from openpilot.common.conversions import Conversions as CV

# Paths
LOG_PATH = "/data/openpilot/log"
TORQUE_MODEL_PATH = "/data/openpilot/selfdrive/frogpilot/model_weights/torque_predictor.pkl"
OUTPUT_DIR = "/data/openpilot/selfdrive/frogpilot/reporting"

def load_logs(days=7, event_name="torque_predictor"):
    """Load torque prediction data from log files"""
    logs = []
    now = datetime.datetime.now()
    cutoff_date = now - datetime.timedelta(days=days)

    # Get all log files from the specified date range
    log_files = glob.glob(f"{LOG_PATH}/*.log")

    for log_file in log_files:
        try:
            file_date_str = os.path.basename(log_file).split("--")[0]
            file_date = datetime.datetime.strptime(file_date_str, "%Y-%m-%d--%H-%M-%S")

            if file_date >= cutoff_date:
                with open(log_file, 'r') as f:
                    for line in f:
                        if event_name in line and "cloudlog.event" in line:
                            try:
                                # Extract JSON data from the log line
                                json_data = json.loads(line.split("cloudlog.event")[1].strip())
                                if json_data.get("event") == event_name:
                                    json_data["timestamp"] = file_date.timestamp()
                                    logs.append(json_data)
                            except (json.JSONDecodeError, IndexError):
                                pass
        except Exception as e:
            print(f"Error processing log file {log_file}: {e}")

    return logs

def load_torque_model():
    """Load the current torque prediction model parameters"""
    try:
        if os.path.exists(TORQUE_MODEL_PATH):
            with open(TORQUE_MODEL_PATH, 'rb') as f:
                return pickle.load(f)
        return {"sensitivity_factor": 1.0, "confidence": 0.8}
    except Exception as e:
        print(f"Error loading torque model: {e}")
        return {"sensitivity_factor": 1.0, "confidence": 0.8}

def analyze_data(logs, verbose=False):
    """Analyze the collected data and generate statistics"""
    if not logs:
        print("No log data found")
        return None

    # Extract key metrics
    curvatures = [log.get("curvature", 0) for log in logs]
    speeds = [log.get("speed", 0) for log in logs]
    required_torques = [log.get("required_torque", 0) for log in logs]
    available_torques = [log.get("available_torque", 0) for log in logs]
    torque_limited = [log.get("torque_limited", False) for log in logs]
    sensitivity_factors = [log.get("sensitivity_factor", 1.0) for log in logs]

    # Calculate statistics
    total_events = len(logs)
    limiting_events = sum(torque_limited)
    limiting_percentage = (limiting_events / total_events * 100) if total_events > 0 else 0

    # Group data by speed ranges
    speed_ranges = defaultdict(lambda: {"count": 0, "limited": 0, "curvatures": [], "required_torques": []})

    for i, speed in enumerate(speeds):
        if speed <= 0:
            continue

        range_key = int(speed * CV.MS_TO_MPH / 10) * 10  # Group in 10 mph buckets
        speed_ranges[range_key]["count"] += 1
        if torque_limited[i]:
            speed_ranges[range_key]["limited"] += 1
        speed_ranges[range_key]["curvatures"].append(curvatures[i])
        speed_ranges[range_key]["required_torques"].append(required_torques[i])

    # Results
    results = {
        "total_events": total_events,
        "limiting_events": limiting_events,
        "limiting_percentage": limiting_percentage,
        "average_curvature": np.mean(curvatures) if curvatures else 0,
        "average_speed": np.mean(speeds) if speeds else 0,
        "average_required_torque": np.mean(required_torques) if required_torques else 0,
        "average_available_torque": np.mean(available_torques) if available_torques else 0,
        "average_sensitivity": np.mean(sensitivity_factors) if sensitivity_factors else 1.0,
        "speed_ranges": dict(speed_ranges)
    }

    if verbose:
        print("\n===== Torque Prediction Model Analysis =====")
        print(f"Total events analyzed: {total_events}")
        print(f"Events with torque limiting: {limiting_events} ({limiting_percentage:.1f}%)")
        print(f"Average curvature: {results['average_curvature']:.6f}")
        print(f"Average speed: {results['average_speed']:.1f} m/s ({results['average_speed'] * CV.MS_TO_MPH:.1f} mph)")
        print(f"Average required torque: {results['average_required_torque']:.1f}")
        print(f"Average available torque: {results['average_available_torque']:.1f}")
        print(f"Average sensitivity factor: {results['average_sensitivity']:.3f}")

        print("\nBreakdown by speed range:")
        for speed_range, data in sorted(speed_ranges.items()):
            limit_pct = (data["limited"] / data["count"] * 100) if data["count"] > 0 else 0
            print(f"{speed_range}-{speed_range+10} mph: {data['count']} events, "
                  f"{limit_pct:.1f}% limited, "
                  f"avg curvature: {np.mean(data['curvatures']):.6f}")

    return results

def generate_plots(results, model_params):
    """Generate visualizations of the model performance"""
    if not results:
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Plot 1: Torque limiting by speed range
    plt.figure(figsize=(12, 6))

    speed_ranges = sorted(results["speed_ranges"].keys())
    limiting_percentages = []

    for speed_range in speed_ranges:
        data = results["speed_ranges"][speed_range]
        limit_pct = (data["limited"] / data["count"] * 100) if data["count"] > 0 else 0
        limiting_percentages.append(limit_pct)

    plt.bar([f"{sr}-{sr+10}" for sr in speed_ranges], limiting_percentages)
    plt.xlabel("Speed Range (mph)")
    plt.ylabel("Percentage of Events with Torque Limiting (%)")
    plt.title(f"Torque Limiting by Speed Range\nSensitivity Factor: {model_params.get('sensitivity_factor', 1.0):.2f}")
    plt.grid(alpha=0.3)
    plt.savefig(f"{OUTPUT_DIR}/torque_limiting_by_speed.png")

    # Plot 2: Required vs Available Torque
    plt.figure(figsize=(12, 6))

    x_data = []
    y_req = []
    y_avail = []
    colors = []

    for speed_range in speed_ranges:
        data = results["speed_ranges"][speed_range]
        if data["count"] > 0:
            x_data.append(speed_range + 5)  # Middle of the range

            # Average required torque for this speed range
            y_req.append(np.mean(data["required_torques"]))

            # Estimated available torque (simplified model)
            speed_ms = (speed_range + 5) * CV.MPH_TO_MS
            base_torque = 409  # MAX_STEER_TORQUE
            available = base_torque
            if speed_ms < 5.0:
                available = base_torque
            elif speed_ms > 30.0:
                available = base_torque * 0.7
            else:
                reduction = (speed_ms - 5.0) / 25.0 * 0.3
                available = base_torque * (1.0 - reduction)

            y_avail.append(available * 0.85)  # 0.85 is TORQUE_MARGIN

            # Color based on limiting percentage
            limit_pct = (data["limited"] / data["count"] * 100)
            colors.append(f"C{min(int(limit_pct/10), 9)}")

    plt.plot(x_data, y_req, 'o-', label="Required Torque")
    plt.plot(x_data, y_avail, 's-', label="Available Torque")
    plt.xlabel("Speed (mph)")
    plt.ylabel("Torque")
    plt.title("Required vs Available Torque by Speed")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.savefig(f"{OUTPUT_DIR}/torque_vs_speed.png")

    # Plot 3: Curvature vs Speed with Torque Requirement
    plt.figure(figsize=(12, 8))

    # Extract data points
    speeds_mph = []
    curvatures = []
    torque_limited = []

    for speed_range, data in results["speed_ranges"].items():
        for i, curve in enumerate(data["curvatures"]):
            if curve > 0:  # Filter out straight roads
                speed_mph = speed_range + 5  # Middle of range as rough estimate
                speeds_mph.append(speed_mph)
                curvatures.append(curve)

                # Check if this would be torque limited
                required = data["required_torques"][i]
                torque_limited.append(required)

    # Create scatter plot
    scatter = plt.scatter(speeds_mph, curvatures, c=torque_limited, cmap='viridis', alpha=0.7)

    # Add colorbar
    cbar = plt.colorbar(scatter)
    cbar.set_label('Required Torque')

    # Plot "limiting curve" - the curvature at which torque saturation occurs at each speed
    if speeds_mph:
        x_curve = np.linspace(min(speeds_mph), max(speeds_mph), 100)
        y_curve = []

        for speed_mph in x_curve:
            speed_ms = speed_mph * CV.MPH_TO_MS

            # Calculate available torque at this speed
            base_torque = 409  # MAX_STEER_TORQUE
            if speed_ms < 5.0:
                available = base_torque
            elif speed_ms > 30.0:
                available = base_torque * 0.7
            else:
                reduction = (speed_ms - 5.0) / 25.0 * 0.3
                available = base_torque * (1.0 - reduction)

            available *= 0.85  # TORQUE_MARGIN

            # Convert to limiting curvature
            # curvature = torque / (speed^2 * mass * steering_ratio * 0.01 * sensitivity)
            if speed_ms > 0:
                limiting_curve = available / (speed_ms**2 * 2055 * 16 * 0.01 * model_params.get('sensitivity_factor', 1.0))
                y_curve.append(limiting_curve)
            else:
                y_curve.append(0)

        plt.plot(x_curve, y_curve, 'r-', linewidth=2, label="Torque Saturation Limit")

    plt.xlabel("Speed (mph)")
    plt.ylabel("Curvature")
    plt.title("Road Curvature vs Speed with Torque Requirements")
    plt.yscale('log')
    plt.grid(True, which="both", ls="--", alpha=0.3)
    plt.legend()
    plt.savefig(f"{OUTPUT_DIR}/curvature_vs_speed.png")

    print(f"Plots saved to {OUTPUT_DIR}/")

def main():
    parser = argparse.ArgumentParser(description="Analyze steering torque prediction data")
    parser.add_argument("--days", type=int, default=7, help="Analyze data from the last N days")
    parser.add_argument("--plot", action="store_true", help="Generate visualization plots")
    parser.add_argument("--verbose", action="store_true", help="Print detailed statistics")
    args = parser.parse_args()

    print(f"Analyzing torque prediction data from the last {args.days} days...")
    logs = load_logs(days=args.days)
    model_params = load_torque_model()

    print(f"Found {len(logs)} relevant log entries")
    print(f"Current model parameters: sensitivity_factor={model_params.get('sensitivity_factor', 1.0):.3f}, "
          f"confidence={model_params.get('confidence', 0.8):.3f}")

    results = analyze_data(logs, verbose=args.verbose)

    if args.plot and results:
        print("Generating visualization plots...")
        generate_plots(results, model_params)

    print("Analysis complete")

if __name__ == "__main__":
    main()