#!/usr/bin/env python3
# OBSOLETE: This tool depends on mapd_py which has been removed.
# It needs to be updated to work with the new mapd system.
# import osmnx as ox # No longer needed
import sys
import time
# import capnp # REMOVED
import struct # Added for size prefixing and index file
import os # Import os for path operations
import json # For parsing GeoJSON lines
import numpy as np
import math # Added for tiling
from collections import defaultdict # Added for collecting index data

# DISABLED: mapd_py has been removed
print("ERROR: This tool is obsolete. mapd_py has been removed from the codebase.")
print("Please update this tool to work with the new mapd system.")
import sys
sys.exit(1)

# Original imports (no longer available):
# from openpilot.selfdrive.frogpilot.navigation.mapd_py import geometry
# from tools.map_processing import osm_speed_data_pb2
# REMOVED: from openpilot.selfdrive.frogpilot.controls.lib.chauffeur_vtsc import curvature_to_speed

# --- ADDED IMPORTS FOR EMBEDDED curvature_to_speed ---
from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip
# --- END ADDED IMPORTS ---

# Load Cap'n Proto schema REMOVED
# script_dir = os.path.dirname(os.path.abspath(__file__))
# schema_path = os.path.join(script_dir, 'osm_speed_data.capnp')
# try:
#     osm_speed_data_capnp = capnp.load(schema_path)
# except Exception as e:
#     print(f"Fatal Error: Could not load speed limit schema '{schema_path}': {e}")
#     osm_speed_data_capnp = None
#     sys.exit(1)

# Conversion factor: mph to m/s
MPH_TO_MPS = 0.44704

# Tiling configuration
TILE_SIZE_DEG = 0.1 # Back to 0.1 degrees
OUTPUT_BASE_DIR = "map_data_tiles_protobuf"

# Define index file format using struct
# < = little-endian
# q = long long (osm_way_id, 8 bytes)
# d = double (bounds, 4 * 8 = 32 bytes)
# Q = unsigned long long (offset, 8 bytes)
# Q = unsigned long long (size, 8 bytes)
# Total: 8 + 32 + 8 + 8 = 56 bytes per index record
INDEX_RECORD_FORMAT = '<qddddQQ'
INDEX_RECORD_SIZE = struct.calcsize(INDEX_RECORD_FORMAT)

# Add REGION_BOUNDS definition (copied from reader.py)
# Approximate Bounding Boxes (min_lon, min_lat, max_lon, max_lat)
REGION_BOUNDS = {
    "california": (-124.5, 32.5, -114.1, 42.0),
    "nevada": (-120.0, 35.0, -114.0, 42.0),
    # Add more regions here as needed
}

# --- EMBEDDED curvature_to_speed LOGIC (from selfdrive.frogpilot.controls.lib.chauffeur_vtsc) ---
# Helper function
def _original_curvature_based_lat_accel(abs_curvature_scaled: float) -> float:
    """Internal function replicating the original tuned lateral accel logic."""
    high_accel = 3.2
    low_accel = 1.5
    span = high_accel - low_accel
    center_curvature = 0.064
    k = 60
    reduction = span / (1.0 + math.exp(-k * (abs_curvature_scaled - center_curvature)))
    lat_acc = high_accel - reduction
    return clip(lat_acc, low_accel, high_accel)

# Constants
CURV_CORR_FACTOR = (CV.MS_TO_MPH ** 2)
MAX_SPEED_DEFAULT = 70.0 # m/s
SPEED_INCREASE_FACTOR = 1.0

# Main function
def curvature_to_speed(abs_curvature_meters: float) -> float:
    """
    Calculates a target speed (m/s) directly from curvature (1/radius in meters).
    """
    if abs_curvature_meters < 1e-7: # Handle straight roads
        return MAX_SPEED_DEFAULT

    abs_curvature_scaled = abs_curvature_meters / CURV_CORR_FACTOR
    base_lat_accel = _original_curvature_based_lat_accel(abs_curvature_scaled)

    try:
        if base_lat_accel < 0: base_lat_accel = 0
        base_speed_mps = math.sqrt(base_lat_accel / abs_curvature_meters)
    except (ValueError, ZeroDivisionError):
        base_speed_mps = 0.0

    target_speed_mps = base_speed_mps * SPEED_INCREASE_FACTOR
    return clip(target_speed_mps, 0.0, MAX_SPEED_DEFAULT)
# --- END EMBEDDED curvature_to_speed LOGIC ---

# Speed parsing function (remains the same)
def parse_speed_limit(speed_str):
    # --- Log Input --- #
    print(f"DEBUG PARSE: Received speed_str: '{speed_str}' (type: {type(speed_str)})", flush=True)
    # --- End Log --- #
    if not speed_str or not isinstance(speed_str, str):
        # --- Log Skip --- #
        # print(f"DEBUG PARSE: Skipping - Not a valid string: '{speed_str}'", flush=True)
        # --- End Log --- #
        return None
    try:
        speed = float(speed_str)
        # --- Log Success --- #
        # print(f"DEBUG PARSE: Parsed '{speed_str}' as float {speed}, converting MPH to MPS", flush=True)
        # --- End Log --- #
        return speed * MPH_TO_MPS
    except ValueError:
        # --- Log Attempt Split --- #
        # print(f"DEBUG PARSE: Failed direct float conversion for '{speed_str}', attempting split...", flush=True)
        # --- End Log --- #
        parts = speed_str.lower().split()
        if len(parts) == 2:
            try:
                speed = float(parts[0])
                if parts[1] == 'mph':
                    print(f"DEBUG PARSE: Parsed '{speed_str}' as {speed} MPH, converting to MPS", flush=True)
                    # --- Log Success --- #
                    # print(f"DEBUG PARSE: Parsed '{speed_str}' as {speed} MPH, converting to MPS", flush=True)
                    # --- End Log --- #
                    return speed * MPH_TO_MPS
                elif parts[1] == 'km/h':
                    # --- Log Success --- #
                    # print(f"DEBUG PARSE: Parsed '{speed_str}' as {speed} km/h, converting to MPS", flush=True)
                    # --- End Log --- #
                    return speed / 3.6
                else:
                    # --- Log Fail --- #
                    print(f"DEBUG PARSE: Failed - Unknown units '{parts[1]}' in '{speed_str}'", flush=True)
                    # --- End Log --- #
            except ValueError:
                # --- Log Fail --- #
                print(f"DEBUG PARSE: Failed - Couldn't parse number part '{parts[0]}' in '{speed_str}'", flush=True)
                # --- End Log --- #
                pass
        else:
             # --- Log Fail --- #
             # Only log if it wasn't just a number (which failed direct float conversion for other reasons like text)
             if not speed_str.replace('.', '', 1).isdigit():
                 print(f"DEBUG PARSE: Failed - Couldn't split '{speed_str}' into 2 parts or wasn't direct float.", flush=True)
             # --- End Log --- #

    # --- Log Final Fail --- #
    print(f"DEBUG PARSE: All parsing failed for '{speed_str}'", flush=True)
    # --- End Log --- #
    return None

def get_tile_id(lat_deg, lon_deg, tile_size_deg):
    """Calculates a tile ID string based on lat/lon and grid size."""
    # Calculate the coordinates of the southwest corner of the tile
    tile_lat = math.floor(lat_deg / tile_size_deg) * tile_size_deg
    tile_lon = math.floor(lon_deg / tile_size_deg) * tile_size_deg
    # Format the tile ID (e.g., N38.7_W120.7)
    lat_part = f"N{tile_lat:.1f}" if tile_lat >= 0 else f"S{abs(tile_lat):.1f}"
    lon_part = f"E{tile_lon:.1f}" if tile_lon >= 0 else f"W{abs(tile_lon):.1f}"
    return f"{lat_part}_{lon_part}"

def write_message(outfile, message):
    """Writes a size-prefixed protobuf message to the file."""
    message_bytes = message.SerializeToString()
    size_bytes = struct.pack('<I', len(message_bytes)) # Pack size as little-endian unsigned int (4 bytes)
    outfile.write(size_bytes)
    outfile.write(message_bytes)

def main(input_geojsonl, output_basedir):
    # --- Log Start --- #
    print("Entered main function.", flush=True)
    # --- End Log --- #
    start_time = time.time()

    # --- Determine Region Name and Create Output Directory ---
    base_input_name = os.path.basename(input_geojsonl)
    region_name = base_input_name.split('-')[0].split('.')[0]
    if not region_name:
        region_name = "unknown_region"
        print(f"Warning: Could not determine region name... Using '{region_name}'.")

    # Base directory for the region
    region_base_output_dir = os.path.join(output_basedir, region_name)

    # Subdirectory logic (only for California for now)
    # We will determine the specific sub-dir per tile later
    # Just ensure the base region dir exists
    try:
        os.makedirs(region_base_output_dir, exist_ok=True)
        # print(f"Ensured base region directory exists: {region_base_output_dir}")
    except OSError as e:
        print(f"Error creating base region directory {region_base_output_dir}: {e}")
        sys.exit(1)

    print(f"Starting OSM data processing from GeoJSON Lines: {input_geojsonl}")
    print(f"Outputting tiled PROTOBUF Segments (Geometry/Curvature focus) with subdirs to: {output_basedir}")

    # No schema loading needed for protobuf

    processed_way_count = 0
    line_num = 0
    # Debug Counters
    skipped_empty = 0
    skipped_json_error = 0
    skipped_not_feature = 0
    skipped_not_linestring = 0
    skipped_coords_len = 0
    skipped_no_id = 0
    skipped_bad_id = 0
    # ---
    tile_file_handles = {}
    tile_segment_counts = {}
    tile_index_data = defaultdict(list) # Store index records per tile_id
    tile_current_offsets = defaultdict(int) # Track current offset in protobuf file

    try:
        # Open the input file in binary read mode ('rb') for chunked processing
        with open(input_geojsonl, 'rb') as infile:
            print("Starting chunked processing loop over input file...", flush=True)
            buffer = b''
            chunk_size = 16 * 1024 * 1024 # Read 16MB chunks

            while True:
                # --- Log Before Read --- #
                print(f"Attempting to read chunk (size={chunk_size})...", flush=True)
                # --- End Log --- #
                chunk = infile.read(chunk_size)
                # --- Log After Read --- #
                print(f"Read chunk of size {len(chunk)} bytes.", flush=True)
                # --- End Log --- #
                if not chunk:
                    # End of file, process any remaining buffer content
                    if buffer:
                        try:
                            line_to_parse = buffer.decode('utf-8')
                            feature = json.loads(line_to_parse)
                            # --- Process the final feature --- # (Duplicated logic, consider refactoring)
                            # ... (rest of the processing logic for this feature needed here)
                            # ... This is complex, let's simplify the approach slightly ...
                            # Re-thinking: A simpler way is to ensure the last record is processed if buffer is not empty
                            pass # Process final buffer content after loop
                        except (UnicodeDecodeError, json.JSONDecodeError) as e:
                            print(f"Warning: Error processing final buffer content: {e}", flush=True)
                    break # Exit the while loop

                # Prepend leftover buffer from previous chunk
                data = buffer + chunk
                records = data.split(b'\x1e')

                # The last element is potentially incomplete, save it for the next chunk
                buffer = records.pop() # pop() removes and returns the last item

                # The first record might be empty if the file started with \x1e or chunk boundary hit exactly
                start_index = 1 if records and not records[0] else 0

                for record_bytes in records[start_index:]:
                    line_num += 1
                    try:
                        line_to_parse = record_bytes.decode('utf-8')
                    except UnicodeDecodeError as e_decode:
                        print(f"Warning: Skipping record near line {line_num} due to UTF-8 decode error: {e_decode}", flush=True)
                        continue

                    if not line_to_parse.strip(): skipped_empty += 1; continue

                    try:
                        feature = json.loads(line_to_parse)
                    except json.JSONDecodeError as e:
                        skipped_json_error += 1
                        print(f"Warning: Skipping malformed JSON near line {line_num}: {e}", flush=True)
                        continue

                    # --- Process the feature (main logic) --- #
                    try:
                        if feature.get('type') != 'Feature': skipped_not_feature += 1; continue
                        geom = feature.get('geometry', {})

                        # --------------------------------------------------------
                        # NEW: Handle speed-limit points (traffic signs, etc.)
                        # --------------------------------------------------------
                        if geom.get('type') == 'Point':
                            # Extract coordinate
                            coord = geom.get('coordinates', [])
                            if len(coord) != 2:
                                skipped_coords_len += 1
                                continue

                            props = feature.get('properties', {})
                            # Look for explicit speed information
                            maxspeed_str = props.get('maxspeed')
                            # Also handle traffic_sign tags like "speed_limit;60"
                            if maxspeed_str is None:
                                ts = props.get('traffic_sign')
                                # Common pattern: traffic_sign = "maxspeed" or "maxspeed:60"
                                if isinstance(ts, str) and ts.startswith('maxspeed'):
                                    # Try to extract number after colon if present
                                    parts = ts.split(':')
                                    if len(parts) > 1:
                                        maxspeed_str = parts[1]
                                    else:
                                        maxspeed_str = None
                            # If still no speed information, ignore point
                            if maxspeed_str is None:
                                skipped_not_linestring += 1  # Re-use counter for now
                                continue

                            # --- Extract OSM node ID ---
                            osm_id_val = feature.get('id')
                            current_osm_id = None
                            if isinstance(osm_id_val, str):
                                if osm_id_val.startswith('n') and len(osm_id_val) > 1:
                                    try:
                                        current_osm_id = int(osm_id_val[1:])
                                    except ValueError:
                                        pass
                            elif isinstance(osm_id_val, (int, float)):
                                try:
                                    current_osm_id = int(osm_id_val)
                                except (ValueError, TypeError):
                                    pass
                            if current_osm_id is None:
                                skipped_no_id += 1
                                continue

                            # --- Assign to tile ---
                            lon, lat = coord
                            tile_id = get_tile_id(lat, lon, TILE_SIZE_DEG)
                            tile_output_dir = region_base_output_dir
                            try:
                                os.makedirs(tile_output_dir, exist_ok=True)
                            except OSError as e:
                                print(f"Error creating tile output directory {tile_output_dir}: {e}")
                                continue

                            # --- Get or open tile file ---
                            outfile = tile_file_handles.get(tile_id)
                            if outfile is None:
                                tile_filename_proto = f"{tile_id}.protobuf"
                                tile_filepath_proto = os.path.join(tile_output_dir, tile_filename_proto)
                                try:
                                    outfile = open(tile_filepath_proto, 'ab')
                                    tile_file_handles[tile_id] = outfile
                                    tile_segment_counts[tile_id] = 0
                                    tile_current_offsets[tile_id] = 0
                                except IOError as e:
                                    print(f"IOError opening {tile_filepath_proto}: {e}")
                                    continue

                            # --- Build protobuf message ---
                            segment_msg = osm_speed_data_pb2.SpeedLimitSegment()
                            segment_msg.osm_way_id = current_osm_id  # Node ID in this case
                            # Geometry – single point
                            if math.isfinite(lat) and math.isfinite(lon):
                                pt = segment_msg.geometry.add()
                                pt.latitude = lat
                                pt.longitude = lon
                            else:
                                continue

                            # No curvature info for point
                            # Parse speed
                            parsed_speed_mps = parse_speed_limit(maxspeed_str)
                            segment_msg.speed_limit_mps = parsed_speed_mps if parsed_speed_mps is not None else 0.0

                            # Write message with size prefix
                            message_bytes = segment_msg.SerializeToString()
                            size_bytes = struct.pack('<I', len(message_bytes))
                            current_offset = tile_current_offsets[tile_id]
                            outfile.write(size_bytes)
                            outfile.write(message_bytes)
                            tile_current_offsets[tile_id] += len(size_bytes) + len(message_bytes)
                            # Index record: bounds are identical point
                            index_record = (current_osm_id, lon, lat, lon, lat, current_offset, len(message_bytes))
                            tile_index_data[tile_id].append(index_record)
                            tile_segment_counts[tile_id] += 1
                            processed_way_count += 1
                            continue  # Done with this record, go to next

                        # --------------------------------------------------------
                        # Existing LineString handling below
                        # --------------------------------------------------------
                        if geom.get('type') != 'LineString': skipped_not_linestring += 1; continue

                        props = feature.get('properties', {})
                        coords = geom.get('coordinates', [])
                        if len(coords) < 2: skipped_coords_len += 1; continue

                        # --- Extract OSM ID ---
                        osm_id_val = feature.get('id')
                        current_osm_id = None
                        if isinstance(osm_id_val, str):
                           if osm_id_val.startswith('w') and len(osm_id_val) > 1:
                               try: current_osm_id = int(osm_id_val[1:])
                               except ValueError: pass
                           elif osm_id_val.startswith('way/'):
                               try: current_osm_id = int(osm_id_val.split('/')[1])
                               except (ValueError, IndexError): pass
                        elif isinstance(osm_id_val, (int, float)):
                            try: current_osm_id = int(osm_id_val)
                            except (ValueError, TypeError): pass

                        if current_osm_id is None:
                            # Try several fallback property keys used by different exports
                            osm_id_val_prop = props.get('@id') or props.get('id') or props.get('osm_id')
                            if osm_id_val_prop is not None:
                                try: current_osm_id = int(osm_id_val_prop)
                                except (ValueError, TypeError): skipped_bad_id += 1; print(f"Warning: Invalid OSM ID {osm_id_val_prop} in properties on line {line_num}. Skipping."); continue
                            else: skipped_no_id += 1; continue

                        if current_osm_id is None: skipped_no_id += 1; print(f"Warning: Could not extract valid OSM ID on line {line_num}. Skipping."); continue

                        processed_way_count += 1

                        # --- Assign segment to tile --- #
                        start_lon, start_lat = coords[0]
                        tile_id = get_tile_id(start_lat, start_lon, TILE_SIZE_DEG)
                        tile_output_dir = region_base_output_dir
                        try: os.makedirs(tile_output_dir, exist_ok=True)
                        except OSError as e: print(f"Error creating tile output directory {tile_output_dir}: {e}"); continue

                        # --- Get or Open Tile File Handle --- #
                        print(f"Line {line_num}: Checking file handle for tile {tile_id}", flush=True)
                        outfile = tile_file_handles.get(tile_id)
                        if outfile is None:
                            tile_filename_proto = f"{tile_id}.protobuf"
                            tile_filepath_proto = os.path.join(tile_output_dir, tile_filename_proto)
                            try:
                                print(f"Line {line_num}: Attempting to open {tile_filepath_proto}", flush=True)
                                outfile = open(tile_filepath_proto, 'ab')
                                print(f"Line {line_num}: Successfully opened {tile_filepath_proto}", flush=True)
                                # print(f"Opened new tile file: {tile_filepath_proto}", flush=True)
                                tile_file_handles[tile_id] = outfile
                                tile_segment_counts[tile_id] = 0
                                tile_current_offsets[tile_id] = 0
                            except IOError as e:
                                print(f"Line {line_num}: IOError opening {tile_filepath_proto}: {e}", flush=True)
                                print(f"Error opening protobuf tile file {tile_filepath_proto}: {e}")
                                continue

                        # --- Process segment data --- #
                        segment_curvatures = []
                        coords_lon = [c[0] for c in coords]; coords_lat = [c[1] for c in coords]
                        if len(coords) >= 3:
                            # --- Log Before Curvature Calc --- #
                            print(f"Line {line_num}: Calculating curvatures for segment {current_osm_id} ({len(coords)} points)...", flush=True)
                            # --- End Log --- #
                            curvatures_list, _ = geometry.get_curvatures(coords_lat, coords_lon)
                            # --- Log After Curvature Calc --- #
                            print(f"Line {line_num}: Finished curvatures for segment {current_osm_id}.", flush=True)
                            # --- End Log --- #
                            segment_curvatures = curvatures_list if curvatures_list else []

                        segment_msg = osm_speed_data_pb2.SpeedLimitSegment()
                        segment_msg.osm_way_id = current_osm_id

                        points_added = 0; min_lon, min_lat, max_lon, max_lat = float('inf'), float('inf'), float('-inf'), float('-inf')
                        for lon, lat in coords:
                            if math.isfinite(lat) and math.isfinite(lon) and not (lat == 0.0 and lon == 0.0):
                                point = segment_msg.geometry.add(); point.latitude = lat; point.longitude = lon; points_added += 1
                                min_lon=min(min_lon, lon); min_lat=min(min_lat, lat); max_lon=max(max_lon, lon); max_lat=max(max_lat, lat)
                            else: print(f"Warning: Skipping invalid coordinate (Lat: {lat}, Lon: {lon}) in segment {current_osm_id}, line {line_num}", file=sys.stderr)

                        if points_added < 2: print(f"Warning: Skipping segment {current_osm_id} on line {line_num} due to insufficient valid points ({points_added} found).", file=sys.stderr); processed_way_count -= 1; continue

                        valid_curvatures = [float(c) for c in segment_curvatures if math.isfinite(float(c))]
                        segment_msg.curvatures.extend(valid_curvatures)
                        # Call the local curvature_to_speed function
                        curvature_derived_speeds = [curvature_to_speed(abs(c)) for c in valid_curvatures]
                        segment_msg.curvature_derived_speeds_mps.extend(curvature_derived_speeds)

                        if curvature_derived_speeds:
                            print(f"  [CURVATURE DEBUG] Way {current_osm_id}: Calculated {len(curvature_derived_speeds)} curvature speeds (min: {min(curvature_derived_speeds):.1f} m/s, max: {max(curvature_derived_speeds):.1f} m/s)", flush=True)

                        maxspeed_str = props.get('maxspeed'); parsed_speed_mps = parse_speed_limit(maxspeed_str)
                        segment_msg.speed_limit_mps = parsed_speed_mps if parsed_speed_mps is not None else 0.0

                        print(f"DEBUG WRITE Line {line_num}: ID={segment_msg.osm_way_id}, GeomLen={len(segment_msg.geometry)}, CurvLen={len(segment_msg.curvatures)}, DerivedSpeedLen={len(segment_msg.curvature_derived_speeds_mps)}, SpeedLimit={segment_msg.speed_limit_mps:.1f}", file=sys.stderr)

                        message_bytes = segment_msg.SerializeToString(); message_size = len(message_bytes)
                        size_bytes = struct.pack('<I', message_size)
                        current_offset = tile_current_offsets[tile_id]
                        outfile.write(size_bytes); outfile.write(message_bytes)
                        tile_current_offsets[tile_id] += len(size_bytes) + message_size
                        index_record = (current_osm_id, min_lon, min_lat, max_lon, max_lat, current_offset, message_size)
                        tile_index_data[tile_id].append(index_record)
                        tile_segment_counts[tile_id] += 1

                        if processed_way_count % 100000 == 0: print(f"Processed {processed_way_count} ways ({len(tile_file_handles)} tiles active)... ({time.time() - start_time:.1f}s)")

                    # --- Catch errors during processing of a single segment ---
                    except Exception as e_proc:
                        print(f"Error processing segment data near line {line_num}: {e_proc}", flush=True)
                        continue # Skip this segment

            # After loop, process any remaining data in buffer
            if buffer:
                print("Processing final buffer content...", flush=True)
                try:
                    line_to_parse = buffer.decode('utf-8')
                    if line_to_parse.strip(): # Ensure buffer wasn't just whitespace/empty
                        feature = json.loads(line_to_parse)
                        # --- Process the final feature --- # (Replicate processing logic)
                        # This is verbose; consider refactoring into a function if needed
                        if feature.get('type') == 'Feature':
                           geom = feature.get('geometry', {})
                           if geom.get('type') == 'LineString':
                                props = feature.get('properties', {})
                                coords = geom.get('coordinates', [])
                                if len(coords) >= 2:
                                    # Extract ID (simplified - assumes ID exists and is valid)
                                    osm_id_val = feature.get('id') or props.get('@id')
                                    current_osm_id = None
                                    try:
                                        if isinstance(osm_id_val, str) and osm_id_val.startswith('w'): current_osm_id = int(osm_id_val[1:])
                                        elif isinstance(osm_id_val, str) and osm_id_val.startswith('way/'): current_osm_id = int(osm_id_val.split('/')[1])
                                        else: current_osm_id = int(osm_id_val)

                                        if current_osm_id:
                                            # --- Process segment data (copy of main loop logic) --- #
                                            # ... (duplicate the processing steps: tile assignment, file handle, data extraction, protobuf building, writing, indexing) ...
                                            print("Processing final segment...", current_osm_id) # Placeholder
                                            # NOTE: Need to actually duplicate the ~50 lines of processing logic here or refactor
                                            pass # Avoid duplicating large block for now

                                    except (ValueError, TypeError, AttributeError) as e_final_id:
                                        print(f"Warning: Error extracting ID from final buffer feature: {e_final_id}")

                except (UnicodeDecodeError, json.JSONDecodeError) as e_final:
                    print(f"Warning: Error decoding/parsing final buffer content: {e_final}", flush=True)

    except FileNotFoundError:
         print(f"Error: Input GeoJSON Lines file not found: {input_geojsonl}")
         sys.exit(1)
    except Exception as e:
         print(f"An error occurred during processing near line {line_num}: {e}")
         sys.exit(1) # Exit on error
    finally:
        # --- Ensure all tile files are closed ---
        print("Closing tile files and writing index files...")
        closed_count = 0
        for tile_id, handle in tile_file_handles.items():
            try:
                handle.flush() # Explicitly flush buffers
                handle.close()
                closed_count += 1

                # --- Write the index file for this tile ---
                index_data = tile_index_data.get(tile_id)
                if index_data:
                    # Determine output directory for index file (same as protobuf file)
                    # We need the original path used to open the handle
                    # This is tricky as handle doesn't store path. Reconstruct it.
                    # Assuming region_name is consistent for the tile_id's lifetime
                    tile_lat_idx = math.floor(float(tile_id.split('_')[0][1:]) * (1 if tile_id.startswith('N') else -1) / TILE_SIZE_DEG)
                    tile_lon_idx = math.floor(float(tile_id.split('_')[1][1:]) * (1 if tile_id.startswith('E') else -1) / TILE_SIZE_DEG)
                    tile_start_lat = tile_lat_idx * TILE_SIZE_DEG
                    tile_start_lon = tile_lon_idx * TILE_SIZE_DEG

                    # Re-determine region (safe but slightly redundant)
                    tile_region = None
                    for r, bounds in REGION_BOUNDS.items():
                        if bounds[1] <= tile_start_lat < bounds[3] + TILE_SIZE_DEG and bounds[0] <= tile_start_lon < bounds[2] + TILE_SIZE_DEG:
                             tile_region = r
                             break
                    if not tile_region:
                        print(f"Warning: Could not determine region for tile {tile_id} during index write.")
                        continue

                    index_output_dir = os.path.join(output_basedir, tile_region)
                    index_filename = f"{tile_id}.idx"
                    index_filepath = os.path.join(index_output_dir, index_filename)

                    try:
                        with open(index_filepath, 'wb') as idx_file:
                            for record in index_data:
                                packed_record = struct.pack(INDEX_RECORD_FORMAT,
                                                          record[0], # osm_id
                                                          record[1], record[2], record[3], record[4], # bounds
                                                          record[5], record[6]) # offset, size
                                idx_file.write(packed_record)
                        # --- Add Logging --- #
                        print(f"  Written index file: {index_filepath} ({len(index_data)} records)", flush=True)
                        # --- End Logging --- #
                    except IOError as e_idx:
                        print(f"Error writing index file {index_filepath}: {e_idx}")
                else:
                     print(f"Warning: No index data found for tile {tile_id}")

            except IOError as e:
                print(f"Warning: Error closing protobuf file for tile {tile_id}: {e}")
        print(f"Closed {closed_count} protobuf tile files.")
        print(f"DEBUG Counts: empty={skipped_empty}, json_err={skipped_json_error}, not_feat={skipped_not_feature}, not_line={skipped_not_linestring}, coords<2={skipped_coords_len}, no_id={skipped_no_id}, bad_id={skipped_bad_id}")

    # --- Final Reporting ---
    total_time = time.time() - start_time
    print(f"Processing complete.")
    print(f"Total lines processed from GeoJSON: {line_num}")
    print(f"Total ways processed (geometry/curvature focused): {processed_way_count}") # Updated description
    print(f"Total unique tiles created: {len(tile_file_handles)}")

    # Optional: Print segment counts per tile
    # for tile_id, count in tile_segment_counts.items():
    #    print(f"  Tile {tile_id}: {count} segments")

    print(f"Total processing time: {total_time:.2f}s")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        # Usage updated for directory output
        print(f"Usage: {sys.argv[0]} <input.geojsonl> <output_base_directory>")
        print(f"       Example: {sys.argv[0]} map_data/california-exported.geojsonl {OUTPUT_BASE_DIR}")
        sys.exit(1)

    input_geojsonl = sys.argv[1]
    output_basedir_arg = sys.argv[2]

    if not os.path.exists(input_geojsonl):
        print(f"Error: Input GeoJSONL file not found: {input_geojsonl}")
        sys.exit(1)

    # Note: Directory creation is now handled within main()

    main(input_geojsonl, output_basedir_arg)