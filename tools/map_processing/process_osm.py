#!/usr/bin/env python3
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

# Import our geometry functions
from openpilot.selfdrive.frogpilot.navigation.mapd_py import geometry
# Import generated protobuf classes
from tools.map_processing import osm_speed_data_pb2
# Import the curvature_to_speed function
from openpilot.selfdrive.frogpilot.controls.lib.chauffeur_vtsc import curvature_to_speed

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

# Speed parsing function (remains the same)
def parse_speed_limit(speed_str):
    if not speed_str or not isinstance(speed_str, str):
        return None
    try:
        speed = float(speed_str)
        return speed * MPH_TO_MPS
    except ValueError:
        parts = speed_str.lower().split()
        if len(parts) == 2:
            try:
                speed = float(parts[0])
                if parts[1] == 'mph':
                    return speed * MPH_TO_MPS
                elif parts[1] == 'km/h':
                    return speed / 3.6
            except ValueError:
                pass
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
        with open(input_geojsonl, 'r') as infile:
            for line in infile:
                # if line_num % 100000 == 1: print(f"DEBUG: Reading line {line_num}") # Keep commented for now

                line_num += 1
                if not line.strip(): skipped_empty += 1; continue
                try: feature = json.loads(line)
                except json.JSONDecodeError as e: skipped_json_error += 1; print(f"Warning: Skipping malformed JSON on line {line_num}: {e}"); continue

                # --- Wrap segment processing in a try-except ---
                try:
                    if feature.get('type') != 'Feature': skipped_not_feature += 1; continue
                    geom = feature.get('geometry', {})
                    if geom.get('type') != 'LineString': skipped_not_linestring += 1; continue

                    props = feature.get('properties', {})
                    coords = geom.get('coordinates', [])
                    if len(coords) < 2: skipped_coords_len += 1; continue

                    # --- Extract OSM ID ---
                    # Try top-level 'id' first (common osmium geojson format, e.g., "w12345")
                    # Then fall back to 'properties.@id'
                    osm_id_val = feature.get('id')
                    current_osm_id = None
                    # Handle IDs like "w12345" or "way/12345"
                    if isinstance(osm_id_val, str):
                        if osm_id_val.startswith('w') and len(osm_id_val) > 1:
                            try:
                                current_osm_id = int(osm_id_val[1:]) # Get int part after 'w'
                            except ValueError:
                                pass # Handled below
                        elif osm_id_val.startswith('way/'): # Keep old check just in case
                            try:
                                current_osm_id = int(osm_id_val.split('/')[1])
                            except (ValueError, IndexError):
                                pass # Handled below
                    elif isinstance(osm_id_val, (int, float)): # Sometimes it might be numeric directly
                         try:
                            current_osm_id = int(osm_id_val)
                         except (ValueError, TypeError):
                             pass # Handled below

                    # Fallback to properties if top-level 'id' didn't yield a valid ID
                    if current_osm_id is None:
                        osm_id_val_prop = props.get('@id')
                        if osm_id_val_prop is not None:
                            try:
                                current_osm_id = int(osm_id_val_prop)
                            except (ValueError, TypeError):
                                print(f"Warning: Invalid OSM ID {osm_id_val_prop} in properties on line {line_num}. Skipping.")
                                skipped_bad_id += 1; continue # Skip if prop ID is bad
                        else:
                            # If neither feature['id'] nor props['@id'] provided a usable ID
                            skipped_no_id += 1; continue # Skip if no ID found

                    # Final check if ID extraction failed somehow (should be rare)
                    if current_osm_id is None:
                         print(f"Warning: Could not extract valid OSM ID on line {line_num}. Skipping.")
                         skipped_no_id += 1; continue

                    # --- Process segment if it's a valid LineString with an ID ---
                    processed_way_count += 1

                    # --- Assign segment to tile AND determine sub-directory ---
                    start_lon, start_lat = coords[0]
                    tile_id = get_tile_id(start_lat, start_lon, TILE_SIZE_DEG)

                    # Construct final output directory for the tile
                    tile_output_dir = region_base_output_dir # No subdir for other regions

                    # Ensure the specific tile output directory exists
                    # Creating directories within the loop might be slow, but ensures correctness
                    # Consider optimizing later if it becomes a bottleneck
                    try:
                        os.makedirs(tile_output_dir, exist_ok=True)
                    except OSError as e:
                         print(f"Error creating tile output directory {tile_output_dir}: {e}")
                         continue # Skip segment if dir creation fails

                    # --- Get or Open Tile File Handle (using full path) ---
                    outfile = tile_file_handles.get(tile_id)
                    if outfile is None:
                        tile_filename_proto = f"{tile_id}.protobuf"
                        tile_filepath_proto = os.path.join(tile_output_dir, tile_filename_proto) # Use the determined output dir
                        try:
                            # Use 'ab' for protobuf file
                            outfile = open(tile_filepath_proto, 'ab')
                            tile_file_handles[tile_id] = outfile
                            tile_segment_counts[tile_id] = 0
                            # Initialize offset for new file
                            tile_current_offsets[tile_id] = 0
                        except IOError as e:
                            print(f"Error opening protobuf tile file {tile_filepath_proto}: {e}")
                            continue

                    # DEBUG: Are we reaching the processing point?
                    # print(f"DEBUG: Reached processing point for line {line_num}, OSM ID {current_osm_id}")

                    # --- Process Required Data (ID, Geometry, Curvature) ---
                    segment_curvatures = []
                    coords_lon = [c[0] for c in coords]
                    coords_lat = [c[1] for c in coords]
                    if len(coords) >= 3:
                        curvatures_list, _ = geometry.get_curvatures(coords_lat, coords_lon)
                        segment_curvatures = curvatures_list if curvatures_list else []

                    # --- Build Protobuf Message (Focus on ID, Geometry, Curvature) ---
                    segment_msg = osm_speed_data_pb2.SpeedLimitSegment()
                    segment_msg.osm_way_id = current_osm_id

                    # Populate geometry, skipping non-finite and (0,0) points
                    points_added = 0
                    min_lon, min_lat, max_lon, max_lat = float('inf'), float('inf'), float('-inf'), float('-inf')
                    for lon, lat in coords:
                        # Check for finite *and* non-zero coordinates
                        if math.isfinite(lat) and math.isfinite(lon) and not (lat == 0.0 and lon == 0.0):
                            point = segment_msg.geometry.add()
                            point.latitude = lat
                            point.longitude = lon
                            points_added += 1
                            # Update bounds for index
                            min_lon = min(min_lon, lon)
                            min_lat = min(min_lat, lat)
                            max_lon = max(max_lon, lon)
                            max_lat = max(max_lat, lat)
                        else:
                            # Keep the warning for non-finite, but maybe silence for (0,0)? - Keeping warning for now.
                            print(f"Warning: Skipping invalid coordinate (Lat: {lat}, Lon: {lon}) in segment {current_osm_id}, line {line_num}", file=sys.stderr)

                    # --- Ensure geometry is not empty before proceeding ---
                    if points_added < 2: # Need at least 2 valid points for a line segment
                        print(f"Warning: Skipping segment {current_osm_id} on line {line_num} due to insufficient valid points ({points_added} found).", file=sys.stderr)
                        processed_way_count -= 1 # Decrement because we are skipping after incrementing
                        continue # Skip to next line in geojsonl

                    # Populate curvatures - Ensure they are standard, finite floats
                    valid_curvatures = [float(c) for c in segment_curvatures if math.isfinite(float(c))]
                    segment_msg.curvatures.extend(valid_curvatures)

                    # Calculate curvature-derived speeds using the imported function
                    curvature_derived_speeds = [curvature_to_speed(abs(c)) for c in valid_curvatures]
                    segment_msg.curvature_derived_speeds_mps.extend(curvature_derived_speeds)

                    # Populate speed limit with default value (required by reader)
                    # segment_msg.speed_limit_mps = 0.0 <-- Remove old default

                    # --- Get and Parse Speed Limit ---
                    maxspeed_str = props.get('maxspeed')
                    parsed_speed_mps = parse_speed_limit(maxspeed_str)
                    segment_msg.speed_limit_mps = parsed_speed_mps if parsed_speed_mps is not None else 0.0

                    # --- DEBUG: Print message state before writing ---
                    print(f"DEBUG WRITE Line {line_num}: ID={segment_msg.osm_way_id}, GeomLen={len(segment_msg.geometry)}, CurvLen={len(segment_msg.curvatures)}, DerivedSpeedLen={len(segment_msg.curvature_derived_speeds_mps)}, SpeedLimit={segment_msg.speed_limit_mps:.1f}", file=sys.stderr)

                    # --- Write Size-Prefixed Message to Tile File ---
                    message_bytes = segment_msg.SerializeToString()
                    message_size = len(message_bytes)
                    size_bytes = struct.pack('<I', message_size) # Pack size as little-endian unsigned int (4 bytes)

                    # Store current offset before writing
                    current_offset = tile_current_offsets[tile_id]

                    outfile.write(size_bytes)
                    outfile.write(message_bytes)

                    # Update offset for the next message
                    tile_current_offsets[tile_id] += len(size_bytes) + message_size

                    # Add record to index data for this tile
                    index_record = (current_osm_id, min_lon, min_lat, max_lon, max_lat, current_offset, message_size)
                    tile_index_data[tile_id].append(index_record)

                    tile_segment_counts[tile_id] += 1

                    # Update overall progress
                    if processed_way_count % 100000 == 0: # Reduce progress frequency
                         elapsed = time.time() - start_time
                         print(f"Processed {processed_way_count} ways ({len(tile_file_handles)} tiles active)... ({elapsed:.1f}s)")

                # --- Catch errors during processing of a single segment ---
                except Exception as e_proc:
                    print(f"Error processing segment data on line {line_num}: {e_proc}")
                    # Decide whether to skip (continue) or abort (raise/sys.exit)
                    continue # Skip this segment and move to the next line

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
                        print(f"  Written index file: {index_filepath} ({len(index_data)} records)")
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