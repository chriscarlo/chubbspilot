# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: This WSL instance is exclusively intended for developing on this specific openpilot fork. The runtime environment should be emulated as closely as possible to the target AGNOS/TICI environment.

## Project Overview

This is a fork of openpilot called "chauffeur" with FrogPilot customizations. It's an advanced driver assistance system (ADAS) that provides autonomous driving capabilities including lane keeping, adaptive cruise control, and driver monitoring.

**Note**: The README indicates this fork is deprecated with development continuing in official sunnypilot branches.

## Architecture

The codebase follows a process-based architecture with message passing via Cap'n Proto:

- **`selfdrive/`** - Core driving logic and vehicle interfaces
  - `controls/` - Vehicle control algorithms (controlsd.py, plannerd.py, radard.py)  
  - `car/` - Vehicle-specific interfaces and fingerprinting
  - `modeld/` - ML model inference (vision models)
  - `ui/` - User interface and Qt components
  - `frogpilot/` - Custom FrogPilot extensions
- **`system/`** - System services and hardware abstraction
  - `manager/` - Process orchestration (manager.py)
  - `hardware/` - Hardware abstraction layer
  - `camerad/` - Camera interface
  - `loggerd/` - Data logging services
- **`cereal/`** - IPC message definitions (Cap'n Proto)
- **`opendbc/`** - CAN bus database for vehicle communication
- **`tools/`** - Development and analysis utilities

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

## Build System

- **SCons** - Primary build system (see SConstruct)
- **Poetry** - Python dependency management (pyproject.toml)
- **Architecture Support**: larch64 (TICI), aarch64, x86_64, Darwin
- **Compilers**: clang/clang++ (required)
- **Python**: 3.11+ required

## Key Dependencies

- **Core**: pycapnp, Cython, numpy, sympy
- **ML**: onnx, onnxruntime-gpu, tinygrad  
- **Hardware**: libusb1, spidev (Linux only)
- **UI**: Qt5 (PyQt5 on x86_64)
- **Communication**: pyzmq for messaging

## Testing Configuration

Tests are configured in pyproject.toml with these key settings:
- Parallel execution with pytest-xdist
- Excludes: openpilot/, cereal/, opendbc/, panda/ submodules
- Special markers: `slow` (skippable), `tici` (device-specific)
- Coverage analysis available

## Hardware Platforms

Code supports multiple architectures:
- **larch64**: Linux TICI (aarch64 with AGNOS)
- **aarch64**: Linux PC aarch64
- **x86_64**: Linux PC x64  
- **Darwin**: macOS (x64/arm64)

Platform-specific code isolated in system/hardware/ with feature detection.

## Message Passing

Inter-process communication uses:
- **Cap'n Proto** for serialization (cereal/)
- **ZeroMQ** for transport (msgq)
- **Services** defined in cereal/services.py
- **Manager** orchestrates all processes (system/manager/)

## Development Notes

- All Python imports must use absolute paths (e.g., `openpilot.selfdrive`)
- Code style enforced via ruff with 160 character line limit
- 2-space indentation for Python
- Type hints required (mypy enforcement)
- No unittest - use pytest only

## Documentation Maintenance

### agentDocumentation Directory
Maintain comprehensive documentation in `/data/openpilot/agentDocumentation/` for:
- Development environment analysis
- Cross-platform testing strategies
- Infrastructure improvements
- Implementation roadmaps

### Documentation Workflow
1. **Update documentation** as part of normal development workflow
2. **Mark completed objectives** in roadmap documents
3. **Add new ideas** and discoveries to relevant docs
4. **Track infrastructure changes** in cleanup plan
5. **Document platform-specific issues** and solutions

### Key Documentation Files
- `DEVELOPMENT_ENVIRONMENT.md` - Current state and challenges
- `CROSS_PLATFORM_TESTING_PLAN.md` - Testing strategy and roadmap
- `INFRASTRUCTURE_CLEANUP_PLAN.md` - Technical debt and cleanup
- `IMMEDIATE_ACTION_PLAN.md` - Quick start for cross-platform dev

## Cross-Platform Development

### Development Environment
- **Dev**: Ubuntu 24.04 x86_64
- **Target**: AGNOS (Ubuntu-based) on aarch64 (Comma 3X/TICI)

### Build for Target Architecture
```bash
# Build for TICI from x86_64
scons -j8 --arch=larch64

# Run hardware-independent tests
pytest -m "not tici"

# Use simulation
USE_SIMULATOR=1 python selfdrive/test/process_replay/replay.py
```

### Platform Detection
```python
TICI = os.path.isfile('/TICI')
PC = not TICI
```

## SSH Configuration

For git operations, SSH keys are stored in `~/.ssh/`:
- Private key: `~/.ssh/claude_github_key`
- Public key: `~/.ssh/claude_github_key.pub`

The public key needs to be added to GitHub SSH keys in user settings for git push operations.

## System Configuration

For system operations requiring elevated privileges:
- Sudo password: stored in `~/.sudo_pass` (permissions 600)
- Use with: `sudo -S command < ~/.sudo_pass`

## Prebuilt Release Workflow

FrogPilot and openpilot use a special workflow for fast device installation:
- Build directly on TICI device using `release/build_release.sh`
- Commit compiled binaries to special release branches
- Mark with `prebuilt` file to indicate pre-compiled release
- Users get immediate functionality without 20+ minute compilation

**Near-term objective**: Implement similar prebuilt workflow for this fork to enable fast device installation.

## Current Status

**Last Updated:** January 7, 2025 04:48 PST  
**Current Commit:** `228fcf8c` - Fix shapely module dependency at boot time

### Recent Accomplishments
- ✅ Implemented dual-architecture protoc v27.1 support for cross-platform development
- ✅ Fixed "protoc failed: [Errno 8] Exec format error" on TICI device
- ✅ Enabled CPU-intensive map tile generation in x86_64 dev environment
- ✅ Platform detection in SConscript automatically selects correct binary
- ✅ Added aarch64 cross-compilation toolchain packages to install_ubuntu_dependencies.sh
- ✅ Added --force-arch option to SConstruct for cross-compilation builds
- ✅ Fixed ICU library dependency for MapLibre (requires libicu66 on Ubuntu 24.04)
- ✅ Fixed "searching for libgcc_s.so.1" error on TICI by adding AGNOS library paths
- ✅ Added prebuilt libyuv.a library for larch64 from working exp05 branch
- ✅ Fixed shapely module runtime dependency with multi-layered boot-time installation

### Build System Fixes
1. **Cross-compilation support**: Added gcc-aarch64-linux-gnu, g++-aarch64-linux-gnu, and libc6-dev-arm64-cross to dependencies
2. **Architecture forcing**: Added --force-arch option to allow building for larch64 from x86_64 host
3. **ICU compatibility**: MapLibre requires ICU 66 - installed from Ubuntu 20.04 archives for compatibility
4. **TICI library paths**: Added /lib/aarch64-linux-gnu and /usr/lib/gcc/aarch64-linux-gnu/9 for AGNOS
5. **Conditional cross-compilation**: Cross-compilation flags only apply when building from x86_64 for larch64
6. **Missing libyuv library**: Added prebuilt libyuv.a from exp05 branch (build script approach was insufficient)

### Runtime Dependency Fixes
1. **Shapely module**: Created multi-layered approach to ensure installation before any imports:
   - `ensure_boot_dependencies.sh` - Early boot-time shell script for dependency installation
   - `ensure_dependencies.py` - Python script with pip and apt-get fallbacks
   - `mapd_daemon_wrapper.py` - Process-specific wrapper ensuring shapely before import
   - Modified `process_config.py` to use wrapper instead of direct module import

### Active Development Focus
The build system now supports:
- **x86_64 WSL Development Environment** - Native builds working with ICU 66 fix
- **TICI Native Builds** - Library paths fixed for AGNOS, libyuv build script provided
- **Cross-compilation** - Partial support (complex Qt cross-compilation not worth pursuing)

### Build Ready Status
- **TICI Native Builds**: All required libraries present, build should complete successfully
- **x86_64 Development**: Fully functional with all dependencies resolved
- **Runtime Dependencies**: Multi-layered dependency installation ensures missing Python packages are installed at boot

## Additional Guidance

- Always maintain a file called AGENTS.md for each CLAUDE.md and make AGENTS.md an exact copy of CLAUDE.md
- When user says "commit xyz", assume they mean commit AND push unless they specifically say not to push
- After every push, update all relevant documentation (CLAUDE.md, AGENTS.md, and any other affected docs) with current status, timestamp, and commit hash

## Memories

- Always include a current time and which commit we are on when updating documentation
- never include "co-authored by claude" or anything of that sort in commit notes or messages.