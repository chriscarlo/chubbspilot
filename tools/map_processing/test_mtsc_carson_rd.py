#!/usr/bin/env python3
# OBSOLETE: This test depends on mapd_py which has been removed.
# It needs to be updated to work with the new mapd system.
import sys
import os
import time
import json
import math
import numpy as np

# Assume openpilot directory structure for imports
try:
    from common.params import Params
    script_dir = os.path.dirname(os.path.abspath(__file__))
    openpilot_root = script_dir # Assuming script is in the root of the openpilot workspace.
    sys.path.insert(0, openpilot_root)
    # DISABLED: mapd_py has been removed
    print("ERROR: This test is obsolete. mapd_py has been removed from the codebase.")
    print("Please update this test to work with the new mapd system.")
    sys.exit(1)
except ImportError as e:
    print(f"ImportError: {e}")
    print("Make sure you are running this script from a location where")
    print("the necessary openpilot modules can be found (e.g., workspace root)")
    print("Or adjust sys.path accordingly.")
    sys.exit(1)

# --- Simulation Parameters ---
# Mock GPS Coordinates: Carson Rd eastbound towards Placerville, near Camino, CA
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

SIM_VEHICLE_SPEED_MS = 15.0
SIM_TIME_STEP_S = 1.0 # Increased to give MapReader's worker more time per step

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
    bearing = (initial_bearing_deg + 360) % 360
    return bearing

# --- Main Simulation ---
if __name__ == "__main__":
    print("Starting MapReader Direct Test Simulation...")

    try:
        # Instantiate MapReader directly
        map_reader = MapReader()
        print("MapReader initialized.")
        # Give MapReader's worker thread a moment to start up fully if needed
        time.sleep(1.0)
    except Exception as e:
        print(f"Error initializing MapReader: {e}")
        sys.exit(1)

    params_memory = None
    try:
        params_memory = Params("/dev/shm/params")
        print("Acquired params_memory handle.")
    except Exception as e:
        print(f'Could not get Params("/dev/shm/params"): {e}')
        print("This script can run without params for MapReader, but initial region finding might be impaired.")
        # MapReader has fallbacks if params aren't available or GPS isn't there

    print("\n--- Running Simulation Loop (Focus on MapReader) ---")
    last_gps_point = None
    for i, (lat, lon) in enumerate(MOCK_GPS_POINTS_DEG):
        print(f"\nStep {i+1}: Simulating GPS at ({lat:.5f}, {lon:.5f})")

        bearing_deg = 90.0 # Default eastbound
        bearing_rad = math.radians(bearing_deg)
        if last_gps_point is not None:
            bearing_deg = calculate_bearing(last_gps_point[0], last_gps_point[1], lat, lon)
            bearing_rad = math.radians(bearing_deg)
            print(f"  Calculated Bearing: {bearing_deg:.1f} degrees")

        # Mock LastGPSPosition (MapReader might use this for initial region, but also uses current pos)
        if params_memory:
            gps_data = {
                'latitude': lat,
                'longitude': lon,
                'accuracy': 1.0,
                'speed': SIM_VEHICLE_SPEED_MS,
                'bearingDeg': bearing_deg, # Changed from 'bearing' to 'bearingDeg' for consistency with some internal openpilot usage.
                                          # MapReader's _determine_initial_region might not use this field, but good practice.
                'altitude': 1000.0,
                'timestamp': time.time() * 1000
            }
            try:
                params_memory.put("LastGPSPosition", json.dumps(gps_data))
            except Exception as e:
                print(f"  Error writing to Params: {e}")

        # Use MapReader to get segment data (this triggers tile loading)
        try:
            print(f"  Calling map_reader.get_segment_data_at({lat=}, {lon=}, bearing_rad={bearing_rad:.2f})")
            # The call below is the primary action that should trigger tile loading requests
            # and eventually populate map_reader.segments_data via its worker thread.
            closest_segment_info = map_reader.get_segment_data_at(lat, lon, bearing_rad)

            print(f"  MapReader state after get_segment_data_at call:")
            with map_reader.loading_lock: # Access shared data under lock for safety
                print(f"    Loaded Tiles: {list(map_reader.loaded_tiles)}")
                print(f"    Queued/Loading Tiles: {list(map_reader.queued_or_loading)}")
                print(f"    Segments in Cache: {len(map_reader.segments_data)}")
                if map_reader.segments_data:
                    # Print a sample of cached segments to verify data presence
                    sample_count = 0
                    print(f"    Sample of cached segments (first few):")
                    for seg_id, seg_data in map_reader.segments_data.items():
                        print(f"      ID: {seg_id}, SpeedMPS: {seg_data.get('speed_mps', 'N/A')}, Coords: {len(seg_data.get('geom', {}).coords) if hasattr(seg_data.get('geom'), 'coords') else 'N/A'}")
                        sample_count +=1
                        if sample_count >= 3:
                            break
                if closest_segment_info:
                    print(f"    Closest segment found by get_segment_data_at: ID {closest_segment_info.get('id')}")
                else:
                    print(f"    No specific closest segment returned by get_segment_data_at for this point.")

        except Exception as e:
            print(f"  Error during map_reader.get_segment_data_at(): {e}")
            import traceback
            traceback.print_exc()

        last_gps_point = (lat, lon)
        print(f"  Sleeping for {SIM_TIME_STEP_S}s to allow MapReader worker to process...")
        time.sleep(SIM_TIME_STEP_S) # Give worker thread time to load/process

    print("\n--- Simulation Complete ---")
    # Optional: Wait for MapReader's queue to clear to see final logs
    print("Waiting for MapReader queue to empty (max 5s)...")
    try:
        map_reader.load_queue.join()
    except Exception as e: # Older Python queue.join might not have timeout or other issues
        print(f"  Note: map_reader.load_queue.join() failed with {e}. Continuing without join.")
        pass
    print("Final MapReader state:")
    with map_reader.loading_lock:
        print(f"  Loaded Tiles: {list(map_reader.loaded_tiles)}")
        print(f"  Segments in Cache: {len(map_reader.segments_data)}")
    print("Test finished.")