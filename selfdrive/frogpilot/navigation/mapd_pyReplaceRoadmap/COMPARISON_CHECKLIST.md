# Comparison Checklist: exp04 vs Upstream Branch

This checklist is for comparing the current branch (chriscarlo/chauffeur/exp04) with an upstream branch where mapd was never replaced with mapd_py. The only expected functional difference should be the mapd repository hosting location.

## Expected Differences

### 1. Repository References
- [ ] **mapd submodule URL**
  - Current: Should point to `chriscarlo/mapd` or similar
  - Upstream: Should point to `FrogAi/mapd` or original location
  - Check: `.gitmodules`, `mapd_fork/.git/config`

### 2. Build/Download Scripts
- [ ] **download_mapd.sh**
  - Current: Downloads from chriscarlo's releases
  - Upstream: Downloads from FrogAi's releases
  - Check: `MAPD_REPO` variable in script

## Should Be Identical

### 1. Core mapd Integration
- [ ] **Process Configuration**
  - Both should have: `PythonProcess("mapd", "selfdrive.frogpilot.navigation.mapd", always_run)`
  - Location: `/system/manager/process_config.py`
  - No mapd_py process should exist in either

- [ ] **mapd.py wrapper**
  - Should exist in both branches
  - Core functionality should be identical
  - Location: `/selfdrive/frogpilot/navigation/mapd.py`

### 2. Turn Speed Controllers
- [ ] **MTSC (chauffeur_mtsc.py)**
  - Should read from liveMapData in both branches
  - No protobuf imports
  - Location: `/selfdrive/frogpilot/controls/lib/chauffeur_mtsc.py`

- [ ] **VTSC (chauffeur_vtsc.py)**
  - Should be unchanged between branches
  - Location: `/selfdrive/frogpilot/controls/lib/chauffeur_vtsc.py`

### 3. Message Definitions
- [ ] **liveMapData in services.py**
  - Should be identical in both branches
  - Frequency: 1 Hz
  - Location: `/system/manager/process_config.py` service list

### 4. Dependencies
- [ ] **No protobuf dependencies**
  - Neither branch should have protobuf in requirements
  - Check: `poetry.lock`, `pyproject.toml`, requirements files

- [ ] **No proto files**
  - Neither branch should have `.proto` files
  - Check: No `map_data.proto` or similar

### 5. Build System
- [ ] **SConscript files**
  - No mapd_py entries in either branch
  - Check: All SConscript files in the tree

## Should NOT Exist in Either Branch

### 1. mapd_py Directory
- [ ] `/selfdrive/frogpilot/navigation/mapd_py/` - Should not exist
- [ ] No Python files implementing map data parsing
- [ ] No protobuf-related code

### 2. Proto-generated Files
- [ ] No `*_pb2.py` files related to map data
- [ ] No protobuf imports in map-related code

### 3. Obsolete Tools
- [ ] `/tools/map_processing/` files should either:
  - Not exist in either branch, OR
  - Be marked as obsolete in both branches

## Unique to exp04 (Our Work)

### 1. Unified Turn Controller (Future Enhancement)
- [ ] `/selfdrive/frogpilot/controls/lib/unified_turn_controller.py`
- [ ] `/selfdrive/frogpilot/controls/lib/turn_speed_common.py`
- [ ] `/selfdrive/frogpilot/controls/lib/migrate_to_unified_controller.py`
  - These may not exist in upstream if they haven't unified controllers yet

### 2. Enhanced Testing
- [ ] `/selfdrive/frogpilot/navigation/test_controller_simulation.py`
- [ ] `/selfdrive/frogpilot/navigation/test_full_integration.py`
- [ ] `/selfdrive/frogpilot/navigation/test_scenarios_documentation.md`
- [ ] `/selfdrive/frogpilot/navigation/monitor_performance.py`
  - These comprehensive tests may be unique to our implementation

### 3. Documentation
- [ ] `/selfdrive/frogpilot/navigation/mapd_pyReplaceRoadmap/` - Entire directory
  - This documents our replacement work and wouldn't exist upstream

## Verification Commands

```bash
# Check for mapd_py references
grep -r "mapd_py" . --exclude-dir=".git" --exclude="*.md"

# Check for protobuf imports in navigation
grep -r "import.*proto" selfdrive/frogpilot/navigation/

# Check process configuration
grep -A5 -B5 "mapd" system/manager/process_config.py

# Check for proto files
find . -name "*.proto" -path "*/navigation/*"

# Compare mapd submodule URL
cd mapd_fork && git remote -v

# Check for build system references
grep -r "mapd_py" . --include="SConscript" --include="SConstruct"
```

## Functional Testing

Both branches should:
1. [ ] Start mapd process successfully
2. [ ] Read GPS data from LastGPSPosition param
3. [ ] Output map data to MapTargetVelocities param
4. [ ] Publish liveMapData messages at 1 Hz
5. [ ] MTSC reads liveMapData and adjusts speed accordingly
6. [ ] No protobuf serialization/deserialization overhead

## Performance Comparison

Both branches should have similar:
1. [ ] CPU usage for mapd process (< 5%)
2. [ ] Memory usage for mapd process (< 50MB)
3. [ ] Message latency (< 100ms from GPS update to liveMapData)
4. [ ] No memory leaks over extended operation

## Summary

The upstream branch and exp04 should be functionally identical for mapd operation, with the only difference being:
1. Repository hosting location (chriscarlo vs FrogAi)
2. Possible additional enhancements in exp04 (unified controller, enhanced testing)

Both should be using the Go-based mapd, not the Python mapd_py implementation.