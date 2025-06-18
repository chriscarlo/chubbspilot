# Claude Instructions for Chauffeur/FrogPilot

## Critical Setup Information
This is a chauffeur/FrogPilot fork of OpenPilot - an autonomous driving system. 

**⚠️ IMPORTANT:** Always maintain the corresponding AGENTS.md file alongside this CLAUDE.md file. When updating this file, copy the exact contents to AGENTS.md. See "File Maintenance" section below.

## Quick Start Commands
```bash
# Activate environment (after bootstrap)
source /tmp/openpilot-env/bin/activate
cd /workspace

# Build system
scons -j4

# Run tests
python -m pytest selfdrive/test/

# Current branch status
git branch --show-current
git status
```

## Environment Requirements
- **Python**: 3.11+ (primary language)
- **Build System**: SCons with cache in `/tmp/scons_cache`
- **Key Paths**: 
  - PYTHONPATH="/workspace"
  - OPENPILOT_PREFIX="/workspace"

## Current Development Focus Areas

### Navigation System (Priority: HIGH)
- **Location**: `selfdrive/frogpilot/navigation/`
- **Key Work**: Map download integration with mapd/pfeifer repository
- **Status**: Currently on exp04 branch with unified turn controller
- **See**: `selfdrive/frogpilot/navigation/CLAUDE.md` for detailed instructions

### Turn Speed Control System
- **Location**: `selfdrive/frogpilot/controls/lib/`
- **Key Files**: `unified_turn_controller.py`, `turn_speed_common.py`
- **Status**: Unified MTSC/VTSC system implemented

## Branch Strategy
- **Main Development**: `exp04` branch
- **Base Branch**: `exp00` (for PRs)
- **Always check current branch** before making changes

## Key Documentation References
- Build instructions: `tools/README.md`
- Car implementations: `selfdrive/car/README.md`
- FrogPilot features: Check individual component README files

## Common Tasks

### Git Workflow
```bash
# Check status
git status
git branch --show-current

# Commit changes
git add <files>
git commit -m "Description"
git push origin <branch>
```

### Building and Testing
```bash
# Clean build
scons -c && scons -j4

# Test specific module
python -m pytest selfdrive/frogpilot/navigation/test_*.py

# Check for type errors
# (Look for lint/typecheck commands in project)
```

## File Maintenance

### AGENTS.md Synchronization
**CRITICAL**: This CLAUDE.md file must be kept in sync with the corresponding AGENTS.md file.

**When updating this file:**
1. Copy the entire contents of this file
2. Paste into the corresponding AGENTS.md file 
3. Ensure both files are identical
4. Commit both files together

**Location of twin file**: `/workspace/AGENTS.md`

### Documentation Philosophy
- CLAUDE.md files are **instructional** - they tell Claude what to do
- README.md files are **documentary** - they describe what exists
- **Reference documentation, don't duplicate it** in CLAUDE.md files
- Keep instructions concise and actionable

## Error Handling
- **Import errors**: Check PYTHONPATH and virtual environment
- **Build errors**: Check SCons cache and dependencies
- **Git errors**: Verify branch and remote status
- **Test failures**: Check for missing dependencies or environment setup

## Security Notes
- This codebase contains autonomous driving logic - be careful with safety-critical changes
- Always test thoroughly before committing control system changes
- Verify map data sources and integrity

## System Access
- **Sudo password**: Available in `/persist/sudo_password.txt` (DO NOT copy this line to AGENTS.md)

## Getting Help
- Check component-specific CLAUDE.md files in subdirectories
- Refer to README.md files for documentation
- Use git log to understand recent changes
- Check process_config.py for system architecture