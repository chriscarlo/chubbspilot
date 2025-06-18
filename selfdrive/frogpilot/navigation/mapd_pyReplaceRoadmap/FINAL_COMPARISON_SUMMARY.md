# Final Comparison Summary: exp04 Reversion Success

## Situation Clarification

After investigation, the actual situation is:

1. **upstream-chubbspilot** = Already uses Go-based mapd (the good baseline)
2. **exp04 BEFORE our work** = Had mapd_py (Python implementation) 
3. **exp04 AFTER our work** = Successfully reverted to Go-based mapd

## Comparison Results: exp04 vs upstream-chubbspilot

### Core mapd Implementation ✅ MATCHES

**upstream-chubbspilot:**
```python
PythonProcess("mapd", "selfdrive.frogpilot.navigation.mapd", always_run),
```

**exp04 (after our work):**
```python
PythonProcess("mapd", "selfdrive.frogpilot.navigation.mapd", always_run),
```

### Python Wrapper Approach ✅ MATCHES

Both branches now have:
- `/selfdrive/frogpilot/navigation/mapd.py` - Python wrapper
- Downloads/manages Go binary
- Bridges params → liveMapData messages
- NO mapd_py directory

### Message Flow ✅ MATCHES

Both use the same data flow:
```
GPS → mapd (Go binary) → params → mapd.py wrapper → liveMapData → MTSC
```

### Dependencies ✅ MATCHES

Both branches:
- NO protobuf dependencies
- NO mapd_py Python dependencies (rtree, shapely)
- NO proto files

### Build System ✅ MATCHES

Both branches:
- NO mapd_py SConscript entries
- Clean build configuration

## Key Differences

### 1. Repository References
- **upstream-chubbspilot**: Downloads from FrogAi/pfeiferj repositories
- **exp04**: Downloads from chriscarlo repository
- **Impact**: Functional equivalent, just different hosting

### 2. Additional Features in exp04
- Unified turn controller implementation
- Comprehensive test suite
- Migration documentation
- **Impact**: Enhancements beyond baseline, not breaking changes

### 3. Obsolete Tools Handling
- **exp04**: Explicitly marks map_processing tools as obsolete
- **upstream-chubbspilot**: May still have outdated tools
- **Impact**: Better documentation of deprecated components

## Verification Summary

| Component | upstream-chubbspilot | exp04 (our work) | Status |
|-----------|---------------------|-------------------|---------|
| Process Config | `mapd` | `mapd` | ✅ MATCH |
| Python Wrapper | ✓ | ✓ | ✅ MATCH |
| Go Binary Management | ✓ | ✓ | ✅ MATCH |
| Params → Cereal Bridge | ✓ | ✓ | ✅ MATCH |
| No mapd_py | ✓ | ✓ | ✅ MATCH |
| No Protobuf | ✓ | ✓ | ✅ MATCH |
| MTSC Integration | liveMapData | liveMapData | ✅ MATCH |

## What We Removed from exp04

The exp04 branch previously had:
```python
# Old process configuration
PythonProcess("map_downloader", "selfdrive.frogpilot.navigation.mapd_py.downloader.downloader", always_run),
PythonProcess("mapd_py", "selfdrive.frogpilot.navigation.mapd_py.mapd_daemon", always_run),
```

We successfully removed:
- ❌ `/selfdrive/frogpilot/navigation/mapd_py/` directory
- ❌ Protobuf infrastructure (`tools/bin/protoc`, proto files)
- ❌ Python map data processing
- ❌ mapd_py dependencies in pyproject.toml
- ❌ SConscript entries for mapd_py

## Conclusion

**The reversion was successful!** 

The exp04 branch now functionally matches upstream-chubbspilot's Go-based mapd implementation. Both branches:
- Use a Python wrapper to manage the Go binary
- Have identical process configurations
- Use the same params → cereal message flow
- Have no Python map data processing code

The only differences are:
1. Repository URLs (easily configurable)
2. Additional enhancements in exp04 (unified controller, testing)

The core mapd functionality is now identical between the branches, confirming that our manual reversion from mapd_py back to Go-based mapd was completed correctly.