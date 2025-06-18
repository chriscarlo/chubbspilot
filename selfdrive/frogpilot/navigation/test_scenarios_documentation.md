# Turn Speed Controller Test Scenarios Documentation

This document describes the comprehensive test scenarios for validating the unified turn speed controller implementation after replacing mapd_py with the original mapd.

## Test Categories

### 1. Basic Functionality Tests

#### Startup Validation
- **Purpose**: Ensure system starts without crashes
- **Method**: Launch openpilot with mapd enabled
- **Expected**: No import errors, mapd process launches successfully
- **Verification**: Check process list, review logs for errors

#### Straight Road Driving
- **Purpose**: Verify controllers don't unnecessarily limit speed
- **Method**: Drive on straight highway
- **Expected**: Target speed equals cruise speed
- **Verification**: Monitor liveMapData messages, check target speeds

### 2. Map-Only Curve Detection

#### Long Sweeper Curve
- **Scenario**: Highway curve beyond vision range
- **Test Location**: Highway with gradual curve after hill or bridge
- **Expected Behavior**:
  - MTSC detects curve from map data ~500m ahead
  - Speed reduction begins before vision sees curve
  - Smooth deceleration to safe speed
  - UI shows map-based slowdown
- **Data Collection**: Log MapTargetVelocities, liveMapData, target speeds

#### Exit Ramp Test
- **Scenario**: Known sharp exit ramp with map data
- **Expected**: Early speed reduction based on map curvature
- **Verification**: Compare slowdown timing with/without map data

### 3. Vision-Only Curve Detection

#### Unmapped Road Test
- **Scenario**: Backroad or parking lot without map data
- **Test Conditions**: Disable map controller or use unmapped area
- **Expected Behavior**:
  - VTSC detects curves from model predictions
  - Speed reduction based on vision curvature
  - Similar behavior to pre-unification VTSC
- **Metrics**: Response time, deceleration profile, minimum speed

#### Model Curvature Validation
- **Purpose**: Ensure vision detection unchanged
- **Method**: Compare logs before/after unification
- **Key Points**: Curvature calculation, speed targets, smoothness

### 4. Combined Input Scenarios

#### Redundant Detection
- **Scenario**: Curve visible to both map and vision
- **Expected Behavior**:
  - Map provides early warning
  - Vision confirms and refines
  - No oscillation or conflict
  - Smooth speed profile
- **Analysis**: Profile blending, transition points

#### Discrepant Inputs
- **Scenario**: Map and vision disagree
- **Test Cases**:
  - Highway overpass (false positive)
  - Construction zone (map outdated)
  - Temporary detour
- **Expected**: Intelligent resolution based on blend mode

### 5. Edge Cases and False Positives

#### Highway Overpass
- **Issue**: Map shows curve for overpass ramp
- **Expected**: No slowdown on straight road
- **Mitigation**: Model confirmation required

#### Parallel Roads
- **Issue**: Nearby curved road in map data
- **Expected**: Filter to active route only
- **Verification**: Check MapTargetVelocities filtering

### 6. Performance Tests

#### CPU/Memory Usage
- **Metrics**:
  - mapd CPU usage (target < 5%)
  - Memory footprint (target < 50MB)
  - Message frequency (10Hz nominal)
- **Duration**: 1-hour continuous operation

#### Latency Testing
- **Measure**: GPS update to liveMapData delay
- **Target**: < 100ms end-to-end
- **Method**: Timestamp correlation

### 7. Aggressiveness Testing

#### Parameter Sweep
- **Values**: 0.5, 0.8, 1.0, 1.2, 1.5, 2.0
- **Scenarios**: Standard test curve
- **Metrics**:
  - Minimum speed achieved
  - Deceleration rate
  - User comfort rating

### 8. Regression Testing

#### Behavior Comparison
- **Method**: Side-by-side old vs new system
- **Scenarios**: Standard test route
- **Acceptance**: ±10% speed targets

#### Log Replay
- **Data**: Historical driving logs
- **Process**: Feed through new controller
- **Compare**: Speed profiles, intervention points

## Test Execution Protocol

### Pre-Test Setup
1. Verify mapd binary present
2. Clear parameter cache
3. Set test configuration
4. Enable logging

### During Test
1. Monitor system health
2. Record all parameters
3. Note subjective feel
4. Capture UI state

### Post-Test Analysis
1. Extract key metrics
2. Plot speed profiles
3. Identify anomalies
4. Generate report

## Success Criteria

### Functional Requirements
- ✓ No system crashes or errors
- ✓ Map data properly ingested
- ✓ Vision data properly processed
- ✓ Unified controller produces valid outputs

### Performance Requirements
- ✓ CPU usage < 10% combined
- ✓ Memory stable over time
- ✓ Message rate 10Hz ± 2Hz
- ✓ Latency < 200ms

### Safety Requirements
- ✓ No sudden speed changes
- ✓ Fail-safe to vision-only
- ✓ Predictable behavior
- ✓ Conservative when uncertain

### User Experience
- ✓ Smooth speed transitions
- ✓ Appropriate turn speeds
- ✓ Consistent behavior
- ✓ Clear UI feedback

## Known Limitations

1. **Map Data Quality**: Depends on OpenStreetMap accuracy
2. **GPS Accuracy**: Urban canyons may affect positioning
3. **Vision Range**: Limited to ~200m ahead
4. **Weather**: Heavy rain/fog affects vision

## Future Enhancements

1. **Crowdsourced Validation**: Learn from fleet data
2. **ML Confidence**: Neural net for blend weights
3. **Predictive Loading**: Pre-fetch map tiles
4. **Driver Profiles**: Personalized aggressiveness