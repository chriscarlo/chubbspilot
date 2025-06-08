# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: This WSL instance is exclusively intended for developing on this specific openpilot fork. The runtime environment should be emulated as closely as possible to the target AGNOS/TICI environment.

## ⚠️ CRITICAL DEVELOPMENT ENVIRONMENT NOTICE ⚠️

**This is a SOURCE CODE DEVELOPMENT environment, NOT a running openpilot system!**

**DO NOT attempt to:**
- Run system commands like `systemctl`, `journalctl`, or service management commands
- Check for running processes with `pgrep`, `ps`, or similar
- Access `/TICI` file or expect TICI-specific behavior
- Look for system logs, crash logs, or runtime output
- Execute openpilot processes or services
- Check network services or ports

**This environment is for:**
- Reading and editing source code
- Building with `scons`
- Running tests with `pytest`
- Analyzing code structure and dependencies
- Git operations and documentation

**For runtime debugging:** Use an actual TICI device or proper simulation environment.

## Project Overview

This is a fork of openpilot called "chauffeur" with FrogPilot customizations. It's an advanced driver assistance system (ADAS) that provides autonomous driving capabilities including lane keeping, adaptive cruise control, and driver monitoring.

**Note**: The README indicates this fork is deprecated with development continuing in official sunnypilot branches.

## Architecture

The codebase follows a process-based architecture with message passing via Cap'n Proto:

- **`selfdrive/`** - Core driving logic and vehicle interfaces (*see selfdrive/CLAUDE.md*)
- **`system/`** - System services and hardware abstraction (*see system/CLAUDE.md*)
- **`cereal/`** - IPC message definitions and messaging (*see cereal/CLAUDE.md*)
- **`tools/`** - Development and analysis utilities (*see tools/CLAUDE.md*)
- **`release/`** - Release management and prebuilt workflows (*see release/CLAUDE.md*)
- **`opendbc/`** - CAN bus database for vehicle communication

## Quick Start

```bash
# Build entire project
scons -j$(nproc)

# Run all tests
pytest

# See tools/CLAUDE.md for detailed development commands
```

## Build System

- **SCons** - Primary build system (see SConstruct)
- **Poetry** - Python dependency management (pyproject.toml)
- **Architecture Support**: larch64 (TICI), aarch64, x86_64, Darwin
- **Compilers**: clang/clang++ (required)
- **Python**: 3.11+ required

See *tools/CLAUDE.md* for detailed build commands and cross-platform development.

## Key Dependencies

- **Core**: pycapnp, Cython, numpy, sympy
- **ML**: onnx, onnxruntime-gpu, tinygrad
- **Hardware**: libusb1, spidev (Linux only)
- **UI**: Qt5 (PyQt5 on x86_64)
- **Communication**: pyzmq for messaging

See *tools/CLAUDE.md* for dependency management system details.

## Hardware Platforms

Code supports multiple architectures with platform-specific implementations in *system/hardware/*:
- **larch64**: Linux TICI (aarch64 with AGNOS)
- **aarch64**: Linux PC aarch64
- **x86_64**: Linux PC x64
- **Darwin**: macOS (x64/arm64)

See *system/CLAUDE.md* for hardware abstraction details.

## Development Notes

- All Python imports must use absolute paths (e.g., `openpilot.selfdrive`)
- Code style enforced via ruff with 160 character line limit
- 2-space indentation for Python
- Type hints required (mypy enforcement)
- No unittest - use pytest only

See *tools/CLAUDE.md* for detailed development commands and testing procedures.

## Documentation Maintenance

Comprehensive documentation is maintained in `/data/openpilot/agentDocumentation/` for development environment analysis, cross-platform testing strategies, infrastructure improvements, and implementation roadmaps.

### Documentation Workflow
1. **Update documentation** as part of normal development workflow
2. **Mark completed objectives** in roadmap documents
3. **Add new ideas** and discoveries to relevant docs
4. **Track infrastructure changes** in cleanup plan
5. **Document platform-specific issues** and solutions

### Documentation Directory Overview

The `agentDocumentation/` directory contains:
- **`CRITICAL_RUNTIME_DEPENDENCIES.md`** - Analysis of essential runtime dependencies required by openpilot.
- **`EXTERNAL_IMPORTS_ANALYSIS.md`** - Detailed breakdown of external library imports and their usage.
- **`IMMEDIATE_ACTION_PLAN.md`** - Prioritized quick-start action items to address immediate development tasks.
- **`INFRASTRUCTURE_CLEANUP_PLAN.md`** - Roadmap for cleaning and refactoring infrastructure components.
- **`README.md`** - Overview and navigation guide for this documentation directory.
- **`CROSS_PLATFORM_TESTING_PLAN.md`** - Strategies for cross-platform testing across supported architectures.
- **`DEVELOPMENT_ENVIRONMENT.md`** - Analysis and setup instructions for the development environment.
- **`BOOT_SEQUENCE_ROADMAP.md`** - Comprehensive plan to replace FrogPilot boot graphics with professional terminal interface.
- **`CONCIERGE_REFACTOR_PLAN.md`** - Comprehensive architectural refactor plan for the Concierge web server to address separation of concerns and code maintainability.
- **`CONCIERGE_REFACTOR_CHECKLIST.md`** - Progress tracking checklist for the Concierge refactor implementation.

## Platform Detection

```python
TICI = os.path.isfile('/TICI')
PC = not TICI
```

See *system/CLAUDE.md* for hardware platform details and *tools/CLAUDE.md* for cross-platform development.

## SSH Configuration

For git operations, SSH keys are stored in `~/.ssh/`:
- Private key: `~/.ssh/claude_github_key`
- Public key: `~/.ssh/claude_github_key.pub`

## System Configuration

For system operations requiring elevated privileges:
- Sudo password: stored in `~/.sudo_pass` (permissions 600)
- Use with: `sudo -S command < ~/.sudo_pass`

## Release Management

See *release/CLAUDE.md* for prebuilt workflow details and fast device installation procedures.

## Current Status

**Last Updated:** January 8, 2025 20:45 PST
**Current Commit:** `cae214e3` - Refactor Concierge UI: Move diagnostics into toggle description

### Build Ready Status
- **TICI Native Builds**: All required libraries present, build should complete successfully
- **x86_64 Development**: Fully functional with all dependencies resolved
- **Runtime Dependencies**: Comprehensive multi-layered system handles 661 external imports
- **GUI Integration**: Concierge web server management now available in FrogPilot Utilities
  - Enhanced diagnostics with real-time health monitoring
  - Automatic dependency installation with Fix button (TICI-aware)
  - Platform-specific behavior:
    - TICI: Verifies pre-installed Python deps, skips Node.js deps
    - Development: Uses Poetry/npm with timeouts to prevent hanging
  - Real-time progress display with [CONCIERGE] prefixed messages
  - Timeout protection: 30s for Poetry, 60s for npm
  - Toggle disabled when dependencies missing
  - Relaunch button for easy service restart
- **Concierge Refactor Plan**: Comprehensive architectural refactor plan created to address monolithic code structure and improve maintainability
- **Boot UI Overhaul**: Replaced FrogPilot graphics with terminal-based boot interface
  - ASCII art Chauffeur logo with venetian blind effect
  - Real-time service status display
  - Actionable error reporting with stack traces
  - Backward compatible with existing spinner
  - Fixed TICI display rendering (centered for 2160x1080 screen)
  - Added simple fallback UI for debugging display issues

### Concierge UI Updates
- **Refactored UI**: All diagnostics now integrated into the toggle control's expandable description area
- **Fixed Text Wrapping**: Long diagnostic messages are now properly wrapped at 60 characters to prevent screen overflow
- **TICI CSS Handling**: 
  - Pre-built CSS detection on TICI devices
  - Clear error messaging when Tailwind CSS needs to be built offline
  - Created `BUILD_TAILWIND.md` with detailed instructions for building CSS on development machines
- **Improved Fix Button**: 
  - Now appears inline within the description when dependencies are missing
  - Real-time progress display during installation
  - Proper error handling and feedback
- **Simplified Architecture**: Removed separate status widget, all functionality now in single toggle control

See *tools/CLAUDE.md* for detailed dependency management and *agentDocumentation/* for complete development history.

## Additional Guidance

- Always maintain a file called AGENTS.md for each CLAUDE.md and make AGENTS.md an exact copy of CLAUDE.md
- When user says "commit xyz", assume they mean commit AND push unless they specifically say not to push
- After every push, update all relevant documentation (CLAUDE.md, AGENTS.md, and any other affected docs) with current status, timestamp, and commit hash

- Whenever you perform a `git commit` or `git push`, update all `CLAUDE.md` and `AGENTS.md` files (root and in `agentDocumentation/`) to include any new or updated documentation and refresh the **Last Updated** and **Current Commit** fields in each file.

See *tools/CLAUDE.md* for detailed dependency management system

## Memories

- Always include a current time and which commit we are on when updating documentation
- Never include "co-authored by claude" or anything of that sort in commit notes or messages