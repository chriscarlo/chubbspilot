import os
# import capnp # REMOVED
import struct # Added for size prefix reading
import math
import sys
import json
import sys # Add sys import
import os # Add os import
from openpilot.common.params import Params
from rtree import index as rtree_index
from shapely.geometry import Point, LineString
# Import generated protobuf classes
from tools.map_processing import osm_speed_data_pb2

# Find the repository root relative to this file
# __file__ is selfdrive/frogpilot/navigation/mapd_py/reader.py
# We need to go up 5 levels to reach the repo root (/home/chris/openpilot/)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_script_dir, "../../../../..")) # Adjusted levels

# Add repo root to Python path BEFORE attempting the import
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Define paths relative to the repository root found above
MAP_DATA_DIR = os.path.join(_repo_root, "map_data")
SCHEMA_DIR = os.path.join(_repo_root, "tools/map_processing")

# Define path to our custom capnp file and schema relative to openpilot root
# Adjust these paths if necessary
# DEFAULT_SPEED_LIMIT_DATA_PATH = "map_data/nevada-speedlimits.capnp" # Hardcoded for now -- Replaced by dynamic logic
# OP_ROOT = "/data/openpilot" # Assume standard openpilot path on device -- Temporarily Disabled for Simulation

# Approximate Bounding Boxes (min_lon, min_lat, max_lon, max_lat)
REGION_BOUNDS = {
    "california": (-124.5, 32.5, -114.1, 42.0),
    "nevada": (-120.0, 35.0, -114.0, 42.0),
    # Add more regions here as needed
}
REGION_FILES = {
    "california": os.path.join(MAP_DATA_DIR, "california-speedlimits.capnp"), # Use relative MAP_DATA_DIR
    "nevada": os.path.join(MAP_DATA_DIR, "nevada-speedlimits.capnp"), # Use relative MAP_DATA_DIR
}
DEFAULT_REGION_FILE = REGION_FILES["nevada"] # Choose a reasonable default (uses relative path now)

SCHEMA_PATH = os.path.join(SCHEMA_DIR, "osm_speed_data.capnp") # Use relative SCHEMA_DIR
# SCHEMA_PATH = os.path.join(OP_ROOT, "tools/map_processing/osm_speed_data.capnp") # Assume schema is also relative to root -- Temporarily Disabled

# Load our custom Cap'n Proto schema
# try:
#     osm_speed_data_capnp = capnp.load(SCHEMA_PATH)
# except Exception as e:
#     print(f"Fatal Error: Could not load speed limit schema '{SCHEMA_PATH}': {e}")
#     osm_speed_data_capnp = None

# Remove old helper functions
# def get_bounds_filename(...)
# def find_area_box(...)

# --- Tiling Setup ---
TILE_SIZE_DEG = 0.1 # Back to 0.1 degrees
def get_tile_id(lat_deg, lon_deg, tile_size_deg):
    tile_lat = math.floor(lat_deg / tile_size_deg) * tile_size_deg
    tile_lon = math.floor(lon_deg / tile_size_deg) * tile_size_deg
    lat_part = f"N{tile_lat:.1f}" if tile_lat >= 0 else f"S{abs(tile_lat):.1f}"
    lon_part = f"E{tile_lon:.1f}" if tile_lon >= 0 else f"W{abs(tile_lon):.1f}"
    return f"{lat_part}_{lon_part}"

# Assuming script runs on device where OP_ROOT is standard
OP_ROOT = "/data/openpilot"
# Base directory for tiles - USE THIS OR RELATIVE PATH depending on context
# TILE_DATA_BASE_DIR = os.path.join(OP_ROOT, "map_data_tiles")
# --- OR --- Using relative path for simulation context based on previous steps:
TILE_DATA_BASE_DIR = os.path.join(_repo_root, "map_data_tiles_protobuf") # Updated dir name
# SCHEMA_DIR = os.path.join(_repo_root, "tools/map_processing") # No longer needed
# SCHEMA_PATH = os.path.join(SCHEMA_DIR, "osm_speed_data.capnp") # No longer needed

class MapReader:
    def __init__(self):
        print("MapReader (Tiled PROTOBUF - Geom Focus) Initializing...") # Updated name
        # No schema check needed

        self.segments_data = {}
        self.segment_tile_map = {}
        self.rtree_idx = rtree_index.Index()
        self.loaded_tiles = set()
        self.current_region = None

        self._determine_initial_region()

        print("MapReader (Tiled PROTOBUF - Geom Focus) Initialized. Ready to load tiles on demand.")

    def _determine_initial_region(self):
        # Simplified logic to find region for path construction
        # (Doesn't load tiles here)
        print("MapReader: Determining initial region...")
        params_memory = None
        last_gps = None
        try:
            params_memory = Params("/dev/shm/params")
            # Use non-blocking read without timeout (fixed earlier)
            gps_json = params_memory.get("LastGPSPosition", block=False)
            if gps_json:
                last_gps = json.loads(gps_json)
                if 'latitude' in last_gps and 'longitude' in last_gps:
                    lat = last_gps['latitude']
                    lon = last_gps['longitude']
                    print(f"MapReader: Using GPS Lat={lat}, Lon={lon} for initial region.")
                    for region, bounds in REGION_BOUNDS.items():
                        min_lon, min_lat, max_lon, max_lat = bounds
                        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                            self.current_region = region
                            print(f"MapReader: Initial region set to: {self.current_region}")
                            break
                    if self.current_region is None:
                        print("MapReader: GPS location not in known regions.")
                else:
                    print("MapReader: GPS data missing lat/lon.")
            else:
                print("MapReader: No initial GPS data found in params.")
        except Exception as e:
            print(f"MapReader: Error reading LastGPSPosition for initial region: {e}")

        if self.current_region is None:
            print("MapReader: Could not determine initial region.")

    def _get_tile_path(self, tile_id, lat_deg, lon_deg):
        """Constructs the expected path for a given tile ID, including subdirs."""
        # Determine region based on lat/lon if not already set
        # (This might duplicate effort from _update_loaded_tiles but ensures region is known)
        determined_region = self.current_region
        if not determined_region:
            for region, bounds in REGION_BOUNDS.items():
                min_lon_b, min_lat_b, max_lon_b, max_lat_b = bounds
                if min_lon_b <= lon_deg <= max_lon_b and min_lat_b <= lat_deg <= max_lat_b:
                    determined_region = region
                    break

        if not determined_region:
             # print("Warning: Cannot get tile path, region not determined for lat/lon.")
             return None

        # Base directory for the determined region
        region_base_dir = os.path.join(TILE_DATA_BASE_DIR, determined_region)

        # Determine sub-directory
        sub_dir = ""
        if determined_region == "california":
            if lat_deg >= 35.8:
                 sub_dir = "NorCal"
            else:
                 sub_dir = "SoCal"

        # Construct final path
        tile_output_dir = os.path.join(region_base_dir, sub_dir) if sub_dir else region_base_dir
        return os.path.join(tile_output_dir, f"{tile_id}.protobuf")

    def _load_tile(self, tile_id):
        """Loads data from a specific tile file."""
        if tile_id in self.loaded_tiles:
            return True

        # PROBLEM: _load_tile doesn't know the lat/lon to determine the subdir!
        # We need to pass lat/lon used to determine the tile_id here, or refactor.
        # TEMP FIX: Try both NorCal/SoCal paths if region is CA and path doesn't exist?
        # This is inefficient and hacky.

        # TODO: Refactor tile loading to pass context (lat/lon) or determine path differently.

        # -- Placeholder/Inefficient Fix Attempt ---
        # First, try to guess path assuming current self.current_region context
        # This requires _update_loaded_tiles to set self.current_region correctly first.
        temp_lat, temp_lon = self._get_approx_center_for_tile(tile_id) # Need helper
        if temp_lat is None or temp_lon is None:
             print(f"Warning: Cannot determine approx coords for tile {tile_id}, load might fail.")
             # Fallback: maybe try without subdir?
             # tile_path = os.path.join(TILE_DATA_BASE_DIR, self.current_region or "unknown", f"{tile_id}.protobuf")
             return False # Cannot reliably construct path

        tile_path = self._get_tile_path(tile_id, temp_lat, temp_lon)
        # --- End Placeholder ---

        if not tile_path:
            print(f"Error: Could not construct path for tile {tile_id}")
            return False

        # Check if file exists AND is effectively empty (e.g., < 4 bytes for size prefix)
        file_exists = os.path.exists(tile_path)
        if not file_exists or (file_exists and os.path.getsize(tile_path) < 4):
            # Check alternate California subdir if the first guess failed
            if self.current_region == "california" and not file_exists:
                alt_sub_dir = "SoCal" if temp_lat >= 35.8 else "NorCal"
                alt_region_base_dir = os.path.join(TILE_DATA_BASE_DIR, self.current_region)
                alt_tile_output_dir = os.path.join(alt_region_base_dir, alt_sub_dir)
                alt_tile_path = os.path.join(alt_tile_output_dir, f"{tile_id}.protobuf")
                alt_file_exists = os.path.exists(alt_tile_path)
                if alt_file_exists and os.path.getsize(alt_tile_path) >= 4:
                    print(f"Found tile {tile_id} in alternate subdir: {alt_tile_path}")
                    tile_path = alt_tile_path # Use the path we found
                    file_exists = True # Update status
                # else:
                     # print(f"Tile {tile_id} not found or empty in either subdir.") # Too noisy

        # Final check before trying to load
        if not file_exists or (file_exists and os.path.getsize(tile_path) < 4):
             # print(f"Tile file not found or effectively empty: {tile_path}") # Too noisy
             self.loaded_tiles.add(tile_id)
             return True

        # print(f"Loading tile: {tile_path}") # Too noisy
        segment_count_in_tile = 0
        loaded_segment_ids = set() # Track IDs loaded in this call
        try:
            with open(tile_path, 'rb') as f:
                while True:
                    size_bytes = f.read(4)
                    if not size_bytes: break
                    if len(size_bytes) < 4: break
                    message_size = struct.unpack('<I', size_bytes)[0]
                    message_bytes = f.read(message_size)
                    if len(message_bytes) < message_size: break

                    segment = osm_speed_data_pb2.SpeedLimitSegment()
                    segment.ParseFromString(message_bytes)

                    coords = [(p.longitude, p.latitude) for p in segment.geometry]
                    if len(coords) < 2: continue
                    line = LineString(coords)
                    osm_id = segment.osm_way_id
                    if osm_id == 0: continue

                    # Avoid reloading if segment ID already exists (e.g., from overlapping tile loads)
                    if osm_id in self.segments_data:
                         continue

                    # Extract core data + defaults for others
                    self.segments_data[osm_id] = {
                       'id': osm_id,
                       'speed_mps': segment.speed_limit_mps,
                       'geom': line,
                       'curvatures': list(segment.curvatures),
                       'highway': segment.highway_type,
                       'lanes': segment.lanes,
                       'oneway': segment.oneway,
                       'name': segment.name,
                       'ref': segment.ref,
                       'surface': segment.surface,
                       'is_bridge': segment.is_bridge,
                       'is_tunnel': segment.is_tunnel,
                    }
                    self.segment_tile_map[osm_id] = tile_id
                    self.rtree_idx.insert(osm_id, line.bounds, obj=osm_id)
                    segment_count_in_tile += 1
                    loaded_segment_ids.add(osm_id)

            if segment_count_in_tile > 0:
                 print(f"Loaded {segment_count_in_tile} segments from tile {tile_id} ({os.path.basename(os.path.dirname(tile_path))})") # Add subdir info
            self.loaded_tiles.add(tile_id)
            return True

        except Exception as e: # Catch other errors like parsing
             print(f"Error processing tile {tile_path}: {e}")
             # Clean up only segments added in this failed load attempt
             for sid in loaded_segment_ids:
                 if sid in self.segments_data: del self.segments_data[sid]
                 if sid in self.segment_tile_map: del self.segment_tile_map[sid]
                 # Rtree cleanup remains tricky, potentially leave stale entries for now
             print(f"Cleaned up partially loaded data for failed tile {tile_id}")
             # Don't mark as loaded if fundamental error occurred
             if tile_id in self.loaded_tiles: self.loaded_tiles.remove(tile_id)
             return False

    # Helper function to estimate tile center (needed for placeholder fix)
    def _get_approx_center_for_tile(self, tile_id):
        try:
            parts = tile_id.split('_')
            lat_part = parts[0]
            lon_part = parts[1]

            lat = float(lat_part[1:])
            if lat_part[0] == 'S': lat *= -1

            lon = float(lon_part[1:])
            if lon_part[0] == 'W': lon *= -1

            # Return center coordinates
            center_lat = lat + TILE_SIZE_DEG / 2.0
            center_lon = lon + TILE_SIZE_DEG / 2.0
            return center_lat, center_lon
        except Exception as e:
            print(f"Error parsing tile_id '{tile_id}': {e}")
            return None, None

    def _unload_tile(self, tile_id):
        """Unloads data for a specific tile."""
        if tile_id not in self.loaded_tiles:
            return
        print(f"Unloading tile: {tile_id}")
        ids_to_remove = [seg_id for seg_id, t_id in self.segment_tile_map.items() if t_id == tile_id]

        removed_count = 0
        for seg_id in ids_to_remove:
            # Remove from R-tree - This is tricky, requires bounds or iterating
            # Strategy 1: Iterate through index results near the segment bounds
            if seg_id in self.segments_data:
                try:
                    segment_bounds = self.segments_data[seg_id]['geom'].bounds
                    items_to_delete = list(self.rtree_idx.intersection(segment_bounds, objects=True))
                    found_in_rtree = False
                    for item in items_to_delete:
                        # Check if the object stored in the index matches our segment ID
                        if item.object == seg_id:
                            self.rtree_idx.delete(item.id, item.bbox) # Use item.id from index node
                            found_in_rtree = True
                            break
                    # if not found_in_rtree:
                    #     print(f"Warning: Segment {seg_id} bounds search didn't find exact match in R-tree for deletion.")
                except Exception as e:
                    print(f"Warning: Error removing segment {seg_id} from R-tree: {e}")
            # else: # Should not happen if logic is correct
                # print(f"Warning: Cannot remove segment {seg_id} from R-tree, data not found.")

            # Remove from data stores
            if seg_id in self.segments_data:
                del self.segments_data[seg_id]
                removed_count += 1
            if seg_id in self.segment_tile_map:
                del self.segment_tile_map[seg_id]

        print(f"Unloaded {removed_count} segments for tile {tile_id}")
        self.loaded_tiles.remove(tile_id)

    def _update_loaded_tiles(self, lat, lon):
        """Determine current tile, load it & neighbors, unload old ones."""
        # Determine current region if not set or changed
        current_point_region = None
        for region, bounds in REGION_BOUNDS.items():
            min_lon_b, min_lat_b, max_lon_b, max_lat_b = bounds
            if min_lon_b <= lon <= max_lon_b and min_lat_b <= lat <= max_lat_b:
                current_point_region = region
                break

        if current_point_region != self.current_region:
            print(f"Region changed from {self.current_region} to {current_point_region}. Unloading all tiles.")
            # Simple strategy: unload all when region changes
            all_tiles = list(self.loaded_tiles)
            for t_id in all_tiles:
                self._unload_tile(t_id)
            self.current_region = current_point_region

        if not self.current_region:
            # print("Warning: Current location outside known regions. Cannot load tiles.") # Repetitive
            # Ensure everything is unloaded if we are outside known regions
            if self.loaded_tiles:
                print("Warning: Outside known regions, unloading remaining tiles.")
                all_tiles = list(self.loaded_tiles)
                for t_id in all_tiles:
                    self._unload_tile(t_id)
            return

        # Calculate current tile ID
        current_tile_id = get_tile_id(lat, lon, TILE_SIZE_DEG)

        # Define neighbors (e.g., 3x3 grid around current)
        tiles_to_load = set()
        # Use integer math on tile indices for clarity
        current_lat_idx = math.floor(lat / TILE_SIZE_DEG)
        current_lon_idx = math.floor(lon / TILE_SIZE_DEG)

        for lat_idx_offset in [-1, 0, 1]: # Neighboring rows
            for lon_idx_offset in [-1, 0, 1]: # Neighboring columns
                neighbor_lat = (current_lat_idx + lat_idx_offset) * TILE_SIZE_DEG
                neighbor_lon = (current_lon_idx + lon_idx_offset) * TILE_SIZE_DEG
                # Use actual corner lat/lon to generate ID consistently
                tiles_to_load.add(get_tile_id(neighbor_lat, neighbor_lon, TILE_SIZE_DEG))

        # Load needed tiles (pass lat/lon context - though _load_tile doesn't use it yet)
        for tile_id in tiles_to_load:
            if tile_id not in self.loaded_tiles:
                # Pass context, although _load_tile has placeholder logic for now
                self._load_tile(tile_id)

        # Unload tiles no longer needed (outside the 3x3 grid)
        tiles_to_unload = self.loaded_tiles - tiles_to_load
        for tile_id in tiles_to_unload:
            self._unload_tile(tile_id)

    def get_segment_data_at(self, lat, lon):
        """Finds the closest map segment to the given coordinates."""
        # Update loaded tiles based on current position FIRST
        self._update_loaded_tiles(lat, lon)

        if not self.segments_data:
            # print("Warning: No map data loaded/relevant, cannot get segment data.")
            return None

        current_point = Point(lon, lat)

        try:
            # Query R-tree for nearest segments (using object=True to get osm_id)
            # Increase candidates queried; index now contains only nearby tiles.
            nearest_candidates = list(self.rtree_idx.nearest((lon, lat, lon, lat), 10, objects=True))

            if not nearest_candidates:
                # print("No nearby segments found in R-tree for loaded tiles.")
                return None

            closest_segment_info = None
            min_dist = float('inf')

            # Find the segment whose geometry is actually closest among candidates
            for item in nearest_candidates:
                segment_id = item.object
                # Check data is still loaded (robustness against race conditions?)
                if segment_id not in self.segments_data:
                    # This might happen if a tile was unloaded between query and lookup
                    # print(f"Warning: R-tree pointed to unloaded segment {segment_id}")
                    continue
                segment_info = self.segments_data[segment_id]
                distance = segment_info['geom'].distance(current_point)

                if distance < min_dist:
                    # Optional: Add a threshold for max distance?
                    MAX_RELEVANT_DISTANCE_DEGREES = 0.0015 # Approx 166m, slightly larger?
                    if distance < MAX_RELEVANT_DISTANCE_DEGREES:
                        min_dist = distance
                        closest_segment_info = segment_info
            # else:
                # print(f"Closest candidate distance {min_dist:.6f} > threshold")

            return closest_segment_info

        except Exception as e:
            print(f"Error during spatial query: {e}")
            return None

    # Remove old _load_and_index_data method
    # def _load_and_index_data(self):
    #    ...

# Example usage section (modified for new structure)
if __name__ == '__main__':
    print("\n--- Testing Custom MapReader ---")

    # Check if schema loaded
    # if osm_speed_data_capnp is None:
    #     print("Schema failed to load. Exiting test.")
    #     sys.exit(1)

    # Specify the data file path explicitly for testing
    test_data_path = "map_data/california-speedlimits.capnp"
    print(f"Using test data path: {test_data_path}")

    if not os.path.exists(test_data_path):
        print(f"Test data file '{test_data_path}' not found.")
        print("Please ensure you have run the processing script first:")
        # Updated example command in error message
        print(f"  python3 tools/map_processing/process_osm.py map_data/california-exported.geojsonl {test_data_path}")
        sys.exit(1)

    print(f"Initializing MapReader with data: {test_data_path}")
    reader = MapReader()

    # Example coordinates (somewhere in California now, e.g., near SF)
    # test_lat = 39.16 # Approx Reno
    # test_lon = -119.75
    test_lat = 37.77 # Approx SF
    test_lon = -122.41

    if reader.segments_data: # Check if data was loaded and indexed
        print(f"\nQuerying segment data near Lat={test_lat}, Lon={test_lon}")
        segment_data = reader.get_segment_data_at(test_lat, test_lon)

        if segment_data is not None:
            MPH_CONVERSION = 2.23694
            speed_limit = segment_data.get('speed_mps', 0.0)
            osm_id = segment_data.get('id', 'N/A')
            curvatures = segment_data.get('curvatures', [])
            highway = segment_data.get('highway', 'N/A')
            lanes = segment_data.get('lanes', '?')
            oneway = segment_data.get('oneway', '?')
            print(f"Found Segment ID: {osm_id}")
            print(f"  Highway: {highway}")
            print(f"  Lanes: {lanes}")
            print(f"  Oneway: {oneway}")
            print(f"  Speed Limit: {speed_limit:.2f} m/s (~{speed_limit * MPH_CONVERSION:.1f} mph)")
            print(f"  Curvatures available: {len(curvatures) > 0} (Count: {len(curvatures)})")
        else:
            print("No relevant segment data found nearby.")
    else:
        print("MapReader did not load data successfully. Cannot perform query.")

    print("--- Test Complete ---")
