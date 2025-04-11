# Map Data Tiling Strategy Plan

This document outlines the steps required to modify the map data pipeline to use geographically tiled `.capnp` files instead of large, single regional files. This aims to overcome loading limitations (e.g., "Message has too many segments" errors) and improve runtime memory efficiency.

## Goal

Transition from loading large regional map data files (like `california-speedlimits.capnp`) at startup to dynamically loading smaller, geographically tiled map data files based on the vehicle's current location.

## Components Affected

1.  **Data Generation:** `tools/map_processing/process_osm.py`
2.  **Data Loading/Reading:** `selfdrive/frogpilot/navigation/mapd_py/reader.py`
3.  **Data Storage:** File structure for storing map data.

## Rollout Steps (Implementing Tiling)

1.  **Modify `process_osm.py`:**
    *   **Define Tiling Scheme:** Choose a tiling method (e.g., simple lat/lon grid, S2 cells). Define the tile size/level.
    *   **Output Directory:** Create a new output directory structure for tiles (e.g., `map_data_tiles/region_name/tile_id.capnp`).
    *   **Modify `main` Function:**
        *   As it iterates through GeoJSON features (road segments), determine the tile(s) each segment belongs to (using its starting coordinates or potentially all coordinates if segments cross boundaries).
        *   Maintain a dictionary of open file handles, one for each active tile being written to.
        *   Write the packed `SpeedLimitSegment` message to the file corresponding to its tile.
        *   Handle segments crossing tile boundaries (e.g., write to all relevant tiles, or implement logic in `MapReader` to query neighboring tiles).
        *   Ensure the streaming approach (line-by-line processing) is maintained to avoid high memory usage during processing.

2.  **Generate Tiled Data:** Run the modified `process_osm.py` for each region (California, Nevada) to create the tiled `.capnp` files in the new directory structure (e.g., `map_data_tiles/california/...`, `map_data_tiles/nevada/...`).

3.  **Modify `reader.py` (`MapReader` Class):**
    *   **Update Path Logic:** Modify constants/logic to point to the new `map_data_tiles/` directory structure and handle tile naming conventions.
    *   **Modify `__init__`:** Remove logic for loading a single large regional file based on initial GPS. It might not load *any* data at init, or perhaps only the tile corresponding to the initial GPS.
    *   **Implement Tile Loading Logic:** Add a method `_load_tile(tile_id)` that:
        *   Constructs the path to the specified tile's `.capnp` file.
        *   Opens and reads the segments using `read_multiple` (hopefully avoiding segment limit errors due to smaller file size).
        *   Adds the loaded segments to `self.segments_data` (or a new tile-aware structure).
        *   Adds the segments' bounds to the R-tree index (`self.idx`), potentially associating them with the `tile_id`.
    *   **Implement Tile Unloading Logic:** Add a method `_unload_tile(tile_id)` to remove data associated with a specific tile from memory (`self.segments_data`) and the R-tree index to conserve resources.
    *   **Modify `update` (or add new logic):**
        *   Determine the current `tile_id` based on the vehicle's real-time GPS coordinates.
        *   Compare the current `tile_id` to the currently loaded tile(s).
        *   If the tile has changed or is not loaded, call `_load_tile()` for the new tile (and potentially neighboring tiles for lookahead).
        *   Call `_unload_tile()` for tiles that are no longer relevant (e.g., far away from the current tile).
    *   **Modify `get_segment_data_at`:** Ensure this query still works correctly with the potentially changing set of loaded segments in `self.segments_data` and the R-tree.

4.  **Deployment:** Ensure the new `map_data_tiles/` directory structure with the generated tile files is included in the deployment (e.g., via `git pull`) under `/data/openpilot/`. Adjust file paths in `reader.py` to use `/data/openpilot` base if necessary for the on-device environment (reverting simulation paths).

5.  **Testing:** Thoroughly test:
    *   Correct loading of initial tile based on GPS.
    *   Correct loading/unloading of tiles when crossing boundaries.
    *   Performance of `get_segment_data_at` queries.
    *   Memory usage.
    *   MTSC behavior using data from tiles.

## Reversion Steps (Back to Single Regional Files)

1.  **Revert `process_osm.py`:** Restore the previous version where the `main` function writes all processed segments for a region into a single output `.capnp` file (e.g., `map_data/california-speedlimits.capnp`). Remove tiling logic.
2.  **Re-generate Regional Data:** Run the reverted `process_osm.py` to recreate the single large regional `.capnp` files in the original `map_data/` directory.
3.  **Revert `reader.py`:** Restore the previous version of the `MapReader` class where:
    *   `__init__` determines the region and loads the single corresponding regional file.
    *   `_load_and_index_data` reads the entire regional file.
    *   Tile loading/unloading/switching logic is removed.
    *   Paths point to the single regional files in `map_data/` (or `/data/openpilot/map_data/` for device).
4.  **Deployment:** Ensure the reverted code and the single large regional `.capnp` files are deployed.

## Considerations

*   **Tile Size vs. Overhead:** Very small tiles increase the frequency of loading/unloading and boundary checks.
*   **Boundary Handling:** How to handle road segments that cross tile boundaries needs careful consideration (duplicate in both tiles? Query neighbors?).
*   **Lookahead:** MTSC/VTSC often need data significantly ahead of the car. The tile loading logic must account for this, likely by pre-loading neighboring tiles in the direction of travel.
*   **State Management:** Persistently tracking which tiles are loaded might be necessary.
*   **Error Handling:** Robustly handle missing tile files or errors during tile loading/unloading.