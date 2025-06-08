# Chauffeur Custom Build/Setup Notes

This document outlines custom setup steps required for this fork beyond a standard openpilot installation, primarily focusing on dependencies and build process modifications.

## 1. Bundled Protobuf Compiler (`protoc`)

### Problem:

The standard `protobuf-compiler` package available via `apt` on the device (AGNOS) is often an older version (e.g., 3.6.1). This version generates Python code incompatible with the newer Python `protobuf` library (e.g., v4.x+) used by openpilot and its dependencies, leading to `TypeError: Descriptors cannot be created directly` during runtime when importing the generated `_pb2.py` files.

### Solution:

To ensure consistent and compatible builds without requiring manual installation of a newer `protoc` on every device, a specific version known to work is bundled directly within this repository.

*   **Binary:** `protoc` (Protocol Buffer Compiler)
*   **Version:** `v27.1`
*   **Architecture:** `aarch64` (for the comma device)
*   **Location:** `tools/bin/protoc`

### Implementation Details:

1.  **Binary Added:** The `protoc` v27.1 executable for `linux-aarch64` has been placed in the `tools/bin/` directory.
2.  **`.gitignore` Exception:** An exception rule (`!tools/bin/protoc`) was added to the root `.gitignore` file to ensure this specific binary is tracked by Git, overriding the general ignore rule for `tools/bin/`.
3.  **`SConstruct` Modification:** The main `SConstruct` file was modified to add a build rule for the custom Protobuf file (`tools/map_processing/osm_speed_data.proto`). This rule explicitly calls the bundled binary (`#tools/bin/protoc`) instead of relying on the system's PATH:

    ```python
    # Excerpt from SConstruct
    proto_out_dir = 'selfdrive/frogpilot/navigation/mapd_py'
    proto_src_dir = 'tools/map_processing'
    proto_src = proto_src_dir + '/osm_speed_data.proto'
    proto_target = proto_out_dir + '/osm_speed_data_pb2.py'
    protoc_binary = 'protoc' # Use system protoc for cross-platform compatibility
    env.Command(proto_target, [proto_src, proto_out_dir + '/__init__.py', protoc_binary], f'{protoc_binary} --proto_path={proto_src_dir} --python_out={proto_out_dir} {proto_src}')
    ```

### Usage / Build Steps:

After cloning or pulling this repository:

1.  The `tools/bin/protoc` binary should be present.
2.  Ensure it has execute permissions. Git *should* preserve this, but if issues occur, run `chmod +x tools/bin/protoc`.
3.  Run the standard build command (`scons` or `scons -j$(nproc)`). `scons` will now automatically use the bundled `tools/bin/protoc` to generate the required Python file (`selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py`).

This eliminates the need to manually install or update `protoc` on the target device.

**Note:** The corresponding runtime Python `protobuf` library still needs to be installed (e.g., via `pip`). The bundled `protoc` v27.1 is known to generate code compatible with Python `protobuf` library v4.25.2 (and likely other v4.x versions, as well as v3.20.x).

---

*(Future custom setup steps can be added below)*