# Immediate Action Plan for Cross-Platform Development

## Current Situation
- **Dev Environment**: Ubuntu 24.04 x86_64
- **Target**: AGNOS/TICI aarch64
- **Need**: Test features locally before deploying to device

## Quick Win Solutions

### 1. Leverage Existing Infrastructure
The codebase already has cross-platform support! Use it:

```bash
# Build for TICI from your x86 machine
scons -j8 --arch=larch64

# Run tests that don't require hardware
pytest -m "not tici"

# Use simulation for driving scenarios
USE_SIMULATOR=1 python selfdrive/test/process_replay/replay.py
```

### 2. Set Up Mock Hardware Layer
Create a simple mock layer for testing:

```python
# In your test files
if PC:
    from selfdrive.hardware.mock import MockHardware as Hardware
else:
    from selfdrive.hardware import Hardware
```

### 3. Use Process Replay
Test with recorded data:
```bash
# Download test routes
python tools/lib/route.py <route_name>

# Replay through your code
python selfdrive/test/process_replay/replay.py <route_name>
```

### 4. Remote Device Testing
If you have a Comma device:
```bash
# Use existing build_chubbspilot.sh
./build_chubbspilot.sh

# Or manual SSH testing
ssh comma@<device_ip>
cd /data/openpilot
python your_test_script.py
```

## Recommended Workflow

### For New Features:
1. **Write code** with platform checks:
   ```python
   if TICI:
       # Hardware-specific code
   else:
       # Mock/simulation code
   ```

2. **Test locally**:
   ```bash
   # Unit tests
   pytest selfdrive/car/tests/test_your_feature.py
   
   # Integration with simulation
   python tools/sim/launch_sim.py
   ```

3. **Build for target**:
   ```bash
   scons -j8 --arch=larch64 your_component
   ```

4. **Deploy and test**:
   ```bash
   # If you have a device
   tools/ssh_deploy.py <device_ip>
   ```

### For Modifications:
1. **Check existing tests**: See how similar features are tested
2. **Use replay data**: Test against real driving scenarios
3. **Mock hardware calls**: Don't let hardware dependencies block you
4. **Verify on CI**: Let Jenkins test on real hardware

## Tools You Can Use NOW

### 1. MetaDrive Simulation
```bash
# Already integrated!
python tools/sim/launch_sim.py
```

### 2. Replay Testing
```bash
# Test against recorded drives
python selfdrive/test/process_replay/test_processes.py
```

### 3. Unit Test Suite
```bash
# Run all non-hardware tests
pytest -n auto -m "not tici"
```

### 4. Docker Development
```bash
# Use existing Docker setup
docker build -f Dockerfile.openpilot_base -t openpilot-base .
docker run -it openpilot-base bash
```

## What NOT to Do (Yet)

1. **Don't modify** core build system (SConstruct)
2. **Don't remove** any Docker files or scripts
3. **Don't change** architecture detection logic
4. **Don't alter** safety-critical code without hardware testing

## Next Development Session Tasks

1. **Set up cross-compilation** toolchain locally
2. **Create mock interfaces** for your specific features
3. **Write tests** that can run on both platforms
4. **Document** platform-specific code paths

## Key Files to Understand

1. **`selfdrive/hardware/`** - Hardware abstraction
2. **`selfdrive/test/`** - Testing infrastructure
3. **`tools/sim/`** - Simulation setup
4. **`SConstruct`** - Build configuration
5. **`conftest.py`** - pytest configuration

## Success Metrics

- [ ] Can build for aarch64 from x86_64
- [ ] Can run unit tests locally
- [ ] Can test with simulation
- [ ] Can deploy to device (if available)
- [ ] Can verify functionality before commit