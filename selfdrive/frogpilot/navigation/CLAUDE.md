# Claude Instructions for FrogPilot Navigation System

## Critical Setup Information
This directory contains the FrogPilot navigation system, including map downloads and route planning.

**⚠️ IMPORTANT:** Always maintain the corresponding AGENTS.md file alongside this CLAUDE.md file. When updating this file, copy the exact contents to AGENTS.md. See "File Maintenance" section below.

## Current Status - HIGH PRIORITY
- **Branch**: exp04 (active development)
- **Focus**: Map download integration with mapd/pfeifer repository
- **Recent Work**: Unified turn speed controller implementation

## Key Files and Components

### Map Download System
- **`mapd.py`** - Main map daemon that downloads and runs mapd binary from pfeifer
- **`map_download_helper.py`** - Bridge between UI triggers and mapd downloads
- **`test_map_download.py`** - Test script for California/Nevada map downloads

### Map Integration
- **Source**: Maps downloaded from `https://map-data.pfeifer.dev/offline/`
- **Storage**: `/data/media/0/osm/offline/`
- **Binary**: mapd downloaded from `https://github.com/pfeiferj/openpilot-mapd/releases/`

## Map Download Workflow

### Current Implementation
1. **Map Selection**: UI sets `MapsSelected` parameter with JSON: `{"states": ["CA", "NV"], "nations": []}`
2. **Trigger**: `update_maps()` in `frogpilot_utilities.py` copies to `OSMDownloadLocations`
3. **Download**: mapd binary monitors `OSMDownloadLocations` and downloads from pfeifer
4. **Progress**: Tracked via `OSMDownloadProgress` parameter

### Testing Map Downloads
```bash
# Test download functionality
python selfdrive/frogpilot/navigation/test_map_download.py

# Check current map selection
python -c "from openpilot.selfdrive.frogpilot.frogpilot_variables import params; print(params.get('MapsSelected', encoding='utf-8'))"

# Manually trigger CA/NV download
python -c "
from openpilot.selfdrive.frogpilot.frogpilot_variables import params_memory
import json
maps = {'states': ['CA', 'NV'], 'nations': []}
params_memory.put('OSMDownloadLocations', json.dumps(maps))
print('Download triggered for CA/NV')
"

# Check download progress
python -c "from openpilot.selfdrive.frogpilot.frogpilot_variables import params; print('Progress:', params.get('OSMDownloadProgress', encoding='utf-8'))"
```

### Verifying Map Data
```bash
# Check if maps directory exists
ls -la /data/media/0/osm/offline/

# Verify mapd binary
ls -la /data/media/0/osm/mapd
file /data/media/0/osm/mapd

# Check mapd version
cat /data/media/0/osm/mapd_version
```

## Process Integration

### mapd Process
- **Configured in**: `system/manager/process_config.py`
- **Process name**: `mapd`
- **Command**: `selfdrive.frogpilot.navigation.mapd`
- **Runs**: Always (background daemon)

### Map Update Integration
- **Function**: `update_maps()` in `frogpilot_utilities.py`
- **Called by**: `frogpilot_process.py` in update checks
- **Schedule**: Configurable (daily/weekly/monthly) via `PreferredSchedule` param

## Parameters Used

### Core Parameters
- **`MapsSelected`** - JSON with selected states/nations (persistent)
- **`OSMDownloadLocations`** - Triggers mapd downloads (memory)
- **`OSMDownloadProgress`** - Current download status (persistent)
- **`LastMapsUpdate`** - Date of last successful update (persistent)
- **`PreferredSchedule`** - Update frequency (0=daily, 1=weekly, 2=monthly)

### Parameter Debugging
```bash
# View all map-related parameters
python -c "
from openpilot.selfdrive.frogpilot.frogpilot_variables import params
for key in ['MapsSelected', 'OSMDownloadProgress', 'LastMapsUpdate', 'PreferredSchedule']:
    value = params.get(key, encoding='utf-8')
    print(f'{key}: {value}')
"
```

## Troubleshooting

### Common Issues
1. **No download starting**: Check if `OSMDownloadLocations` is set and mapd process is running
2. **Download fails**: Verify network connectivity to `map-data.pfeifer.dev`
3. **mapd binary missing**: Check download from GitHub releases
4. **UI not triggering**: Verify parameter flow from UI → MapsSelected → OSMDownloadLocations

### Debug Commands
```bash
# Check mapd process status
ps aux | grep mapd

# Monitor mapd logs
tail -f /tmp/tmux_out.log | grep -i mapd

# Test network connectivity
curl -I https://map-data.pfeifer.dev/
curl -I https://github.com/pfeiferj/openpilot-mapd/releases/

# Reset download state
python -c "
from openpilot.selfdrive.frogpilot.frogpilot_variables import params
params.remove('OSMDownloadProgress')
print('Download state cleared')
"
```

## Development Workflow

### Making Changes
```bash
# Always check current branch
git branch --show-current

# Test changes
python selfdrive/frogpilot/navigation/test_map_download.py

# Build if needed
scons selfdrive/frogpilot/navigation/
```

### Adding New Map Regions
1. Check available regions in mapd_fork bounding box files
2. Update UI to include new region options
3. Test with `test_map_download.py`
4. Verify downloads complete successfully

## File Maintenance

### AGENTS.md Synchronization
**CRITICAL**: This CLAUDE.md file must be kept in sync with the corresponding AGENTS.md file.

**When updating this file:**
1. Copy the entire contents of this file
2. Paste into the corresponding AGENTS.md file 
3. Ensure both files are identical
4. Commit both files together

**Location of twin file**: `selfdrive/frogpilot/navigation/AGENTS.md`

## Safety Considerations
- Map data affects navigation and turn speed control
- Always verify map data integrity before deployment
- Test route planning with new map data
- Ensure download doesn't impact driving performance

## Related Documentation
- **Main FrogPilot**: `../CLAUDE.md`
- **Map bounding boxes**: `../../mapd_fork/us_states_bounding_boxes.json`
- **Process config**: `../../../system/manager/process_config.py`
- **Utilities**: `../frogpilot_utilities.py` (update_maps function)