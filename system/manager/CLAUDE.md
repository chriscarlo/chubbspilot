# Claude Instructions for System Manager

## Critical Setup Information
This directory contains the system process manager that orchestrates all OpenPilot/FrogPilot processes.

**⚠️ IMPORTANT:** Always maintain the corresponding AGENTS.md file alongside this CLAUDE.md file. When updating this file, copy the exact contents to AGENTS.md. See "File Maintenance" section below.

## Key Components

### Process Configuration (`process_config.py`)
This is the **central configuration file** that defines all system processes, their dependencies, and when they run.

### Current FrogPilot Processes
```python
# Key FrogPilot processes in process_config.py:
PythonProcess("frogpilot_process", "selfdrive.frogpilot.frogpilot_process", always_run)
PythonProcess("mapd", "selfdrive.frogpilot.navigation.mapd", always_run)  
PythonProcess("fleet_manager", "selfdrive.frogpilot.fleetmanager.fleet_manager", always_run)
```

## Process Types and Functions

### Process Condition Functions
- **`always_run`** - Process runs regardless of driving state
- **`only_onroad`** - Process only runs while driving
- **`only_offroad`** - Process only runs when parked
- **`driverview`** - Runs when driver monitoring is active

### FrogPilot-Specific Functions
- **`allow_logging`** - Controls logging based on FrogPilot settings
- **`allow_uploads`** - Controls uploads based on FrogPilot settings

## Understanding Process Dependencies

### Core System Processes
```bash
# Always running processes
- frogpilot_process (coordinates FrogPilot features)
- mapd (map daemon for navigation)
- fleet_manager (web interface)
- ui (user interface)
- pandad (hardware interface)

# Driving-only processes  
- controlsd (vehicle control)
- plannerd (path planning)
- radard (radar processing)
- locationd (GPS/positioning)
```

### Process Debugging
```bash
# Check running processes
ps aux | grep -E "(python|\.py)" | grep -E "(frogpilot|mapd|fleet)"

# Monitor process status
python -c "
import cereal.messaging as messaging
sm = messaging.SubMaster(['managerState'])
sm.update()
for proc in sm['managerState'].processes:
    if 'frog' in proc.name or 'mapd' in proc.name:
        print(f'{proc.name}: running={proc.running}, pid={proc.pid}')
"
```

## Modifying Process Configuration

### Adding New Processes
When adding FrogPilot processes:
1. **Define the process** in the `procs` list
2. **Choose appropriate condition function** (always_run, only_onroad, etc.)
3. **Test thoroughly** to ensure no conflicts

### Example Process Addition
```python
# Template for adding new FrogPilot process
PythonProcess("new_process_name", "selfdrive.frogpilot.module.script", condition_function)
```

### Process Monitoring
```bash
# View process configuration
python -c "
from openpilot.system.manager.process_config import managed_processes
for name, proc in managed_processes.items():
    if 'frog' in name or 'mapd' in name:
        print(f'{name}: {proc.proc[1]} - {proc.enabled}')
"
```

## Integration with FrogPilot

### Key Integration Points
1. **frogpilot_process** - Main coordinator that:
   - Manages FrogPilot-specific features
   - Coordinates map downloads
   - Handles UI integration
   - Manages theme and asset updates

2. **mapd** - Navigation daemon that:
   - Downloads map data from pfeifer repository
   - Processes OSM data for navigation
   - Provides map data to control systems

3. **fleet_manager** - Web interface that:
   - Provides remote access to device
   - Manages system settings and logs
   - Handles navigation input

### Process Communication
Processes communicate via cereal messaging:
```bash
# Monitor FrogPilot messages
python -c "
import cereal.messaging as messaging
sm = messaging.SubMaster(['frogpilotPlan', 'frogpilotNavigation'])
while True:
    sm.update()
    if sm.updated['frogpilotPlan']:
        print('FrogPilot plan updated')
    if sm.updated['frogpilotNavigation']:
        print('FrogPilot navigation updated')
"
```

## Development and Testing

### Testing Process Changes
```bash
# Test process configuration syntax
python -c "
from openpilot.system.manager.process_config import managed_processes
print(f'Loaded {len(managed_processes)} processes successfully')
"

# Check specific process definitions
python -c "
from openpilot.system.manager.process_config import managed_processes
frog_procs = {k: v for k, v in managed_processes.items() if 'frog' in k or 'mapd' in k}
for name, proc in frog_procs.items():
    print(f'{name}: {proc}')
"
```

### Process Lifecycle Management
The manager handles:
- **Starting processes** based on conditions
- **Restarting failed processes** automatically  
- **Stopping processes** when conditions change
- **Monitoring process health** and performance

## Safety Considerations

### Critical Safety Notes
- **Process manager controls safety-critical systems**
- **Always test process changes thoroughly**
- **Ensure process dependencies are correct**
- **Monitor for process crashes or failures**

### Process Monitoring Commands
```bash
# Check for crashed processes
dmesg | grep -i "killed\|segfault\|crashed"

# Monitor process restarts
tail -f /tmp/tmux_out.log | grep -i "process\|restart\|died"

# Check system resources
top -p $(pgrep -d, -f "python.*frogpilot\|mapd")
```

## File Maintenance

### AGENTS.md Synchronization
**CRITICAL**: This CLAUDE.md file must be kept in sync with the corresponding AGENTS.md file.

**When updating this file:**
1. Copy the entire contents of this file
2. Paste into the corresponding AGENTS.md file 
3. Ensure both files are identical
4. Commit both files together

**Location of twin file**: `system/manager/AGENTS.md`

## Troubleshooting

### Common Issues
1. **Process not starting**: Check condition function and dependencies
2. **Process crashing**: Check logs and import errors
3. **Process not responding**: Check for deadlocks or infinite loops
4. **High CPU usage**: Monitor process performance and optimize

### Debug Commands
```bash
# Check process manager logs
tail -f /tmp/tmux_out.log | grep manager

# Restart specific process (if needed)
# (Note: This requires manager restart - be careful)
python -c "
from openpilot.system.manager.process_config import managed_processes
print('Process restart requires manager intervention')
"

# Check process imports manually
python -c "
try:
    import openpilot.selfdrive.frogpilot.frogpilot_process
    print('✓ frogpilot_process imports successfully')
except Exception as e:
    print('✗ Import failed:', e)
"
```

## Related Documentation
- **FrogPilot Main**: `../../selfdrive/frogpilot/CLAUDE.md`
- **Navigation System**: `../../selfdrive/frogpilot/navigation/CLAUDE.md`
- **Fleet Manager**: `../../selfdrive/frogpilot/fleetmanager/README.md`
- **Main Instructions**: `../../CLAUDE.md`