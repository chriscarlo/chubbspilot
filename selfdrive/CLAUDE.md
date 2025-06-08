# CLAUDE.md - Selfdrive Directory

Core driving logic and vehicle interfaces for the openpilot chauffeur fork.

## Architecture Overview

The `selfdrive/` directory contains the core autonomous driving algorithms and vehicle integration:

- **`controls/`** - Vehicle control algorithms (controlsd.py, plannerd.py, radard.py)  
- **`car/`** - Vehicle-specific interfaces and fingerprinting
- **`modeld/`** - ML model inference (vision models)
- **`ui/`** - User interface and Qt components
- **`frogpilot/`** - Custom FrogPilot extensions

## Key Components

### Controls
- **controlsd.py** - Main vehicle control loop
- **plannerd.py** - Path planning and trajectory generation
- **radard.py** - Radar data processing and object tracking

### Car Interface
- Vehicle-specific CAN message handling
- Fingerprinting for vehicle identification
- Safety model implementations
- Steering, acceleration, and braking interfaces

### Model Inference
- **modeld/** - Primary vision model for driving
- **classic_modeld/** - Legacy model implementation
- **tinygrad_modeld/** - TinyGrad-based model implementation
- **dmonitoringmodeld** - Driver monitoring model

### User Interface
- Qt-based UI components
- Real-time driving visualization
- Settings and configuration interface
- Alert and notification system

### FrogPilot Extensions
Custom enhancements specific to this fork:
- Additional driving features
- Custom UI elements
- Extended configuration options

## Platform Detection

All selfdrive components use platform detection for hardware-specific behavior:

```python
TICI = os.path.isfile('/TICI')
PC = not TICI
```

## Development Notes

- All Python imports use absolute paths (e.g., `openpilot.selfdrive`)
- Code style enforced via ruff with 160 character line limit
- 2-space indentation for Python
- Type hints required (mypy enforcement)

## Building Selfdrive Components

```bash
# Build UI components
scons selfdrive/ui/

# Build model inference
scons selfdrive/modeld/

# Build specific control component
scons selfdrive/controls/
```

## Testing

```bash
# Run selfdrive-specific tests
pytest selfdrive/

# Run car interface tests
pytest selfdrive/car/

# Run control algorithm tests
pytest selfdrive/controls/
```

## Simulation

For development and testing without hardware:

```bash
# Use simulation mode
USE_SIMULATOR=1 python selfdrive/test/process_replay/replay.py
```