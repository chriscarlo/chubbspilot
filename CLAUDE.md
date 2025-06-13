# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Openpilot is an open-source driver assistance system providing Adaptive Cruise Control (ACC) and Automated Lane Centering (ALC). This is a fork with ongoing work to remove driver monitoring components.

**IMPORTANT: This fork is being developed EXCLUSIVELY for the 2023 Kia EV6 with HDA II and CAN-FD.**
- Target vehicle: 2023 Kia EV6 (HDA II, CAN-FD)
- Do NOT remove other car support (many dependencies break)
- Focus all testing and development on EV6-specific code

## Development Commands

```bash
# Environment setup
tools/ubuntu_setup.sh        # Install system dependencies
poetry shell                 # Activate Python virtual environment

# Building
scons -j$(nproc)            # Build everything
scons -j8 selfdrive/ui/     # Build specific component
scons -u -j8                # Build from current directory
scons -c                    # Clean build

# Testing
pytest .                    # Run all tests
pytest selfdrive/car/       # Run tests for specific module
pytest -k test_name         # Run specific test
pytest -m "not slow"        # Skip slow tests

# Code quality
pre-commit run --all        # Run all linters and formatters
ruff check .                # Python linting
ruff format .               # Python formatting
```

## Architecture

The codebase follows a modular architecture with clear separation of concerns:

- **cereal/**: Message definitions using Cap'n Proto for inter-process communication
- **selfdrive/**: Core driving logic
  - **car/**: Vehicle-specific interfaces - each supported car has its own subdirectory
  - **controls/**: Control algorithms for ACC and ALC
  - **modeld/**: Neural network models for vision processing
  - **locationd/**: Localization and calibration
- **system/**: System services (cameras, hardware abstraction, logging)
- **panda/**: CAN interface firmware
- **opendbc/**: CAN database files for vehicle communication

## Key Development Patterns

1. **Inter-process Communication**: Uses Cap'n Proto messages over ZMQ. Message definitions in `cereal/`.

2. **Vehicle Support**: New vehicles are added in `selfdrive/car/`. Each brand has its own module with standardized interfaces.

3. **Safety**: Safety-critical code follows MISRA C guidelines. Primary safety logic is in the Panda hardware.

4. **Testing**: Always run relevant tests after changes. Use pytest markers for different test types.

5. **Process Management**: Main processes are defined in `selfdrive/manager/process_config.py`.

## Important Context

- Current branch: `upstream-development`
- PR target branch: `exp00`
- Python 3.11 required
- Uses Git LFS for large files
- Driver monitoring system is being removed (see git status)

## Sensitive Files and Security

**IMPORTANT**: Sensitive files have been moved to `/persist/.secret/` for security. Never commit these files to version control.

### Locations of Sensitive Data:

1. **SSH Keys**:
   - `/persist/.secret/id_rsa` - SSH private key (symlinked from `tools/ssh/id_rsa`)
   
2. **System Credentials**:
   - `/persist/.secret/.sudo_pass` - Sudo password file (moved from `/home/chris/.sudo_pass`)
   
3. **API Tokens and Credentials**:
   - JWT tokens: Stored in `auth.json` (managed by `tools/lib/auth_config.py`)
   - Azure tokens: Located at `/data/azure_token` or via `AZURE_TOKEN` env var
   - Mapbox tokens: Via `MAPBOX_TOKEN` env var or `MapboxSecretKey` parameter
   
4. **Device Registration**:
   - Private key for JWT signing: `/comma/id_rsa` (referenced in `common/api/__init__.py`)
   - Registration keys: Managed by `system/athena/registration.py`

### Security Guidelines:

- Always check for sensitive data before committing
- Use environment variables for API keys when possible
- Store any new sensitive files in `/persist/.secret/`
- Create symlinks if needed for backward compatibility
- Never hardcode passwords, tokens, or private keys in the codebase

## Custom Forks and Dependencies

### mapd (Map Daemon)
- **Original source**: https://github.com/pfeiferj/mapd
- **Our fork**: https://github.com/chriscarlo/mapd (to be created)
- **Local copy**: `/data/openpilot/mapd_fork/`
- **Modified file**: `selfdrive/frogpilot/navigation/mapd.py` (updated to check our fork first)
- **Push script**: `mapd_fork/push_to_github.sh`

The mapd binary provides map and location data. We maintain our own fork to allow custom modifications for the EV6.