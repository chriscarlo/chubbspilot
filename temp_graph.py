import numpy as np
import matplotlib.pyplot as plt
import math

# Define conversion constant
MPH_TO_MS = 0.44704  # mph to m/s conversion
MS_TO_MPH = 1.0 / MPH_TO_MS  # m/s to mph conversion

# Speed range in mph
speeds_mph = np.linspace(0, 80, 200)
speeds_ms = speeds_mph * MPH_TO_MS

# Current implementation
def current_lat_accel(v_ego_ms):
    v_ego_mph = v_ego_ms * MS_TO_MPH
    base = 1.62
    span = 2.38
    center = 35.0
    k = 0.10
    lat_acc = base + span / (1 + math.exp(-k * (v_ego_mph - center)))
    lat_acc = min(lat_acc, 3.02)
    return lat_acc

# Proposed implementation
def proposed_lat_accel(v_ego_ms):
    v_ego_mph = v_ego_ms * MS_TO_MPH
    base = 1.4
    span = 1.8
    center = 30.0
    k = 0.10
    lat_acc = base + span / (1 + math.exp(-k * (v_ego_mph - center)))
    lat_acc = min(lat_acc, 3.2)
    return lat_acc

# Calculate lateral acceleration values
current_lat_accs = [current_lat_accel(s) for s in speeds_ms]
proposed_lat_accs = [proposed_lat_accel(s) for s in speeds_ms]

# Define curvature values for different scenarios
curvatures = {
    "Gentle curve (radius=200m)": 0.005,
    "Moderate curve (radius=100m)": 0.01,
    "Sharp curve (radius=40m)": 0.025
}

# Create figures
plt.figure(figsize=(12, 8))

# Plot for lateral acceleration limits
plt.subplot(2, 1, 1)
plt.plot(speeds_mph, current_lat_accs, 'b-', linewidth=2, label='Current')
plt.plot(speeds_mph, proposed_lat_accs, 'r--', linewidth=2, label='Proposed')
plt.xlabel('Vehicle Speed (mph)')
plt.ylabel('Lateral Acceleration Limit (m/s²)')
plt.title('Lateral Acceleration Limits vs Vehicle Speed')
plt.grid(True)
plt.legend()

# Plot for speed differences at different curvatures
plt.subplot(2, 1, 2)
for curve_name, curvature_value in curvatures.items():
    current_speeds = [math.sqrt(acc / curvature_value) * MS_TO_MPH for acc in current_lat_accs]
    proposed_speeds = [math.sqrt(acc / curvature_value) * MS_TO_MPH for acc in proposed_lat_accs]

    # Calculate speed difference (proposed - current)
    speed_diff = np.array(proposed_speeds) - np.array(current_speeds)

    plt.plot(speeds_mph, speed_diff, linewidth=2, label=curve_name)

plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
plt.xlabel('Vehicle Speed (mph)')
plt.ylabel('Speed Difference (Proposed - Current) (mph)')
plt.title('Speed Limit Difference: Proposed vs Current')
plt.grid(True)
plt.legend()

plt.tight_layout()
plt.savefig('speed_comparison.png')

# Create a second figure with absolute speed limits for each curve type
plt.figure(figsize=(15, 10))

for i, (curve_name, curvature_value) in enumerate(curvatures.items(), 1):
    current_speeds = [math.sqrt(acc / curvature_value) * MS_TO_MPH for acc in current_lat_accs]
    proposed_speeds = [math.sqrt(acc / curvature_value) * MS_TO_MPH for acc in proposed_lat_accs]

    plt.subplot(len(curvatures), 1, i)
    plt.plot(speeds_mph, current_speeds, 'b-', linewidth=2, label='Current')
    plt.plot(speeds_mph, proposed_speeds, 'r--', linewidth=2, label='Proposed')
    plt.plot(speeds_mph, speeds_mph, 'k:', linewidth=1, alpha=0.5, label='1:1 Line')
    plt.xlabel('Vehicle Speed (mph)')
    plt.ylabel('Speed Limit (mph)')
    plt.title(f'Speed Limits for {curve_name} (curvature = {curvature_value})')
    plt.grid(True)
    plt.legend()

    # Add y=x line to show when speed limits become active
    plt.fill_between(speeds_mph, speeds_mph, 0, alpha=0.1, color='gray')

plt.tight_layout()
plt.savefig('speed_limits_by_curve.png')

print('Graphs saved to speed_comparison.png and speed_limits_by_curve.png')