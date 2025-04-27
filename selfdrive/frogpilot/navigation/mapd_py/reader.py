import os
# import capnp # REMOVED
import struct # Added for size prefix reading and index file
import math
import sys
import json
import sys # Add sys import
import os # Add os import
from openpilot.common.params import Params
from rtree import index as rtree_index
from shapely.geometry import Point, LineString
from collections import OrderedDict # Added for LRU cache
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

# Define index record format (must match process_osm.py)
INDEX_RECORD_FORMAT = '<qddddQQ'
INDEX_RECORD_SIZE = struct.calcsize(INDEX_RECORD_FORMAT)

# Cache configuration
DEFAULT_CACHE_SIZE = 5000 # Max number of segments to keep in memory

class MapReader:
    def __init__(self, cache_size=DEFAULT_CACHE_SIZE):
        print("MapReader (Indexed Tiled PROTOBUF - Geom Focus) Initializing...") # Updated name
        # No schema check needed

        self.segments_data = OrderedDict() # LRU Cache for segment data dicts
        self.cache_size = cache_size

        self.segment_tile_map = {} # Still needed to track which tile a segment came from for unloading
        self.rtree_idx = rtree_index.Index() # R-tree will index segments currently IN THE CACHE
        self.loaded_tiles = set() # Tracks which TILE INDICES have been loaded (not necessarily all segments)
        self.current_region = None

        self._determine_initial_region()

        print(f"MapReader Initialized (Cache Size: {self.cache_size}). Ready to load tiles on demand.")

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

        # Construct final path - NO SUBDIRS
        # tile_output_dir = region_base_dir # Use region base directly - This line is redundant
        # REMOVED SUBDIR LOGIC
        # if determined_region == "california":
        #     # Need lat/lon to determine NorCal/SoCal
        #     if lat_deg >= 35.8:
        #         tile_output_dir = os.path.join(region_base_dir, "NorCal")
        #     else:
        #         tile_output_dir = os.path.join(region_base_dir, "SoCal")
        # else:
        tile_output_dir = region_base_dir # No subdir for other regions

        return os.path.join(tile_output_dir, f"{tile_id}.protobuf")

    def _load_tile(self, tile_id, current_lat, current_lon): # Added lat/lon context
        """Loads relevant segment data from a specific tile file using its index."""
        if tile_id in self.loaded_tiles:
            return True

        # Determine path for both protobuf and index file
        tile_path_proto = self._get_tile_path(tile_id, current_lat, current_lon) # Use context lat/lon
        if not tile_path_proto:
            print(f"Error: Could not construct path for tile {tile_id}")
            # Mark as "loaded" to avoid retrying a tile we can't pathfind
            self.loaded_tiles.add(tile_id)
            return False

        tile_path_idx = tile_path_proto.replace(".protobuf", ".idx")

        # Check if index file exists and is not empty
        if not os.path.exists(tile_path_idx) or os.path.getsize(tile_path_idx) < INDEX_RECORD_SIZE:
            # print(f"Index file not found or empty for tile {tile_id}: {tile_path_idx}")
            self.loaded_tiles.add(tile_id) # Mark as loaded (nothing to load)
            return True # Considered "loaded" successfully (as there's nothing to load)

        # print(f"Loading index for tile: {tile_path_idx}") # Can be noisy
        loaded_this_call = 0
        segments_to_cache = [] # List of (osm_id, segment_data_dict)

        try:
            # --- Read Index Records ---
            index_records = []
            with open(tile_path_idx, 'rb') as idx_file:
                while True:
                    record_bytes = idx_file.read(INDEX_RECORD_SIZE)
                    if not record_bytes or len(record_bytes) < INDEX_RECORD_SIZE:
                        break
                    # osm_id, min_lon, min_lat, max_lon, max_lat, offset, size
                    record = struct.unpack(INDEX_RECORD_FORMAT, record_bytes)
                    index_records.append(record)

            if not index_records:
                 # print(f"No index records found in {tile_path_idx}")
                 self.loaded_tiles.add(tile_id) # Mark as loaded
                 return True

            # Process ALL records from the index if they aren't already cached
            candidate_records = []
            for rec in index_records:
                osm_id = rec[0]
                if osm_id not in self.segments_data:
                     candidate_records.append(rec)

            if not candidate_records:
                # print(f"No *new* segments found in tile {tile_id} index (all might be cached).")
                self.loaded_tiles.add(tile_id) # Mark as loaded
                return True

            # print(f"Found {len(candidate_records)} candidates in tile {tile_id} index near location.") # Now potentially all segments
            # --- Read and Deserialize Only Candidate Segments ---
            with open(tile_path_proto, 'rb') as proto_file:
                for rec in candidate_records:
                    osm_id, _, _, _, _, offset, size = rec
                    try:
                        proto_file.seek(offset)
                        # Read and discard the 4-byte size prefix
                        _ = proto_file.read(4)
                        # Now read the actual message bytes
                        message_bytes = proto_file.read(size)
                        if len(message_bytes) < size:
                            print(f"Warning: Could not read full message ({len(message_bytes)}/{size} bytes) for segment {osm_id} in {tile_path_proto}")
                            continue

                        segment = osm_speed_data_pb2.SpeedLimitSegment()
                        segment.ParseFromString(message_bytes)

                        coords = [(p.longitude, p.latitude) for p in segment.geometry]
                        if len(coords) < 2: continue
                        line = LineString(coords)

                        # --- Store Segment Data Temporarily ---
                        segment_data = {
                           'id': osm_id,
                           'speed_mps': segment.speed_limit_mps,
                           'geom': line,
                           'curvatures': list(segment.curvatures),
                           # Placeholders needed by matcher/consumers
                           'highway': '', 'lanes': 0, 'oneway': 0, 'name': '',
                           'ref': '', 'surface': '', 'is_bridge': False, 'is_tunnel': False,
                           # Store bounds used for indexing/unloading
                           '_bounds': (rec[1], rec[2], rec[3], rec[4]) # min_lon, min_lat, max_lon, max_lat
                        }
                        segments_to_cache.append((osm_id, segment_data))
                        loaded_this_call += 1

                    except DecodeError as de:
                        print(f"Protobuf DecodeError at offset {offset}, size {size} in {tile_path_proto} for segment {osm_id}: {de}")
                        continue # Skip this segment
                    except Exception as e_read:
                        print(f"Error reading/parsing segment {osm_id} at offset {offset} in {tile_path_proto}: {e_read}")
                        continue # Skip this segment

            # --- Add Loaded Segments to LRU Cache ---
            for osm_id, segment_data in segments_to_cache:
                self._add_to_cache(osm_id, segment_data, tile_id)

            if loaded_this_call > 0:
                print(f"Cached {loaded_this_call} new segments from tile {tile_id}. Cache size: {len(self.segments_data)}")

            self.loaded_tiles.add(tile_id) # Mark tile index as processed
            return True

        except FileNotFoundError:
             print(f"Tile index or protobuf file not found during load: {tile_path_idx} or {tile_path_proto}")
             self.loaded_tiles.add(tile_id) # Avoid retrying
             return False
        except Exception as e:
             print(f"Error processing index/tile {tile_id}: {e}")
             # Don't mark as loaded if fundamental error occurred
             if tile_id in self.loaded_tiles: self.loaded_tiles.remove(tile_id)
             return False

    def _add_to_cache(self, osm_id, segment_data, tile_id):
        """Adds a segment to the LRU cache and R-tree, handling eviction."""
        # Add to cache (OrderedDict)
        if osm_id in self.segments_data:
            self.segments_data.move_to_end(osm_id) # Mark as recently used
        self.segments_data[osm_id] = segment_data
        self.segment_tile_map[osm_id] = tile_id

        # Add to R-tree
        try:
            segment_bounds = segment_data['_bounds'] # Use stored bounds
            self.rtree_idx.insert(osm_id, segment_bounds, obj=osm_id)
        except Exception as e_rtree:
            print(f"Warning: Failed to insert segment {osm_id} into R-tree: {e_rtree}")

        # Enforce cache size limit
        while len(self.segments_data) > self.cache_size:
            evicted_id, evicted_data = self.segments_data.popitem(last=False) # Remove oldest
            # print(f"Cache full. Evicting segment {evicted_id}") # Can be noisy
            self._remove_from_rtree(evicted_id, evicted_data)
            if evicted_id in self.segment_tile_map:
                del self.segment_tile_map[evicted_id]

    def _remove_from_rtree(self, segment_id, segment_data):
        """Removes a segment from the R-tree index."""
        try:
            segment_bounds = segment_data.get('_bounds')
            if segment_bounds:
                # Use Rtree delete method with exact ID and bounds
                self.rtree_idx.delete(segment_id, segment_bounds)
            # else: Fallback - search and delete (less efficient)
            #    items_to_delete = list(self.rtree_idx.intersection(segment_bounds, objects=True))
            #    for item in items_to_delete:
            #        if item.object == segment_id:
            #            self.rtree_idx.delete(item.id, item.bbox)
            #            break
        except Exception as e:
            # Rtree raises specific errors if ID/bounds not found, can be noisy
            # print(f"Warning: Error removing segment {segment_id} from R-tree during eviction: {e}")
            pass # Suppress R-tree deletion errors for now

    def _unload_tile(self, tile_id):
        """Unloads data for a specific tile - now primarily manages cache based on tile ID."""
        if tile_id not in self.loaded_tiles:
            return
        # print(f"Requesting unload for tile: {tile_id}")

        ids_in_tile = [seg_id for seg_id, t_id in self.segment_tile_map.items() if t_id == tile_id]

        unloaded_count = 0
        for seg_id in ids_in_tile:
            if seg_id in self.segments_data:
                segment_data = self.segments_data.pop(seg_id)
                self._remove_from_rtree(seg_id, segment_data)
                unloaded_count += 1
            if seg_id in self.segment_tile_map:
                del self.segment_tile_map[seg_id]

        # if unloaded_count > 0:
        #     print(f"Unloaded {unloaded_count} cached segments associated with tile {tile_id}. Cache size: {len(self.segments_data)}")
        self.loaded_tiles.remove(tile_id)

    def _update_loaded_tiles(self, lat, lon):
        """Determine current tile, load relevant segments using index, unload old tiles/segments."""
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

        # Load needed tiles (pass lat/lon context)
        for tile_id in tiles_to_load:
            if tile_id not in self.loaded_tiles:
                # Pass context lat/lon for index searching and path finding
                self._load_tile(tile_id, lat, lon)

        # Unload tiles no longer needed (triggers cache eviction for segments from those tiles)
        tiles_to_unload = self.loaded_tiles - tiles_to_load
        for tile_id in tiles_to_unload:
            self._unload_tile(tile_id)

        # Check cache directly first - segment might be loaded even if tile isn't "active"
        # if not self.segments_data: # This check is misleading with cache
        if len(self.segments_data) == 0:
            # print("Warning: No map data in cache, cannot get segment data.")
            return None

        current_point = Point(lon, lat)
        try:
            # Query R-tree (which mirrors the cache) for nearest segments
            search_bounds = (lon - 1e-4, lat - 1e-4, lon + 1e-4, lat + 1e-4) # Smaller search box for R-tree query
            nearest_candidates = list(self.rtree_idx.intersection(search_bounds, objects=True))

            if not nearest_candidates:
                # print("No segments found in R-tree cache near location.")
                return None

            closest_segment_info = None
            min_dist = float('inf')

            # Find the segment whose geometry is actually closest among candidates
            for item in nearest_candidates:
                segment_id = item.object
                # Check data is still loaded (robustness - less needed with LRU if accessed)
                if segment_id not in self.segments_data:
                    # This might happen if evicted between rtree query and dict access (rare)
                    # print(f"Warning: R-tree pointed to evicted segment {segment_id}")
                    continue
                # segment_info = self.segments_data[segment_id]
                # Access via get to handle potential rare race condition, and move to end for LRU
                segment_info = self.segments_data.get(segment_id)
                if segment_info is None:
                    continue # Was evicted between query and get
                self.segments_data.move_to_end(segment_id) # Mark as recently used

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

    # Manually trigger tile loading for the test location
    print(f"\nManually updating loaded tiles for Lat={test_lat}, Lon={test_lon}")
    reader._update_loaded_tiles(test_lat, test_lon)

    if len(reader.segments_data) > 0:
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
