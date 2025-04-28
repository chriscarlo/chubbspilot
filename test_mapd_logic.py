#!/usr/bin/env python3
import csv
import os
import sys
import math
from shapely.geometry import Point
import time # Added for polling wait

# --- Configuration ---
INPUT_CSV_PATH = "/home/chris/openpilot/rlogs/parsed_logs/extracted_gps_data.csv"
# We will override the TILE_DATA_BASE_DIR *after* importing the reader module
TARGET_MAP_DATA_DIR = "/home/chris/openpilot/map_data_tiles_protobuf"
TARGET_REGION = "california" # Force the region for tile path calculation
MAX_RELEVANT_DISTANCE_DEGREES = 0.0015 # Max distance for matching segment (from mapd_daemon)
MPH_CONVERSION = 2.23694
# --- End Configuration ---

# --- Add openpilot root to path for imports ---
# Assuming this script is in /home/chris/openpilot
OP_ROOT = os.path.dirname(os.path.abspath(__file__))
if OP_ROOT not in sys.path:
    print(f"Adding {OP_ROOT} to sys.path")
    sys.path.append(OP_ROOT)
# ----------------------------------------------

try:
    # Import mapd_py components AFTER potentially adding to path
    from selfdrive.frogpilot.navigation.mapd_py import reader as map_reader_module
    from selfdrive.frogpilot.navigation.mapd_py import matcher
except ImportError as e:
    print(f"Error importing mapd_py modules: {e}")
    print("Make sure you are running this script from the openpilot root directory")
    print(f"or that {OP_ROOT} is correctly added to your PYTHONPATH.")
    sys.exit(1)

def main():
    print("--- Mapd Logic Test Script ---")
    print(f"Input GPS Data: {INPUT_CSV_PATH}")
    print(f"Target Map Data Dir: {TARGET_MAP_DATA_DIR}")
    print(f"Target Region: {TARGET_REGION}")

    if not os.path.exists(INPUT_CSV_PATH):
        print(f"Error: Input CSV file not found: {INPUT_CSV_PATH}")
        sys.exit(1)

    # --- Monkey-patch the MapReader's tile directory ---
    print(f"Overriding MapReader's TILE_DATA_BASE_DIR to: {TARGET_MAP_DATA_DIR}")
    # This assumes TILE_DATA_BASE_DIR is checked dynamically or can be overridden.
    # If it's determined strictly at import time based on /data/..., this might need adjustment.
    # Let's try setting it on the module level AND the instance level if needed.
    map_reader_module.TILE_DATA_BASE_DIR = TARGET_MAP_DATA_DIR
    # ----------------------------------------------------

    # --- Initialize MapReader ---
    print("Initializing MapReader...")
    try:
        map_reader = map_reader_module.MapReader()
        # Explicitly set the region and override base dir again just in case
        map_reader.current_region = TARGET_REGION
        # We might need to override the internal path construction logic more directly if needed
        # For now, relying on setting the module's variable.
        print(f"MapReader Initialized. Cache Size: {map_reader.cache_size}")
        print(f"MapReader Using Tile Base Dir: {map_reader_module.TILE_DATA_BASE_DIR}") # Verify override
    except Exception as e:
        print(f"Error initializing MapReader: {e}")
        sys.exit(1)
    # --------------------------

    print("Processing GPS points...")
    row_count = 0
    found_count = 0

    try:
        with open(INPUT_CSV_PATH, 'r', newline='') as infile:
            reader = csv.reader(infile)
            header = next(reader) # Skip header

            # Find column indices (assuming standard output from previous script)
            try:
                 ts_idx = header.index('timestamp')
                 lat_idx = header.index('latitude')
                 lon_idx = header.index('longitude')
                 brg_idx = header.index('bearing_rad')
            except ValueError as e:
                 print(f"Error: Missing expected column in {INPUT_CSV_PATH}: {e}")
                 sys.exit(1)


            for i, row in enumerate(reader):
                row_count += 1
                start_poll_time = time.monotonic()
                last_poll_print_time = start_poll_time
                MAX_POLL_DURATION_S = 15.0 # Max time to wait for data for one point
                POLL_INTERVAL_S = 0.5
                found_in_poll = False

                try:
                    timestamp = float(row[ts_idx])
                    latitude = float(row[lat_idx])
                    longitude = float(row[lon_idx])
                    bearing_rad = float(row[brg_idx])

                    # Create Position object
                    pos = matcher.Position(latitude=latitude, longitude=longitude, bearing_rad=bearing_rad)

                    # 1. Update loaded tiles (queue tiles for background loading)
                    map_reader._update_loaded_tiles(latitude, longitude)

                    # --- Polling Loop --- Wait for data to appear in R-tree
                    while time.monotonic() - start_poll_time < MAX_POLL_DURATION_S:
                        segment_data = None
                        current_segment_id = None
                        on_way_result = None
                        is_on_segment = False
                        speed_limit_mps = 0.0
                        speed_limit_mph = 0.0
                        candidates_found_this_poll = False

                        # 2. Query R-tree (Under Lock)
                        search_bounds = (longitude - 1e-4, latitude - 1e-4, longitude + 1e-4, latitude + 1e-4)
                        nearest_candidates = [] # Default to empty
                        closest_segment_info = None
                        min_dist = float('inf')
                        closest_candidate_id = None
                        current_point = Point(longitude, latitude)

                        with map_reader.loading_lock:
                            try:
                                nearest_candidates = list(map_reader.rtree_idx.intersection(search_bounds, objects=True))
                                if nearest_candidates:
                                    candidates_found_this_poll = True
                                    # Process candidates to find closest geometric match (still under lock)
                                    for item in nearest_candidates:
                                        segment_id_candidate = item.object
                                        segment_info = map_reader.segments_data.get(segment_id_candidate)
                                        if segment_info:
                                            try:
                                                distance = segment_info['geom'].distance(current_point)
                                                if distance < min_dist and distance < MAX_RELEVANT_DISTANCE_DEGREES:
                                                    min_dist = distance
                                                    closest_segment_info = segment_info
                                                    closest_candidate_id = segment_id_candidate
                                            except Exception as e_dist:
                                                pass # Ignore dist errors

                                    # Mark the best one found as recently used (under lock)
                                    if closest_segment_info:
                                         closest_id = closest_segment_info.get('id')
                                         if closest_id and closest_id in map_reader.segments_data:
                                              map_reader.segments_data.move_to_end(closest_id)

                            except Exception as e_rtree:
                                 print(f"    Warn: R-tree query error: {e_rtree}")
                                 candidates_found_this_poll = False # Treat error as no candidates

                        # --- Process results (Outside Lock) ---
                        if candidates_found_this_poll and closest_segment_info:
                            segment_data = closest_segment_info # Use the one found under lock
                            # 3. Check if On Way and Get Speed Limit
                            segment_id = segment_data.get('id')
                            if segment_id:
                                on_way_result = matcher.on_way(pos, segment_id, segment_data)
                                if on_way_result.on_way:
                                    is_on_segment = True
                                    current_segment_id = segment_id
                                    speed_limit_mps = segment_data.get('speed_mps', 0.0)
                                    speed_limit_mph = speed_limit_mps * MPH_CONVERSION
                                    found_count += 1
                                    found_in_poll = True # Mark success

                        # --- Report Status and Decide Next Action ---
                        if found_in_poll:
                            elapsed_time = time.monotonic() - start_poll_time
                            status = f"Segment Found (ID: {current_segment_id}, Speed: {speed_limit_mps:.1f} m/s / {speed_limit_mph:.1f} mph, Found after {elapsed_time:.2f}s)"
                            print(f"Time: {timestamp:.2f}, Lat: {latitude:.6f}, Lon: {longitude:.6f}, Bear: {math.degrees(bearing_rad):.1f}° -> {status}")
                            break # Exit the polling loop for this point
                        else:
                            # Check for timeout
                            if time.monotonic() - start_poll_time >= MAX_POLL_DURATION_S:
                                status = f"No Segment Found (Timeout after {MAX_POLL_DURATION_S:.1f}s)"
                                print(f"Time: {timestamp:.2f}, Lat: {latitude:.6f}, Lon: {longitude:.6f}, Bear: {math.degrees(bearing_rad):.1f}° -> {status}")
                                break # Exit polling loop (timeout)

                            # Print waiting message only once per second
                            current_time = time.monotonic()
                            if current_time - last_poll_print_time >= 1.0:
                                print(f"    Polling for point {i+1} (Time: {timestamp:.2f})... elapsed {current_time - start_poll_time:.1f}s (Cache: {len(map_reader.segments_data)}, Queue: {map_reader.load_queue.qsize()}) Rtree candidates this poll: {len(nearest_candidates)}")
                                last_poll_print_time = current_time

                            time.sleep(POLL_INTERVAL_S) # Wait before next poll
                    # --- End Polling Loop ---

                except (ValueError, IndexError) as e:
                    print(f"Warning: Skipping row {i+1} due to error: {e}. Row data: {row}")

    except FileNotFoundError:
        print(f"Error: Input CSV file not found: {INPUT_CSV_PATH}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging
        sys.exit(1)

    print(f"--- Processing Complete ---")
    print(f"Total GPS points processed: {row_count}")
    print(f"Segments with speed limits found: {found_count}")

if __name__ == "__main__":
    main()