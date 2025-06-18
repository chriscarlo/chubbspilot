# Claude Instructions for FrogPilot Components

## Critical Setup Information
This directory contains FrogPilot-specific enhancements to the OpenPilot system.

**⚠️ IMPORTANT:** Always maintain the corresponding AGENTS.md file alongside this CLAUDE.md file. When updating this file, copy the exact contents to AGENTS.md. See "File Maintenance" section below.

## Directory Structure
- **`controls/`** - Enhanced control algorithms and libraries
- **`navigation/`** - Map and navigation system (CURRENT PRIORITY)
- **`ui/`** - User interface components and themes
- **`assets/`** - Themes, models, and asset management
- **`fleetmanager/`** - Web-based fleet management interface
- **`utilities/`** - System utilities and tools

## Current Development Priorities

### 1. Navigation System (HIGH PRIORITY)
- **Location**: `navigation/`
- **Focus**: Map download integration with mapd/pfeifer repository
- **Status**: Active development on exp04 branch
- **Key Files**: `mapd.py`, `map_download_helper.py`, `test_map_download.py`
- **See**: `navigation/CLAUDE.md` for detailed instructions

### 2. Control Systems
- **Location**: `controls/lib/`
- **Key Components**: Unified turn speed controller, acceleration control
- **Status**: Recent unification of MTSC/VTSC systems

## Key Configuration Files
- **`frogpilot_variables.py`** - Core system variables and paths
- **`frogpilot_process.py`** - Main process management
- **`frogpilot_utilities.py`** - Utility functions including map downloads
- **`frogpilot_functions.py`** - Core FrogPilot functionality

## Common Development Tasks

### Testing FrogPilot Components
```bash
# Test navigation system
python -m pytest selfdrive/frogpilot/navigation/test_*.py

# Test map downloads
python selfdrive/frogpilot/navigation/test_map_download.py

# Test control systems
python -m pytest selfdrive/frogpilot/controls/test_*.py
```

### Map Download System
```bash
# Check current map selection
python -c "from openpilot.selfdrive.frogpilot.frogpilot_variables import params; print(params.get('MapsSelected', encoding='utf-8'))"

# Trigger download manually
python -c "from openpilot.selfdrive.frogpilot.frogpilot_variables import params_memory; import json; params_memory.put('OSMDownloadLocations', json.dumps({'states': ['CA'], 'nations': []}))"
```

### Fleet Manager
```bash
# Start fleet manager (runs on port 8082)
python selfdrive/frogpilot/fleetmanager/fleet_manager.py

# Access at: http://device_ip:8082
```

## Integration Points

### Process Configuration
FrogPilot components are integrated into the main system via `system/manager/process_config.py`:
- `frogpilot_process` - Main FrogPilot coordinator
- `mapd` - Map daemon for navigation
- `fleet_manager` - Web interface

### Parameter System
FrogPilot uses OpenPilot's parameter system:
- **`params`** - Persistent parameters
- **`params_memory`** - In-memory parameters
- Key navigation params: `MapsSelected`, `OSMDownloadLocations`, `OSMDownloadProgress`

## Build and Test Workflow
```bash
# Build FrogPilot components
scons selfdrive/frogpilot/

# Test all FrogPilot components
python -m pytest selfdrive/frogpilot/

# Check UI components (requires Qt)
# See ui/ subdirectory for specific instructions
```

## File Maintenance

### AGENTS.md Synchronization
**CRITICAL**: This CLAUDE.md file must be kept in sync with the corresponding AGENTS.md file.

**When updating this file:**
1. Copy the entire contents of this file
2. Paste into the corresponding AGENTS.md file 
3. Ensure both files are identical
4. Commit both files together

**Location of twin file**: `selfdrive/frogpilot/AGENTS.md`

## Safety Considerations
- FrogPilot modifies autonomous driving behavior - test thoroughly
- Navigation changes affect route planning and turn control
- Fleet manager provides remote device access - verify security settings
- Always test on safe routes before deploying changes

## Documentation References
- Fleet Manager: `fleetmanager/README.md`
- Navigation system: `navigation/CLAUDE.md` (when created)
- Asset management: `assets/README.md` (if exists)
- Main project docs: See root `CLAUDE.md`