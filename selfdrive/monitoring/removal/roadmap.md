# Driver Monitoring System Removal Roadmap

## ⚠️ CRITICAL SAFETY CONSIDERATIONS ⚠️

**WARNING**: The driver monitoring system includes SAFETY-CRITICAL features:

1. **Force Deceleration Safety Feature**: When driver attention is not detected (`awarenessStatus < 0`), the system:
   - Sets cruise speed to 0, forcing the vehicle to slow down
   - Prevents runaway vehicles when driver is unattentive
   - Located in `controlsd.py` line 836

2. **Required Safety Mitigations**: When removing driver monitoring, you MUST:
   - Ensure `awarenessStatus` is always >= 0 in any stub implementation
   - Consider alternative safety mechanisms (timeout-based disengagement)
   - Test thoroughly to ensure no safety regressions

3. **UI Dependencies**: Multiple UI components depend on driver monitoring state:
   - Driver face icon positioning affects other UI elements
   - Alert systems expect driver monitoring events
   - Settings and camera preview features are integrated

## Overview
This document outlines the complete removal of the driver monitoring system from openpilot. The goal is to eliminate all components, dependencies, and references to driver monitoring functionality.

## System Architecture Overview

### Core Components
1. **dmonitoringmodeld** - ML model that analyzes driver face/attention
   - Located in: `/selfdrive/modeld/dmonitoringmodeld.py`
   - Variants: classic, tinygrad versions
   - Model files: `.onnx`, `.dlc`, `.pkl` formats

2. **dmonitoringd** - Main process that runs driver monitoring logic
   - Located in: `/selfdrive/monitoring/dmonitoringd.py`
   - Helper functions: `/selfdrive/monitoring/helpers.py`
   - Processes model output into driver state

3. **Driver-facing camera** - Hardware component (AR0231 sensor)
   - Configured in: `/system/camerad/cameras/camera_qcom2.cc`
   - Logs to: `driverCameraState`
   - Resolution: 1928x1208 @ 30fps

4. **Events system** - Generates alerts based on driver state
   - Events defined in: `/selfdrive/controls/lib/events.py`
   - Alert types: pre/prompt/terminal for distracted/unresponsive

5. **UI components** - Visual/audio alerts to driver
   - Driver face icon: `/selfdrive/ui/qt/onroad/annotated_camera.cc`
   - Alert banners and sounds
   - Driver view in settings

### Detailed Data Flow
```
┌─────────────────┐
│ Driver Camera   │
│   (AR0231)      │
└────────┬────────┘
         │ Raw frames
         ▼
┌─────────────────┐     ┌──────────────────┐
│   camerad       │────▶│ driverCameraState│
│                 │     └──────────────────┘
└────────┬────────┘
         │ YUV frames
         ▼
┌─────────────────┐     ┌──────────────────┐
│dmonitoringmodeld│────▶│  driverStateV2   │
│  (ML Model)     │     │ - face position  │
│                 │     │ - eye state      │
│                 │     │ - pose angles    │
└─────────────────┘     └────────┬─────────┘
                                 │
                                 ▼
┌─────────────────┐     ┌──────────────────┐
│  dmonitoringd   │────▶│driverMonitoring  │
│ (Logic/Policy)  │     │     State        │
│                 │     │ - awareness      │
│                 │     │ - distracted     │
│                 │     │ - events         │
└─────────────────┘     └────────┬─────────┘
                                 │
                ┌────────────────┴────────────────┐
                ▼                                 ▼
┌─────────────────┐                   ┌─────────────────┐
│   controlsd     │                   │       UI        │
│ - engageable    │                   │ - visual alerts │
│ - alerts        │                   │ - sounds        │
│ - safety        │                   │ - driver icon   │
└─────────────────┘                   └─────────────────┘
```

### Message Types and Contents

**driverStateV2** (from model):
- Face detection probability
- Face position (x, y)
- Face orientation (pitch, yaw, roll)
- Eye probabilities (left/right)
- Blink probabilities
- Sunglasses probability
- Poor vision probability
- Distraction scores

**driverMonitoringState** (from logic):
- Face detected (bool)
- Driver distracted (bool)
- Awareness level (0-1)
- Active monitoring mode
- Pose offsets (calibrated)
- Events (pre/prompt/terminal alerts)
- Step change rate
- Hi/low std counts

## Phase 1: Analysis and Discovery

### 1.1 Identify All Components
- [ ] Find all driver monitoring related processes
- [ ] Map all event types related to driver monitoring
- [ ] Identify all params/settings
- [ ] Find UI components
- [ ] Locate model files
- [ ] Identify camera configurations

### 1.2 Dependency Mapping
- [ ] What processes consume driverMonitoringState?
- [ ] What processes depend on driverStateV2?
- [ ] Which UI elements display driver monitoring info?
- [ ] What safety features rely on driver monitoring?

## Phase 2: Neutralization (Current Approach)

### 2.1 Stub Out Functions
- [x] Make helpers.py return nominal values
- [ ] Stub dmonitoringmodeld outputs
- [ ] Neutralize event generation

### 2.2 Benefits
- Quick implementation
- Reversible
- Low risk of breaking other systems

### 2.3 Drawbacks
- Still consumes resources
- Dead code remains
- Camera still active

## Phase 3: Complete Removal Plan

### 3.1 Process Removal
1. **Remove from process_config.py**
   ```python
   # Remove these lines:
   PythonProcess("dmonitoringmodeld", "selfdrive.modeld.dmonitoringmodeld", driverview, enabled=(not PC or WEBCAM))
   PythonProcess("dmonitoringd", "selfdrive.monitoring.dmonitoringd", driverview, enabled=(not PC or WEBCAM))
   ```

### 3.2 Code Removal
1. **Core monitoring code**
   - `/selfdrive/monitoring/` - entire directory
   - `/selfdrive/modeld/dmonitoringmodeld.py`
   - `/selfdrive/classic_modeld/dmonitoringmodeld.py`
   - `/selfdrive/tinygrad_modeld/dmonitoringmodeld.py`
   - `/selfdrive/tinygrad_modeld/dmonitoringmodeld` (binary)
   
2. **Model files**
   ```
   /selfdrive/modeld/models/dmonitoring_model.current
   /selfdrive/modeld/models/dmonitoring_model_q.dlc
   /selfdrive/modeld/models/dmonitoring_model.onnx
   /selfdrive/modeld/models/dmonitoring_model_tinygrad.pkl
   ```
   
3. **Camera configuration**
   - `/system/camerad/cameras/camera_qcom2.cc` - Remove driver_cam
   - `/system/camerad/cameras/camera_qcom2.h` - Remove CameraState driver_cam
   - Update VISION_STREAM_* enums

### 3.3 Files Requiring Modification

#### Controls System
1. **controlsd.py** - Remove:
   - `sm.add_reader(['driverMonitoringState'])`
   - All references to `sm['driverMonitoringState']`
   - Driver monitoring event handling
   
2. **events.py** - Remove events:
   - `EventName.preDriverDistracted`
   - `EventName.promptDriverDistracted`
   - `EventName.driverDistracted`
   - `EventName.preDriverUnresponsive`
   - `EventName.promptDriverUnresponsive`
   - `EventName.driverUnresponsive`
   - `EventName.tooDistracted`

#### UI System
1. **annotated_camera.cc** - Remove:
   - Line 42: `dm_img` loading
   - Lines 98-103: Driver monitoring state updates
   - Lines 672-718: `drawDriverState()` function
   - Lines 894-897: Driver state data updates
   - Line 1169: CEM widget positioning relative to DM icon
   
2. **annotated_camera.h** - Remove:
   - Lines 65-68: DM state variables (`dmActive`, `rightHandDM`, `dm_fade_state`)
   - Line 110: `dmIconPosition` variable
   - Line 197: `drawDriverState()` declaration
   
3. **ui.cc** - Remove:
   - Lines 195-227: `update_dmonitoring()` function
   - Line 550: `driverMonitoringState` and `driverStateV2` subscriptions
   - Line 588: Driver camera timer updates
   
4. **ui.h** - Remove:
   - Lines 43-51: Default face keypoint coordinates
   - Lines 115-119: Driver pose arrays
   - Line 387: `update_dmonitoring()` declaration
   
5. **Additional UI files**:
   - **driverview.cc/h**: Complete removal (driver camera preview)
   - **settings.cc**: Remove driver camera recording toggles (lines 152-153, 226-227)
   - **home.cc**: Remove driver view integration (lines 44-46, 73, 91)
   - **window.cc**: Remove driver camera timer check (line 95)

#### FrogPilot Integration
1. **frogpilot_process.py** - Remove:
   - Driver camera toggle logic
   - Always-on monitoring settings
   
2. **frogpilot_variables.py** - Remove:
   - `self.driver_camera_in_reverse`
   - `self.always_on_lateral_set`
   - Related params

#### Testing
1. Remove test files:
   - `/selfdrive/monitoring/test_monitoring.py`
   - Any process replay tests for DM
   
2. Update integration tests:
   - Remove DM from process list checks
   - Update safety test expectations

### 3.3 Message/Event Removal
1. **Cereal messages**
   - Remove from log.capnp:
     - driverState
     - driverStateV2
     - driverMonitoringState
     - driverCameraState
   
2. **Events**
   - Remove from events.py:
     - preDriverDistracted
     - promptDriverDistracted
     - driverDistracted
     - preDriverUnresponsive
     - promptDriverUnresponsive
     - driverUnresponsive
     - tooDistracted

### 3.4 UI Component Removal
1. **Remove monitoring UI elements**
   - Driver face icon
   - Attention alerts
   - Monitoring status displays

2. **Remove sounds**
   - Attention warning sounds
   - Distraction alerts

### 3.5 Conditional Code Updates
1. **controlsd.py**
   - Remove driver monitoring state checks
   - Remove event generation based on driver state
   
2. **plannerd.py**
   - Remove any planning decisions based on driver attention
   
3. **Safety checks**
   - Ensure no safety-critical code depends on driver monitoring

## Phase 4: Testing Plan

### 4.1 Unit Tests
- [ ] Remove driver monitoring related tests
- [ ] Update tests that check for monitoring events

### 4.2 Integration Tests
- [ ] Verify controlsd works without monitoring
- [ ] Ensure no crashes from missing messages
- [ ] Test engagement/disengagement flows

### 4.3 Hardware Tests
- [ ] Verify system works with driver camera disconnected
- [ ] Check power consumption improvements
- [ ] Validate thermal improvements

## Phase 5: Cleanup

### 5.1 Documentation
- [ ] Update README files
- [ ] Remove monitoring from safety docs
- [ ] Update API documentation

### 5.2 Build System
- [ ] Remove monitoring from SConscript files
- [ ] Update build dependencies
- [ ] Remove model download logic

### 5.3 Parameters
- [ ] Remove monitoring-related params
- [ ] Clean up settings UI

## Risk Assessment

### High Risk Areas
1. **Safety-critical code** - Some safety features may depend on driver monitoring
   - **CRITICAL FINDING**: `forceDecel` safety feature in controlsd.py (line 836)
   - When `awarenessStatus < 0`, the system sets cruise speed to 0, forcing the car to slow down
   - This is a SAFETY-CRITICAL feature that prevents runaway vehicles when driver is unattentive
2. **Regulatory compliance** - May affect compliance in certain regions
3. **Message compatibility** - Other systems may expect these messages

### Mitigation Strategies
1. **Gradual removal** - Start with stubbing, then remove incrementally
2. **Compatibility layer** - Provide empty messages for transition period
3. **Feature flag** - Add param to enable/disable monitoring
4. **CRITICAL**: Replace `forceDecel` logic with alternative safety mechanism:
   - Option A: Always set `awarenessStatus = 1.0` (driver always attentive) in stub
   - Option B: Implement timeout-based safety (disengage after X seconds without driver input)
   - Option C: Remove force deceleration entirely (NOT RECOMMENDED - safety risk)

## Implementation Order

1. **Week 1: Discovery**
   - Complete component analysis
   - Create dependency graph
   - Identify all touch points

2. **Week 2: Stubbing**
   - Implement comprehensive stubbing
   - Test thoroughly
   - Monitor for issues

3. **Week 3: Process Removal**
   - Remove processes from config
   - Update build system
   - Remove model files

4. **Week 4: Code Cleanup**
   - Remove source files
   - Update imports
   - Clean up events

5. **Week 5: UI/UX Updates**
   - Remove UI components
   - Update layouts
   - Remove sounds

6. **Week 6: Testing & Polish**
   - Comprehensive testing
   - Documentation updates
   - Final cleanup

## Expected Benefits

### Performance Improvements
1. **CPU Usage**
   - ~10-15% reduction (dmonitoringmodeld uses significant CPU)
   - Less thermal throttling
   - Better performance for other processes

2. **Memory Usage**
   - ~200-300MB RAM saved
   - Model files removed from memory
   - Reduced camera buffer usage

3. **Power Consumption**
   - Driver camera can be powered down
   - Less compute = less power draw
   - Longer device life on battery

4. **Storage**
   - ~100MB saved from model files
   - No driver camera recordings
   - Smaller log files

### User Experience
1. **No False Alerts**
   - No incorrect distraction warnings
   - No face detection issues
   - More reliable engagement

2. **Privacy**
   - No driver recording
   - No face data processing
   - Complete driver privacy

## Potential Issues and Mitigations

### Issue 1: Safety Features
**Problem**: Some safety features may depend on driver attention
**Mitigation**: 
- Audit all safety-critical code paths
- Ensure no hidden dependencies
- Add feature flags for gradual rollout

### Issue 2: Message Compatibility
**Problem**: Other forks/tools may expect DM messages
**Mitigation**:
- Provide stub messages for compatibility
- Document breaking changes
- Version the API changes

### Issue 3: Regulatory Compliance
**Problem**: Some regions may require driver monitoring
**Mitigation**:
- Make it a compile-time option
- Add regional flags
- Keep stubbed version available

### Issue 4: Unexpected Dependencies
**Problem**: Hidden dependencies in the codebase
**Mitigation**:
- Thorough grep/search before removal
- Extensive testing
- Gradual removal approach

## Success Metrics
- [ ] No driver monitoring processes running
- [ ] Reduced CPU usage by measured amount
- [ ] Reduced memory usage by measured amount
- [ ] No driver monitoring events generated
- [ ] Clean build with no monitoring references
- [ ] All tests passing
- [ ] No runtime errors or crashes
- [ ] Driver camera powered off

## Rollback Plan
If issues arise, we can:
1. **Quick Fix**: Re-enable stubbed helpers.py
2. **Process Level**: Re-add processes to config but keep stubbed
3. **Full Revert**: Git revert to previous state
4. **Hybrid Approach**: Keep infrastructure but disable functionally

---

## Next Steps
1. Begin with comprehensive grep/search for all monitoring components
2. Create detailed dependency graph
3. Start with Phase 2 (stubbing) for immediate relief
4. Plan Phase 3 based on discoveries from Phase 1

---

## Appendix A: Quick Stubbing Guide

For immediate relief from driver monitoring, modify these files:

### 1. `/selfdrive/monitoring/helpers.py`
```python
# In _get_distracted_types():
def _get_distracted_types(self):
    return []  # Never distracted

# In _update_states():
self.face_detected = True  # Always detected
self.driver_distracted = False  # Never distracted
self.awareness = 1.0  # CRITICAL: Must be positive to prevent force deceleration

# In _update_events():
# CRITICAL: Ensure awareness_status is always positive
# This prevents triggering the safety force deceleration in controlsd
```

### 2. `/selfdrive/modeld/dmonitoringmodeld.py` (Optional)
```python
# At the top of main():
# Create fake output that shows attentive driver
fake_output = messaging.new_message('driverStateV2')
fake_output.driverStateV2.leftDriverData.faceProb = 1.0
fake_output.driverStateV2.rightDriverData.faceProb = 1.0
# ... set other fields to nominal values

# In main loop:
while True:
    pm.send('driverStateV2', fake_output)
    time.sleep(0.05)  # 20Hz
```

### 3. Disable camera (optional but saves resources)
In `/system/manager/process_config.py`:
```python
# Change enabled condition:
PythonProcess("dmonitoringmodeld", "selfdrive.modeld.dmonitoringmodeld", driverview, enabled=False),
PythonProcess("dmonitoringd", "selfdrive.monitoring.dmonitoringd", driverview, enabled=False),
```

This approach provides immediate relief while keeping the system architecture intact for a gradual removal later.

---

## Appendix B: Testing Checklist

After any modification, test:
- [ ] System boots normally
- [ ] Can engage openpilot
- [ ] No driver monitoring alerts appear
- [ ] UI doesn't show errors
- [ ] Logs don't show DM-related errors
- [ ] Controls behave normally
- [ ] No performance degradation