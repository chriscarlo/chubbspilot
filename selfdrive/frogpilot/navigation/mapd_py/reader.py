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
import threading # Added for background loading
import queue     # Added for background loading
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
        self.loaded_tiles = set() # Tracks which TILE INDICES have been loaded
        self.current_region = None

        # --- Threading and Queue for Background Loading ---
        self.loading_lock = threading.Lock()
        self.load_queue = queue.Queue()
        self.queued_or_loading = set() # Track tiles requested but not yet fully loaded
        self.worker_thread = threading.Thread(target=self._tile_loader_worker, daemon=True)
        self.worker_thread.start()
        # -------------------------------------------------

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
        """DEPRECATED: Logic moved to _tile_loader_worker. Use request_tiles instead."""
        # This method should no longer be called directly by the main thread.
        # The worker thread handles the loading logic.
        print(f"Warning: _load_tile called directly for {tile_id}. This should not happen.")
        # Optionally, queue it if called unexpectedly?
        # self.request_tiles({tile_id})
        return False # Indicate loading is handled elsewhere

    def _tile_loader_worker(self):
        """Background thread worker to load tiles from the queue."""
        print("MapReader: Tile loader worker thread started.")
        while True:
            tile_id = self.load_queue.get() # Blocks until a tile ID is available
            # print(f"Worker: Processing tile {tile_id}")

            # Determine path for both protobuf and index file
            # We need lat/lon context. How to get this reliably?
            # Maybe the queue item should be (tile_id, lat_context, lon_context)?
            # For now, let's assume _get_tile_path can work without perfect context
            # or we modify _get_tile_path logic slightly.
            # Let's try getting context from a recently processed point (if available)
            # This is imperfect. A better way is needed.
            # TEMP HACK: Use placeholder coords if none readily available.
            # A better solution: Pass context through the queue, or make _get_tile_path robust.
            # Let's make _get_tile_path potentially determine region based on tile ID if needed.
            tile_path_proto = self._get_tile_path_for_worker(tile_id) # Modified path getter
            if not tile_path_proto:
                print(f"Worker: Error - Could not construct path for tile {tile_id}")
                with self.loading_lock:
                    if tile_id in self.queued_or_loading: self.queued_or_loading.remove(tile_id)
                self.load_queue.task_done()
                continue

            tile_path_idx = tile_path_proto.replace(".protobuf", ".idx")

            segments_to_cache_local = [] # Store locally before acquiring lock
            tile_processed_successfully = False

            try:
                # Check if index file exists and is not empty
                if not os.path.exists(tile_path_idx) or os.path.getsize(tile_path_idx) < INDEX_RECORD_SIZE:
                    # print(f"Worker: Index file not found or empty for tile {tile_id}")
                    tile_processed_successfully = True # Nothing to load is success
                else:
                    # --- Read Index Records --- (Same as before)
                    index_records = []
                    with open(tile_path_idx, 'rb') as idx_file:
                        while True:
                            record_bytes = idx_file.read(INDEX_RECORD_SIZE)
                            if not record_bytes or len(record_bytes) < INDEX_RECORD_SIZE:
                                break
                            record = struct.unpack(INDEX_RECORD_FORMAT, record_bytes)
                            index_records.append(record)

                    if index_records:
                        # Process ALL records from the index (check cache *inside* lock later)
                        candidate_records = index_records # Load all, check cache with lock

                        # --- Read and Deserialize Segments --- (Same as before)
                        with open(tile_path_proto, 'rb') as proto_file:
                            for rec in candidate_records:
                                osm_id, _, _, _, _, offset, size = rec
                                try:
                                    proto_file.seek(offset)
                                    _ = proto_file.read(4)
                                    message_bytes = proto_file.read(size)
                                    # ... rest of parsing ...
                                    segment = osm_speed_data_pb2.SpeedLimitSegment()
                                    segment.ParseFromString(message_bytes)
                                    coords = [(p.longitude, p.latitude) for p in segment.geometry]
                                    if len(coords) < 2: continue
                                    line = LineString(coords)
                                    segment_data = {
                                        # ... (populate segment_data dict identically)
                                        'id': osm_id,
                                        'speed_mps': segment.speed_limit_mps,
                                        'geom': line,
                                        'curvatures': list(segment.curvatures),
                                        'highway': '', 'lanes': 0, 'oneway': 0, 'name': '',
                                        'ref': '', 'surface': '', 'is_bridge': False, 'is_tunnel': False,
                                        '_bounds': (rec[1], rec[2], rec[3], rec[4])
                                    }
                                    segments_to_cache_local.append((osm_id, segment_data))
                                except (DecodeError, Exception) as e_read:
                                     # print(f"Worker: Error reading segment {osm_id} in {tile_path_proto}: {e_read}")
                                     continue # Skip this segment
                        tile_processed_successfully = True
                    else:
                        # print(f"Worker: No index records found in {tile_path_idx}")
                        tile_processed_successfully = True # No records is success

            except FileNotFoundError:
                print(f"Worker: File not found for tile {tile_id}: {tile_path_idx} or {tile_path_proto}")
                # Keep it in queued_or_loading so we don't retry?
                # Or remove it to allow retrying later? Let's remove for now.
                tile_processed_successfully = False
            except Exception as e:
                print(f"Worker: Error processing tile {tile_id}: {e}")
                tile_processed_successfully = False

            # --- Update Shared State (Cache, R-tree, Sets) --- (Under Lock) ---
            loaded_count_for_tile = 0
            if segments_to_cache_local:
                with self.loading_lock:
                    for osm_id, segment_data in segments_to_cache_local:
                        # Only add if not already present (avoids overwriting if loaded via another tile)
                        # And ensures eviction logic works correctly based on current cache state
                        if osm_id not in self.segments_data:
                             self._add_to_cache_locked(osm_id, segment_data, tile_id)
                             loaded_count_for_tile += 1
                    # Enforce cache size limit after adding
                    while len(self.segments_data) > self.cache_size:
                         evicted_id, evicted_data = self.segments_data.popitem(last=False)
                         self._remove_from_rtree_locked(evicted_id, evicted_data)
                         if evicted_id in self.segment_tile_map:
                              del self.segment_tile_map[evicted_id]

                if loaded_count_for_tile > 0:
                     print(f"Worker: Cached {loaded_count_for_tile} new segments from tile {tile_id}. Cache size: {len(self.segments_data)}")

            # --- Mark Tile as Processed (Under Lock) ---
            with self.loading_lock:
                if tile_processed_successfully:
                    self.loaded_tiles.add(tile_id)
                # Always remove from queued_or_loading set once processing attempt is done
                if tile_id in self.queued_or_loading:
                    self.queued_or_loading.remove(tile_id)

            self.load_queue.task_done() # Signal completion for this item

    def _get_tile_path_for_worker(self, tile_id):
        """Gets tile path. Attempts to infer region from tile ID if needed."""
        # Example tile ID: N38.7_W120.6
        try:
            lat_part, lon_part = tile_id.split('_')
            lat_val = float(lat_part[1:]) * (1 if lat_part[0] == 'N' else -1)
            lon_val = float(lon_part[1:]) * (1 if lon_part[0] == 'E' else -1)

            # Use these extracted coords to find region if necessary
            determined_region = self.current_region
            if not determined_region:
                 # Acquiring lock here might be slow/contentious? Try without first.
                 # with self.loading_lock: current_region = self.current_region
                 for region, bounds in REGION_BOUNDS.items():
                      min_lon_b, min_lat_b, max_lon_b, max_lat_b = bounds
                      if min_lon_b <= lon_val <= max_lon_b and min_lat_b <= lat_val <= max_lat_b:
                          determined_region = region
                          # Optionally update self.current_region here? Needs lock.
                          break

            if not determined_region:
                print(f"Warning: Cannot get tile path for {tile_id}, region not determined.")
                return None

            region_base_dir = os.path.join(TILE_DATA_BASE_DIR, determined_region)
            # Assume no subdirs for simplicity in worker path finding
            tile_output_dir = region_base_dir
            return os.path.join(tile_output_dir, f"{tile_id}.protobuf")

        except Exception as e:
            print(f"Error parsing tile_id '{tile_id}' for path: {e}")
            return None

    def request_tiles(self, tile_ids: set[str]):
        """Requests tiles to be loaded by the background worker."""
        queued_count = 0
        with self.loading_lock:
            for tile_id in tile_ids:
                if tile_id not in self.loaded_tiles and tile_id not in self.queued_or_loading:
                    self.queued_or_loading.add(tile_id)
                    self.load_queue.put(tile_id)
                    queued_count += 1
        # if queued_count > 0:
        #     print(f"MainThread: Queued {queued_count} new tiles for loading.")

    # --- Locked Helper Methods --- (Assume lock is held by caller)
    def _add_to_cache_locked(self, osm_id, segment_data, tile_id):
        """Adds a segment to cache/R-tree. Assumes lock is held."""
        # Add to cache (OrderedDict)
        if osm_id in self.segments_data:
            self.segments_data.move_to_end(osm_id) # Mark as recently used
        self.segments_data[osm_id] = segment_data
        self.segment_tile_map[osm_id] = tile_id
        self._insert_into_rtree_locked(osm_id, segment_data)

    def _insert_into_rtree_locked(self, osm_id, segment_data):
        """Inserts into R-tree. Assumes lock is held."""
        try:
            segment_bounds = segment_data.get('_bounds')
            if segment_bounds:
                self.rtree_idx.insert(osm_id, segment_bounds, obj=osm_id)
        except Exception as e_rtree:
            print(f"Warning: Failed to insert segment {osm_id} into R-tree: {e_rtree}")

    def _remove_from_rtree_locked(self, segment_id, segment_data):
        """Removes a segment from R-tree. Assumes lock is held."""
        try:
            segment_bounds = segment_data.get('_bounds')
            if segment_bounds:
                self.rtree_idx.delete(segment_id, segment_bounds)
        except Exception as e:
            # Rtree raises specific errors if ID/bounds not found, can be noisy
            # print(f"Warning: Error removing segment {segment_id} from R-tree during eviction: {e}")
            pass

    def _unload_tile_locked(self, tile_id):
        """Unloads data for a specific tile. Assumes lock is held."""
        # Assumes lock is held by caller (_update_loaded_tiles)
        if tile_id not in self.loaded_tiles:
            return

        ids_in_tile = [seg_id for seg_id, t_id in self.segment_tile_map.items() if t_id == tile_id]
        unloaded_count = 0
        for seg_id in ids_in_tile:
            if seg_id in self.segments_data:
                segment_data = self.segments_data.pop(seg_id)
                self._remove_from_rtree_locked(seg_id, segment_data)
                unloaded_count += 1
            if seg_id in self.segment_tile_map:
                del self.segment_tile_map[seg_id]

        # if unloaded_count > 0:
        #     print(f"MainThread: Unloaded {unloaded_count} segments for tile {tile_id}. Cache size: {len(self.segments_data)}")
        self.loaded_tiles.remove(tile_id)
        # Also remove from queued_or_loading if it was there (e.g., queued then immediately unloaded)
        if tile_id in self.queued_or_loading:
             self.queued_or_loading.remove(tile_id)
    # ---------------------------

    # --- Methods potentially called by main thread --- (Need locking for shared data access)
    def _update_loaded_tiles(self, lat, lon):
        """Determine current/neighbor tiles, queue new ones, unload old ones."""
        # Determine current region (outside lock - read only access to REGION_BOUNDS)
        current_point_region = None
        for region, bounds in REGION_BOUNDS.items():
             min_lon_b, min_lat_b, max_lon_b, max_lat_b = bounds
             if min_lon_b <= lon <= max_lon_b and min_lat_b <= lat <= max_lat_b:
                 current_point_region = region
                 break

        region_changed = False
        # Update shared self.current_region carefully (optional lock, but infrequent write)
        # Let's skip locking here for simplicity, assuming region changes are rare.
        if current_point_region != self.current_region:
            print(f"Region changed from {self.current_region} to {current_point_region}.")
            region_changed = True
            self.current_region = current_point_region
            # TODO: Handle region change - unload *all* tiles?
            # Need to acquire lock to modify loaded_tiles and call unload
            with self.loading_lock:
                all_tiles_before_change = list(self.loaded_tiles)
            print(f"  Requesting unload of {len(all_tiles_before_change)} tiles due to region change.")
            for t_id in all_tiles_before_change:
                 # Acquire lock for each unload call
                 with self.loading_lock:
                      self._unload_tile_locked(t_id)
            # Clear the queue as well?
            with self.load_queue.mutex:
                 self.load_queue.queue.clear()
            with self.loading_lock:
                 self.queued_or_loading.clear()


        if not self.current_region:
            # Ensure everything is unloaded if we are outside known regions
            # Similar logic as region change, check if tiles are loaded first
            with self.loading_lock:
                 if self.loaded_tiles:
                      print("Warning: Outside known regions, unloading remaining tiles.")
                      all_tiles = list(self.loaded_tiles)
                 else:
                      all_tiles = []
            if all_tiles:
                for t_id in all_tiles:
                    with self.loading_lock:
                         self._unload_tile_locked(t_id)
                # Clear queue too
                with self.load_queue.mutex:
                     self.load_queue.queue.clear()
                with self.loading_lock:
                     self.queued_or_loading.clear()
            return # Cannot load tiles outside known region

        # Calculate current tile ID and neighbors (3x3 grid)
        current_tile_id = get_tile_id(lat, lon, TILE_SIZE_DEG)
        reactive_tiles_to_load = set()
        current_lat_idx = math.floor(lat / TILE_SIZE_DEG)
        current_lon_idx = math.floor(lon / TILE_SIZE_DEG)
        for lat_idx_offset in [-1, 0, 1]:
             for lon_idx_offset in [-1, 0, 1]:
                  # ... (neighbor calculation as before)
                  neighbor_lat = (current_lat_idx + lat_idx_offset) * TILE_SIZE_DEG
                  neighbor_lon = (current_lon_idx + lon_idx_offset) * TILE_SIZE_DEG
                  reactive_tiles_to_load.add(get_tile_id(neighbor_lat, neighbor_lon, TILE_SIZE_DEG))

        # --- Queue Tiles for Loading --- (uses request_tiles which handles locking)
        self.request_tiles(reactive_tiles_to_load)

        # --- Unload Tiles No Longer Needed --- (acquire lock inside loop)
        with self.loading_lock:
             # Determine tiles to unload based on *currently loaded* set
             current_loaded = set(self.loaded_tiles) # Copy loaded set under lock
        tiles_to_unload = current_loaded - reactive_tiles_to_load
        if tiles_to_unload:
            # print(f"MainThread: Requesting unload for tiles: {tiles_to_unload}")
            for tile_id in tiles_to_unload:
                 # Acquire lock for each unload
                 with self.loading_lock:
                      self._unload_tile_locked(tile_id)

        # --- R-tree Query (Needs Lock) ---
        # The spatial query itself should happen here in the main thread,
        # operating on the *current* state of the R-tree.
        closest_segment_info = None
        current_point = Point(lon, lat)
        search_bounds = (lon - 1e-4, lat - 1e-4, lon + 1e-4, lat + 1e-4)

        with self.loading_lock: # Protect access to rtree_idx and segments_data
            try:
                nearest_candidates = list(self.rtree_idx.intersection(search_bounds, objects=True))
                if nearest_candidates:
                    min_dist = float('inf')
                    # Find the segment whose geometry is actually closest among candidates
                    for item in nearest_candidates:
                        segment_id = item.object
                        # Check data is still loaded (robustness)
                        segment_info = self.segments_data.get(segment_id)
                        if segment_info is None:
                            continue # Was evicted between query and get

                        # Use shapely distance (can be done outside lock if geom is copied? No, keep simple)
                        try:
                             distance = segment_info['geom'].distance(current_point)
                             # Optional: Add a threshold for max distance?
                             MAX_RELEVANT_DISTANCE_DEGREES = 0.0015
                             if distance < min_dist and distance < MAX_RELEVANT_DISTANCE_DEGREES:
                                 min_dist = distance
                                 closest_segment_info = segment_info # Keep ref while holding lock
                                 # Mark as recently used *only if* it's the closest candidate?
                                 # Or mark all candidates accessed? Let's mark the best one.
                        except Exception as e_dist:
                            # print(f"Warn: Error calculating distance for segment {segment_id}: {e_dist}")
                            pass # Ignore segments causing distance errors

                    # Mark the closest one found as recently used
                    if closest_segment_info:
                         closest_id = closest_segment_info.get('id')
                         if closest_id and closest_id in self.segments_data:
                              self.segments_data.move_to_end(closest_id)

            except Exception as e:
                 print(f"Error during spatial query under lock: {e}")

        # Return the *data* of the closest segment found (copy? or ref?)
        # Returning the dict ref should be okay as long as caller doesn't modify it deeply.
        return closest_segment_info

    def get_segment_coords(self, segment_id: int) -> list[tuple[float, float]] | None:
         """Safely gets coordinates for a segment ID, acquiring lock."""
         with self.loading_lock:
              segment_data = self.segments_data.get(segment_id)
              if segment_data:
                   # Use helper that doesn't need lock
                   return _get_coords_from_segment(segment_data)
              else:
                   return None

# Helper function (can be outside class)
def _get_coords_from_segment(segment_data: dict) -> list[tuple[float, float]]:
    """Extracts node coordinates as (lat, lon) tuples from segment geom."""
    # ... (identical implementation as before)
    if not segment_data or 'geom' not in segment_data:
        return []
    geom = segment_data['geom']
    if not hasattr(geom, 'coords'):
        return []
    return [(coord[1], coord[0]) for coord in geom.coords]

# Example usage section remains the same...
if __name__ == '__main__':
    # ... (test code mostly unchanged, but won't reflect threading well)
    pass
