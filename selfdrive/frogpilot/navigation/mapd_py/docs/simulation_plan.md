# MTSC Simulation Setup Plan

This document outlines the temporary modifications needed to run MTSC simulation scripts (like `test_mtsc_carson_rd.py`) in a development environment without relying on the exact on-device paths (`/data/openpilot`) or potentially the standard parameter store mechanism (`/dev/shm/params`) for GPS mocking, and how to revert these changes.

## Goal

Enable running `test_mtsc_carson_rd.py` (or similar scripts) directly from the source code checkout (e.g., on a PC/Mac/WSL) by making `ChauffeurMtsc` (and its internal `MapReader`) find necessary data files within the source tree and allowing the script to simulate GPS updates.

## Options Considered

1.  **Modify `MapReader` Paths:** Temporarily change the path definitions within `selfdrive/frogpilot/navigation/mapd_py/reader.py` to calculate paths relative to the source code structure instead of using the hardcoded `/data/openpilot` prefix. The simulation script would still attempt to use `Params("/dev/shm/params")` for GPS mocking.
2.  **Direct GPS Injection:** Modify `selfdrive/frogpilot/controls/lib/chauffeur_mtsc.py` to accept mock GPS data directly (e.g., via an optional argument to `update()` or by modifying `_get_current_position()` for testing). Modify the simulation script to pass data directly instead of using `Params`. Keep `MapReader` paths pointing to `/data/openpilot`.

## Chosen Approach: Option 1 - Modify `MapReader` Paths

This approach is less intrusive to the core MTSC logic and only requires changes to the `MapReader` initialization, which is already designed to handle dynamic path selection (though we're overriding that temporarily for simulation).

### Rollout Steps (Enabling Simulation)

1.  **Target File:** `selfdrive/frogpilot/navigation/mapd_py/reader.py`
2.  **Modification:** Comment out the `OP_ROOT = "/data/openpilot"` line and the logic that uses it for `REGION_FILES` and `SCHEMA_PATH`. Replace it with logic that calculates the repository root based on `__file__` and defines paths relative to that root.
    *   Specifically, add code like:
        ```python
        import os
        # Find the repository root relative to this file
        _script_dir = os.path.dirname(os.path.abspath(__file__))
        _repo_root = os.path.abspath(os.path.join(_script_dir, "../../../../..")) # Adjust level as needed

        # Define paths relative to the repository root found above
        MAP_DATA_DIR = os.path.join(_repo_root, "map_data")
        SCHEMA_DIR = os.path.join(_repo_root, "tools/map_processing")

        # Update REGION_FILES and SCHEMA_PATH to use MAP_DATA_DIR and SCHEMA_DIR
        REGION_FILES = {
            "california": os.path.join(MAP_DATA_DIR, "california-speedlimits.capnp"),
            "nevada": os.path.join(MAP_DATA_DIR, "nevada-speedlimits.capnp"),
        }
        DEFAULT_REGION_FILE = REGION_FILES["nevada"] # Or appropriate default
        SCHEMA_PATH = os.path.join(SCHEMA_DIR, "osm_speed_data.capnp")
        ```
    *   Ensure the `Params("/dev/shm/params")` calls in the simulation script (`test_mtsc_carson_rd.py`) and potentially within `MapReader.__init__` remain. The `Params` library might fall back to file-based storage if shared memory isn't available, which could be sufficient for this simulation.

### Reversion Steps (Disabling Simulation / Preparing for Device)

1.  **Target File:** `selfdrive/frogpilot/navigation/mapd_py/reader.py`
2.  **Modification:** Remove or comment out the relative path calculation logic (`_script_dir`, `_repo_root`, `MAP_DATA_DIR`, `SCHEMA_DIR`). Restore the `OP_ROOT = "/data/openpilot"` definition and ensure `REGION_FILES` and `SCHEMA_PATH` use `OP_ROOT` as their base.
    *   Ensure the paths are exactly as they were before the simulation rollout, e.g.:
        ```python
        OP_ROOT = "/data/openpilot"
        REGION_FILES = {
            "california": os.path.join(OP_ROOT, "map_data/california-speedlimits.capnp"),
            "nevada": os.path.join(OP_ROOT, "map_data/nevada-speedlimits.capnp"),
        }
        DEFAULT_REGION_FILE = REGION_FILES["nevada"] # Or appropriate default
        SCHEMA_PATH = os.path.join(OP_ROOT, "tools/map_processing/osm_speed_data.capnp")
        ```

## Notes

*   This plan assumes the `.capnp` map data files and the schema file are present in their respective locations within the source code tree (`map_data/` and `tools/map_processing/`).
*   Successful execution of the simulation script still depends on having the necessary Python dependencies (`capnp`, `numpy`, `rtree`, `shapely`, etc.) installed in the environment where the script is run.
*   The behavior of `Params` when `/dev/shm/params` is unavailable might vary. If direct parameter communication fails in the simulation environment, Option 2 (Direct GPS Injection) might need to be reconsidered.