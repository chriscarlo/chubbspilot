#!/usr/bin/env python3
# import osmnx as ox # No longer needed
import sys
import time
# import capnp # REMOVED
import struct # Added for size prefixing
import os # Import os for path operations
import json # For parsing GeoJSON lines
import numpy as np
import math # Added for tiling

# Import our geometry functions
from openpilot.selfdrive.frogpilot.navigation.mapd_py import geometry
# Import generated protobuf classes
from tools.map_processing import osm_speed_data_pb2

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

    try:
        with open(input_geojsonl, 'r') as infile:
            for line in infile:
                # if line_num % 100000 == 1: print(f"DEBUG: Reading line {line_num}") # Keep commented for now

                line_num += 1
                if not line.strip(): skipped_empty += 1; continue
                try: feature = json.loads(line)
                except json.JSONDecodeError as e: skipped_json_error += 1; print(f"Warning: Skipping malformed JSON on line {line_num}: {e}"); continue

                if feature.get('type') != 'Feature': skipped_not_feature += 1; continue
                geom = feature.get('geometry', {})
                if geom.get('type') != 'LineString': skipped_not_linestring += 1; continue

                props = feature.get('properties', {})
                coords = geom.get('coordinates', [])
                if len(coords) < 2: skipped_coords_len += 1; continue

                # --- Extract OSM ID ---
                # Try top-level 'id' first (common osmium geojson format, e.g., "way/12345")
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

                # --- Assign segment to tile AND determine sub-directory ---
                start_lon, start_lat = coords[0]
                tile_id = get_tile_id(start_lat, start_lon, TILE_SIZE_DEG)

                # Determine sub-directory based on region and latitude
                sub_dir_name = None
                if region_name == "california":
                    if start_lat >= 35.8:
                        sub_dir_name = "NorCal"
                    else:
                        sub_dir_name = "SoCal"

                # Construct final output directory for the tile
                if sub_dir_name:
                    tile_output_dir = os.path.join(region_base_output_dir, sub_dir_name)
                else:
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
                # Use a tuple (tile_output_dir, tile_id) as key if needed, or just tile_id if unique across subdirs
                # Sticking with tile_id as key for now, assuming it implies location
                outfile = tile_file_handles.get(tile_id)
                if outfile is None:
                    tile_filename = f"{tile_id}.protobuf"
                    tile_filepath = os.path.join(tile_output_dir, tile_filename) # Use the determined output dir
                    try:
                        outfile = open(tile_filepath, 'ab')
                        tile_file_handles[tile_id] = outfile
                        tile_segment_counts[tile_id] = 0
                    except IOError as e:
                        print(f"Error opening tile file {tile_filepath}: {e}")
                        continue

                # DEBUG: Are we reaching the processing point?
                print(f"DEBUG: Reached processing point for line {line_num}, OSM ID {current_osm_id}")

                # --- Process Required Data (ID, Geometry, Curvature) ---
                processed_way_count += 1

                segment_curvatures = []
                coords_lon = [c[0] for c in coords]
                coords_lat = [c[1] for c in coords]
                if len(coords) >= 3:
                    curvatures_list, _ = geometry.get_curvatures(coords_lat, coords_lon)
                    segment_curvatures = curvatures_list if curvatures_list else []

                # --- Build Protobuf Message (Focus on ID, Geometry, Curvature) ---
                segment_msg = osm_speed_data_pb2.SpeedLimitSegment()
                segment_msg.osm_way_id = current_osm_id

                # Populate geometry
                for lon, lat in coords:
                    point = segment_msg.geometry.add()
                    point.latitude = lat
                    point.longitude = lon
                # Populate curvatures
                segment_msg.curvatures.extend(segment_curvatures)

                # Populate speed limit with default value (required by reader)
                segment_msg.speed_limit_mps = 0.0

                # --- Write Size-Prefixed Message to Tile File ---
                try:
                    write_message(outfile, segment_msg)
                    tile_segment_counts[tile_id] += 1
                except IOError as e:
                    print(f"Error writing to tile file for {tile_id}: {e}")
                    continue

                # Update overall progress
                if processed_way_count % 100000 == 0: # Reduce progress frequency
                     elapsed = time.time() - start_time
                     print(f"Processed {processed_way_count} ways ({len(tile_file_handles)} tiles active)... ({elapsed:.1f}s)")

    except FileNotFoundError:
         print(f"Error: Input GeoJSON Lines file not found: {input_geojsonl}")
         sys.exit(1)
    except Exception as e:
         print(f"An error occurred during processing near line {line_num}: {e}")
         sys.exit(1) # Exit on error
    finally:
        # --- Ensure all tile files are closed ---
        print("Closing tile files...")
        closed_count = 0
        for tile_id, handle in tile_file_handles.items():
            try:
                handle.close()
                closed_count += 1
            except IOError as e:
                print(f"Warning: Error closing file for tile {tile_id}: {e}")
        print(f"Closed {closed_count} tile files.")
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