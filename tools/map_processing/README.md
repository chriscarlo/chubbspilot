# OSM Map Data Processing Workflow

This document outlines the steps to download OpenStreetMap (OSM) data, process it using `osmium-tool`, and generate tiled map data in protobuf format using the `process_osm.py` script. This tiled data includes road geometry, curvature information, and speed limits, suitable for use in systems like openpilot.

## Prerequisites

- **`osmium-tool`**: Ensure `osmium-tool` is installed. ([Installation Instructions](https://osmcode.org/osmium-tool/))
- **Python Environment**: A Python environment with the necessary libraries (`numpy`, `protobuf`, etc.). Install dependencies using `pip install -r requirements.txt` (assuming a `requirements.txt` file exists or is created).
- **Protobuf Compiler**: The protobuf compiler (`protoc`) must be installed and used to generate the Python classes from `osm_speed_data.proto` (e.g., `osm_speed_data_pb2.py`). Example command: `protoc --python_out=. osm_speed_data.proto`

## Workflow Steps

1.  **Download OSM PBF Data:**
    *   Obtain the latest OSM data extract in PBF format for your desired region. A common source is [Geofabrik](https://download.geofabrik.de/).
    *   Example: Download the California extract. Create a directory (e.g., `map_data`) if it doesn't exist.
      ```bash
      mkdir -p map_data
      wget -O map_data/california-latest.osm.pbf https://download.geofabrik.de/north-america/us/california-latest.osm.pbf
      ```
    *   Replace the URL with the appropriate one for your region.

2.  **Filter Relevant OSM Features:**
    *   Use `osmium tags-filter` to extract only the necessary features. We typically need roads (`highway` ways) and potentially nodes with traffic signs (`traffic_sign` nodes) for speed limit information.
    *   This creates an intermediate, smaller PBF file.
      ```bash
      osmium tags-filter map_data/california-latest.osm.pbf w/highway n/traffic_sign -o map_data/california-filtered.osm.pbf --overwrite
      ```
      *   `w/highway`: Keeps all ways (LineStrings) that have a `highway` tag.
      *   `n/traffic_sign`: Keeps all nodes (Points) that have a `traffic_sign` tag.
      *   `--overwrite`: Allows overwriting the output file if it exists.

3.  **Export to GeoJSON Text Sequence:**
    *   Convert the filtered PBF data into GeoJSON Text Sequence format (`.geojsonl`). This format uses a record separator (`\x1e`) between JSON objects, making it suitable for streaming processing.
    *   Crucially, use `osmium export` with `--add-unique-id=type_id` to ensure each feature's OSM ID (e.g., `w12345` or `n67890`) is added as a top-level `id` property in the GeoJSON, which the `process_osm.py` script expects.
      ```bash
      osmium export map_data/california-filtered.osm.pbf -o map_data/california-exported.geojsonl --output-format geojsonseq --add-unique-id=type_id
      ```

4.  **Clean Up Intermediate File (Optional):**
    *   You can remove the filtered PBF file to save space.
      ```bash
      rm map_data/california-filtered.osm.pbf
      ```

5.  **Process GeoJSONL and Generate Tiles:**
    *   Run the `process_osm.py` script, providing the generated `.geojsonl` file as input and specifying the base output directory for the tiles.
    *   The script reads each GeoJSON feature, calculates curvatures for LineStrings, parses speed limits (from `maxspeed` or `traffic_sign` properties), assigns features to geographic tiles, and writes the data as size-prefixed protobuf messages (`.protobuf`) along with corresponding spatial index files (`.idx`).
      ```bash
      python tools/map_processing/process_osm.py map_data/california-exported.geojsonl map_data_tiles_protobuf
      ```
    *   This will create a directory structure like `map_data_tiles_protobuf/region_name/` containing the `.protobuf` and `.idx` tile files (e.g., `map_data_tiles_protobuf/california/N34.0_W118.2.protobuf`).

## Output Files

-   **`.protobuf` Files**: Contain sequences of size-prefixed `SpeedLimitSegment` protobuf messages. Each message represents a road segment (or a speed-related point) and includes its OSM Way/Node ID, geometry (coordinates), curvature array (for LineStrings), curvature-derived speed array, and the parsed speed limit in m/s.
-   **`.idx` Files**: Binary index files corresponding to each `.protobuf` tile. Each record contains the OSM ID, bounding box (min_lon, min_lat, max_lon, max_lat), byte offset, and size of the corresponding protobuf message within the tile file. This allows for quick spatial lookups.

This process generates the necessary map data tiles for use in navigation and driving assistance systems.
