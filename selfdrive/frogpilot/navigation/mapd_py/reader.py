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
# We need to go up 4 levels to reach the repo root (e.g. /openpilot/)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_script_dir, "../../../..")) # Corrected: up 4 levels

# Add repo root to Python path BEFORE attempting the import
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Define paths relative to the repository root found above
MAP_DATA_DIR = os.path.join(_repo_root, "map_data")
SCHEMA_DIR = os.path.join(_repo_root, "tools/map_processing")

# Constants
FROGPILOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) # Corrected: up to selfdrive/frogpilot
DEFAULT_CAPNP_PATH = os.path.join(FROGPILOT_DIR, 'capnp', 'map_data.capnp')
WAY_GEOMETRY_MAX_DIST_ERROR_M = 20.0  # Max error allowed to consider a point on the way geometry

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
    def __init__(self, cache_size: int = DEFAULT_CACHE_SIZE, worker_cpu: int | None = None):
        print("MapReader (Indexed Tiled PROTOBUF - Threaded) Initializing...")
        self.segments_data = OrderedDict()
        self.cache_size = cache_size
        self.segment_tile_map = {}
        self.rtree_idx = rtree_index.Index()
        self.loaded_tiles = set()
        self.current_region = None

        # --- Threading and Queue for Background Loading ---
        self.loading_lock = threading.Lock()
        self.load_queue = queue.Queue()
        self.queued_or_loading = set()
        self.worker_thread = threading.Thread(target=self._tile_loader_worker, daemon=True)
        self.worker_thread.start()
        # -------------------------------------------------

        # Optionally pin the tile-loader worker thread to a dedicated CPU core so it
        # doesn't contend with the MapdPyDaemon's timing-critical main loop.
        if worker_cpu is not None:
            try:
                native_id = getattr(self.worker_thread, "native_id", None)
                if native_id is not None:
                    os.sched_setaffinity(native_id, {worker_cpu})
                    print(f"MapReader: Worker thread pinned to CPU {worker_cpu} (native id={native_id}).")
            except AttributeError:
                # os.sched_setaffinity may not be available on some platforms
                print("MapReader: WARNING – CPU affinity not supported on this platform.")
            except PermissionError as e:
                # Non-root or lacking CAP_SYS_NICE/CAP_SYS_ADMIN can fail – continue gracefully
                print(f"MapReader: WARNING – Failed to set CPU affinity: {e}")
            except Exception as e:
                print(f"MapReader: Unexpected error while setting affinity: {e}")

        self._determine_initial_region()
        print(f"MapReader Initialized (Cache Size: {self.cache_size}). Ready to load tiles on demand.")

    def _determine_initial_region(self):
        print("MapReader: Determining initial region...")
        params_memory = None
        last_gps = None
        try:
            params_memory = Params("/dev/shm/params")
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

    def _get_tile_path_for_worker(self, tile_id):
        """Gets tile path. Attempts to infer region from tile ID if needed."""
        try:
            lat_part, lon_part = tile_id.split('_')
            lat_val = float(lat_part[1:]) * (1 if lat_part[0] == 'N' else -1)
            lon_val = float(lon_part[1:]) * (1 if lon_part[0] == 'E' else -1)

            determined_region = self.current_region
            if not determined_region:
                # Lock not strictly needed for read, but ensures consistency if region changes
                # with self.loading_lock: determined_region = self.current_region
                 for region, bounds in REGION_BOUNDS.items():
                      min_lon_b, min_lat_b, max_lon_b, max_lat_b = bounds
                      if min_lon_b <= lon_val <= max_lon_b and min_lat_b <= lat_val <= max_lat_b:
                          determined_region = region
                          break

            if not determined_region:
                print(f"Warning: Cannot get tile path for {tile_id}, region not determined.")
                return None

            region_base_dir = os.path.join(TILE_DATA_BASE_DIR, determined_region)
            tile_output_dir = region_base_dir # Assume no subdirs
            return os.path.join(tile_output_dir, f"{tile_id}.protobuf")

        except Exception as e:
            print(f"Error parsing tile_id '{tile_id}' for path: {e}")
            return None

    def _tile_loader_worker(self):
        """Background thread worker to load tiles from the queue."""
        print("MapReader: Tile loader worker thread started.")
        while True:
            tile_id = self.load_queue.get()
            # print(f"Worker: Processing tile {tile_id}")

            tile_path_proto = self._get_tile_path_for_worker(tile_id)
            if not tile_path_proto:
                print(f"Worker: Error - Could not construct path for tile {tile_id}")
                with self.loading_lock:
                    if tile_id in self.queued_or_loading:
                        self.queued_or_loading.remove(tile_id)
                self.load_queue.task_done()
                continue # Skip to next item in queue

            tile_path_idx = tile_path_proto.replace(".protobuf", ".idx")
            segments_to_cache_local = []
            tile_processed_successfully = False

            try:
                if not os.path.exists(tile_path_idx) or os.path.getsize(tile_path_idx) < INDEX_RECORD_SIZE:
                    tile_processed_successfully = True # Nothing to load is success
                else:
                    # Read Index Records
                    index_records = []
                    with open(tile_path_idx, 'rb') as idx_file:
                        while True:
                            record_bytes = idx_file.read(INDEX_RECORD_SIZE)
                            if not record_bytes: break
                            record = struct.unpack(INDEX_RECORD_FORMAT, record_bytes)
                            index_records.append(record)

                    if index_records:
                        # Read and Deserialize Segments
                        with open(tile_path_proto, 'rb') as proto_file:
                            for rec in index_records:
                                osm_id, _, _, _, _, offset, size = rec
                                try:
                                    proto_file.seek(offset)
                                    _ = proto_file.read(4) # Discard size prefix
                                    message_bytes = proto_file.read(size)
                                    if len(message_bytes) < size: continue

                                    segment = osm_speed_data_pb2.SpeedLimitSegment()
                                    segment.ParseFromString(message_bytes)
                                    coords = [(p.longitude, p.latitude) for p in segment.geometry]

                                    # Handle both line and point geometries
                                    if len(coords) >= 2:
                                        geom_obj = LineString(coords)
                                    elif len(coords) == 1:
                                        # Single-node geometry (e.g. speed-limit sign). Use Point so distance() works.
                                        geom_obj = Point(coords[0])
                                    else:
                                        # No coordinates → skip
                                        continue

                                    segment_data = {
                                        'id': osm_id,
                                        'speed_mps': segment.speed_limit_mps,
                                        'geom': geom_obj,
                                        'curvature_derived_speeds_mps': list(segment.curvature_derived_speeds_mps),
                                        'highway': '', 'lanes': 0, 'oneway': 0, 'name': '',
                                        'ref': '', 'surface': '', 'is_bridge': False, 'is_tunnel': False,
                                        '_bounds': (rec[1], rec[2], rec[3], rec[4])
                                    }
                                    segments_to_cache_local.append((osm_id, segment_data))
                                except (DecodeError, Exception) as e_read:
                                     # print(f"Worker: Error reading segment {osm_id} in {tile_path_proto}: {e_read}")
                                     continue # Skip bad segment
                        tile_processed_successfully = True
                    else:
                        tile_processed_successfully = True # No index records is success

            except FileNotFoundError:
                print(f"Worker: File not found for tile {tile_id}: {tile_path_idx} or {tile_path_proto}")
                tile_processed_successfully = False
            except Exception as e:
                print(f"Worker: Error processing tile {tile_id}: {e}")
                tile_processed_successfully = False

            # Update Shared State (Under Lock)
            loaded_count_for_tile = 0
            if segments_to_cache_local:
                with self.loading_lock:
                    for osm_id, segment_data in segments_to_cache_local:
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

            # Mark Tile as Processed (Under Lock)
            with self.loading_lock:
                if tile_processed_successfully:
                    self.loaded_tiles.add(tile_id)
                if tile_id in self.queued_or_loading:
                    self.queued_or_loading.remove(tile_id)

            self.load_queue.task_done()

    def request_tiles(self, tile_ids: set[str]):
        """Requests tiles to be loaded by the background worker."""
        queued_count = 0
        with self.loading_lock:
            for tile_id in tile_ids:
                if tile_id not in self.loaded_tiles and tile_id not in self.queued_or_loading:
                    self.queued_or_loading.add(tile_id)
                    self.load_queue.put(tile_id)
                    queued_count += 1
        # if queued_count > 0: print(f"MainThread: Queued {queued_count} new tiles.")

    # --- Locked Helper Methods --- (Assume lock is held by caller)
    def _add_to_cache_locked(self, osm_id, segment_data, tile_id):
        if osm_id in self.segments_data:
            self.segments_data.move_to_end(osm_id)
        self.segments_data[osm_id] = segment_data
        self.segment_tile_map[osm_id] = tile_id
        self._insert_into_rtree_locked(osm_id, segment_data)

    def _insert_into_rtree_locked(self, osm_id, segment_data):
        try:
            segment_bounds = segment_data.get('_bounds')
            if segment_bounds:
                self.rtree_idx.insert(osm_id, segment_bounds, obj=osm_id)
        except Exception as e_rtree:
            print(f"Warning: Failed to insert segment {osm_id} into R-tree: {e_rtree}")

    def _remove_from_rtree_locked(self, segment_id, segment_data):
        try:
            segment_bounds = segment_data.get('_bounds')
            if segment_bounds:
                self.rtree_idx.delete(segment_id, segment_bounds)
        except Exception as e:
            # print(f"Warning: Error removing segment {segment_id} from R-tree: {e}")
            pass

    def _unload_tile_locked(self, tile_id):
        if tile_id not in self.loaded_tiles: return
        ids_in_tile = [seg_id for seg_id, t_id in self.segment_tile_map.items() if t_id == tile_id]
        unloaded_count = 0
        for seg_id in ids_in_tile:
            if seg_id in self.segments_data:
                segment_data = self.segments_data.pop(seg_id)
                self._remove_from_rtree_locked(seg_id, segment_data)
                unloaded_count += 1
            if seg_id in self.segment_tile_map:
                del self.segment_tile_map[seg_id]
        self.loaded_tiles.remove(tile_id)
        if tile_id in self.queued_or_loading:
             self.queued_or_loading.remove(tile_id)
        # if unloaded_count > 0: print(f"MainThread: Unloaded {unloaded_count} segments for tile {tile_id}.")
    # ---------------------------

    # --- Methods potentially called by main thread ---
    def _update_loaded_tiles(self, lat, lon, bearing_rad=None):
        """Determine current/neighbor tiles, queue new ones, unload old ones."""
        # Determine region (read-only access ok without lock)
        current_point_region = None
        for region, bounds in REGION_BOUNDS.items():
             min_lon_b, min_lat_b, max_lon_b, max_lat_b = bounds
             if min_lon_b <= lon <= max_lon_b and min_lat_b <= lat <= max_lat_b:
                 current_point_region = region
                 break

        # Handle region change (needs lock for writes)
        if current_point_region != self.current_region:
            print(f"Region changed from {self.current_region} to {current_point_region}.")
            self.current_region = current_point_region # Update immediately (mostly safe)
            with self.loading_lock:
                all_tiles_before_change = list(self.loaded_tiles)
                # Clear queue safely
                while not self.load_queue.empty():
                    try: self.load_queue.get_nowait()
                    except queue.Empty: break
                self.queued_or_loading.clear()
            print(f"  Requesting unload of {len(all_tiles_before_change)} tiles due to region change.")
            for t_id in all_tiles_before_change:
                 with self.loading_lock: self._unload_tile_locked(t_id)

        if not self.current_region:
            # Handle being outside known regions (needs lock)
            with self.loading_lock:
                 loaded_tiles_list = list(self.loaded_tiles)
                 if loaded_tiles_list: print("Warning: Outside known regions, unloading remaining tiles.")
            if loaded_tiles_list:
                 for t_id in loaded_tiles_list:
                      with self.loading_lock: self._unload_tile_locked(t_id)
                 with self.loading_lock:
                    # Clear queue safely
                    while not self.load_queue.empty():
                        try: self.load_queue.get_nowait()
                        except queue.Empty: break
                    self.queued_or_loading.clear()
            return # Cannot load tiles outside known region

        # --- Calculate reactive tile grid --- Modified ---
        reactive_tiles_to_load = set()
        current_lat_idx = math.floor(lat / TILE_SIZE_DEG)
        current_lon_idx = math.floor(lon / TILE_SIZE_DEG)

        # Always include the current tile
        base_tile_lat = current_lat_idx * TILE_SIZE_DEG
        base_tile_lon = current_lon_idx * TILE_SIZE_DEG
        reactive_tiles_to_load.add(get_tile_id(base_tile_lat, base_tile_lon, TILE_SIZE_DEG))

        # Determine adjacent tiles based on bearing (if available)
        if bearing_rad is not None:
            # Normalize bearing to 0-360 degrees
            bearing_deg = (math.degrees(bearing_rad) + 360) % 360

            # Determine primary adjacent tile offsets based on quadrant
            lat_offset = 0
            lon_offset = 0
            if 0 <= bearing_deg < 90: # NE
                lat_offset = 1
                lon_offset = 1
            elif 90 <= bearing_deg < 180: # SE
                lat_offset = -1
                lon_offset = 1
            elif 180 <= bearing_deg < 270: # SW
                lat_offset = -1
                lon_offset = -1
            else: # NW (270 <= bearing_deg < 360)
                lat_offset = 1
                lon_offset = -1

            # Add the 3 tiles forming the 2x2 grid in the direction of travel
            # (Current tile is already added)
            for d_lat, d_lon in [(lat_offset, 0), (0, lon_offset), (lat_offset, lon_offset)]:
                neighbor_lat = (current_lat_idx + d_lat) * TILE_SIZE_DEG
                neighbor_lon = (current_lon_idx + d_lon) * TILE_SIZE_DEG
                reactive_tiles_to_load.add(get_tile_id(neighbor_lat, neighbor_lon, TILE_SIZE_DEG))
        else:
            # Fallback to 3x3 grid if bearing is not provided (shouldn't happen often)
            print("MapReader: Warning - Bearing not provided, falling back to 3x3 reactive grid.")
            for lat_idx_offset in [-1, 0, 1]:
                 for lon_idx_offset in [-1, 0, 1]:
                      neighbor_lat = (current_lat_idx + lat_idx_offset) * TILE_SIZE_DEG
                      neighbor_lon = (current_lon_idx + lon_idx_offset) * TILE_SIZE_DEG
                      reactive_tiles_to_load.add(get_tile_id(neighbor_lat, neighbor_lon, TILE_SIZE_DEG))
        # --- End Grid Calculation ---

        # Queue reactive tiles (handles locking internally)
        self.request_tiles(reactive_tiles_to_load)

        # Unload old tiles (needs lock)
        with self.loading_lock:
             current_loaded = set(self.loaded_tiles)
        tiles_to_unload = current_loaded - reactive_tiles_to_load
        for tile_id in tiles_to_unload:
             with self.loading_lock: self._unload_tile_locked(tile_id)

        # --- R-tree Query (Needs Lock) ---
        closest_segment_info = None
        # Expand the spatial query to ±0.002° (≈ 220 m) which comfortably
        # covers the 0.0015° (≈ 167 m) distance filter applied below while
        # remaining small enough to keep the R-tree intersection fast.
        SEARCH_RADIUS_DEG = 0.002
        search_bounds = (lon - SEARCH_RADIUS_DEG, lat - SEARCH_RADIUS_DEG,
                         lon + SEARCH_RADIUS_DEG, lat + SEARCH_RADIUS_DEG)
        with self.loading_lock: # Protect access to rtree_idx and segments_data
            try:
                nearest_candidates = list(self.rtree_idx.intersection(search_bounds, objects=True))
                if nearest_candidates:
                    min_dist = float('inf')
                    current_point = Point(lon, lat) # Create Point inside lock? Or outside? Outside is fine.
                    best_candidate_info = None

                    for item in nearest_candidates:
                        segment_id = item.object
                        segment_info = self.segments_data.get(segment_id)
                        if segment_info is None: continue

                        try:
                             distance = segment_info['geom'].distance(current_point)
                             MAX_RELEVANT_DISTANCE_DEGREES = 0.0015
                             if distance < min_dist and distance < MAX_RELEVANT_DISTANCE_DEGREES:
                                 min_dist = distance
                                 best_candidate_info = segment_info
                        except Exception as e_dist: pass # Ignore distance errors

                    # Mark the closest one found as recently used and assign for return
                    if best_candidate_info:
                         closest_segment_info = best_candidate_info
                         closest_id = best_candidate_info.get('id')
                         if closest_id: # Check if ID exists
                              self.segments_data.move_to_end(closest_id)

            except Exception as e: print(f"Error during spatial query under lock: {e}")
        return closest_segment_info

    def get_segment_coords(self, segment_id: int) -> list[tuple[float, float]] | None:
         """Safely gets coordinates for a segment ID, acquiring lock."""
         with self.loading_lock:
              segment_data = self.segments_data.get(segment_id)
              if segment_data:
                   return _get_coords_from_segment(segment_data) # Use helper
              else:
                   return None

    # Public helper ----------------------------------------------------------
    def get_segment_data_at(self, lat: float, lon: float, bearing_rad: float | None = None):
        """Return the closest segment data for a lat/lon point.

        This is a thin convenience wrapper around the internal
        `_update_loaded_tiles` method so that other modules (e.g. the
        planner or MTSC) can retrieve the same information without
        having to know about our tile-management internals.  It will:
        1. Ensure the correct tiles are queued / loaded for the supplied
           coordinate.
        2. Return the *closest* segment dictionary for the coordinate if
           one exists, or ``None`` otherwise.

        The implementation purposefully mirrors the logic already used
        by ``_update_loaded_tiles`` so the behaviour stays consistent
        across the code-base.
        """
        return self._update_loaded_tiles(lat, lon, bearing_rad)
    # -----------------------------------------------------------------------

# Helper function (can be outside class)
def _get_coords_from_segment(segment_data: dict) -> list[tuple[float, float]]:
    """Extracts node coordinates as (lat, lon) tuples from segment geom."""
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
