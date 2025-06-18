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

**UPDATE: The protobuf-based mapd_py system has been removed in favor of the original Go-based mapd. The information below is retained for historical reference only.**

~~1.  **Binary Added:** The `protoc` v27.1 executable for `linux-aarch64` has been placed in the `tools/bin/` directory.~~
~~2.  **`.gitignore` Exception:** An exception rule (`!tools/bin/protoc`) was added to the root `.gitignore` file to ensure this specific binary is tracked by Git, overriding the general ignore rule for `tools/bin/`.~~
~~3.  **`SConstruct` Modification:** The main `SConstruct` file was modified to add a build rule for the custom Protobuf file.~~

### Current Status:

The protobuf infrastructure and mapd_py have been removed. The system now uses the original Go-based mapd implementation which communicates via cereal messages (liveMapData).

---

*(Future custom setup steps can be added below)*