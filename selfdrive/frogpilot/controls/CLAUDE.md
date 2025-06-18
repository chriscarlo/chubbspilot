# Claude Instructions for FrogPilot Control Systems

## Critical Setup Information
This directory contains FrogPilot's enhanced control algorithms and libraries for autonomous driving.

**⚠️ IMPORTANT:** Always maintain the corresponding AGENTS.md file alongside this CLAUDE.md file. When updating this file, copy the exact contents to AGENTS.md. See "File Maintenance" section below.

## Directory Structure
- **`lib/`** - Control libraries and algorithms
- **`frogpilot_planner.py`** - Main FrogPilot planning logic

## Current Status
- **Recent Work**: Unified turn speed controller (MTSC/VTSC consolidation)
- **Branch**: exp04 (active development)
- **Integration**: Connected with navigation system for turn speed control

## Key Components

### Control Libraries (`lib/`)
- **`unified_turn_controller.py`** - NEW: Unified MTSC/VTSC turn speed controller
- **`turn_speed_common.py`** - NEW: Shared utilities for turn speed calculations
- **`map_turn_speed_controller.py`** - Map-based turn speed control
- **`speed_limit_controller.py`** - Speed limit enforcement
- **`frogpilot_acceleration.py`** - Custom acceleration profiles
- **`frogpilot_following.py`** - Following distance control
- **`conditional_experimental_mode.py`** - Dynamic mode switching

### Migration Tools
- **`migrate_to_unified_controller.py`** - Migration utility for transitioning to unified system

## Unified Turn Speed Controller

### Overview
The unified controller consolidates:
- **MTSC** (Map Turn Speed Controller) - Uses map data for turn predictions
- **VTSC** (Vision Turn Speed Controller) - Uses vision model for turn detection

### Key Features
- Seamless switching between map-based and vision-based control
- Improved turn prediction accuracy
- Reduced speed oscillations
- Better integration with navigation system

### Testing Turn Controllers
```bash
# Test unified controller
python selfdrive/frogpilot/navigation/test_unified_controller.py

# Test MTSC integration  
python selfdrive/frogpilot/navigation/test_mtsc_integration.py

# Controller simulation
python selfdrive/frogpilot/navigation/test_controller_simulation.py
```

## Integration with Navigation

### Map Data Usage
- Controller receives map data from navigation system
- Uses turn curvature and speed limit data
- Integrates with mapd for real-time map updates

### Parameter Flow
1. **Map Data** → Navigation system processes OSM data
2. **Turn Detection** → Unified controller analyzes upcoming turns
3. **Speed Planning** → Calculates optimal speeds for turns
4. **Execution** → Applies speed adjustments via planner

## Development and Testing

### Running Controller Tests
```bash
# Full test suite
python -m pytest selfdrive/frogpilot/controls/

# Specific controller tests
python -m pytest selfdrive/frogpilot/controls/lib/test_*.py

# Integration tests
python -m pytest selfdrive/frogpilot/navigation/test_*controller*.py
```

### Performance Monitoring
```bash
# Monitor controller performance
python selfdrive/frogpilot/navigation/monitor_performance.py

# Check controller parameters
python -c "
from openpilot.selfdrive.frogpilot.frogpilot_variables import params
print('Turn Speed Controller:', params.get('TurnSpeedController', encoding='utf-8'))
print('Use Map Turn Speed:', params.get('UseMapTurnSpeed', encoding='utf-8'))
"
```

### Building Control Components
```bash
# Build control libraries
scons selfdrive/frogpilot/controls/

# Test build
python -c "
import openpilot.selfdrive.frogpilot.controls.lib.unified_turn_controller as utc
print('Unified controller loaded successfully')
"
```

## Safety Considerations

### Critical Safety Notes
- **Turn speed control directly affects vehicle safety**
- **Always test on safe, closed courses first**
- **Verify map data accuracy before deployment**
- **Monitor for speed oscillations or erratic behavior**

### Testing Protocol
1. **Simulation Testing**: Use controller simulation tools first
2. **Static Testing**: Verify calculations with known turn data
3. **Closed Course**: Test on safe, controlled environment
4. **Gradual Deployment**: Start with conservative settings

## Configuration Parameters

### Key Parameters
- **`TurnSpeedController`** - Controller mode selection
- **`UseMapTurnSpeed`** - Enable/disable map-based turn control
- **`VisionTurnControl`** - Enable/disable vision-based control
- **`AggressiveMode`** - Controller aggressiveness setting

### Parameter Management
```bash
# View current controller settings
python -c "
from openpilot.selfdrive.frogpilot.frogpilot_variables import params
control_params = ['TurnSpeedController', 'UseMapTurnSpeed', 'VisionTurnControl', 'AggressiveMode']
for param in control_params:
    value = params.get(param, encoding='utf-8')
    print(f'{param}: {value}')
"

# Reset to defaults (if needed)
python -c "
from openpilot.selfdrive.frogpilot.frogpilot_variables import params
params.remove('TurnSpeedController')
print('Controller settings reset')
"
```

## File Maintenance

### AGENTS.md Synchronization
**CRITICAL**: This CLAUDE.md file must be kept in sync with the corresponding AGENTS.md file.

**When updating this file:**
1. Copy the entire contents of this file
2. Paste into the corresponding AGENTS.md file 
3. Ensure both files are identical
4. Commit both files together

**Location of twin file**: `selfdrive/frogpilot/controls/AGENTS.md`

## Troubleshooting

### Common Issues
1. **Controller not engaging**: Check parameter settings and map data availability
2. **Erratic speed changes**: Verify turn detection accuracy and tune parameters
3. **Import errors**: Check that unified controller compiled correctly
4. **Performance issues**: Monitor CPU usage and optimize calculations

### Debug Commands
```bash
# Check controller status
tail -f /tmp/tmux_out.log | grep -i "turn\|speed\|controller"

# Verify controller imports
python -c "
try:
    from openpilot.selfdrive.frogpilot.controls.lib.unified_turn_controller import UnifiedTurnController
    print('✓ Unified controller imported successfully')
except ImportError as e:
    print('✗ Import failed:', e)
"
```

## Related Documentation
- **Navigation System**: `../navigation/CLAUDE.md`
- **Main FrogPilot**: `../CLAUDE.md`
- **Test Documentation**: `../navigation/test_scenarios_documentation.md`
- **Process Integration**: `../../../system/manager/process_config.py`