#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb

# Constants from the codebase
METER_TO_FOOT = 3.28084
FOOT_TO_METER = 0.3048

# User's setting
user_lane_detection_width_feet = 8.5  # User's setting in feet

# Current implementation from annotated_camera.cc
def current_hue_calculation(lane_width_meters, lane_detection_width_meters):
    """
    Replicates the current formula from annotated_camera.cc:
    float hue = 120.0f * (1 - fmin(fabs(laneWidth - laneDetectionWidth) / (laneDetectionWidth / 2), 1));
    """
    deviation = abs(lane_width_meters - lane_detection_width_meters)
    normalized_deviation = min(deviation / (lane_detection_width_meters / 2), 1.0)
    hue = 120.0 * (1.0 - normalized_deviation)
    return hue

# Improved implementation with asymmetrical behavior
def improved_hue_calculation(lane_width_meters, lane_detection_width_meters, is_blind_spot=False):
    """
    Improved formula that treats wider-than-ideal lanes as safe (green)
    while preserving the current behavior for narrower-than-ideal lanes.

    Blind spot detection always returns red (hue=0).
    """
    if is_blind_spot:
        return 0.0  # Always red for blind spots

    # If lane is wider than ideal, it's always green
    if lane_width_meters >= lane_detection_width_meters:
        return 120.0  # Green

    # For narrower lanes, use the same formula as current
    deviation = lane_detection_width_meters - lane_width_meters
    normalized_deviation = min(deviation / (lane_detection_width_meters / 2), 1.0)
    hue = 120.0 * (1.0 - normalized_deviation)
    return hue

# Function to convert hue to RGB color
def hue_to_color(hue):
    """Convert hue (0-120) to RGB color"""
    # HSV: (hue, saturation, value)
    hsv = np.array([hue/360.0, 0.75, 0.5]).reshape(1, 1, 3)
    rgb = hsv_to_rgb(hsv)[0, 0]
    return rgb

# Function to get color name
def get_color_name(hue):
    if hue >= 100:
        return "Green"
    elif hue >= 60:
        return "Yellow-Green"
    elif hue >= 40:
        return "Yellow"
    elif hue >= 20:
        return "Orange"
    else:
        return "Red"

# Test with different lane widths
def test_lane_widths():
    # Convert user setting to meters (as would happen in the code)
    lane_detection_width_meters = user_lane_detection_width_feet * FOOT_TO_METER

    print(f"User setting: {user_lane_detection_width_feet} feet = {lane_detection_width_meters:.2f} meters")
    print(f"Half of ideal width: {lane_detection_width_meters/2:.2f} meters")

    # Test a range of lane widths
    lane_widths_meters = np.linspace(1.0, 5.0, 20)
    current_hues = []
    improved_hues = []

    print("\nComparing current vs. improved color determination:")
    print("-" * 100)
    print(f"{'Lane Width (m)':<12} {'Lane Width (ft)':<12} {'Current Hue':<12} {'Current Color':<15} {'Improved Hue':<12} {'Improved Color':<15} {'Change'}")
    print("-" * 100)

    for lane_width_meters in lane_widths_meters:
        lane_width_feet = lane_width_meters * METER_TO_FOOT

        # Calculate hues using both methods
        current_hue = current_hue_calculation(lane_width_meters, lane_detection_width_meters)
        improved_hue = improved_hue_calculation(lane_width_meters, lane_detection_width_meters)

        current_color = get_color_name(current_hue)
        improved_color = get_color_name(improved_hue)

        # Determine if there's a change
        change = "CHANGED" if current_color != improved_color else ""

        print(f"{lane_width_meters:<12.2f} {lane_width_feet:<12.2f} {current_hue:<12.2f} {current_color:<15} {improved_hue:<12.2f} {improved_color:<15} {change}")

        current_hues.append(current_hue)
        improved_hues.append(improved_hue)

    return lane_widths_meters, current_hues, improved_hues

# Test with specific examples from user
def test_specific_examples():
    # Convert user setting to meters
    lane_detection_width_meters = user_lane_detection_width_feet * FOOT_TO_METER

    print("\nTesting specific examples mentioned by user:")
    print("-" * 100)

    # Example: 3.4-3.6 meters (reported as yellow/orange)
    example_widths = [3.4, 3.5, 3.6]

    for width_m in example_widths:
        width_ft = width_m * METER_TO_FOOT

        # Calculate hues using both methods
        current_hue = current_hue_calculation(width_m, lane_detection_width_meters)
        improved_hue = improved_hue_calculation(width_m, lane_detection_width_meters)

        current_color = get_color_name(current_hue)
        improved_color = get_color_name(improved_hue)

        print(f"Lane width: {width_m:.2f}m ({width_ft:.2f}ft)")
        print(f"  Current: Hue = {current_hue:.2f} → Color = {current_color}")
        print(f"  Improved: Hue = {improved_hue:.2f} → Color = {improved_color}")

    # Test blind spot detection
    print("\nTesting blind spot detection:")
    width_m = 3.5  # Example width
    width_ft = width_m * METER_TO_FOOT

    # Normal calculation
    normal_hue = improved_hue_calculation(width_m, lane_detection_width_meters, is_blind_spot=False)
    # Blind spot calculation
    blind_spot_hue = improved_hue_calculation(width_m, lane_detection_width_meters, is_blind_spot=True)

    print(f"Lane width: {width_m:.2f}m ({width_ft:.2f}ft)")
    print(f"  Without blind spot: Hue = {normal_hue:.2f} → Color = {get_color_name(normal_hue)}")
    print(f"  With blind spot: Hue = {blind_spot_hue:.2f} → Color = {get_color_name(blind_spot_hue)}")

# Plot the results
def plot_results(lane_widths_meters, current_hues, improved_hues):
    plt.figure(figsize=(14, 8))

    # Convert lane widths to feet for x-axis
    lane_widths_feet = lane_widths_meters * METER_TO_FOOT

    # Create color maps
    current_colors = [hue_to_color(h) for h in current_hues]
    improved_colors = [hue_to_color(h) for h in improved_hues]

    # Plot current implementation
    plt.subplot(2, 1, 1)
    plt.scatter(lane_widths_feet, current_hues, c=current_colors, s=100)
    plt.plot(lane_widths_feet, current_hues, 'k--', alpha=0.3)

    # Add vertical line at user's setting
    plt.axvline(x=user_lane_detection_width_feet, color='blue', linestyle='-', alpha=0.5,
                label=f'User setting: {user_lane_detection_width_feet} ft')

    # Add horizontal lines for color transitions
    plt.axhline(y=100, color='green', linestyle='--', alpha=0.5, label='Green-Yellow transition')
    plt.axhline(y=60, color='yellow', linestyle='--', alpha=0.5, label='Yellow')
    plt.axhline(y=20, color='orange', linestyle='--', alpha=0.5, label='Orange-Red transition')

    plt.title('Current Implementation: Lane Width vs. Color Hue')
    plt.ylabel('Hue Value (0-120)')
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Plot improved implementation
    plt.subplot(2, 1, 2)
    plt.scatter(lane_widths_feet, improved_hues, c=improved_colors, s=100)
    plt.plot(lane_widths_feet, improved_hues, 'k--', alpha=0.3)

    # Add vertical line at user's setting
    plt.axvline(x=user_lane_detection_width_feet, color='blue', linestyle='-', alpha=0.5,
                label=f'User setting: {user_lane_detection_width_feet} ft')

    # Add horizontal lines for color transitions
    plt.axhline(y=100, color='green', linestyle='--', alpha=0.5, label='Green-Yellow transition')
    plt.axhline(y=60, color='yellow', linestyle='--', alpha=0.5, label='Yellow')
    plt.axhline(y=20, color='orange', linestyle='--', alpha=0.5, label='Orange-Red transition')

    plt.title('Improved Implementation: Lane Width vs. Color Hue')
    plt.xlabel('Lane Width (feet)')
    plt.ylabel('Hue Value (0-120)')
    plt.grid(True, alpha=0.3)
    plt.legend()

    plt.tight_layout()

    # Save the plot
    plt.savefig('improved_lane_color_analysis.png')
    print("\nPlot saved as 'improved_lane_color_analysis.png'")

# Run the tests
if __name__ == "__main__":
    print("Improved Lane Width Color Determination Analysis")
    print("===============================================")

    lane_widths, current_hues, improved_hues = test_lane_widths()
    test_specific_examples()

    try:
        plot_results(lane_widths, current_hues, improved_hues)
        print("\nAnalysis complete. The improved implementation makes lanes wider than the ideal width always appear green,")
        print("while preserving the current behavior for narrower lanes and blind spot detection.")
    except Exception as e:
        print(f"\nCould not create plot: {e}")
        print("Analysis complete. Check the numerical results above.")