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
    high_accel = 3.7
    low_accel = 1.5
    span = high_accel - low_accel
    # center_curvature = 0.0482 # Tuned value
    center_curvature = 0.044
    k = 40
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
kappa_list = [] # Store corresponding curvature

for kappa in curvatures:
    if kappa < 1e-7: continue
    # Calculate speed using local factor=1.0 func
    target_speed_mps = curvature_to_speed_base(kappa)
    target_speed_mph = target_speed_mps / MPH_TO_MPS

    # Calculate base accel using LOCAL embedded function
    kappa_scaled = kappa / CURV_CORR_FACTOR
    base_lat_acc = _local_test_curvature_based_lat_accel(kappa_scaled)

    # Add triplets, avoiding duplicates based on speed
    if not speeds_mph_list or abs(target_speed_mph - speeds_mph_list[-1]) > 0.01:
         speeds_mph_list.append(target_speed_mph)
         base_accel_list.append(base_lat_acc) # Store base accel
         kappa_list.append(kappa) # Store curvature

# Sort by speed for clarity
if speeds_mph_list:
    # Sort all three lists based on speed
    sorted_triplets = sorted(zip(speeds_mph_list, base_accel_list, kappa_list))
    speeds_mph_sorted = [triplet[0] for triplet in sorted_triplets]
    base_accel_sorted = [triplet[1] for triplet in sorted_triplets] # This is BASE accel
    kappa_sorted = [triplet[2] for triplet in sorted_triplets] # This is curvature
else:
    speeds_mph_sorted = []
    base_accel_sorted = []
    kappa_sorted = []


# --- Print Table (Speed vs BASE Accel) ---
print("VTSC Test Script (LOCAL FUNCTION): Target Speed vs. Base Lateral Acceleration")
print(f"(Using embedded base accel function with factor=1.0)")
print("="*75)
# Modify table headers if needed (not strictly necessary for just adding plot axis)
print(f"{'Target Speed (MPH)':<25} | {'Base Lat Accel (m/s²)'}")
print("-"*75)

# Select representative points for the table, starting near 0
if speeds_mph_sorted:
    min_speed_for_table = 0.1
    max_speed_for_table = max(speeds_mph_sorted) - 0.5
    if max_speed_for_table > min_speed_for_table:
        target_mph_points = np.linspace(min_speed_for_table, max_speed_for_table, 15)
        # Interpolate the BASE accel values (curvature interpolation not needed for table)
        interpolated_accels = np.interp(target_mph_points, speeds_mph_sorted, base_accel_sorted)

        for speed_mph, base_accel in zip(target_mph_points, interpolated_accels):
            if speed_mph >= speeds_mph_sorted[0]:
                 print(f"{speed_mph:<25.1f} | {base_accel:.3f}")
    else:
        print("(Speed range too narrow for interpolation, showing raw points)")
        for speed_mph, base_accel, _ in sorted_triplets: # Iterate through triplets
            print(f"{speed_mph:<25.1f} | {base_accel:.3f}")
else:
    print("No valid speed points generated.")

print("-"*75)
print("Generating plot (Speed vs BASE Accel & Curvature)...")

# --- Plotting (Speed vs BASE Accel & Curvature) ---
if speeds_mph_sorted:
    fig, ax1 = plt.subplots(figsize=(12, 7)) # Slightly wider figure

    # Plot BASE accel on primary axis (ax1)
    color1 = 'tab:blue'
    ax1.set_xlabel('Target Speed (MPH)')
    ax1.set_ylabel('Base Lateral Accel (m/s²)', color=color1)
    ax1.plot(speeds_mph_sorted, base_accel_sorted, marker='.', linestyle='-', color=color1, label='Base Lateral Accel')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True)
    ax1.set_ylim(bottom=1.0, top=3.5) # Limit Y axis to expected base range
    ax1.set_xlim(left=0)

    # Create secondary axis sharing the same x-axis
    ax2 = ax1.twinx()
    color2 = 'tab:red'
    ax2.set_ylabel('Curvature (1/m)', color=color2) # Label axis correctly
    # Plot curvature on secondary axis (ax2)
    ax2.plot(speeds_mph_sorted, kappa_sorted, marker='x', linestyle='--', color=color2, label='Curvature')
    ax2.tick_params(axis='y', labelcolor=color2)
    # Optional: Invert curvature axis if desired, as low curvature = high speed
    # ax2.invert_yaxis()
    # Optional: Set limits for curvature axis if needed
    ax2.set_ylim(bottom=0)


    # Add title
    plt.title('VTSC (LOCAL FUNCTION): Target Speed vs. Base Lat Accel & Curvature')

    # Add legends
    # fig.legend(loc="upper right", bbox_to_anchor=(1,1), bbox_transform=ax1.transAxes) # Alternative legend placement
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='center right')


    plt.show()
else:
    print("Cannot generate plot, no data points.")

print("Script finished.")