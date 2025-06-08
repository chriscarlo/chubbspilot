# CLAUDE.md - Tools Directory

This directory contains development and analysis utilities for the openpilot chauffeur fork.

## Development Commands

### Setup
```bash
# Install system dependencies (Ubuntu)
tools/ubuntu_setup.sh

# Manual dependency installation
tools/install_ubuntu_dependencies.sh
tools/install_python_dependencies.sh
```

### Building
```bash
# Build entire project
scons -j$(nproc)

# Build with parallel jobs (recommended)
scons -j8

# Build specific component
scons selfdrive/ui/

# Minimal build (no tests/tools)
scons --minimal

# Build with debug options
scons --asan     # Address sanitizer
scons --ubsan    # Undefined behavior sanitizer
scons --coverage # Test coverage
```

### Testing
```bash
# Run all tests
pytest

# Run tests in parallel
pytest -n auto

# Run specific module tests
pytest selfdrive/car/
pytest system/loggerd/

# Run with coverage
pytest --cov

# Skip slow tests
pytest -m "not slow"
```

### Code Quality
```bash
# Run linter
ruff check .

# Run type checker  
mypy .

# Format code
ruff format .

# Run pre-commit hooks
pre-commit run --all-files
```

### Cross-Platform Development

#### Build for Target Architecture
```bash
# Build for TICI from x86_64
scons -j8 --arch=larch64

# Run hardware-independent tests
pytest -m "not tici"

# Use simulation
USE_SIMULATOR=1 python selfdrive/test/process_replay/replay.py
```

## Dependency Management System

**IMPORTANT**: Any future custom library or module additions MUST be configured in the dependency management system:

1. **Add to ensure_dependencies.py**: Add the import name to REQUIRED_PACKAGES list with appropriate tier
2. **Handle Package Name Mapping**: If the import name differs from the PyPI package name, add special handling:
   - `cv2` → `opencv-python`
   - `PIL` → `Pillow`
   - `zmq` → `pyzmq`
   - `capnp` → `pycapnp`
   - `serial` → `pyserial`
   - `usb1` → `libusb1`
3. **Critical Packages**: Add to ensure_boot_dependencies.sh if boot-critical
4. **Process-Specific**: Create a wrapper if the package is only used by one process
5. **Run Analysis**: Use `python3 tools/analyze_imports.py` to verify coverage

The system uses a multi-layered approach to ensure maximum reliability on TICI devices where manual intervention is difficult.

### Runtime Dependency Analysis

1. **Comprehensive Analysis**: Scanned entire codebase (1260 files) and identified 661 unique external imports
   - Created `tools/analyze_imports.py` for ongoing dependency analysis
   - Generated `EXTERNAL_IMPORTS_ANALYSIS.md` with complete import breakdown
   - Created `CRITICAL_RUNTIME_DEPENDENCIES.md` with prioritized installation guide

2. **Multi-layered Installation System**: Ensures critical packages available before any imports:
   - `ensure_boot_dependencies.sh` - Early boot-time shell script (tier 1 packages)
   - `ensure_dependencies.py` - Comprehensive Python installer with special package handling
   - `mapd_daemon_wrapper.py` - Process-specific wrapper ensuring shapely before import
   - `main_wrapper.py` - Concierge wrapper ensuring web framework dependencies
   - Modified `process_config.py` to use wrappers instead of direct module imports

3. **Package Coverage**: Now handles critical packages with fallback installation methods:
   - **Tier 1 Critical**: numpy (290 usages), shapely, pydantic, uvicorn, jinja2, requests
   - **Tier 2 Important**: zmq, psutil, PIL, cv2 (opencv-python)
   - **Special Handling**: Package name mapping (cv2→opencv-python, PIL→Pillow, zmq→pyzmq)

## Key Tools

- **`analyze_imports.py`** - Dependency analysis for entire codebase
- **`ubuntu_setup.sh`** - Automated system dependency installation
- **`install_ubuntu_dependencies.sh`** - Manual Ubuntu package installation
- **`install_python_dependencies.sh`** - Python package installation
- Development utilities in subdirectories:
  - `debug/` - Debugging and analysis tools
  - `replay/` - Log replay utilities
  - `sim/` - Simulation tools
  - `car_porting/` - Vehicle porting utilities
  - `plotjuggler/` - Data visualization