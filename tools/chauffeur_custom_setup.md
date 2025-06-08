# Chauffeur Custom Build/Setup Notes

This document outlines custom setup steps required for this fork beyond a standard openpilot installation, primarily focusing on dependencies and build process modifications.

## 1. Bundled Protobuf Compiler (`protoc`)

### Problem:

The standard `protobuf-compiler` package available via `apt` on the device (AGNOS) is often an older version (e.g., 3.6.1). This version generates Python code incompatible with the newer Python `protobuf` library (e.g., v4.x+) used by openpilot and its dependencies, leading to `TypeError: Descriptors cannot be created directly` during runtime when importing the generated `_pb2.py` files.

### Solution:

To ensure consistent and compatible builds without requiring manual installation of a newer `protoc` on every device, a specific version known to work is bundled directly within this repository.

*   **Binary:** `protoc` (Protocol Buffer Compiler)
*   **Version:** `v27.1`
*   **Architectures:** Both `x86_64` (for dev environment) and `aarch64` (for comma device)
*   **Locations:**
    - `tools/bin/protoc-x86_64` - For development/map tile generation
    - `tools/bin/protoc-aarch64` - For TICI device builds

### Implementation Details:

1.  **Binaries Added:** Both `protoc` v27.1 executables (for `linux-x86_64` and `linux-aarch64`) have been placed in the `tools/bin/` directory.
2.  **`.gitignore` Exception:** An exception rule (`!tools/bin/protoc-*`) was added to the root `.gitignore` file to ensure these specific binaries are tracked by Git, overriding the general ignore rule for `tools/bin/`.
3.  **`SConscript` Modification:** The `selfdrive/frogpilot/navigation/mapd_py/SConscript` file includes platform detection logic to automatically select the correct protoc binary based on the system architecture:

    ```python
    # Platform detection and protoc binary selection
    import platform
    arch = platform.machine()
    if arch == 'x86_64':
        protoc_binary = '#tools/bin/protoc-x86_64'
    elif arch == 'aarch64':
        protoc_binary = '#tools/bin/protoc-aarch64'
    else:
        # Fallback to system protoc if architecture not recognized
        protoc_binary = 'protoc'
        print(f"WARNING: Unknown architecture {arch}, falling back to system protoc")
    ```

### Usage / Build Steps:

After cloning or pulling this repository:

1.  The architecture-specific `tools/bin/protoc-*` binaries should be present.
2.  Ensure they have execute permissions. Git *should* preserve this, but if issues occur, run:
    ```bash
    chmod +x tools/bin/protoc-x86_64
    chmod +x tools/bin/protoc-aarch64
    ```
3.  Run the standard build command (`scons` or `scons -j$(nproc)`). `scons` will now automatically detect the system architecture and use the appropriate bundled protoc binary to generate the required Python file (`selfdrive/frogpilot/navigation/mapd_py/osm_speed_data_pb2.py`).

This eliminates the need to manually install or update `protoc` on the target device.

**Note:** The corresponding runtime Python `protobuf` library still needs to be installed (e.g., via `pip`). The bundled `protoc` v27.1 is known to generate code compatible with Python `protobuf` library v4.25.2 (and likely other v4.x versions, as well as v3.20.x).

---

---

## Documentation Status

**Last Updated:** June 7, 2025 19:12 PDT  
**Current Commit:** `0bd4a5eb` - Add dual-architecture protoc v27.1 binaries for cross-platform development

This document reflects the current state of the protoc implementation, which successfully enables:
- Cross-platform development between x86_64 WSL and aarch64 TICI device
- CPU-intensive map tile generation in the development environment  
- Device builds using the correct architecture-specific protoc binary

*(Future custom setup steps can be added below)*