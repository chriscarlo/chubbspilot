import math
import numpy as np
import matplotlib.pyplot as plt

# --- Constants (copied from chauffeur_vtsc.py) ---
MPH_TO_MPS = 0.44704
CURV_CORR_FACTOR = MPH_TO_MPS ** 2
MAX_SPEED_DEFAULT = 70.0 # m/s
# --- End Constants ---

# --- Embed the target function directly --- (Bypasses imports)
def _local_test_curvature_based_lat_accel(abs_curvature_scaled: float) -> float:
    """Internal function using original sigmoid shape and tuned center."""
    high_accel = 3.2
    low_accel = 1.5
    span = high_accel - low_accel
    center_curvature = 0.0482 # Tuned value
    k = 180
    reduction = span / (1.0 + math.exp(-k * (abs_curvature_scaled - center_curvature)))
    lat_acc = high_accel - reduction
    return np.clip(lat_acc, low_accel, high_accel)
# --- End Embedded Function ---

# --- Override Factor for Base Profile Tuning ---
SPEED_INCREASE_FACTOR = 1.0
# --- End Override ---

def curvature_to_speed_base(abs_curvature_meters: float) -> float:
    """ Calculates speed using the LOCAL base accel function and factor=1.0 """
    if abs_curvature_meters < 1e-7:
        return MAX_SPEED_DEFAULT
    abs_curvature_scaled = abs_curvature_meters / CURV_CORR_FACTOR
    # Use LOCAL embedded function
    base_lat_accel = _local_test_curvature_based_lat_accel(abs_curvature_scaled)
    try:
        if base_lat_accel < 0: base_lat_accel = 0
        if abs_curvature_meters <= 1e-9:
             base_speed_mps = MAX_SPEED_DEFAULT
        else:
             base_speed_mps = math.sqrt(base_lat_accel / abs_curvature_meters)
    except (ValueError, ZeroDivisionError):
        base_speed_mps = 0.0
    # Use local factor=1.0
    target_speed_mps = base_speed_mps * SPEED_INCREASE_FACTOR
    return np.clip(target_speed_mps, 0.0, MAX_SPEED_DEFAULT)

# --- Calculations for Table & Plot --- (Using LOCAL base accel func)
# Generate curvatures from sharp to gentle
curvatures = np.linspace(0.1, 0.0005, 120)
speeds_mph_list = []
base_accel_list = [] # Store base accel directly

for kappa in curvatures:
    if kappa < 1e-7: continue
    # Calculate speed using local factor=1.0 func
    target_speed_mps = curvature_to_speed_base(kappa)
    target_speed_mph = target_speed_mps / MPH_TO_MPS

    # Calculate base accel using LOCAL embedded function
    kappa_scaled = kappa / CURV_CORR_FACTOR
    base_lat_acc = _local_test_curvature_based_lat_accel(kappa_scaled)

    # Add pairs, avoiding duplicates
    if not speeds_mph_list or abs(target_speed_mph - speeds_mph_list[-1]) > 0.01:
         speeds_mph_list.append(target_speed_mph)
         base_accel_list.append(base_lat_acc) # Store base accel

# Sort by speed for clarity
if speeds_mph_list:
    sorted_pairs = sorted(zip(speeds_mph_list, base_accel_list))
    speeds_mph_sorted = [pair[0] for pair in sorted_pairs]
    base_accel_sorted = [pair[1] for pair in sorted_pairs] # This is BASE accel
else:
    speeds_mph_sorted = []
    base_accel_sorted = []


# --- Print Table (Speed vs BASE Accel) ---
print("VTSC Test Script (LOCAL FUNCTION): Target Speed vs. Base Lateral Acceleration")
print(f"(Using embedded base accel function with factor=1.0)")
print("="*75)
print(f"{'Target Speed (MPH)':<25} | {'Base Lat Accel (m/s²)'}")
print("-"*75)

# Select representative points for the table, starting near 0
if speeds_mph_sorted:
    min_speed_for_table = 0.1
    max_speed_for_table = max(speeds_mph_sorted) - 0.5
    if max_speed_for_table > min_speed_for_table:
        target_mph_points = np.linspace(min_speed_for_table, max_speed_for_table, 15)
        # Interpolate the BASE accel values
        interpolated_accels = np.interp(target_mph_points, speeds_mph_sorted, base_accel_sorted)

        for speed_mph, base_accel in zip(target_mph_points, interpolated_accels):
            if speed_mph >= speeds_mph_sorted[0]:
                 print(f"{speed_mph:<25.1f} | {base_accel:.3f}")
    else:
        print("(Speed range too narrow for interpolation, showing raw points)")
        for speed_mph, base_accel in sorted_pairs:
            print(f"{speed_mph:<25.1f} | {base_accel:.3f}")
else:
    print("No valid speed points generated.")

print("-"*75)
print("\nGenerating plot (Speed vs BASE Accel)...")

# --- Plotting (Speed vs BASE Accel) ---
if speeds_mph_sorted:
    plt.figure(figsize=(10, 6))
    # Plot BASE accel
    plt.plot(speeds_mph_sorted, base_accel_sorted, marker='.', linestyle='-')
    plt.xlabel('Target Speed (MPH)')
    plt.ylabel('Base Lateral Accel (m/s²)') # Label axis correctly
    plt.title('VTSC (LOCAL FUNCTION): Target Speed vs. Base Lateral Acceleration')
    plt.grid(True)
    plt.ylim(bottom=1.0, top=3.5) # Limit Y axis to expected base range
    plt.xlim(left=0)
    plt.show()
else:
    print("Cannot generate plot, no data points.")

print("\nScript finished.")