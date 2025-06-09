# CLAUDE.md

Agent instructions for Claude Code working with the chauffeur openpilot fork.

## 🚨 CRITICAL RULES 🚨

1. **ALWAYS keep AGENTS.md as exact copy of CLAUDE.md**
2. **"commit xyz" = commit AND push unless specified otherwise**
3. **NEVER log status/changes in CLAUDE.md - use `agentDocumentation/CHANGELOG.md`**
4. **ALWAYS update CHANGELOG.md and relevant docs with EVERY commit/push**
5. **Environment-specific capabilities - see Environment Detection section**

## 🚨 TICI PERSISTENCE RULES 🚨

**CRITICAL: On TICI devices, `/home/comma` is EPHEMERAL and wiped on every reboot!**

### Persistent Storage Locations:
- **`/persist/`** - For secrets, SSH keys, configs (NOT in git) - Only 27MB!
- **`/data/openpilot/`** - For dependencies, project files (in git)
- **NEVER use:**
  - `/home/comma/` - WIPED ON REBOOT
  - `pip install --user` - Goes to ephemeral home
  - `~/.ssh/` - Use `/persist/comma/.ssh/` instead

### Python Dependencies on TICI:
```bash
# CORRECT - Persistent installation
pip3 install --target=/data/openpilot/.local/lib/python3.11/site-packages <package>

# WRONG - Will be lost on reboot
pip3 install --user <package>
```

### Git/SSH Setup on TICI:
```bash
# Configure git to use persistent SSH key
git config --global core.sshCommand "ssh -i /persist/comma/.ssh/claude_github_key -o StrictHostKeyChecking=no"

# Repository has moved to:
git remote set-url origin git@github.com:chriscarlo/chauffeur.git
```

### Adding Python Path in Scripts:
```python
import sys
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
```

## Environment Detection

**CRITICAL: Detect your environment first to understand capabilities:**

```bash
# Check architecture
uname -m
# aarch64 = Running on TICI device (runtime environment)
# x86_64 = Running in WSL/Linux dev environment
```

### TICI Runtime Environment (aarch64)
- **Location:** Running directly on comma.ai TICI hardware
- **Capabilities:** Full system access, can run services, check logs, test hardware
- **Access to:** systemctl, journalctl, ps, hardware interfaces, CAN bus
- **Use for:** Testing, debugging live system, hardware integration
- **Note:** No sudo password required - running as comma user

### Development Environment (x86_64)
- **Location:** WSL or Linux development machine
- **Capabilities:** Code editing, building, unit tests
- **NO access to:** Runtime services, TICI hardware, live system logs
- **Use for:** Development, code changes, simulation testing

**Platform detection in Python:**
```python
import platform
IS_TICI = platform.machine() == "aarch64" and os.path.isfile('/TICI')
IS_DEV = platform.machine() == "x86_64"
```

## Project Overview

This is the **chauffeur** fork of openpilot (experimental branch) - an open-source driver assistance system. **WARNING: This is experimental/deprecated code - see README.md for safety warnings.**

### Project Structure

- **`selfdrive/`** - Core driving logic (*see selfdrive/CLAUDE.md*)
  - `controls/` - Vehicle control algorithms
  - `car/` - Vehicle-specific interfaces
  - `modeld/` - ML model inference
  - `ui/` - User interface (Qt)
  - `frogpilot/` - Custom FrogPilot extensions
- **`system/`** - System services (*see system/CLAUDE.md*)
- **`cereal/`** - IPC messaging (*see cereal/CLAUDE.md*)
- **`tools/`** - Dev utilities (*see tools/CLAUDE.md*)
- **`release/`** - Release management (*see release/CLAUDE.md*)
- **`opendbc/`** - CAN database definitions
- **`panda/`** - Hardware interface library

## Build Commands

```bash
# Basic build
scons -j$(nproc)

# Build options
scons -j$(nproc) --minimal     # No tests/tools
scons -j$(nproc) --coverage    # With coverage
scons -j$(nproc) --asan        # Address sanitizer
scons -j$(nproc) --ubsan       # UB sanitizer
scons --clean                  # Clean build

# Architecture-specific
scons --force-arch=larch64     # TICI hardware
scons --force-arch=aarch64     # Linux ARM64
scons --force-arch=x86_64      # x86_64

# Component builds
scons selfdrive/ui/
scons cereal/ common/
```

## Test Commands

```bash
# Run all tests
pytest

# Test options
pytest -m 'not slow'                    # Skip slow tests
pytest --cov --cov-report=xml           # With coverage
pytest -n auto                          # Parallel execution
pytest selfdrive/car/tests/             # Specific directory

# Run a single test
pytest path/to/test_file.py::test_name

# Common CI test command
CI=1 pytest --continue-on-collection-errors --cov --cov-report=xml --cov-append --durations=0 --durations-min=5 --hypothesis-seed 0 -n logical
```

## Linting & Code Quality

```bash
# Pre-commit hooks (recommended)
pre-commit install
pre-commit run --all-files

# Individual linters
ruff check .                   # Python linter
ruff format .                  # Python formatter
mypy --local-partial-types     # Type checking

# C++ linting
cppcheck --error-exitcode=1 --language=c++ --quiet --force -j8 <files>
cpplint --quiet --counting=total --linelength=240 <files>
```

## TICI-Specific Commands (aarch64 only)

```bash
# Service management
sudo systemctl status openpilot
sudo systemctl restart openpilot
sudo journalctl -u openpilot -f

# Hardware testing
cd /data/openpilot && python -c "from openpilot.selfdrive.car.tests.test_models import test_car_interfaces; test_car_interfaces()"

# CAN debugging
candump can0
cansend can0 123#DEADBEEF
```

## Development Requirements

- **Python:** 3.11+ (required)
- **Build tools:** SCons, Poetry, clang/clang++
- **Platforms:** larch64 (TICI), aarch64, x86_64, Darwin
- **Dependencies:** See `poetry.lock` and `requirements.txt`

## Code Style

- **Imports:** Absolute (`from openpilot.selfdrive.car import...`)
- **Line length:** 160 characters
- **Python indent:** 2 spaces
- **Type hints:** Required for all new code
- **Tests:** pytest only (no unittest)
- **C++:** Follow cpplint rules

## Credentials & Authentication

- **SSH:** `~/.ssh/claude_github_key[.pub]`
- **Sudo (dev environment only):** `sudo -S cmd < ~/.sudo_pass`
- **TICI Runtime:** No sudo password needed - running as comma user with necessary permissions

## Documentation

**Status/Changes:** `agentDocumentation/CHANGELOG.md`  
**Technical Docs:** See `agentDocumentation/` for dependencies, build instructions, refactor plans

## Key Reminders

- Include timestamp/commit hash in CHANGELOG.md entries
- No "co-authored by claude" in commit messages
- For component-specific details, always check the relevant subdirectory's CLAUDE.md
- Check your environment (TICI vs dev) before attempting runtime operations
- Remember: This is experimental/deprecated code (see README.md warnings)