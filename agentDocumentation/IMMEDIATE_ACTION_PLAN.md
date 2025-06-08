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

## CRITICAL DISCOVERY: FrogPilot Prebuilt Release Workflow

### How FrogPilot/openpilot Handle Fast Installs

**Discovery**: FrogPilot (and upstream openpilot) use a special workflow to avoid 20+ minute compilation times on device:

1. **Build ON Device**: They run the build process directly on a TICI device
2. **Commit Binaries**: They commit compiled binaries to special release branches
3. **Mark as Prebuilt**: A `prebuilt` file indicates pre-compiled release
4. **Fast Install**: Users get working binaries immediately, no compilation needed

### The Release Process (from `release/build_release.sh`):
```bash
# Runs ON the TICI device at /data/openpilot
BUILD_DIR=/data/openpilot

# Build with minimal components
scons -j$(nproc) --minimal

# Clean build artifacts but KEEP binaries
find . -name '*.a' -delete
find . -name '*.o' -delete
find . -name '*.os' -delete

# Mark as prebuilt
touch prebuilt

# Commit binaries to git
git add -f .
git commit --amend -m "openpilot v$VERSION"

# Push to release branch
git push -f origin $RELEASE_BRANCH
```

### Near-Term Objectives for This Fork

1. **Implement Prebuilt Workflow** [HIGH PRIORITY]
   - Set up Jenkins/CI to build on actual TICI hardware
   - Create release branches with prebuilt binaries
   - Automate the release process

2. **Device Build Compatibility** [IMMEDIATE]
   - Ensure current fork can build on TICI
   - Fix any device-specific build issues
   - Test installation process

3. **Create Build Documentation**
   - Document exact build steps on device
   - Create troubleshooting guide
   - Set up automated testing

### Information Needed from TICI Device

To ensure this fork builds on device, we need:

1. **System Information**:
   ```bash
   # OS and kernel version
   cat /etc/os-release
   uname -a
   
   # Python version
   python3 --version
   python3 -m pip --version
   
   # Compiler versions
   gcc --version
   clang --version
   
   # Build tools
   scons --version
   poetry --version || echo "poetry not found"
   ```

2. **Library Versions**:
   ```bash
   # Check critical libraries
   ldconfig -p | grep -E "(libicu|libQt5|libOpenCL)"
   pkg-config --modversion capnp
   
   # Python packages
   python3 -m pip list | grep -E "(numpy|cython|pyqt5)"
   ```

3. **Build Environment**:
   ```bash
   # Check environment variables
   env | grep -E "(PATH|PYTHONPATH|LD_LIBRARY_PATH)"
   
   # Check build directories
   ls -la /data/
   df -h /data
   
   # Check for AGNOS-specific paths
   ls -la /system/comma/usr/
   ```

4. **Test Current Build**:
   ```bash
   # Try building a simple component
   cd /data/openpilot
   scons -j1 cereal/
   
   # Check for errors
   echo $?
   ```

5. **Device-Specific Files**:
   ```bash
   # Check for device markers
   ls -la /TICI /AGNOS
   
   # Check hardware config
   cat /proc/cpuinfo | head -20
   cat /proc/meminfo | head -10
   ```

### Immediate Actions to Take

1. **Fix Build Issues**: Based on device info, update build scripts to match device environment
2. **Create Device Profile**: Document exact versions and paths from device
3. **Set Up Remote Build**: Configure ability to trigger builds on device
4. **Test Installation**: Verify fork can be installed and run