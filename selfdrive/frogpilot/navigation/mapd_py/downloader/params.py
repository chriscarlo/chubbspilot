"""Module for handling openpilot params relevant to mapd."""

import os
import json
import errno
import fcntl # For file locking on Unix-like systems
import time

PARAMS_PATH = "/data/params/d"
MEM_PARAMS_PATH = "/dev/shm/params/d"

# Check if we are in a simulation or specific environment where /data might not exist
def get_base_osm_path():
    """Determines the base path for OSM data storage."""
    # Use media/0 path if it exists (standard on-device path)
    # Otherwise, use a relative path (likely for simulation/testing)
    media_path = "/data/media/0"
    if os.path.exists(media_path) and os.path.isdir(media_path):
        return os.path.join(media_path, "osm")
    else:
        # Fallback for simulation/development environments
        # Ensure this relative path makes sense in the context it runs
        return os.path.join(os.getcwd(), "media", "osm") # Relative to current dir

BASE_PATH = get_base_osm_path() # Base path for actual map data storage


# Param Keys (match the Go version)
ROAD_NAME                 = "RoadName"
MAP_HAZARD                = "MapHazard"
NEXT_MAP_HAZARD           = "NextMapHazard"
MAP_SPEED_LIMIT           = "MapSpeedLimit"
MAP_ADVISORY_LIMIT        = "MapAdvisoryLimit"
NEXT_MAP_ADVISORY_LIMIT   = "NextMapAdvisoryLimit"
NEXT_MAP_SPEED_LIMIT      = "NextMapSpeedLimit"
LAST_GPS_POSITION         = "LastGPSPosition"
DOWNLOAD_BOUNDS           = "OSMDownloadBounds"
DOWNLOAD_LOCATIONS        = "OSMDownloadLocations"
DOWNLOAD_PROGRESS         = "OSMDownloadProgress"
MAP_CURVATURES            = "MapCurvatures"
MAP_TARGET_VELOCITIES     = "MapTargetVelocities"
MAP_TARGET_LAT_A          = "MapTargetLatA"
MAPD_LOG_LEVEL            = "MapdLogLevel"
MAPD_PRETTY_LOG           = "MapdPrettyLog"

def _param_path(name, persistent=False):
    """Constructs the full path to a parameter file."""
    base = PARAMS_PATH if persistent else MEM_PARAMS_PATH
    return os.path.join(base, name)

def ensure_param_directories():
    """Creates the parameter directories if they don't exist."""
    os.makedirs(PARAMS_PATH, 0o775, exist_ok=True)
    os.makedirs(MEM_PARAMS_PATH, 0o775, exist_ok=True)

ensure_param_directories() # Ensure they exist on module load

def get_param(name, persistent=False, block=False, default=None):
    """Reads a parameter value.

    Args:
        name: The name of the parameter.
        persistent: Whether to read from the persistent path.
        block: Whether to block until the parameter exists.
        default: Value to return if the param doesn't exist (and not blocking).

    Returns:
        The parameter value as bytes, or default.
    """
    path = _param_path(name, persistent)
    while True:
        try:
            with open(path, 'rb') as f:
                # Implement file locking for read (shared lock)
                # This prevents reading while another process is writing
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    return f.read()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except FileNotFoundError:
            if block:
                time.sleep(0.1) # Wait a bit before retrying
                continue
            else:
                return default
        except OSError as e:
            print(f"Warning: Error reading param '{name}': {e}")
            if block:
                 time.sleep(0.1)
                 continue
            return default

def get_param_json(name, persistent=False, block=False, default=None):
     """Reads a parameter value and parses it as JSON."""
     data_bytes = get_param(name, persistent, block, default=None)
     if data_bytes is None:
         return default
     try:
         # Decode assuming UTF-8, handle potential empty data
         if not data_bytes:
             return default
         data_str = data_bytes.decode('utf-8')
         return json.loads(data_str)
     except (json.JSONDecodeError, UnicodeDecodeError) as e:
         print(f"Warning: Could not parse JSON from param '{name}': {e}")
         return default

def put_param(name, value, persistent=False):
    """Writes a parameter value.

    Args:
        name: The name of the parameter.
        value: The value to write (as bytes).
        persistent: Whether to write to the persistent path.
    """
    if not isinstance(value, bytes):
        raise TypeError("Parameter value must be bytes")

    path = _param_path(name, persistent)
    tmp_path = path + ".tmp"
    lock_path = os.path.join(os.path.dirname(path), ".lock")

    # Ensure the directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lock_file = None
    try:
        # Acquire exclusive lock for writing
        lock_file = open(lock_path, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX)

        # Write to temporary file first
        with open(tmp_path, 'wb') as f:
            f.write(value)
            f.flush() # Ensure data is written to OS buffer
            os.fsync(f.fileno()) # Ensure data is written to disk

        # Atomically rename the temporary file to the final path
        os.rename(tmp_path, path)

        # Sync the directory to ensure the rename operation is persisted
        # This might be less critical on modern filesystems but matches Go impl.
        dir_fd = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

        return True # Indicate success

    except Exception as e:
        print(f"Error writing param '{name}': {e}")
        # Clean up temporary file if it exists
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass # Ignore cleanup errors
        return False # Indicate failure
    finally:
        # Release the lock
        if lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
            # Attempt to remove the lock file, ignore errors
            try:
                 os.remove(lock_path)
            except OSError:
                 pass

def put_param_json(name, value, persistent=False):
    """Writes a Python object as JSON to a parameter."""
    try:
        json_bytes = json.dumps(value, separators=(',', ':')).encode('utf-8')
        return put_param(name, json_bytes, persistent)
    except TypeError as e:
         print(f"Error encoding JSON for param '{name}': {e}")
         return False

def remove_param(name, persistent=False):
    """Removes a parameter file."""
    path = _param_path(name, persistent)
    lock_path = os.path.join(os.path.dirname(path), ".lock")
    lock_file = None
    try:
        lock_file = open(lock_path, 'w')
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        os.remove(path)
        # Sync directory after removal
        dir_fd = os.open(os.path.dirname(path), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        return True
    except FileNotFoundError:
        return True # Already removed
    except Exception as e:
        print(f"Error removing param '{name}': {e}")
        return False
    finally:
         if lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
            try:
                 os.remove(lock_path)
            except OSError:
                 pass

def get_base_path():
    """Public getter for the base OSM data path."""
    return BASE_PATH


# Initialize by ensuring directories are present
ensure_param_directories()

# Example Usage (can be removed later)
if __name__ == "__main__":
    print(f"Using Base OSM Path: {get_base_path()}")
    print(f"Using Params Path: {PARAMS_PATH}")
    print(f"Using Mem Params Path: {MEM_PARAMS_PATH}")

    # Test writing and reading
    test_param_name = "TestPythonParam"
    test_value_bytes = b'hello world'
    print(f"Putting '{test_param_name}' (mem)...")
    success = put_param(test_param_name, test_value_bytes, persistent=False)
    if success:
        print(" Put successful.")
        read_value = get_param(test_param_name, persistent=False)
        print(f" Reading back: {read_value}")
        assert read_value == test_value_bytes
        print(f" Removing '{test_param_name}'...")
        remove_param(test_param_name, persistent=False)
        print(f" Removed.")
    else:
        print(" Put failed.")

    # Test JSON
    test_json_param = "TestJsonParam"
    test_json_value = {"a": 1, "b": [True, None, "string"]}
    print(f"Putting JSON '{test_json_param}' (persistent)...")
    success = put_param_json(test_json_param, test_json_value, persistent=True)
    if success:
        print(" Put JSON successful.")
        read_json = get_param_json(test_json_param, persistent=True)
        print(f" Reading JSON back: {read_json}")
        assert read_json == test_json_value
        print(f" Removing JSON '{test_json_param}'...")
        remove_param(test_json_param, persistent=True)
        print(" Removed JSON.")
    else:
         print(" Put JSON failed.")