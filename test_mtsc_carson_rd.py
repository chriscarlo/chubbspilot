#!/usr/bin/env python3
import sys
import os
import time
import json
import math
import numpy as np

# Assume openpilot directory structure for imports
try:
    from openpilot.common.params import Params
    # Need to ensure the path allows finding the ChauffeurMtsc class
    # This might require adding the parent directory if running from tools/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    openpilot_root = os.path.abspath(os.path.join(script_dir, "..")) # Assuming script is in root
    # Ensure the selfdrive directory is in the path for ChauffeurMtsc import
    sys.path.insert(0, openpilot_root)
    from selfdrive.frogpilot.controls.lib.chauffeur_mtsc import ChauffeurMtsc
    print("Imports successful.")
except ImportError as e:
    print(f"ImportError: {e}")
    print("Make sure you are running this script from a location where")
    print("the necessary openpilot modules can be found (e.g., workspace root)")
    print("Or adjust sys.path accordingly.")
    sys.exit(1)

# --- Simulation Parameters ---
# Mock GPS Coordinates: Carson Rd eastbound towards Placerville, near Camino, CA
# Obtained manually from Google Maps / OpenStreetMap
MOCK_GPS_POINTS_DEG = [
    (38.7483, -120.7005), # Start further west
    (38.7480, -120.6980),
    (38.7477, -120.6955), # Entering a slight curve section
    (38.7474, -120.6930),
    (38.7471, -120.6905), # Near apex of curve?
    (38.7468, -120.6880),
    (38.7465, -120.6855), # Straightening out
    (38.7462, -120.6830),
]

SIM_VEHICLE_SPEED_MS = 15.0 # approx 33.5 mph
SIM_VEHICLE_ACCEL_MS2 = 0.0
SIM_TIME_STEP_S = 0.5 # Simulate calling update every 500ms

# Dummy toggles object (assuming not critical for this test)
DUMMY_FROGPILOT_TOGGLES = {}

# --- Helper Functions ---
def calculate_bearing(lat1_deg, lon1_deg, lat2_deg, lon2_deg):
    """ Calculates initial bearing in degrees from point 1 to point 2. """
    lat1_rad = math.radians(lat1_deg)
    lon1_rad = math.radians(lon1_deg)
    lat2_rad = math.radians(lat2_deg)
    lon2_rad = math.radians(lon2_deg)

    dlon = lon2_rad - lon1_rad
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)

    initial_bearing_rad = math.atan2(y, x)
    initial_bearing_deg = math.degrees(initial_bearing_rad)

    # Normalize to 0-360
    bearing = (initial_bearing_deg + 360) % 360
    return bearing

# --- Main Simulation ---
if __name__ == "__main__":
    print("Starting Chauffeur MTSC Simulation...")

    # Instantiate the MTSC class
    # It will internally create its own MapReader
    # Ensure MapReader's dynamic loading points to the correct .capnp file
    # (Assumes MapReader paths are set for relative source tree access)
    try:
        mtsc = ChauffeurMtsc()
        print("ChauffeurMtsc initialized.")
        # Give MapReader a moment to potentially load data if it does so async (unlikely but safe)
        time.sleep(1.0)
    except Exception as e:
        print(f"Error initializing ChauffeurMtsc: {e}")
        print("Ensure the MapReader can find the schema and potentially map data.")
        sys.exit(1)

    # Get access to the shared memory params for mocking GPS
    try:
        params_memory = Params("/dev/shm/params")
        print("Acquired params_memory handle.")
    except Exception as e:
        print(f"Could not get Params(\"/dev/shm/params\"): {e}")
        print("This script needs access to the param store used by openpilot processes.")
        print("Attempting to continue, but MTSC may fail to get GPS updates.")
        # Allow simulation to continue, MTSC might fail internally
        # sys.exit(1)


    print("\n--- Running Simulation Loop ---")
    last_gps_point = None
    for i, (lat, lon) in enumerate(MOCK_GPS_POINTS_DEG):
        print(f"\nStep {i+1}: Simulating GPS at ({lat:.5f}, {lon:.5f})")

        # Calculate bearing if we have a previous point
        bearing_deg = 90.0 # Default eastbound
        if last_gps_point is not None:
            bearing_deg = calculate_bearing(last_gps_point[0], last_gps_point[1], lat, lon)
            print(f"  Calculated Bearing: {bearing_deg:.1f} degrees")

        # Mock the LastGPSPosition parameter
        gps_data = {
            'latitude': lat,
            'longitude': lon,
            'accuracy': 1.0,
            'speed': SIM_VEHICLE_SPEED_MS,
            'bearing': bearing_deg,
            'altitude': 1000.0, # Placeholder
            'timestamp': time.time() * 1000 # Milliseconds
        }
        try:
            # Ensure params_memory was successfully acquired before trying to use it
            if 'params_memory' in locals() and params_memory is not None:
              params_memory.put("LastGPSPosition", json.dumps(gps_data))
            # print(f"  Mocked LastGPSPosition: {json.dumps(gps_data)}") # Verbose
            else:
              print("  Skipping Params write: handle not acquired.")
        except Exception as e:
            print(f"  Error writing to Params: {e}")
            # Continue simulation but MTSC might fail internally

        # Call the MTSC update function
        try:
            distance_profile, speed_profile = mtsc.update(
                v_ego=SIM_VEHICLE_SPEED_MS,
                a_ego=SIM_VEHICLE_ACCEL_MS2,
                v_cruise_cluster=SIM_VEHICLE_SPEED_MS,  # Use current speed as cruise for test
                frogpilot_toggles=DUMMY_FROGPILOT_TOGGLES
            )

            # Analyze the results
            print(f"  MTSC Curvature Valid: {mtsc.curvature_valid}")

            if speed_profile is not None and len(speed_profile) > 0:
                print(f"  MTSC Speed Profile (m/s): {np.round(speed_profile, 2)}")
                # Check if profile suggests slowing down from max speed
                if np.any(speed_profile < 69.0): # Check against internal STRAIGHT_SPEED_LIMIT minus a buffer
                    print("  -> Profile indicates potential curve speed adjustment.")
                else:
                    print("  -> Profile seems to be at max speed (straight road?).")
            else:
                print("  MTSC returned empty or None speed profile.")

            # Also print the current MapSpeedLimit it should have published
            # Ensure params_memory was successfully acquired before trying to use it
            if 'params_memory' in locals() and params_memory is not None:
                try:
                    current_limit_mps = params_memory.get_float("MapSpeedLimit")
                    print(f"  Published MapSpeedLimit: {current_limit_mps:.2f} m/s")
                except Exception as e:
                    print(f"  Could not read MapSpeedLimit from Params: {e}")
            else:
                print("  Skipping MapSpeedLimit read: Params handle not acquired.")

        except Exception as e:
            print(f"  Error during mtsc.update(): {e}")

        last_gps_point = (lat, lon)
        time.sleep(SIM_TIME_STEP_S)

    print("\n--- Simulation Complete ---")