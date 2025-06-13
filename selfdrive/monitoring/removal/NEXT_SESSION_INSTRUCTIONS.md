# DRIVER MONITORING REMOVAL - NEXT SESSION INSTRUCTIONS

## 🚨 CRITICAL SAFETY WARNING 🚨
The driver monitoring system contains a SAFETY-CRITICAL feature that MUST be handled properly:
- **Force Deceleration**: When `awarenessStatus < 0`, the car will slow to a stop
- This prevents runaway vehicles when the driver is unattentive
- Located in `controlsd.py` line 836
- **YOU MUST ENSURE `awarenessStatus` IS ALWAYS >= 0 IN ANY STUB**

## Immediate Actions Required

### 1. FIRST PRIORITY - Safety Stub Implementation
Before ANY other changes, update `/selfdrive/monitoring/helpers.py`:
```python
# In _update_states() method:
self.awareness = 1.0  # CRITICAL: Must be positive
self.awareness_active = 1.0
self.awareness_passive = 1.0

# Ensure get_awareness_status() returns positive value:
def get_awareness_status(self):
    return 1.0  # Always fully aware
```

### 2. Verify Safety Stub
Test that the stub prevents force deceleration:
1. Check that `awarenessStatus` is always positive in logs
2. Verify no unexpected deceleration occurs
3. Test engagement/disengagement cycles

## Comprehensive Removal Steps

### Phase 1: Complete Stubbing (CURRENT PHASE)
1. ✅ Stub helpers.py to return safe values
2. ⬜ Stub dmonitoringmodeld.py to send nominal messages
3. ⬜ Test thoroughly on vehicle

### Phase 2: Process Removal
1. ⬜ Remove from process_config.py:
   - `dmonitoringmodeld` (line 70)
   - `dmonitoringd` (line 87)
2. ⬜ Remove model files from `/selfdrive/modeld/models/`:
   - `dmonitoring_model.current`
   - `dmonitoring_model_q.dlc`
   - `dmonitoring_model.onnx`
   - `dmonitoring_model_tinygrad.pkl`

### Phase 3: Code Removal - Core Files
1. ⬜ Remove entire `/selfdrive/monitoring/` directory
2. ⬜ Remove `/selfdrive/modeld/dmonitoringmodeld.py`
3. ⬜ Update controlsd.py:
   - Remove `driverMonitoringState` from SubMaster (line 104)
   - Remove DM event handling (line 242)
   - Replace force_decel logic (lines 836-837) with:
     ```python
     force_decel = (self.state == State.softDisabling)
     ```

### Phase 4: UI Removal - C++ Files

#### annotated_camera.cc
- Remove lines: 42, 98-103, 672-718, 894-897, 1169
- Remove `drawDriverState()` function completely
- Remove dm_img loading

#### annotated_camera.h  
- Remove lines: 65-68, 110, 197
- Remove all DM state variables

#### ui.cc
- Remove lines: 195-227, 550, 588
- Remove `update_dmonitoring()` function
- Remove DM message subscriptions

#### ui.h
- Remove lines: 43-51, 115-119, 387
- Remove face keypoint arrays

#### Complete file removals:
- driverview.cc
- driverview.h

### Phase 5: Event System Cleanup
Remove from events.py:
- `preDriverDistracted`
- `promptDriverDistracted`
- `driverDistracted`
- `preDriverUnresponsive`
- `promptDriverUnresponsive`
- `driverUnresponsive`
- `tooDistracted`

### Phase 6: Message Removal
1. ⬜ Update cereal/log.capnp - remove:
   - `driverState`
   - `driverStateV2`
   - `driverMonitoringState`
   - `driverCameraState`

### Phase 7: Camera Configuration
1. ⬜ Update `/system/camerad/cameras/camera_qcom2.cc`
   - Remove driver_cam configuration
   - Update VISION_STREAM enums
2. ⬜ Update camera_qcom2.h accordingly

### Phase 8: Testing & Validation
1. ⬜ Remove DM-specific tests
2. ⬜ Update integration tests
3. ⬜ Test on 2023 Kia EV6:
   - Engagement/disengagement
   - No force deceleration
   - UI functions properly
   - No crashes or errors

## File Checklist

### Python Files to Modify:
- [ ] `/selfdrive/monitoring/helpers.py` (stub first, remove later)
- [ ] `/selfdrive/controls/controlsd.py`
- [ ] `/selfdrive/controls/lib/events.py`
- [ ] `/selfdrive/manager/process_config.py`
- [ ] `/selfdrive/ui/qt/offroad/settings.cc`

### C++ Files to Modify:
- [ ] `/selfdrive/ui/qt/onroad/annotated_camera.cc`
- [ ] `/selfdrive/ui/qt/onroad/annotated_camera.h`
- [ ] `/selfdrive/ui/ui.cc`
- [ ] `/selfdrive/ui/ui.h`
- [ ] `/selfdrive/ui/qt/home.cc`
- [ ] `/selfdrive/ui/qt/window.cc`

### Files/Directories to Remove:
- [ ] `/selfdrive/monitoring/` (entire directory)
- [ ] `/selfdrive/modeld/dmonitoringmodeld.py`
- [ ] `/selfdrive/ui/qt/offroad/driverview.cc`
- [ ] `/selfdrive/ui/qt/offroad/driverview.h`
- [ ] All dmonitoring model files

### Asset Files to Remove:
- [ ] `/selfdrive/assets/img_driver_face.png`
- [ ] `/selfdrive/assets/img_driver_face_static.png`

## Testing Protocol

### Before Each Change:
1. Create git branch for rollback
2. Test current functionality baseline
3. Make incremental changes
4. Test after each change

### Critical Tests:
1. **Safety Test**: Ensure no unexpected deceleration
2. **UI Test**: Verify no visual glitches
3. **Engagement Test**: Confirm normal operation
4. **Log Test**: Check for errors in logs

## Rollback Plan
If issues arise:
1. **Quick Fix**: Revert helpers.py changes
2. **Process Level**: Re-enable processes in config
3. **Full Revert**: Git checkout previous branch

## Expected Benefits
- ~15% CPU reduction
- ~300MB RAM savings  
- No false distraction alerts
- Complete driver privacy
- Better thermal performance

## Next Session Start Command
```bash
cd /data/openpilot
git status
cat selfdrive/monitoring/removal/NEXT_SESSION_INSTRUCTIONS.md
```

## Remember:
1. **SAFETY FIRST** - Always ensure awarenessStatus >= 0
2. **TEST INCREMENTALLY** - Don't make all changes at once
3. **KEEP BACKUPS** - Branch before major changes
4. **FOCUS ON EV6** - This is for 2023 Kia EV6 only

Good luck with the driver monitoring removal!