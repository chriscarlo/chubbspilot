#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb

# Constants from the codebase
METER_TO_FOOT = 3.28084
FOOT_TO_METER = 0.3048

# User's setting
user_lane_detection_width_feet = 8.5  # User's setting in feet

# Function to calculate hue based on the formula in annotated_camera.cc
def calculate_hue(lane_width_meters, lane_detection_width_meters):
    """
    Replicates the formula from annotated_camera.cc:
    float hue = 120.0f * (1 - fmin(fabs(laneWidth - laneDetectionWidth) / (laneDetectionWidth / 2), 1));
    """
    deviation = abs(lane_width_meters - lane_detection_width_meters)
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
    print("\nTesting different lane widths:")
    print("-" * 80)
    print(f"{'Lane Width (m)':<15} {'Lane Width (ft)':<15} {'Deviation (m)':<15} {'Normalized Dev':<15} {'Hue':<10} {'Color'}")
    print("-" * 80)

    # Test a range of lane widths
    lane_widths_meters = np.linspace(1.0, 5.0, 20)
    hues = []

    for lane_width_meters in lane_widths_meters:
        lane_width_feet = lane_width_meters * METER_TO_FOOT
        deviation = abs(lane_width_meters - lane_detection_width_meters)
        normalized_deviation = min(deviation / (lane_detection_width_meters / 2), 1.0)
        hue = calculate_hue(lane_width_meters, lane_detection_width_meters)
        color_name = get_color_name(hue)

        print(f"{lane_width_meters:<15.2f} {lane_width_feet:<15.2f} {deviation:<15.2f} {normalized_deviation:<15.2f} {hue:<10.2f} {color_name}")
        hues.append(hue)

    return lane_widths_meters, hues

# Test with specific examples from user
def test_specific_examples():
    # Convert user setting to meters
    lane_detection_width_meters = user_lane_detection_width_feet * FOOT_TO_METER

    print("\nTesting specific examples mentioned by user:")
    print("-" * 80)

    # Example: 3.4-3.6 meters (reported as red)
    example_widths = [3.4, 3.5, 3.6]

    for width_m in example_widths:
        width_ft = width_m * METER_TO_FOOT
        hue = calculate_hue(width_m, lane_detection_width_meters)
        color_name = get_color_name(hue)

        print(f"Lane width: {width_m:.2f}m ({width_ft:.2f}ft) → Hue: {hue:.2f} → Color: {color_name}")

        # Calculate what the color should be based on the formula
        deviation = abs(width_m - lane_detection_width_meters)
        half_ideal = lane_detection_width_meters / 2

        print(f"  Deviation: {deviation:.2f}m, Half of ideal width: {half_ideal:.2f}m")
        if deviation > half_ideal:
            print(f"  Expected color: Red (deviation > half of ideal width)")
        else:
            normalized = deviation / half_ideal
            print(f"  Normalized deviation: {normalized:.2f} (should be {normalized*100:.0f}% of the way from green to red)")

# Plot the results
def plot_results(lane_widths_meters, hues):
    plt.figure(figsize=(12, 6))

    # Convert lane widths to feet for x-axis
    lane_widths_feet = lane_widths_meters * METER_TO_FOOT

    # Create color map
    colors = [hue_to_color(h) for h in hues]

    # Plot
    plt.scatter(lane_widths_feet, hues, c=colors, s=100)
    plt.plot(lane_widths_feet, hues, 'k--', alpha=0.3)

    # Add vertical line at user's setting
    plt.axvline(x=user_lane_detection_width_feet, color='blue', linestyle='-', alpha=0.5,
                label=f'User setting: {user_lane_detection_width_feet} ft')

    # Add horizontal lines for color transitions
    plt.axhline(y=100, color='green', linestyle='--', alpha=0.5, label='Green-Yellow transition')
    plt.axhline(y=60, color='yellow', linestyle='--', alpha=0.5, label='Yellow')
    plt.axhline(y=20, color='orange', linestyle='--', alpha=0.5, label='Orange-Red transition')

    plt.xlabel('Lane Width (feet)')
    plt.ylabel('Hue Value (0-120)')
    plt.title('Lane Width vs. Color Hue')
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Save the plot
    plt.savefig('lane_width_color_analysis.png')
    print("\nPlot saved as 'lane_width_color_analysis.png'")

# Run the tests
if __name__ == "__main__":
    print("Lane Width Color Determination Analysis")
    print("======================================")

    lane_widths, hues = test_lane_widths()
    test_specific_examples()

    try:
        plot_results(lane_widths, hues)
        print("\nAnalysis complete. Check the results above to understand the color determination logic.")
    except Exception as e:
        print(f"\nCould not create plot: {e}")
        print("Analysis complete. Check the numerical results above.")