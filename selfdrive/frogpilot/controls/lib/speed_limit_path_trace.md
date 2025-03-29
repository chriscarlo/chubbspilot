# Speed Limit Path Trace

## From `speed_limit_controller.py` to Onroad UI

1. **Speed Limit Calculation**:
   - In `speed_limit_controller.py`, the `SpeedLimitController` class calculates the speed limit using the `get_speed_limit` method. This method is called within the `update` method, which sets `self.speed_limit`.

2. **Integration with FrogPilotVCruise**:
   - The `SpeedLimitController` instance (`self.slc`) is used in the `FrogPilotVCruise` class, specifically in its `update` method. Here, the `update` method of `SpeedLimitController` is called to update the speed limit:
     ```python
     self.slc.update(
         frogpilotCarState.dashboardSpeedLimit,
         controlsState.enabled,
         frogpilotNavigation.navigationSpeedLimit,
         v_cruise_cluster,
         v_ego,
         frogpilot_toggles
     )
     ```

3. **Publishing to Scene**:
   - The `FrogPilotVCruise` class updates the `desired_slc_target` with the `desired_speed_limit` from `SpeedLimitController`. This value is then used to update the `scene` object in the UI state:
     ```cpp
     scene.speed_limit = frogpilotPlan.getSlcSpeedLimit();
     ```

4. **UI State Update**:
   - In `ui.cc`, the `scene.speed_limit` is updated with the value from `frogpilotPlan`, which is derived from the `SpeedLimitController`.

5. **Rendering in UI**:
   - In `annotated_camera.cc`, the `updateState` method of `AnnotatedCameraWidget` retrieves the speed limit from the `UIState` object:
     ```cpp
     if (s.scene.show_speed_limits || s.scene.speed_limit_controller) {
       speedLimit = slcOverridden ? s.scene.speed_limit_overridden_speed : s.scene.speed_limit;
     }
     ```

6. **Display on UI**:
   - The `speedLimit` variable is then used in various UI rendering functions to display the speed limit on the onroad UI.

## UI Handling of Speed Limit and Offset

1. **UI State Update**:
   - The `UIState` object is updated with various speed limit-related values from the `scene` object. This includes the speed limit, offset, and other related flags.

2. **AnnotatedCameraWidget Update**:
   - In `annotated_camera.cc`, the `updateState` method of the `AnnotatedCameraWidget` class processes these values:
     ```cpp
     if (s.scene.show_speed_limits || s.scene.speed_limit_controller) {
       speedLimit = slcOverridden ? s.scene.speed_limit_overridden_speed : s.scene.speed_limit;
     } else {
       speedLimit = nav_alive ? nav_instruction.getSpeedLimit() : 0.0;
     }
     speedLimit *= (s.scene.is_metric ? MS_TO_KPH : MS_TO_MPH);
     if (s.scene.speed_limit_controller && !showSLCOffset && !slcOverridden && speedLimit != 0) {
       speedLimit += slcSpeedLimitOffset;
     }
     ```

3. **Metric Conversion**:
   - The speed limit value is converted to the appropriate unit (km/h or mph) based on the user's settings (`s.scene.is_metric`).

4. **Offset Handling**:
   - If the speed limit controller is active and the offset is not overridden, the offset (`slcSpeedLimitOffset`) is added to the speed limit for display purposes.

5. **Rendering the Speed Limit**:
   - The `drawHud` method in `AnnotatedCameraWidget` is responsible for rendering the speed limit on the UI. It uses the `speedLimit` variable to draw the speed limit sign:
     ```cpp
     QString speedLimitStr = (speedLimit > 1) ? QString::number(std::nearbyint(speedLimit)) : "–";
     ```

6. **Displaying the Speed Limit Sign**:
   - The UI draws the speed limit sign using the `speedLimitStr`. It also handles different styles for US/Canada and EU speed limit signs, adjusting the display based on the presence of an offset or overridden speed limit.

7. **Pending Speed Limit Changes**:
   - If there are pending speed limit changes, the UI displays a "PENDING" sign next to the current speed limit, indicating an upcoming change.

8. **Source Display**:
   - If enabled, the UI can also display the source of the speed limit data (e.g., Dashboard, Map Data, Navigation) using the `speedLimitSource` variable.