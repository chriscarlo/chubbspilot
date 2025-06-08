# CLAUDE.md - System Directory

System services and hardware abstraction for the openpilot chauffeur fork.

## Architecture Overview

The `system/` directory contains system-level services and hardware abstraction:

- **`manager/`** - Process orchestration (manager.py)
- **`hardware/`** - Hardware abstraction layer
- **`camerad/`** - Camera interface
- **`loggerd/`** - Data logging services
- **`athena/`** - Cloud connectivity
- **`sensord/`** - Sensor data collection

## Hardware Platforms

Code supports multiple architectures with platform-specific implementations:

- **larch64**: Linux TICI (aarch64 with AGNOS)
- **aarch64**: Linux PC aarch64
- **x86_64**: Linux PC x64  
- **Darwin**: macOS (x64/arm64)

Platform-specific code isolated in `system/hardware/` with feature detection.

### Platform Detection
```python
TICI = os.path.isfile('/TICI')
PC = not TICI
```

## Key Components

### Process Manager
- **manager.py** - Central process orchestration
- **process_config.py** - Process configuration and startup
- Handles process lifecycle, restart policies, and dependencies
- Manages all selfdrive and system processes

### Hardware Abstraction
- **hw.py** - Main hardware interface
- **base.py** - Base hardware class
- **fan_controller.py** - Thermal management
- **power_monitoring.py** - Power and battery monitoring
- Platform-specific implementations for TICI vs PC

### Camera System
- **camerad/** - Camera capture and processing
- **main.cc** - C++ camera implementation
- Multi-camera support (road, driver, wide)
- Hardware-accelerated video encoding

### Logging System
- **loggerd/** - Data logging and storage
- **logger.cc/.h** - Core logging implementation
- **uploader.py** - Cloud upload functionality
- **deleter.py** - Log rotation and cleanup
- **encoderd.cc** - Video encoding

### Connectivity
- **athena/** - Cloud services integration
- **athenad.py** - Main athena daemon
- **registration.py** - Device registration
- Remote access and debugging capabilities

## System Configuration

### Boot Dependencies
Multi-layered dependency management ensures critical packages are available:

1. **ensure_boot_dependencies.sh** - Early boot-time shell script (tier 1 packages)
2. **ensure_dependencies.py** - Comprehensive Python installer with special package handling
3. Process-specific wrappers for complex dependencies

### Service Management
Services are configured and managed through the process manager:
- Automatic restart on failure
- Dependency ordering
- Resource monitoring
- Log collection

## Building System Components

```bash
# Build camera system
scons system/camerad/

# Build logging system
scons system/loggerd/

# Build sensor interfaces
scons system/sensord/
```

## Testing

```bash
# Run system-specific tests
pytest system/

# Run logging tests
pytest system/loggerd/

# Skip device-specific tests on PC
pytest system/ -m "not tici"
```

## Hardware-Specific Notes

### TICI (Device) Environment
- AGNOS operating system (Ubuntu-based)
- ARM64 architecture (larch64)
- Comma hardware integration
- Specific library paths: `/lib/aarch64-linux-gnu`, `/usr/lib/gcc/aarch64-linux-gnu/9`

### PC Development Environment
- x86_64 Ubuntu development
- Simulation mode available
- Hardware abstraction allows most functionality to work

### Cross-Platform Development
- Use `--arch=larch64` for cross-compilation
- Platform detection automatically selects appropriate code paths
- Hardware-independent components work across platforms