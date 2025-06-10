# Python Unfuckery Complete - Summary Report

## What Was Fixed

### 1. Created PYTHON_TRUTH.md
- Single source of truth for all Python configuration
- Located at `/data/openpilot/PYTHON_TRUTH.md`
- Clearly documents the ONLY correct way to use Python

### 2. Cleaned Python Installation
- Removed Python 3.12 compiled files from 3.11 directory
- Fixed package installation methods
- Ensured all packages use Python 3.11.4

### 3. Updated ALL Documentation
- Added Python truth reference to all CLAUDE.md files
- Fixed incorrect pip install examples
- Added warnings about ephemeral directories

### 4. Created Pre-flight Check Script
- `/data/openpilot/scripts/python_preflight_check.sh`
- Run this to validate Python environment
- Shows exactly what needs fixing

### 5. Added Python Validation to Scripts
- Critical scripts now validate Python version
- Automatic path setup in all scripts
- Clear error messages if wrong Python used

## The Rules (Forever)

1. **ALWAYS USE**: `/home/chris/.pyenv/versions/3.11.4/bin/python3`
2. **ALWAYS INSTALL TO**: `/data/openpilot/.local/lib/python3.11/site-packages`
3. **ALWAYS SET**: `export PYTHONPATH="/data/openpilot:/data/openpilot/.local/lib/python3.11/site-packages"`
4. **NEVER USE**: System pip3, pip install --user, or any other method

## Quick Commands

```bash
# Check environment
/data/openpilot/scripts/python_preflight_check.sh

# Set environment
export PYTHONPATH="/data/openpilot:/data/openpilot/.local/lib/python3.11/site-packages"

# Install packages
/home/chris/.pyenv/versions/3.11.4/bin/python3 -m pip install \
  --target=/data/openpilot/.local/lib/python3.11/site-packages \
  <package>
```

## Prevention Strategy

1. **PYTHON_TRUTH.md** - Always refer to this first
2. **Pre-flight checks** - Run before any Python work
3. **Script validation** - All scripts check Python version
4. **Documentation** - All CLAUDE.md files reference truth
5. **NO EXCEPTIONS** - Follow the rules exactly

This should be the LAST TIME we have Python dependency issues.