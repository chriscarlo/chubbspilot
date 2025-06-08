# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 CRITICAL DOCUMENTATION REQUIREMENTS 🚨

**READ THIS FIRST - MANDATORY FOR ALL AGENTS:**

1. **ALWAYS maintain a file called AGENTS.md for each CLAUDE.md and make AGENTS.md an exact copy of CLAUDE.md**
2. **When user says "commit xyz", assume they mean commit AND push unless they specifically say not to push**
3. **NEVER log status updates, implementation details, or commit tracking in CLAUDE.md files**
4. **For development history and status updates, use `agentDocumentation/CHANGELOG.md`**
5. **Whenever you perform a `git commit` or `git push`, update CHANGELOG.md with changes, NOT CLAUDE.md**
6. **CLAUDE.md files are for AGENT INSTRUCTIONS ONLY - keep them clean and focused**

## 📋 Current Development Status

For current build status, recent changes, and implementation details, see:
**`agentDocumentation/CHANGELOG.md`**

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

## Documentation Structure

Comprehensive documentation is maintained in `/data/openpilot/agentDocumentation/`:

### Key Documentation Files
- **`CHANGELOG.md`** - Development history, status updates, and implementation tracking
- **`BUILD_TAILWIND.md`** - Instructions for building Tailwind CSS for Concierge
- **`DEVELOPMENT_ENVIRONMENT.md`** - Analysis and setup instructions for the development environment
- **`INFRASTRUCTURE_CLEANUP_PLAN.md`** - Roadmap for cleaning and refactoring infrastructure components
- **`CONCIERGE_REFACTOR_PLAN.md`** - Comprehensive architectural refactor plan for the Concierge web server
- **`CRITICAL_RUNTIME_DEPENDENCIES.md`** - Analysis of essential runtime dependencies
- **`EXTERNAL_IMPORTS_ANALYSIS.md`** - Detailed breakdown of external library imports
- **`CROSS_PLATFORM_TESTING_PLAN.md`** - Strategies for cross-platform testing

### Documentation Workflow
1. **Update CHANGELOG.md** with development changes and status updates
2. **Mark completed objectives** in roadmap documents
3. **Add new discoveries** to relevant technical docs
4. **Keep CLAUDE.md clean** - no status tracking or implementation details
5. **Document platform-specific issues** and solutions in appropriate files

## Memories

- Always include current time and commit info in CHANGELOG.md, NOT CLAUDE.md
- Never include "co-authored by claude" in commit messages
- Focus on agent instructions in CLAUDE.md, development tracking in CHANGELOG.md