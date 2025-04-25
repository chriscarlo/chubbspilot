import os
# import capnp # REMOVED
import struct # Added for size prefix reading
import math
import sys
import json
import sys # Add sys import
import os # Add os import
from collections import OrderedDict # Added for LRU Cache
from openpilot.common.params import Params
from rtree import index as rtree_index
from shapely.geometry import Point, LineString
# Import generated protobuf classes - now relative
# from tools.map_processing import osm_speed_data_pb2
from . import osm_speed_data_pb2
# Import specific protobuf error
from google.protobuf.message import DecodeError

# Print the path of the imported module for verification
print(f"osm_speed_data_pb2 imported from: {osm_speed_data_pb2.__file__}")

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
# OP_ROOT = "/data/openpilot"
# Base directory for tiles - USE THIS OR RELATIVE PATH depending on context
# TILE_DATA_BASE_DIR = os.path.join(OP_ROOT, "map_data_tiles")
# --- OR --- Using relative path for simulation context based on previous steps:
# TILE_DATA_BASE_DIR = os.path.join(_repo_root, "map_data_tiles_protobuf") # Updated dir name

# Define base directory for tiles - check device path first
OP_ROOT_ON_DEVICE = "/data/openpilot"
MEDIA_ROOT_ON_DEVICE = "/data/media/0" # Define the media path
if os.path.exists(MEDIA_ROOT_ON_DEVICE): # Check for media partition first
    # Use path on media partition if available
    TILE_DATA_BASE_DIR = os.path.join(MEDIA_ROOT_ON_DEVICE, "map_data_tiles_protobuf")
elif os.path.exists(OP_ROOT_ON_DEVICE):
    # Fallback to old path if media path doesn't exist but /data/openpilot does
    # This might be useful for some testing scenarios or older setups.
    TILE_DATA_BASE_DIR = os.path.join(OP_ROOT_ON_DEVICE, "map_data_tiles_protobuf")
    print("MapReader: WARNING - Using fallback path on /data/openpilot as media partition not found.")
else:
    # Fallback to relative path for simulation/development
    TILE_DATA_BASE_DIR = os.path.join(_repo_root, "map_data_tiles_protobuf")
print(f"MapReader: Using tile base directory: {TILE_DATA_BASE_DIR}") # Add confirmation print

# SCHEMA_DIR = os.path.join(_repo_root, "tools/map_processing") # No longer needed
# SCHEMA_PATH = os.path.join(SCHEMA_DIR, "osm_speed_data.capnp") # No longer needed

# --- Constants ---
INDEX_RECORD_FORMAT = '<QddddQQ' # Must match process_osm.py (id, minlon, minlat, maxlon, maxlat, offset, size)
INDEX_RECORD_SIZE = struct.calcsize(INDEX_RECORD_FORMAT)
CACHE_MAX_SEGMENTS = 2000 # Max number of segments to keep in LRU cache (tune this value)
NEARBY_QUERY_RADIUS_DEG = 0.002 # Approx 220m, initial radius for finding candidates in index

class MapReader:
    def __init__(self):
        print("MapReader (Indexed PROTOBUF)") # Updated name
        # No schema check needed

        # self.segments_data = {} # Replaced by LRU cache
        self.segments_data = OrderedDict() # LRU Cache: {osm_id: segment_data_dict}
        self.segment_tile_map = {} # Keep track of which tile a segment came from (for debugging/potential future use)
        self.rtree_idx = rtree_index.Index() # R-tree now only indexes items *in the cache*
        self.loaded_tiles = set() # Keep track of *which* tiles have had their *index* processed recently
        self.protobuf_file_handles = {} # Cache open file handles for protobuf files {tile_id: file_handle}

        self.current_region = None
        self._determine_initial_region()

        print("MapReader (Indexed PROTOBUF) Initialized. Ready to load tiles on demand.")

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

        # Construct final path
        tile_output_dir = region_base_dir # Use region base directly
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
            pass # No alternate check needed anymore

        # Final check before trying to load
        if not file_exists or (file_exists and os.path.getsize(tile_path) < 4):
             # print(f"Tile file not found or effectively empty: {tile_path}") # Too noisy
             self.loaded_tiles.add(tile_id)
             return True

        # --- Read the Index File ---
        index_path = tile_path.replace('.protobuf', '.idx')
        if not os.path.exists(index_path) or os.path.getsize(index_path) == 0:
            # print(f"Index file not found or empty: {index_path}") # Too noisy
            self.loaded_tiles.add(tile_id) # Mark tile as processed (even if empty/no index)
            return True

        # print(f"Processing index: {index_path}") # Too noisy
        index_records = []
        try:
            with open(index_path, 'rb') as idx_f:
                while True:
                    record_bytes = idx_f.read(INDEX_RECORD_SIZE)
                    if not record_bytes: break
                    if len(record_bytes) < INDEX_RECORD_SIZE: break # Corrupt?
                    record = struct.unpack(INDEX_RECORD_FORMAT, record_bytes)
                    index_records.append(record) # (osm_id, min_lon, min_lat, max_lon, max_lat, offset, size)
        except Exception as e:
            print(f"Error reading index file {index_path}: {e}")
            # Don't mark as loaded if index read failed fundamentally
            if tile_id in self.loaded_tiles: self.loaded_tiles.remove(tile_id)
            return False

        # --- Find Nearby Candidates from Index (Needs current position) ---
        # This function is now mainly about *preparing* to load segments when needed,
        # triggered by _update_loaded_tiles. The actual loading happens on cache miss.
        # For now, just mark the tile index as processed.
        # TODO: Optionally, pre-populate cache with *very* close segments?

        self.loaded_tiles.add(tile_id)
        return True # Successfully processed index

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
        # print(f"Marking tile index as unloaded: {tile_id}") # Less noisy
        if tile_id in self.protobuf_file_handles:
            try:
                self.protobuf_file_handles[tile_id].close()
            except Exception as e:
                print(f"Warning: Error closing protobuf file handle for tile {tile_id}: {e}")
            del self.protobuf_file_handles[tile_id]

        # We don't proactively remove segments from cache here anymore.
        # Eviction happens naturally as new segments are loaded.
        self.loaded_tiles.remove(tile_id)

    def _ensure_segment_loaded(self, segment_id_to_load):
        """Loads a specific segment ID into the cache if not already present."""
        if segment_id_to_load in self.segments_data:
            # Already in cache, move to end (most recently used)
            self.segments_data.move_to_end(segment_id_to_load)
            return True

        # --- Cache Miss ---
        # Find which tile this segment *should* belong to (requires reverse lookup or storing index data)
        # This is inefficient. A better way: Query the relevant .idx file directly when needed.
        # Let's redesign get_segment_data_at to handle this.
        # This function becomes less useful in the new design.
        print(f"ERROR: _ensure_segment_loaded called for {segment_id_to_load} - this shouldn't happen with new design")
        return False

    def _add_segment_to_cache(self, segment_id, segment_data_dict, tile_id):
        """Adds a segment to the LRU cache and R-tree, handling eviction."""
        if segment_id in self.segments_data:
            # Should not happen if called correctly after checking cache
            print(f"Warning: Attempted to re-add segment {segment_id} to cache.")
            self.segments_data.move_to_end(segment_id)
            return

        # Add to cache
        self.segments_data[segment_id] = segment_data_dict
        self.segment_tile_map[segment_id] = tile_id # Keep track of origin tile

        # Add to R-tree
        try:
            geom = segment_data_dict.get('geom')
            if geom:
                self.rtree_idx.insert(segment_id, geom.bounds, obj=segment_id)
        except Exception as e_rtree:
            print(f"Warning: Failed to insert segment {segment_id} into R-tree: {e_rtree}")

        # --- Enforce Cache Size Limit (Eviction) ---
        while len(self.segments_data) > CACHE_MAX_SEGMENTS:
            # Remove the least recently used item (first item in OrderedDict)
            evicted_id, evicted_data = self.segments_data.popitem(last=False)
            # print(f"Cache Eviction: Removing segment {evicted_id}") # Can be noisy

            # Remove from R-tree
            try:
                evicted_geom = evicted_data.get('geom')
                if evicted_geom:
                    # Search for the specific item ID in the R-tree to delete
                    items_to_delete = list(self.rtree_idx.intersection(evicted_geom.bounds, objects=True))
                    for item in items_to_delete:
                        if item.object == evicted_id:
                            self.rtree_idx.delete(item.id, item.bbox)
                            break # Found and deleted
            except Exception as e_rtree_del:
                print(f"Warning: Failed to delete segment {evicted_id} from R-tree during eviction: {e_rtree_del}")

            # Remove from tile map
            if evicted_id in self.segment_tile_map:
                del self.segment_tile_map[evicted_id]

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

        # Load needed tile *indices* (pass lat/lon context)
        for tile_id in tiles_to_load:
            if tile_id not in self.loaded_tiles:
                # Pass context for path construction
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
            # 1. Query R-tree (containing only *cached* segments)
            search_bounds = (lon - NEARBY_QUERY_RADIUS_DEG, lat - NEARBY_QUERY_RADIUS_DEG,
                             lon + NEARBY_QUERY_RADIUS_DEG, lat + NEARBY_QUERY_RADIUS_DEG)
            cached_candidates = list(self.rtree_idx.intersection(search_bounds, objects=True))

            closest_segment_info = None
            min_dist_cached = float('inf')

            # Find closest among *cached* candidates
            for item in cached_candidates:
                segment_id = item.object
                # Check data is still loaded (should be, as it's from cache R-tree)
                if segment_id not in self.segments_data:
                    # print(f"Warning: R-tree pointed to non-cached segment {segment_id}") # Should not happen
                    continue
                segment_info = self.segments_data[segment_id]
                distance = segment_info['geom'].distance(current_point)

                if distance < min_dist_cached:
                    MAX_RELEVANT_DISTANCE_DEGREES = 0.0015 # Approx 166m
                    if distance < MAX_RELEVANT_DISTANCE_DEGREES:
                        min_dist_cached = distance
                        closest_segment_info = segment_info
                        # Move accessed segment to end of LRU cache
                        self.segments_data.move_to_end(segment_id)

            if closest_segment_info is not None:
                # print(f"Found closest segment {closest_segment_info['id']} in cache.") # Debug
                return closest_segment_info

            # 2. If no suitable candidate in cache, check the index file for the current tile
            # print(f"No suitable segment in cache, checking index for tile containing {lat}, {lon}") # Debug
            current_tile_id = get_tile_id(lat, lon, TILE_SIZE_DEG)
            tile_path_proto = self._get_tile_path(current_tile_id, lat, lon)
            if not tile_path_proto:
                 return None
            index_path = tile_path_proto.replace('.protobuf', '.idx')

            if not os.path.exists(index_path) or os.path.getsize(index_path) == 0:
                # print(f"Index file missing or empty for current tile: {index_path}") # Debug
                return None

            # --- Search Index File ---
            min_dist_index = float('inf')
            best_candidate_record = None
            try:
                with open(index_path, 'rb') as idx_f:
                    while True:
                        record_bytes = idx_f.read(INDEX_RECORD_SIZE)
                        if not record_bytes: break
                        if len(record_bytes) < INDEX_RECORD_SIZE: break
                        record = struct.unpack(INDEX_RECORD_FORMAT, record_bytes)
                        # (osm_id, min_lon, min_lat, max_lon, max_lat, offset, size)
                        osm_id, r_min_lon, r_min_lat, r_max_lon, r_max_lat, _, _ = record

                        # Check if current point is within expanded bounds of this segment
                        if (r_min_lat - NEARBY_QUERY_RADIUS_DEG <= lat <= r_max_lat + NEARBY_QUERY_RADIUS_DEG and
                            r_min_lon - NEARBY_QUERY_RADIUS_DEG <= lon <= r_max_lon + NEARBY_QUERY_RADIUS_DEG):
                            # Estimate distance to bounding box center (crude but fast pre-filter)
                            # center_lon = (r_min_lon + r_max_lon) / 2
                            # center_lat = (r_min_lat + r_max_lat) / 2
                            # approx_dist_sq = (lon - center_lon)**2 + (lat - center_lat)**2
                            # Consider segment if its bbox is close - skip exact dist calc here
                            # Temporarily just consider it a candidate if bbox overlaps query radius
                            if osm_id not in self.segments_data: # Only consider if not already cached
                                 # We need to load it to calculate exact distance,
                                 # but for now, just store the *best candidate record* based on bbox overlap.
                                 # This is imperfect. A better index query is needed.
                                 # Let's just load the first candidate found in the index for now.
                                 best_candidate_record = record
                                 break # Simplification: load first potential match found

            except Exception as e:
                 print(f"Error reading index {index_path} during cache miss lookup: {e}")
                 return None

            # 3. Load the best candidate from index (if found) into cache
            if best_candidate_record:
                osm_id, _, _, _, _, offset, size = best_candidate_record
                # print(f"Cache miss: Loading segment {osm_id} from index record.") # Debug

                # --- Get or open the correct protobuf file handle ---
                proto_f = self.protobuf_file_handles.get(current_tile_id)
                if proto_f is None:
                    try:
                        proto_f = open(tile_path_proto, 'rb')
                        self.protobuf_file_handles[current_tile_id] = proto_f
                    except IOError as e_io:
                        print(f"Error opening protobuf file {tile_path_proto} on cache miss: {e_io}")
                        return None
                # --- Read and deserialize specific segment ---
                segment_data_dict = None
                try:
                    proto_f.seek(offset)
                    message_bytes = proto_f.read(size)
                    if len(message_bytes) == size:
                        segment = osm_speed_data_pb2.SpeedLimitSegment()
                        segment.ParseFromString(message_bytes)
                        # --- Convert to dictionary format used internally ---
                        coords = [(p.longitude, p.latitude) for p in segment.geometry]
                        if len(coords) >= 2:
                             line = LineString(coords)
                             segment_data_dict = {
                                'id': osm_id,
                                'speed_mps': segment.speed_limit_mps,
                                'geom': line,
                                'curvatures': list(segment.curvatures),
                                # Add placeholders for fields not in proto
                                'highway': '', 'lanes': 0, 'oneway': 0,
                                'name': '', 'ref': '', 'surface': '',
                                'is_bridge': False, 'is_tunnel': False,
                            }
                    else:
                         print(f"Error: Read wrong size for segment {osm_id} from {tile_path_proto}. Expected {size}, got {len(message_bytes)}")
                except DecodeError as de:
                    print(f"Protobuf DecodeError loading segment {osm_id} from {tile_path_proto}: {de}")
                except Exception as e_load:
                    print(f"Error loading segment {osm_id} on cache miss: {e_load}")

                # --- Add to cache if loaded successfully ---
                if segment_data_dict:
                    self._add_segment_to_cache(osm_id, segment_data_dict, current_tile_id)
                    # Now check distance again
                    distance = segment_data_dict['geom'].distance(current_point)
                    MAX_RELEVANT_DISTANCE_DEGREES = 0.0015 # Approx 166m
                    if distance < MAX_RELEVANT_DISTANCE_DEGREES:
                        return segment_data_dict
                    else:
                        # Loaded, but too far away after checking exact distance
                        return None
                else:
                    return None # Failed to load/deserialize
            else:
                 # print(f"No candidate found in index file {index_path}") # Debug
                 return None # No candidate found in index

        except Exception as e:
            print(f"Error during spatial query or index lookup: {e}")
            return None

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
