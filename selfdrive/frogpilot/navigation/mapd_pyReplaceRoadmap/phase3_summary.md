# Phase 3 Summary: Adapt mapd Output for MTSC Compatibility

## Completed Tasks

### 1. Verified Data Format Compatibility
- Confirmed that mapd outputs `MapTargetVelocities` as JSON array of objects with:
  - `latitude`: GPS latitude in degrees
  - `longitude`: GPS longitude in degrees  
  - `velocity`: Target speed in m/s (calculated as sqrt(2/curvature))
- This format matches what was expected from the original mapd design

### 2. Enhanced mapd.py Bridge
- Improved the `velocities_to_segments()` function to:
  - Calculate proper distances using haversine formula
  - Filter zero velocities (straight road sections)
  - Find closest velocity point to current GPS position
  - Build cumulative distance arrays from current position
  - Convert to MTSC-expected segment format with:
    - `curvatureDerivedSpeedsMps`: Array of target speeds
    - `distancesForSpeeds`: Array of distances from current position

### 3. Maintained MTSC Compatibility
- MTSC (ChauffeurMtsc) expects liveMapData cereal messages
- No changes needed to MTSC - it already reads from liveMapData
- The mapd.py wrapper successfully bridges params → cereal messages
- Publishing rate set to 1 Hz as per service definition

### 4. Created Testing Infrastructure
- `test_mapd_integration.py`: Tests mapd param reading/writing
- `test_mtsc_integration.py`: Tests complete data flow mapd → MTSC
- `download_mapd.sh`: Script to download pre-built binaries
- Updated documentation with clear data flow explanation

### 5. Cleaned Up Obsolete Code
- All mapd_py references have been removed or marked obsolete
- Tools that depended on mapd_py have been marked as obsolete:
  - `mapd_rtm.py`
  - `process_osm.py`
  - `test_mtsc_carson_rd.py`

## Data Flow Verification

The complete data flow is now:
1. **locationd** → writes GPS to `LastGPSPosition` param
2. **mapd binary** → reads GPS, outputs to params:
   - `MapTargetVelocities`: Array of velocity points
   - `MapSpeedLimit`: Current speed limit
   - `RoadName`: Current road name
3. **mapd.py wrapper** → reads params, publishes `liveMapData`
4. **MTSC** → subscribes to `liveMapData`, generates speed profiles

## Next Steps

With Phase 3 complete, the mapd and MTSC systems are now properly integrated. The next phase would be to unify MTSC and VTSC logic as outlined in Phase 4.