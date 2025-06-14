# Corrected Comparison Checklist: exp04 vs upstream-chubbspilot

## Context Clarification

- **upstream-chubbspilot**: Has mapd_py (the Python implementation we want to remove)
- **exp04**: Our branch where we manually reverted FROM mapd_py BACK TO Go-based mapd
- **Goal**: Verify our reversion on exp04 functionally matches what a proper Go-based mapd implementation should look like

## What upstream-chubbspilot Currently Has (mapd_py)

### Process Configuration
```python
PythonProcess("map_downloader", "selfdrive.frogpilot.navigation.mapd_py.downloader.downloader", always_run),
PythonProcess("mapd_py", "selfdrive.frogpilot.navigation.mapd_py.mapd_daemon", always_run),
```

### Directory Structure
- `/selfdrive/frogpilot/navigation/mapd_py/` - Full Python implementation
- No `/selfdrive/frogpilot/navigation/mapd.py` wrapper
- No mapd binary or download scripts

## What exp04 Should Have (Go-based mapd)

### Process Configuration ✅
```python
PythonProcess("mapd", "selfdrive.frogpilot.navigation.mapd", always_run),
```
**Status**: CORRECT - Single mapd process using Python wrapper

### mapd.py Wrapper ✅
- **Expected**: Python wrapper that:
  - Downloads/ensures mapd binary exists
  - Launches Go binary as subprocess
  - Bridges params → liveMapData messages
- **Status**: IMPLEMENTED - All functionality present

### Directory Structure ✅
- **Should NOT exist**: `/selfdrive/frogpilot/navigation/mapd_py/`
- **Status**: REMOVED - Directory deleted

### Binary Management ✅
- **build_mapd.sh**: Builds from Go source
- **download_mapd.sh**: Downloads pre-built binary
- **Status**: BOTH IMPLEMENTED

### Message Flow ✅
- **Expected**: GPS → mapd (Go) → params → mapd.py → liveMapData → MTSC
- **Status**: CORRECTLY IMPLEMENTED

## Key Functional Requirements

### 1. Process Lifecycle ✅
- [x] mapd.py starts Go binary subprocess
- [x] Monitors and restarts if crashed
- [x] Clean shutdown on exit

### 2. Data Bridge ✅
- [x] Reads mapd params output
- [x] Converts to liveMapData format
- [x] Publishes at 1 Hz
- [x] Handles GPS position updates

### 3. MTSC Integration ✅
- [x] MTSC reads liveMapData (not protobuf)
- [x] No mapd_py imports
- [x] Curvature data properly formatted

### 4. No Protobuf ✅
- [x] No .proto files
- [x] No protobuf imports
- [x] No *_pb2.py files

## Additional Enhancements in exp04

### 1. Unified Turn Controller
- New unified controller combining MTSC/VTSC
- Migration path for backward compatibility
- Not present in original Go implementation

### 2. Comprehensive Testing
- Simulation tests
- Integration tests
- Performance monitoring
- Not present in original

### 3. Documentation
- Complete roadmap documentation
- Test scenarios
- Phase summaries

## Verification Results

### Core Functionality: ✅ PASS
Our exp04 implementation correctly reverts to Go-based mapd architecture:
1. Single Python wrapper process
2. Go binary subprocess management
3. Params to cereal bridge
4. No Python map data processing
5. No protobuf dependencies

### Differences from Pure Upstream Go Implementation
1. **Repository URL**: Points to chriscarlo/mapd instead of original
2. **Binary Download**: Updated to download from appropriate source
3. **Additional Features**: Unified controller, testing suite

## Conclusion

The exp04 branch successfully implements a functionally equivalent Go-based mapd system. The core architecture matches what a proper Go implementation should have:
- Python wrapper for process management
- Go binary for actual map data processing  
- Clean params → cereal message bridge
- No mapd_py Python implementation

The only required change for full upstream compatibility would be updating the mapd repository URLs in the download/build scripts.