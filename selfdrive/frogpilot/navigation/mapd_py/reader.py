import os
import capnp
import math

# Assuming the schema is compiled and available relative to this path or in PYTHONPATH
# Adjust the import path as necessary based on where the compiled schema file (offline_capnp.py) will reside.
# It might need to be generated first using 'capnp compile -opy' on the offline.capnp file from the mapd_source directory.
# For now, let's assume it's generated in the same directory as this reader.py.
try:
    # Attempt to import the generated Cap'n Proto schema
    # This requires 'offline_capnp_cython.so' (or similar) to exist in the Python path,
    # generated via 'capnp compile' with cython plugin and 'python setup_capnp.py build_ext --inplace'.
    import offline_capnp_cython as offline_capnp
except ImportError:
    print("Warning: offline_capnp_cython Python schema module not found.")
    print("Please generate it from 'selfdrive/frogpilot/navigation/mapd_py/offline.capnp' using:")
    print("  capnp compile -I<path_to_pycapnp_includes> -o<path_to_capnpc_cython>:. offline.capnp")
    print("  capnp compile -I<path_to_pycapnp_includes> -oc++:. offline.capnp")
    print("  python setup_capnp.py build_ext --inplace")
    print("Providing a dummy schema to allow development to proceed.")
    # Provide a dummy class if import fails to avoid errors during development
    class DummyOffline:
        minLat = 0.0
        minLon = 0.0
        ways = []
        @staticmethod
        def read_packed(f):
            print("Dummy read_packed called")
            return None # Return None or a dummy object matching the schema structure
    # Alias the dummy under the expected name for the rest of the code
    offline_capnp = type('obj', (object,), {'Offline': DummyOffline})()


# Define constants based on the Go code (generate_offline.go and mapd.go)
AREA_BOX_DEGREES = 0.25  # Degrees for individual area files (Actual observed value)
# GROUP_AREA_BOX_DEGREES = 10.0 # Degrees for grouping area files into directories (Seems unused in lookup?)
BOUNDS_DIR = "/data/media/0/osm/offline" # Correct path based on generate_offline.go and UI code


def get_bounds_filename(lat, lon, min_lat_box, min_lon_box, max_lat_box, max_lon_box):
    """Constructs the filename and path.
    Directory path uses 1.0 degree floor(lat), floor(lon).
    Filename uses the precise 0.25 degree box bounds.
    """
    # Directory based on 1.0 degree floor of original coords
    lat_dir = int(math.floor(lat))
    lon_dir = int(math.floor(lon))
    # Filename based on the calculated 0.25 degree box bounds
    # Use a consistent format specifier for precision, matching observed files
    filename = f"{min_lat_box:.6f}_{min_lon_box:.6f}_{max_lat_box:.6f}_{max_lon_box:.6f}.bin"
    return os.path.join(BOUNDS_DIR, str(lat_dir), str(lon_dir), filename)

def find_area_box(lat, lon):
    """Determine the 0.25 degree bounding box file coordinates."""
    min_lat = math.floor(lat / AREA_BOX_DEGREES) * AREA_BOX_DEGREES
    min_lon = math.floor(lon / AREA_BOX_DEGREES) * AREA_BOX_DEGREES
    max_lat = min_lat + AREA_BOX_DEGREES
    max_lon = min_lon + AREA_BOX_DEGREES
    return min_lat, min_lon, max_lat, max_lon

class MapReader:
    def __init__(self, bounds_dir=BOUNDS_DIR):
        self.bounds_dir = bounds_dir
        self.current_offline_data = None
        self.current_filename = None
        # Ensure the capnp library is loaded
        capnp.remove_import_hook() # Recommended practice if using pycapnp dynamically

    def load_map_data(self, lat, lon):
        """
        Finds and loads the appropriate map data file based on GPS coordinates.
        Returns the parsed Cap'n Proto Offline object.
        Caches the loaded data to avoid redundant reads.
        """
        min_lat, min_lon, max_lat, max_lon = find_area_box(lat, lon)
        # Pass original lat/lon too for directory calculation
        filename = get_bounds_filename(lat, lon, min_lat, min_lon, max_lat, max_lon)

        # Check cache first
        if filename == self.current_filename and self.current_offline_data is not None:
            # print(f"Using cached map data: {filename}") # Optional: for debugging
            return self.current_offline_data

        # print(f"Attempting to load map data from: {filename}") # Optional: for debugging
        try:
            # Ensure parent directories exist before trying to open file
            # This might not be necessary if the generator guarantees structure
            # os.makedirs(os.path.dirname(filename), exist_ok=True)

            with open(filename, 'rb') as f:
                # Use read_packed for compressed capnp data
                offline_data = offline_capnp.Offline.read_packed(f)
                self.current_offline_data = offline_data
                self.current_filename = filename
                # print(f"Successfully loaded map data: {filename}") # Optional: for debugging
                return offline_data
        except FileNotFoundError:
            # This is expected if the map area hasn't been downloaded/generated
            # print(f"Map data file not found: {filename}")
            self.current_offline_data = None
            self.current_filename = None
            return None
        except Exception as e:
            # Catch other potential errors (permissions, capnp decoding issues, etc.)
            print(f"Error reading map data file {filename}: {e}")
            self.current_offline_data = None
            self.current_filename = None
            return None

# Example usage section
if __name__ == '__main__':
    # Note: Generating the schema requires the 'capnp' command-line tool
    # and the 'offline.capnp' file from the mapd_source directory.
    script_dir = os.path.dirname(__file__)
    # Check for the compiled module, not the .py file
    module_ext = '.so' # Simplification, actual extension varies
    schema_module_found = any(f.startswith('offline_capnp_cython') and f.endswith(module_ext) for f in os.listdir(script_dir))
    schema_capnp_abs_path = os.path.abspath(os.path.join(script_dir, 'offline.capnp'))


    # We don't generate a .py file anymore, so checking for it isn't useful.
    # Instead, we check if the module was found above.
    if not schema_module_found:
        print(f"Compiled schema module 'offline_capnp_cython*.so' not found.")
        if os.path.exists(schema_capnp_abs_path):
            print(f"Attempting to generate schema from '{schema_capnp_abs_path}'...")
            # We can't easily replicate the multi-step build process here.
            # Provide instructions instead.
            print("\\n--- Schema Generation Instructions ---")
            print("Please run the following commands in this directory:")
            print("1. Find pycapnp include path (e.g., /path/to/site-packages/capnp)")
            print("   $ python -c \"import capnp; import os; print(os.path.dirname(capnp.__file__))\"")
            print("2. Find capnpc-cython plugin path (e.g., /path/to/bin/capnpc-cython)")
            print("   $ which capnpc-cython")
            print("3. Compile Cython sources:")
            print("   $ capnp compile -I<include_path> -o<plugin_path>:. offline.capnp")
            print("4. Compile C++ sources:")
            print("   $ capnp compile -I<include_path> -oc++:. offline.capnp")
            print("5. Build the Python extension module:")
            print("   $ python setup_capnp.py build_ext --inplace")
            print("--- End Instructions ---\\n")

            # Exit or handle inability to auto-generate gracefully
            print("Cannot automatically generate schema here. Please follow instructions above.")
            # We might still try to import the dummy below, but generation won't happen.

        else:
            print(f"Original schema file '{schema_capnp_abs_path}' not found. Cannot generate Python schema.")


    # Reload the module to ensure the potentially newly generated schema is used
    try:
        import importlib
        # Ensure the top-level package structure is recognized if running as script
        if __package__ is None or __package__ == '':
             # If run directly, adjust path to allow relative import (might not always work)
             import sys
             sys.path.insert(0, os.path.abspath(os.path.join(script_dir, '.'))) # Add current dir
             import offline_capnp_cython as offline_capnp # Import with alias
        else:
             # This relative import might need adjustment depending on final structure
             from . import offline_capnp_cython as offline_capnp # Import with alias
        importlib.reload(offline_capnp)
    except ImportError:
        print("Could not import or reload offline_capnp_cython schema.")
        # Attempt to use the dummy if import failed
        if 'offline_capnp' not in locals() or not hasattr(offline_capnp, 'Offline'):
             print("Falling back to dummy schema defined earlier.")
             # Re-define/ensure dummy is aliased if initial import failed completely
             class DummyOffline:
                 minLat = 0.0
                 minLon = 0.0
                 ways = []
                 @staticmethod
                 def read_packed(f):
                     print("Dummy read_packed called")
                     return None
             offline_capnp = type('obj', (object,), {'Offline': DummyOffline})()

    except NameError:
        # offline_capnp might not be defined if initial import and generation failed
        print("offline_capnp_cython not defined, likely import failed.")
        if 'offline_capnp' not in locals() or not hasattr(offline_capnp, 'Offline'):
             print("Falling back to dummy schema defined earlier.")
             class DummyOffline:
                 minLat = 0.0
                 minLon = 0.0
                 ways = []
                 @staticmethod
                 def read_packed(f):
                     print("Dummy read_packed called")
                     return None
             offline_capnp = type('obj', (object,), {'Offline': DummyOffline})()


    # Example: Somewhere in California within an existing tile
    # Tile 34/-118 contains 34.000000_-118.000000_34.250000_-117.750000.bin
    test_lat = 34.1
    test_lon = -117.9

    print(f"\nTesting MapReader with coordinates: Lat={test_lat}, Lon={test_lon}")
    reader = MapReader()
    map_data = reader.load_map_data(test_lat, test_lon)

    if map_data:
        print(f"Successfully loaded map data.")
        print(f"  Area Bounds: MinLat={map_data.minLat:.4f}, MinLon={map_data.minLon:.4f}, MaxLat={map_data.maxLat:.4f}, MaxLon={map_data.maxLon:.4f}")
        ways = map_data.ways
        print(f"  Number of ways in this area: {len(ways)}")
        if len(ways) > 0:
             # Accessing fields safely using try-except or checking existence might be needed depending on schema generation
             try:
                 print(f"  Example Way 0 Name: '{ways[0].name}'")
             except Exception as e:
                 print(f"  Could not access Way 0 Name: {e}")
             try:
                 print(f"  Example Way 0 Nodes Count: {len(ways[0].nodes)}")
             except Exception as e:
                 print(f"  Could not access Way 0 Nodes: {e}")
    else:
        print("Failed to load map data for the given coordinates. (This might be normal if the file doesn't exist)." )
        # Double check the expected path based on the coordinates:
        min_lat_test, min_lon_test, max_lat_test, max_lon_test = find_area_box(test_lat, test_lon)
        expected_file = get_bounds_filename(test_lat, test_lon, min_lat_test, min_lon_test, max_lat_test, max_lon_test)
        print(f"  (Checked path: {expected_file})")