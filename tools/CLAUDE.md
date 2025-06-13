# Tools Directory Guide

This directory contains development, testing, and analysis tools for openpilot.

## Key Tools Overview

### 1. **Simulation (sim/)**
Contains the MetaDrive simulator integration for testing openpilot without hardware.

**MetaDrive is already installed** in the poetry environment (only on x86_64, not aarch64).

```bash
# Launch openpilot in simulation mode
./sim/launch_openpilot.sh

# Run the MetaDrive bridge (in another terminal)
./sim/run_bridge.py

# With joystick support
./sim/run_bridge.py --joystick
```

**Features:**
- Full driving simulation with MetaDrive
- Simulated cameras, sensors, and car interface
- Manual control via keyboard (WASD) or joystick
- No hardware dependencies
- Bridge controls:
  - `1` - Cruise Resume/Accel
  - `2` - Cruise Set/Decel  
  - `3` - Cruise Cancel
  - `r` - Reset simulation
  - `i` - Toggle ignition
  - `q` - Exit

### 2. **Replay (replay/)**
Replay recorded drives for debugging and analysis.

```bash
# Basic replay
cd tools/replay && ./replay <route-name>

# With UI
python replay/ui.py <route-name>
```

### 3. **Cabana (cabana/)**
CAN bus analysis and DBC file editor with real-time visualization.
- Live CAN stream analysis
- Signal plotting and discovery
- DBC file editing

### 4. **PlotJuggler (plotjuggler/)**
Real-time data visualization tool with pre-configured layouts.

```bash
python plotjuggler/juggle.py --layout layouts/longitudinal.xml
```

### 5. **Joystick Control (joystick/)**
Control the car with a game controller for testing.

```bash
python joystick/joystickd.py
```

### 6. **Car Porting (car_porting/)**
Tools for adding support for new vehicles:
- `auto_fingerprint.py` - Automatic vehicle fingerprinting
- `test_car_model.py` - Test new car implementations
- Example notebooks for specific manufacturers

### 7. **Camera Stream (camerastream/)**
Stream camera data over network using compressed VisionIPC.

### 8. **Development Scripts**

**Setup:**
- `install_python_dependencies.sh` - Install Python packages
- `install_ubuntu_dependencies.sh` - Install system packages
- `ubuntu_setup.sh` - Complete Ubuntu dev environment setup
- `mac_setup.sh` - macOS setup

**Analysis:**
- `latencylogger/` - Measure system latency
- `profiling/` - Performance profiling tools
- `serial/` - Serial console access
- `webcam/` - Use webcam as camera input

### 9. **Library (lib/)**
Shared Python utilities:
- Route and log reading
- API client
- Authentication
- File caching
- Video processing

## Common Development Workflows

### Testing Without Hardware
```bash
# Option 1: Simulation with specific car
FINGERPRINT=TOYOTA_RAV4_TSS2 ./sim/launch_openpilot.sh
./sim/run_bridge.py

# Option 2: Test car interface locally
./local_car_test.py --car honda_accord --interface-test

# Option 3: Generate synthetic car data
./synthetic_car_test.py --scenario cruise --fingerprint HONDA_CIVIC_2022

# Option 4: Webcam input
./webcam/start_camerad.sh

# Option 5: List available test cars
./local_car_test.py --list
```

### Testing Specific Cars Without Comma Servers

Since authentication is required for downloading routes, you can:

1. **Use simulation** - Test any car model in MetaDrive:
   ```bash
   FINGERPRINT=HYUNDAI_SONATA ./sim/launch_openpilot.sh
   ```

2. **Generate synthetic data** - Create fake sensor data:
   ```bash
   ./synthetic_car_test.py --fingerprint TOYOTA_CAMRY
   ```

3. **Override fingerprint** - Force openpilot to think it's in a specific car:
   ```bash
   export FINGERPRINT=SUBARU_OUTBACK
   export SKIP_FW_QUERY=1
   export NOBOARD=1
   ```

### IMPORTANT: Testing for 2023 Kia EV6 (Target Vehicle)

**This codebase is being developed EXCLUSIVELY for the 2023 Kia EV6 with HDA II and CAN-FD.**

For all testing, use:
```bash
# Set fingerprint for Kia EV6
export FINGERPRINT="HYUNDAI_KIA_EV6"

# Test with simulation
FINGERPRINT=HYUNDAI_KIA_EV6 ./sim/launch_openpilot.sh
./sim/run_bridge.py

# Test car interface
./local_car_test.py --fingerprint HYUNDAI_KIA_EV6 --interface-test

# Generate synthetic EV6 data
./synthetic_car_test.py --fingerprint HYUNDAI_KIA_EV6 --scenario cruise
```

The EV6 uses:
- CAN-FD protocol
- HDA II (Highway Driving Assist II)
- Located in: `selfdrive/car/hyundai/`
- Enum: `CAR.KIA_EV6`

### Debugging
```bash
# Live CAN analysis
./cabana/cabana

# Plot real-time data
python plotjuggler/juggle.py

# Profile performance
./profiling/py-spy/profile.sh
```

### Adding New Car Support
```bash
# Collect fingerprint
python car_porting/auto_fingerprint.py

# Test implementation
python car_porting/test_car_model.py
```

## Environment Variables

Key variables for tools:
- `SIMULATION=1` - Enable simulation mode
- `PASSIVE=0/1` - Passive mode (no control)
- `FINGERPRINT` - Override car detection
- `BLOCK` - Comma-separated list of processes to skip
- `MAPBOX_TOKEN` - For map display

## Testing Tips

1. **For Python-only changes**: Use simulation or replay
2. **For UI changes**: Run UI standalone with mocked data
3. **For control logic**: Use joystick control in a safe environment
4. **For new car support**: Start with car_porting tools

## Security Note

The SSH key in `ssh/id_rsa` has been moved to `/persist/.secret/` and symlinked back for security.