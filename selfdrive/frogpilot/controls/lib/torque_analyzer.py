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
import time
from collections import defaultdict

# Import constants from chauffeur_vtsc for consistency
try:
    from openpilot.selfdrive.controls.lib.drive_helpers import V_CRUISE_MAX
    from openpilot.selfdrive.frogpilot.controls.lib.chauffeur_vtsc import SteeringTorqueSaturationPredictor
except ImportError:
    # Fallback values if imports fail
    V_CRUISE_MAX = 145  # kph
    class SteeringTorqueSaturationPredictor:
        pass

# Define conversion constants directly to avoid import issues
class CV:
    """Conversion constants"""
    MPH_TO_MS = 0.44704
    MS_TO_MPH = 2.2369362920544
    KPH_TO_MPH = 0.621371

# Paths - use local log_dir for development
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "log_dir")
TORQUE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "../../../frogpilot/model_weights/torque_predictor.pkl")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../../../frogpilot/reporting")

# Constants for filtering - use imported values or fallbacks
# The speeds are in different units, so convert as needed
MAX_REALISTIC_SPEED_MPH = V_CRUISE_MAX * CV.KPH_TO_MPH  # Convert from kph to mph
# Using the same threshold as in chauffeur_vtsc.py SteeringTorqueSaturationPredictor
MIN_CURVATURE_THRESHOLD = 5e-5  # Minimum meaningful curvature (match learning algorithm)
REALISTIC_CURVE_MIN = 5e-5      # Minimum curvature to be considered a real curve
MAX_BANK_ANGLE = 0.26           # Maximum realistic road bank angle (~15 degrees in radians)

def load_logs(days=7, event_name="torque_predictor", additional_events=None):
    """Load torque prediction data from swaglog files"""
    logs = []
    additional_data = {}
    now = time.time()
    cutoff_time = now - (days * 24 * 60 * 60)

    # Get all swaglog files
    if not os.path.exists(LOG_PATH):
        print(f"Error: Log directory not found at {LOG_PATH}")
        return logs, additional_data

    # Get all swaglog files
    swaglog_files = []
    for filename in os.listdir(LOG_PATH):
        if filename.startswith("swaglog."):
            file_path = os.path.join(LOG_PATH, filename)
            swaglog_files.append(file_path)

    if not swaglog_files:
        print(f"No swaglog files found in {LOG_PATH}")
        return logs, additional_data

    print(f"Found {len(swaglog_files)} swaglog files in {LOG_PATH}")

    # Parse each swaglog file
    for swaglog_file in sorted(swaglog_files):
        try:
            print(f"Processing {swaglog_file}...")

            with open(swaglog_file, 'r') as f:
                for line in f:
                    try:
                        # Parse the JSON line
                        log_entry = json.loads(line)

                        # Check if this is a torque_predictor event
                        if "msg" in log_entry and isinstance(log_entry["msg"], dict) and log_entry["msg"].get("event$s") == event_name:
                            # Extract timestamp
                            timestamp = log_entry.get("created", 0)
                            if timestamp < cutoff_time:
                                continue

                            # Extract the data
                            msg = log_entry["msg"]

                            # Filter out unrealistic speeds
                            speed = msg.get("speed$f", 0)
                            if speed * CV.MS_TO_MPH > MAX_REALISTIC_SPEED_MPH:
                                continue

                            # Filter out effectively straight roads
                            curvature = msg.get("curvature$f", 0)
                            if abs(curvature) < MIN_CURVATURE_THRESHOLD:
                                continue

                            # Filter out extreme road banking
                            road_bank = msg.get("road_bank$f", 0)
                            if abs(road_bank) > MAX_BANK_ANGLE:
                                continue

                            json_data = {
                                "curvature": curvature,
                                "speed": speed,
                                "required_torque": msg.get("required_torque$f", 0),
                                "available_torque": msg.get("available_torque$i", 0),
                                "torque_limited": msg.get("torque_limited$b", False),
                                "sensitivity_factor": msg.get("sensitivity_factor$f", 1.0),
                                "confidence": msg.get("confidence$f", 0.8),
                                "samples_count": msg.get("samples_count$i", 0),
                                "road_bank": msg.get("road_bank$f", 0),
                                "gravity_component": msg.get("gravity_component$f", 0),
                                "timestamp": timestamp
                            }
                            logs.append(json_data)

                        # Collect additional event types if specified
                        if additional_events and "msg" in log_entry and isinstance(log_entry["msg"], dict):
                            event_type = log_entry["msg"].get("event$s")
                            if event_type in additional_events:
                                # Extract timestamp for matching with torque events
                                timestamp = log_entry.get("created", 0)
                                if timestamp < cutoff_time:
                                    continue

                                # Store the additional data by timestamp for later correlation
                                if event_type not in additional_data:
                                    additional_data[event_type] = []

                                additional_data[event_type].append({
                                    "timestamp": timestamp,
                                    "data": log_entry["msg"]
                                })

                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        if "--verbose" in sys.argv:
                            print(f"Error parsing log entry: {e}")
                        continue
        except Exception as e:
            print(f"Error processing swaglog file {swaglog_file}: {e}")

    return logs, additional_data

def load_torque_model():
    """Load the current torque prediction model parameters"""
    try:
        if os.path.exists(TORQUE_MODEL_PATH):
            with open(TORQUE_MODEL_PATH, 'rb') as f:
                return pickle.load(f)
        # Default values if model file doesn't exist
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
    road_banks = [log.get("road_bank", 0.0) for log in logs]

    # Calculate statistics
    total_events = len(logs)
    limiting_events = sum(torque_limited)
    limiting_percentage = (limiting_events / total_events * 100) if total_events > 0 else 0

    # Group data by speed ranges
    speed_ranges = defaultdict(lambda: {"count": 0, "limited": 0, "curvatures": [], "required_torques": [], "speeds_ms": []})

    for i, speed in enumerate(speeds):
        if speed <= 0:
            continue

        range_key = int(speed * CV.MS_TO_MPH / 10) * 10  # Group in 10 mph buckets
        speed_ranges[range_key]["count"] += 1
        speed_ranges[range_key]["speeds_ms"].append(speed)
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
        "average_road_bank": np.mean(road_banks) if road_banks else 0.0,
        "max_road_bank": max(road_banks) if road_banks else 0.0,
        "min_road_bank": min(road_banks) if road_banks else 0.0,
        "speed_ranges": dict(speed_ranges)
    }

    # Calculate torque saturation ratio
    # How close to the available torque are we typically getting?
    torque_ratios = []
    for i in range(len(required_torques)):
        if available_torques[i] > 0:
            torque_ratios.append(required_torques[i] / available_torques[i])

    results["average_torque_ratio"] = np.mean(torque_ratios) if torque_ratios else 0
    results["max_torque_ratio"] = max(torque_ratios) if torque_ratios else 0

    if verbose:
        print("\n===== Torque Prediction Model Analysis =====")
        print(f"Total real curve events analyzed: {total_events}")
        print(f"Events with torque limiting: {limiting_events} ({limiting_percentage:.1f}%)")
        print(f"Average curvature: {results['average_curvature']:.6f}")
        print(f"Average speed: {results['average_speed']:.1f} m/s ({results['average_speed'] * CV.MS_TO_MPH:.1f} mph)")
        print(f"Average required torque: {results['average_required_torque']:.1f}")
        print(f"Average available torque: {results['average_available_torque']:.1f}")
        print(f"Average torque required/available ratio: {results['average_torque_ratio']:.2f}")
        print(f"Maximum torque required/available ratio: {results['max_torque_ratio']:.2f}")
        print(f"Average sensitivity factor: {results['average_sensitivity']:.3f}")
        print(f"Road banking: avg={results['average_road_bank']:.4f}, min={results['min_road_bank']:.4f}, max={results['max_road_bank']:.4f}")

        print("\nBreakdown by speed range:")
        for speed_range, data in sorted(speed_ranges.items()):
            if data["count"] >= 5:  # Only show ranges with enough data points
                limit_pct = (data["limited"] / data["count"] * 100) if data["count"] > 0 else 0
                avg_curve = np.mean(data["curvatures"]) if data["curvatures"] else 0
                avg_torque = np.mean(data["required_torques"]) if data["required_torques"] else 0
                print(f"{speed_range}-{speed_range+10} mph: {data['count']} events, "
                    f"{limit_pct:.1f}% limited, "
                    f"avg curvature: {avg_curve:.6f}, "
                    f"avg torque: {avg_torque:.1f}")

    return results

def generate_plots(results, model_params):
    """Generate visualizations of the model performance"""
    if not results:
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Plot 1: Torque limiting by speed range (with minimum count threshold)
    plt.figure(figsize=(12, 6))

    speed_ranges = []
    limiting_percentages = []
    sample_counts = []
    min_count = 3  # Minimum number of samples to include in plot

    for speed_range, data in sorted(results["speed_ranges"].items()):
        if data["count"] >= min_count:
            speed_ranges.append(f"{speed_range}-\n{speed_range+10}")
            limit_pct = (data["limited"] / data["count"] * 100) if data["count"] > 0 else 0
            limiting_percentages.append(limit_pct)
            sample_counts.append(data["count"])

    if speed_ranges:
        bars = plt.bar(speed_ranges, limiting_percentages)

        # Add count labels to the top of each bar
        for i, (bar, count) in enumerate(zip(bars, sample_counts)):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'n={count}', ha='center', va='bottom', rotation=0, size=8)

        plt.xlabel("Speed Range (mph)")
        plt.ylabel("Percentage of Events with Torque Limiting (%)")
        plt.title(f"Torque Limiting by Speed Range\nSensitivity Factor: {model_params.get('sensitivity_factor', 1.0):.2f}")
        plt.grid(alpha=0.3)
        plt.ylim(0, 105)  # Leave room for the count labels
        plt.savefig(f"{OUTPUT_DIR}/torque_limiting_by_speed.png")

    # Plot 2: Curvature vs Speed, colored by limiting status
    plt.figure(figsize=(12, 8))

    # Extract data points
    speeds_mph = []
    curvatures = []
    is_limited = []

    for speed_range, data in results["speed_ranges"].items():
        for i, curve in enumerate(data["curvatures"]):
            if curve > REALISTIC_CURVE_MIN:  # Only include meaningful curves
                speed_mph = speed_range + 5  # Middle of range as rough estimate
                real_speed = data["speeds_ms"][i] * CV.MS_TO_MPH
                speeds_mph.append(real_speed)
                curvatures.append(curve)

                # Check if torque limited
                required = data["required_torques"][i]
                avail_torque = results["average_available_torque"]
                is_limited.append(required > avail_torque)

    # Create scatter plot
    if speeds_mph:
        plt.scatter(speeds_mph, curvatures, c=is_limited, cmap='coolwarm', alpha=0.7,
                    s=50, edgecolors='k', linewidths=0.5)

        # Add a colorbar legend
        cbar = plt.colorbar(ticks=[0, 1])
        cbar.set_label('Torque Limited')
        cbar.set_ticklabels(['No', 'Yes'])

        # Plot "limiting curve" - the curvature at which torque saturation occurs at each speed
        x_curve = np.linspace(5, max(max(speeds_mph), 85), 100)
        y_curve = []

        for speed_mph in x_curve:
            speed_ms = speed_mph * CV.MPH_TO_MS

            # Calculate available torque (fixed at 409 regardless of speed in the current implementation)
            available = 409 * 0.85  # MAX_STEER_TORQUE * TORQUE_MARGIN

            # Set the required values for the limiting curve calculation
            # From SteeringTorqueSaturationPredictor in chauffeur_vtsc.py - use same values
            vehicle_mass = 2055  # Should match VEHICLE_MASS in SteeringTorqueSaturationPredictor
            steering_ratio = 16.0  # Should match STEERING_RATIO in SteeringTorqueSaturationPredictor
            model_scale_factor = 0.01  # Should match MODEL_SCALE_FACTOR in SteeringTorqueSaturationPredictor
            sensitivity = model_params.get('sensitivity_factor', 1.0)

            # Solve for the curvature at which we'd hit the torque limit
            # curvature = torque / (speed^2 * mass * steering_ratio * model_scale_factor * sensitivity)
            if speed_ms > 0:
                limiting_curve = available / (speed_ms**2 * vehicle_mass * steering_ratio * model_scale_factor * sensitivity)
                y_curve.append(limiting_curve)
            else:
                y_curve.append(0)

        plt.plot(x_curve, y_curve, 'r-', linewidth=2, label="Torque Saturation Limit")

        plt.xlabel("Speed (mph)")
        plt.ylabel("Curvature")
        plt.title("Road Curvature vs Speed with Torque Limiting Status")
        plt.yscale('log')
        plt.grid(True, which="both", ls="--", alpha=0.3)
        plt.legend()
        plt.savefig(f"{OUTPUT_DIR}/curvature_vs_speed.png")

    # Plot 3: Torque Requirements vs Speed
    plt.figure(figsize=(12, 6))

    # Group data by speed range for box plots
    speeds_for_plot = []
    torques_for_plot = []

    for speed_range, data in sorted(results["speed_ranges"].items()):
        if data["count"] >= min_count:
            for _, torque in enumerate(data["required_torques"]):
                speeds_for_plot.append(speed_range + 5)  # Middle of the range
                torques_for_plot.append(torque)

    if speeds_for_plot:
        # Create a box plot grouped by speed
        from itertools import groupby

        # Group data by speed
        speed_groups = defaultdict(list)
        for speed, torque in zip(speeds_for_plot, torques_for_plot):
            speed_groups[speed].append(torque)

        # Prepare data for box plot
        box_data = []
        labels = []
        for speed, torques in sorted(speed_groups.items()):
            if len(torques) >= min_count:
                box_data.append(torques)
                labels.append(f"{int(speed-5)}-{int(speed+5)}")

        plt.boxplot(box_data, labels=labels, patch_artist=True)

        # Add a horizontal line at the available torque level
        plt.axhline(y=results["average_available_torque"], color='r', linestyle='-',
                  label=f"Available Torque: {results['average_available_torque']:.0f}")

        plt.xlabel("Speed Range (mph)")
        plt.ylabel("Required Torque")
        plt.title("Distribution of Required Torque by Speed Range")
        plt.grid(alpha=0.3)
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_DIR}/torque_vs_speed_distribution.png")

    print(f"Plots saved to {OUTPUT_DIR}/")

def main():
    parser = argparse.ArgumentParser(description="Analyze steering torque prediction data")
    parser.add_argument("--days", type=int, default=7, help="Analyze data from the last N days")
    parser.add_argument("--plot", action="store_true", help="Generate visualization plots")
    parser.add_argument("--verbose", action="store_true", help="Print detailed statistics")
    args = parser.parse_args()

    print(f"Analyzing torque prediction data from the last {args.days} days...")

    # Check if the log directory exists
    if not os.path.exists(LOG_PATH):
        print(f"Error: Log directory not found at {LOG_PATH}")
        print(f"Expected path: {LOG_PATH}")
        print("Make sure you have the log_dir directory in your workspace.")
        return

    # We might want to look for other events like carState, modelV2, etc.
    # But for now, just focus on torque_predictor events
    logs, additional_data = load_logs(days=args.days)
    model_params = load_torque_model()

    print(f"Found {len(logs)} relevant real curve log entries")
    print(f"Current model parameters: sensitivity_factor={model_params.get('sensitivity_factor', 1.0):.3f}, "
          f"confidence={model_params.get('confidence', 0.8):.3f}")

    if not logs:
        print("\nNo torque predictor logs found for real curve scenarios. This could be because:")
        print("1. You haven't driven the car with the torque predictor feature enabled")
        print("2. The car hasn't encountered any significant curves to trigger torque prediction")
        print("3. The logs are stored in a different format or location")
        print("\nTry driving the car on some curvy roads with openpilot engaged and then run this script again.")
        return

    results = analyze_data(logs, verbose=args.verbose)

    if args.plot and results:
        print("Generating visualization plots...")
        generate_plots(results, model_params)

    print("Analysis complete")

if __name__ == "__main__":
    main()