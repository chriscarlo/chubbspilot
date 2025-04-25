import numpy as np
import math
import matplotlib.pyplot as plt

# --- Define the function as implemented ---
def curvature_based_lat_accel(abs_curvature: float) -> float:
    """
    Determines target lateral acceleration based on curvature using a tuned decreasing sigmoid.
    Targets high acceleration (3.2 m/s^2) for gentle curves (low curvature / high speed).
    Smoothly decreases towards a lower acceleration (1.5 m/s^2) for very sharp curves
    (high curvature / low speed), approximating low-speed torque/comfort limits.
    """
    # Target lateral acceleration range
    high_accel = 3.2  # Target accel for gentle/moderate curves (kappa -> 0)
    low_accel = 1.5   # Target accel limit for very sharp curves (kappa -> high)
    span = high_accel - low_accel # The range of reduction (1.7 m/s^2)

    # Sigmoid parameters
    center_curvature = 0.018 # Center the transition slightly below kappa=0.02
    k = 180                  # Gain to control the transition sharpness

    # Calculate the decreasing sigmoid value:
    reduction = span / (1.0 + math.exp(-k * (abs_curvature - center_curvature)))
    lat_acc = high_accel - reduction

    # Ensure the value stays within the intended bounds [low_accel, high_accel]
    return np.clip(lat_acc, low_accel, high_accel)
# --- End function definition ---

# --- Generate data for plotting ---
# Create a range of curvatures (kappa) - use logspace for better coverage near zero
# Avoid kappa=0 to prevent division by zero in v_safe calculation
kappa_values = np.logspace(-4, -1, 500) # Covers curvatures from 0.0001 to 0.1 (Radius ~10km down to 10m)

target_lat_accels = []
safe_speeds_ms = []

for kappa in kappa_values:
    if kappa < 1e-9: # Safety check for extremely small kappa
        continue

    # Calculate target lat accel using the function
    a_lat = curvature_based_lat_accel(kappa)

    # Calculate the resulting max safe speed v = sqrt(a / kappa)
    v_safe = math.sqrt(a_lat / kappa)

    # Store the results
    target_lat_accels.append(a_lat)
    safe_speeds_ms.append(v_safe)

# Convert lists to numpy arrays for easier handling
target_lat_accels = np.array(target_lat_accels)
safe_speeds_ms = np.array(safe_speeds_ms)

# --- Create the plot ---
plt.figure(figsize=(10, 6))
plt.plot(safe_speeds_ms, target_lat_accels, label='Target Lat Accel vs. Resulting Safe Speed')

# Add points from the original interp for comparison
interp_speeds = np.array([5, 10, 20])
interp_accels = np.array([1.5, 2.0, 3.0])
plt.scatter(interp_speeds, interp_accels, color='red', zorder=5, label='Reference Interp Points (v_ego, a_lat)')

# Formatting
plt.xlabel("Resulting Max Safe Speed (m/s)")
plt.ylabel("Target Lateral Acceleration (m/s²)")
plt.title("Target Lateral Acceleration vs. Resulting Safe Speed\n(Based on Curvature Policy)")
plt.xlim(0, 40) # Set x-axis limit as requested (0-40 m/s)
plt.ylim(0, 3.5) # Set y-axis limit for clarity
plt.grid(True)
plt.legend()
plt.show()
