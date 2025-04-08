import os
import capnp
import math

# Assuming the schema is compiled and available relative to this path or in PYTHONPATH
# Adjust the import path as necessary based on where the compiled schema file (offline_capnp.py) will reside.
# It might need to be generated first using 'capnp compile -opy' on the offline.capnp file from the mapd_source directory.
# For now, let's assume it's generated in the same directory as this reader.py.
try:
    # Attempt to import the generated Cap'n Proto schema
    # This requires 'offline_capnp.py' to exist in the Python path.
    # Generate it from mapd_source/offline.capnp using:
    # capnp compile -I/path/to/capnp/include -I. --src-prefix=../.. -opy offline.capnp
    # Or more simply (if capnp tool finds schema includes):
    # cd selfdrive/frogpilot/navigation/mapd_source && capnp compile -opy offline.capnp -o ../mapd_py/offline_capnp.py
    import offline_capnp
except ImportError:
    print("Warning: offline_capnp Python schema not found.")
    print("Please generate it from 'selfdrive/frogpilot/navigation/mapd_source/offline.capnp' using:")
    print("  capnp compile -opy offline.capnp -o path/to/mapd_py/offline_capnp.py")
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
    offline_capnp = type('obj', (object,), {'Offline': DummyOffline})()


# Define constants based on the Go code (generate_offline.go and mapd.go)
AREA_BOX_DEGREES = 1.0  # Degrees for individual area files
# GROUP_AREA_BOX_DEGREES = 10.0 # Degrees for grouping area files into directories (Seems unused in lookup?)
BOUNDS_DIR = "/data/media/0/osm/offline" # Correct path based on generate_offline.go and UI code


def get_bounds_filename(min_lat, min_lon, max_lat, max_lon):
    # Mimics GenerateBoundsFileName from generate_offline.go but uses the simpler directory structure seen in FindWaysAroundLocation
    # Note: The Go code has two different directory structures mentioned. FindWaysAroundLocation seems simpler.
    # We might need to adjust this based on how the bounds files are actually generated and stored.
    # Assuming the structure used by FindWaysAroundLocation: BOUNDS_DIR/lat/lon/file.bin
    # Let's stick to the naming convention used in generate_offline.go for the filename itself for clarity.
    lat_dir = int(math.floor(min_lat))
    lon_dir = int(math.floor(min_lon))
    # Ensure formatting matches the expected float representation if needed, Go might format differently.
    filename = f"{min_lat}_{min_lon}_{max_lat}_{max_lon}.bin"
    return os.path.join(BOUNDS_DIR, str(lat_dir), str(lon_dir), filename)

def find_area_box(lat, lon):
    # Determine the bounding box file coordinates based on latitude and longitude
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
        filename = get_bounds_filename(min_lat, min_lon, max_lat, max_lon)

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
    schema_py_path = os.path.join(script_dir, 'offline_capnp.py')
    schema_capnp_rel_path = '../mapd_source/offline.capnp' # Relative path from reader.py
    schema_capnp_abs_path = os.path.abspath(os.path.join(script_dir, schema_capnp_rel_path))

    if not os.path.exists(schema_py_path):
        print(f"Python schema '{schema_py_path}' not found.")
        if os.path.exists(schema_capnp_abs_path):
            print(f"Attempting to generate schema from '{schema_capnp_abs_path}'...")
            # Construct the command carefully. Ensure output path is correct.
            # Running from the mapd_source directory simplifies include paths for capnp tool.
            mapd_source_dir = os.path.dirname(schema_capnp_abs_path)
            # Output path relative to mapd_source dir needs to point back to mapd_py dir
            output_py_rel_to_source = os.path.relpath(schema_py_path, start=mapd_source_dir)

            # Command: cd into source dir, compile schema, output back to mapd_py dir
            compile_cmd = f"cd \"{mapd_source_dir}\" && capnp compile -opy offline.capnp -o \"{output_py_rel_to_source}\""

            print(f"Executing: {compile_cmd}")
            try:
                result = os.system(compile_cmd)
                if result == 0:
                    print("Schema generated successfully.")
                    # Try importing again now that it might exist
                    try:
                        import importlib
                        # Force reload if needed, though restart might be cleaner
                        import offline_capnp
                        importlib.reload(offline_capnp)
                        print("Schema imported successfully after generation.")
                    except ImportError:
                         print("Import failed even after generation attempt.")
                else:
                    print(f"Schema generation failed with exit code {result}. Ensure 'capnp' tool is installed and works.")
            except Exception as e:
                print(f"Error during schema generation command execution: {e}")
        else:
            print(f"Original schema file '{schema_capnp_abs_path}' not found. Cannot generate Python schema.")

    # Reload the module to ensure the potentially newly generated schema is used
    try:
        import importlib
        # Ensure the top-level package structure is recognized if running as script
        if __package__ is None or __package__ == '':
             # If run directly, adjust path to allow relative import (might not always work)
             import sys
             sys.path.insert(0, os.path.abspath(os.path.join(script_dir, '..')))
             import offline_capnp
        else:
             from . import offline_capnp
        importlib.reload(offline_capnp)
    except ImportError:
        print("Could not reload offline_capnp schema.")
    except NameError:
        # offline_capnp might not be defined if initial import and generation failed
        pass

    # Test coordinates (replace with actual test coordinates)
    # Example: Somewhere in California
    test_lat = 34.0522
    test_lon = -118.2437

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
        expected_file = get_bounds_filename(min_lat_test, min_lon_test, max_lat_test, max_lon_test)
        print(f"  (Checked path: {expected_file})")