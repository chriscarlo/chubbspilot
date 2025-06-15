# Claude Instructions for Chauffeur/FrogPilot Tools

## Critical Setup Information
This directory contains development tools and utilities for the chauffeur/FrogPilot system.

**⚠️ IMPORTANT:** Always maintain the corresponding AGENTS.md file alongside this CLAUDE.md file. When updating this file, copy the exact contents to AGENTS.md. See "File Maintenance" section below.

## Key Tools and Utilities

### Development Environment
- **System Target**: Ubuntu 24.04
- **Primary Language**: Python 3.11+
- **Build System**: SCons with caching
- **Repository**: https://github.com/chriscarlo/chauffeur.git

### Environment Setup
For Claude Code/Codex development:
```bash
# Use bootstrap script (see root CLAUDE.md)
source /workspace/activate_env.sh

# Manual setup
python3 -m venv /tmp/openpilot-env
source /tmp/openpilot-env/bin/activate
export PYTHONPATH="/workspace"
export SCONS_CACHE="/tmp/scons_cache"
```

### Core Development Tools

#### Build System
```bash
# Full build
scons -j$(nproc)

# Clean build  
scons -c && scons -j$(nproc)

# Build specific components
scons selfdrive/frogpilot/
```

#### Testing Framework
```bash
# Run all tests
python -m pytest selfdrive/test/

# FrogPilot-specific tests
python -m pytest selfdrive/frogpilot/

# Navigation system tests
python -m pytest selfdrive/frogpilot/navigation/
```

## Tool Categories

### Analysis Tools
- **`replay/`** - Drive replay and analysis tools
- **`plotjuggler/`** - Data visualization and plotting
- **`cabana/`** - CAN message analysis and debugging

### Development Tools  
- **`scripts/`** - Miscellaneous utility scripts
- **`lib/`** - Supporting libraries for tools
- **`sim/`** - Simulation environment

### Hardware Tools
- **`serial/`** - Comma serial device tools
- **`ssh/`** - Device SSH utilities
- **`webcam/`** - PC webcam integration

## Common Development Workflows

### Building and Testing
```bash
# Quick development cycle
cd /workspace
source /tmp/openpilot-env/bin/activate

# Build changes
scons selfdrive/frogpilot/navigation/

# Run tests
python selfdrive/frogpilot/navigation/test_map_download.py

# Check integration
python -m pytest selfdrive/frogpilot/navigation/test_*.py
```

### Debugging Tools
```bash
# Monitor system processes
ps aux | grep -E "(frogpilot|mapd|fleet)"

# Check parameters
python -c "
from openpilot.selfdrive.frogpilot.frogpilot_variables import params
print('Branch:', params.get('GitBranch', encoding='utf-8'))
print('Version:', params.get('Version', encoding='utf-8'))
"

# Monitor logs
tail -f /tmp/tmux_out.log
```

### Map and Navigation Tools
```bash
# Test map downloads
python selfdrive/frogpilot/navigation/test_map_download.py

# Check map data
ls -la /data/media/0/osm/offline/

# Monitor mapd process
ps aux | grep mapd
```

## Development Best Practices

### Environment Management
- **Always use virtual environment** for Python dependencies
- **Set PYTHONPATH** to `/workspace` for proper imports
- **Use SCons cache** to speed up builds
- **Check branch status** before making changes

### Testing Protocol
1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test component interactions  
3. **System Tests**: Test full workflows
4. **Safety Tests**: Verify autonomous driving safety

### Git Workflow
```bash
# Always check current state
git branch --show-current
git status

# Development on exp04 branch
git checkout exp04
git pull origin exp04

# Commit with descriptive messages
git add <files>
git commit -m "component: description of changes"
git push origin exp04
```

## Tool-Specific Instructions

### Fleet Manager
```bash
# Start fleet manager
python selfdrive/frogpilot/fleetmanager/fleet_manager.py

# Access at http://device_ip:8082
# Features: dashcam, logs, navigation, device control
```

### Navigation Testing
```bash
# Map download testing
python selfdrive/frogpilot/navigation/test_map_download.py

# Controller testing
python selfdrive/frogpilot/navigation/test_unified_controller.py

# Performance monitoring
python selfdrive/frogpilot/navigation/monitor_performance.py
```

### Build System Debugging
```bash
# Check build dependencies
scons --tree=status selfdrive/frogpilot/

# Clean and rebuild
scons -c
rm -rf /tmp/scons_cache/*
scons -j$(nproc)

# Check compilation errors
scons selfdrive/frogpilot/ 2>&1 | grep -i error
```

## File Maintenance

### AGENTS.md Synchronization
**CRITICAL**: This CLAUDE.md file must be kept in sync with the corresponding AGENTS.md file.

**When updating this file:**
1. Copy the entire contents of this file
2. Paste into the corresponding AGENTS.md file 
3. Ensure both files are identical
4. Commit both files together

**Location of twin file**: `tools/AGENTS.md`

## Environment Variables Reference
See root `CLAUDE.md` for complete environment setup, but key variables:
```bash
PYTHONPATH="/workspace"
OPENPILOT_PREFIX="/workspace"  
SCONS_CACHE="/tmp/scons_cache"
COMMA_CACHE="/tmp/comma_cache"
```

## Safety and Security
- **Never test untested code in a real vehicle**
- **Use simulation and closed courses for testing**
- **Verify fleet manager security settings**
- **Monitor system resources during development**

## Related Documentation
- **Main Instructions**: `../CLAUDE.md`
- **FrogPilot Components**: `../selfdrive/frogpilot/CLAUDE.md`
- **Navigation System**: `../selfdrive/frogpilot/navigation/CLAUDE.md`
- **Build Instructions**: `README.md` (updated)