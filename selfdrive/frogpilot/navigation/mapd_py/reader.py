import os
import capnp
import math
import sys
from rtree import index # For spatial indexing
from shapely.geometry import Point, LineString # For geometry operations

# Ensure the current directory is in the path for importing the compiled schema module
# script_dir_path = os.path.dirname(__file__)
# if script_dir_path not in sys.path:
#     sys.path.insert(0, script_dir_path)

# Define path to our custom capnp file and schema relative to openpilot root
# Adjust these paths if necessary
DEFAULT_SPEED_LIMIT_DATA_PATH = "map_data/nevada-speedlimits.capnp" # Hardcoded for now
SCHEMA_PATH = "tools/map_processing/osm_speed_data.capnp"

# Load our custom Cap'n Proto schema
try:
    osm_speed_data_capnp = capnp.load(SCHEMA_PATH)
except Exception as e:
    print(f"Fatal Error: Could not load speed limit schema '{SCHEMA_PATH}': {e}")
    # Depending on context, might want sys.exit(1) or raise
    # Create a dummy if needed for basic operation
    osm_speed_data_capnp = None # Indicate failure

# Remove old helper functions
# def get_bounds_filename(...)
# def find_area_box(...)

class MapReader:
    def __init__(self, data_path=DEFAULT_SPEED_LIMIT_DATA_PATH):
        self.data_path = data_path
        self.segments_data = [] # Store segment data (e.g., {id: osm_id, speed: mps, geom: LineString})
        self.idx = index.Index() # R-tree spatial index

        if osm_speed_data_capnp is None:
            print("Error: Speed limit schema not loaded. MapReader will be non-functional.")
            return # Cannot proceed without schema

        self._load_and_index_data()

    def _load_and_index_data(self):
        print(f"Attempting to load streamed speed limit data from: {self.data_path}")
        segment_count = 0 # Initialize counter
        try:
            with open(self.data_path, 'rb') as f:
                # Wrap the file handle in a PackedInputStream using the correct path
                stream = capnp.lib.capnp.PackedInputStream(f)
                print("Reading segments sequentially using PackedInputStream and building spatial index...")

                # Iterate through messages loaded from the stream
                # Use enumerate to get the index for R-tree insertion
                for i, segment in enumerate(stream.iter_load(osm_speed_data_capnp.SpeedLimitSegment, traversal_limit_in_words=2**63-1)):
                    # Remove the manual try/except EOFError/Exception for reading here, as iter_load handles it.

                    # Convert Cap'n Proto points to Shapely LineString
                    coords = [(p.longitude, p.latitude) for p in segment.geometry]
                    if len(coords) < 2:
                        # print(f"Warning: Skipping segment {i} with < 2 coordinates.")
                        continue # Skip invalid geometries
                    line = LineString(coords)

                    # Read curvatures (convert from capnp list reader to Python list)
                    segment_curvatures = list(segment.curvatures) if segment.curvatures else []

                    # Store segment info for later retrieval
                    segment_info = {
                        'id': segment.osmWayId,
                        'speed_mps': segment.speedLimitMps,
                        'geom': line,
                        'curvatures': segment_curvatures,
                        'highway': segment.highwayType,
                        'lanes': segment.lanes,
                        'oneway': segment.oneway,
                        'name': segment.name,
                        'ref': segment.ref,
                        'surface': segment.surface,
                        'is_bridge': segment.isBridge,
                        'is_tunnel': segment.isTunnel,
                    }
                    # Use index `i` from enumerate for self.segments_data
                    self.segments_data.append(segment_info)

                    # Insert into R-tree index using index `i`
                    self.idx.insert(i, line.bounds)

                    segment_count = i + 1 # Keep track of the count for final message

                    # Optional: Add progress indicator if loading takes long
                    if segment_count % 50000 == 0:
                        print(f"  ... processed {segment_count} segments ...")

            print(f"Spatial index built successfully with {segment_count} segments.")

        except FileNotFoundError:
            print(f"Error: Speed limit data file not found: {self.data_path}")
            # Handle error appropriately - maybe raise or log
        except Exception as e:
            print(f"Error reading or indexing speed limit data {self.data_path}: {e}")
            # Handle error appropriately

    def get_segment_data_at(self, lat, lon):
        """
        Finds the closest map segment to the given coordinates and returns its data.
        Returns a dictionary: {'id': osm_id, 'speed_mps': speed, 'geom': LineString, ['curvatures': list_of_floats]}
        Returns None if no data is loaded or no segment is found nearby.
        """
        if not self.segments_data:
             print("Warning: No map data loaded, cannot get segment data.")
             return None # No data loaded

        current_point = Point(lon, lat)

        # print(f"Querying segment data for Lat={lat}, Lon={lon}") # Debug
        try:
            # Query index for nearest bounding box. Increase num_results if needed.
            # Using 1 for now, assuming we only care about the single closest way
            nearest_indices = list(self.idx.nearest((lon, lat, lon, lat), 1))
            if not nearest_indices:
                # print("No nearby segments found in R-tree.") # Debug
                return None # No segments nearby

            # Find the segment whose geometry is actually closest to the point
            # Since we query for 1 nearest, we just check that one if needed,
            # but usually the R-tree nearest is sufficient unless geometries overlap significantly.
            closest_segment_info = None
            min_dist = float('inf')

            # We only expect one index from nearest(..., 1)
            if nearest_indices:
                index = nearest_indices[0]
                segment_info = self.segments_data[index]
                distance = segment_info['geom'].distance(current_point)

                # Optional: Add a threshold for max distance?
                MAX_RELEVANT_DISTANCE_DEGREES = 0.001 # Approx 111m at equator. Tune this.
                if distance < MAX_RELEVANT_DISTANCE_DEGREES:
                    closest_segment_info = segment_info
                    # print(f"Found closest segment {closest_segment_info['id']} at distance {distance:.6f}") # Debug
                # else:
                    # print(f"Nearest segment distance {distance:.6f} > threshold {MAX_RELEVANT_DISTANCE_DEGREES}") # Debug

            return closest_segment_info # Return the whole dict or None

        except Exception as e:
            print(f"Error during spatial query: {e}")
            return None

    # Remove old load_map_data method
    # def load_map_data(self, lat, lon):
    #     ...

# Example usage section (modified for new structure)
if __name__ == '__main__':
    print("\n--- Testing Custom MapReader ---")

    # Check if schema loaded
    if osm_speed_data_capnp is None:
        print("Schema failed to load. Exiting test.")
        sys.exit(1)

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
    reader = MapReader(data_path=test_data_path)

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