# PFEIFER - SLC - Modified by FrogAi for FrogPilot
#!/usr/bin/env python3
import json
import time
import numpy as np # For clip function

from openpilot.selfdrive.frogpilot.frogpilot_utilities import calculate_distance_to_point
from openpilot.selfdrive.frogpilot.frogpilot_variables import TO_RADIANS, params, params_memory
# from openpilot.common.realtime import DT_CTRL # Could use this if the calling loop rate is fixed and known (e.g., 0.01 for 100Hz)

# --- Constants for Speed Limit Smoothing ---
TARGET_ACCEL = 1.0  # m/s^2 - Desired acceleration/deceleration rate for smoothing
# Minimum difference between current smoothed speed and final target to keep ramping active (m/s)
# Helps snap to the final value when close enough and avoids floating point issues.
RAMP_THRESHOLD = 0.1
# Minimum change in raw speed limit to trigger saving to params and setting speed_limit_changed flag (m/s)
# Keeps the original behavior for significant changes.
SIGNIFICANT_CHANGE_THRESHOLD = 1.0

class SpeedLimitController:
  def __init__(self):
    self.experimental_mode = False
    self.speed_limit_changed = False # Flag indicating a significant change occurred this cycle

    # Speed limit sources state
    self.map_speed_limit = 0.0
    self.upcoming_speed_limit = 0.0
    self.source = "None"

    # Stores the last *stable* speed limit from any source after applying logic. Used for fallback and change detection.
    self.previous_speed_limit = params.get_float("PreviousSpeedLimit")

    # --- Ramping State ---
    # The gradually changing speed limit recommendation output by this class
    self.smoothed_desired_speed = 0.0
    # The actual speed limit determined by sources/logic that we are ramping towards
    self.target_speed_limit = 0.0
    # Timestamp of the last update call for dt calculation
    self.last_update_time = 0.0
    # Flag to handle initialization on the first run
    self.initialized = False

  def _calculate_dt(self):
    """Calculates the time delta since the last update."""
    now = time.monotonic()
    # Estimate dt, handle first run or time resetting
    # Default to 0.1s (10Hz) if no previous time or if time jumps backward
    dt = (now - self.last_update_time) if self.last_update_time > 0 else 0.1
    self.last_update_time = now
    # Clamp dt to reasonable values (e.g., ~1Hz to ~100Hz) to prevent extreme steps
    return np.clip(dt, 0.01, 1.0)

  def update(self, dashboard_speed_limit, enabled, navigation_speed_limit, v_cruise, v_ego, frogpilot_toggles):
    """
    Updates the speed limit information and calculates the smoothed desired speed limit.

    Args:
      dashboard_speed_limit: Speed limit from car's dashboard (CAN).
      enabled: Boolean indicating if openpilot longitudinal control is active.
      navigation_speed_limit: Speed limit from navigation data.
      v_cruise: Currently set cruise speed.
      v_ego: Current speed of the vehicle (m/s).
      frogpilot_toggles: Dictionary or object containing FrogPilot feature settings.
    """
    dt = self._calculate_dt()

    # --- Determine the raw target speed limit for this cycle ---
    self.update_map_speed_limit(v_ego, frogpilot_toggles)
    # Determine the maximum speed allowed by current cruise setting or 0 if disabled/off
    max_allowed_speed = v_cruise if enabled else 0.0
    # Get the single speed limit value based on priorities and available sources
    raw_limit = self.get_speed_limit(dashboard_speed_limit, max_allowed_speed, navigation_speed_limit, frogpilot_toggles)

    # --- Handle Initialization ---
    if not self.initialized:
      # On the first run, initialize smoothed speed to current ego speed to prevent sudden jumps.
      self.smoothed_desired_speed = v_ego
      # Set the initial target based on the first valid limit found, or ego speed if no limit exists yet.
      self.target_speed_limit = raw_limit if raw_limit > 1.0 else v_ego
      # Initialize previous stable limit as well
      self.previous_speed_limit = raw_limit if raw_limit > 1.0 else 0.0
      self.initialized = True
      # If the initial target is already close to the ego speed, snap to it immediately.
      if abs(self.target_speed_limit - self.smoothed_desired_speed) < RAMP_THRESHOLD:
        self.smoothed_desired_speed = self.target_speed_limit

    # --- Detect changes in the raw limit and update the final target ---
    # Determine the new final target speed. If raw_limit isn't valid (>1 m/s), target becomes 0.
    new_final_target = raw_limit if raw_limit > 1.0 else 0.0

    # Check if this new target represents a *significant* change from the *last known stable* limit
    if abs(new_final_target - self.previous_speed_limit) > SIGNIFICANT_CHANGE_THRESHOLD:
      params.put_float_nonblocking("PreviousSpeedLimit", new_final_target)
      self.previous_speed_limit = new_final_target
      self.speed_limit_changed = True # Signal a major change occurred (for potential external use)
    else:
      self.speed_limit_changed = False

    # Update the *ramping target* if it differs from the new final target
    # Use a small tolerance to avoid reacting to noise
    if abs(new_final_target - self.target_speed_limit) > 0.1:
      self.target_speed_limit = new_final_target

    # --- Perform Ramping ---
    # Calculate the difference between the current smoothed speed and the final target
    delta_to_target = self.target_speed_limit - self.smoothed_desired_speed

    # If the difference is larger than our threshold, ramp towards the target
    if abs(delta_to_target) > RAMP_THRESHOLD:
      # Calculate the maximum change allowed in this step based on target acceleration and dt
      max_step = TARGET_ACCEL * dt
      # Calculate the actual step, capped by max_step and ensuring we don't overshoot
      step = np.clip(delta_to_target, -max_step, max_step)
      # Apply the step
      self.smoothed_desired_speed += step
    else:
      # If we are close enough, snap the smoothed speed directly to the target
      self.smoothed_desired_speed = self.target_speed_limit

    # --- Final Output ---
    # The desired_speed_limit is the smoothed value, but only if the target is valid (>0)
    # Otherwise, output 0. Ensure it's non-negative.
    self.desired_speed_limit = max(0.0, self.smoothed_desired_speed) if self.target_speed_limit > 0 else 0.0

    # --- Update Experimental Mode ---
    # Base experimental mode fallback on the *raw* limit availability, as before.
    self.experimental_mode = frogpilot_toggles.slc_fallback_experimental_mode and raw_limit <= 1.0 # Use raw_limit here

  def update_map_speed_limit(self, v_ego, frogpilot_toggles):
    position = json.loads(params_memory.get("LastGPSPosition") or "{}")
    if not position:
      self.map_speed_limit = 0.0 # Use float
      return

    self.map_speed_limit = params_memory.get_float("MapSpeedLimit")

    next_map_speed_limit = json.loads(params_memory.get("NextMapSpeedLimit") or "{}")
    self.upcoming_speed_limit = next_map_speed_limit.get("speedlimit", 0.0) # Use float
    if self.upcoming_speed_limit > 1.0: # Use float comparison
      current_latitude = position.get("latitude")
      current_longitude = position.get("longitude")

      upcoming_latitude = next_map_speed_limit.get("latitude")
      upcoming_longitude = next_map_speed_limit.get("longitude")

      # Ensure coordinates are valid before calculating distance
      if all(v is not None for v in [current_latitude, current_longitude, upcoming_latitude, upcoming_longitude]):
          distance_to_upcoming = calculate_distance_to_point(current_latitude * TO_RADIANS, current_longitude * TO_RADIANS, upcoming_latitude * TO_RADIANS, upcoming_longitude * TO_RADIANS)

          # Use upcoming limit if close enough based on speed-adjusted lookahead distance
          if self.previous_speed_limit < self.upcoming_speed_limit:
            max_distance = frogpilot_toggles.map_speed_lookahead_higher * v_ego
          else:
            max_distance = frogpilot_toggles.map_speed_lookahead_lower * v_ego

          if distance_to_upcoming < max_distance:
            self.map_speed_limit = self.upcoming_speed_limit
      else:
          # Handle missing coordinate data if necessary, maybe log a warning
          pass


  def get_offset(self, speed_limit, frogpilot_toggles):
    # This function seems unused in the provided logic for determining the base speed limit.
    # If it were used, it should likely be applied *after* selecting the source but *before* ramping.
    # Current implementation doesn't apply it.
    if speed_limit < 13.5:
      return frogpilot_toggles.speed_limit_offset1
    if speed_limit < 24:
      return frogpilot_toggles.speed_limit_offset2
    if speed_limit < 29:
      return frogpilot_toggles.speed_limit_offset3
    return frogpilot_toggles.speed_limit_offset4

  def get_speed_limit(self, dashboard_speed_limit, max_allowed_speed, navigation_speed_limit, frogpilot_toggles):
    """Determines the single speed limit value based on available sources and priority settings."""
    limits = {
      "Dashboard": dashboard_speed_limit,
      "Map Data": self.map_speed_limit,
      "Navigation": navigation_speed_limit
    }
    # Filter out invalid limits (<= 1 m/s is considered invalid)
    filtered_limits = {source: float(limit) for source, limit in limits.items() if limit is not None and float(limit) > 1.0}

    chosen_limit = 0.0
    self.source = "None"

    if filtered_limits:
      # Apply priority logic
      if frogpilot_toggles.speed_limit_priority_highest:
        self.source = max(filtered_limits, key=filtered_limits.get)
        chosen_limit = filtered_limits[self.source]
      elif frogpilot_toggles.speed_limit_priority_lowest:
        self.source = min(filtered_limits, key=filtered_limits.get)
        chosen_limit = filtered_limits[self.source]
      else:
        # Check custom priority list
        priorities = [
          frogpilot_toggles.speed_limit_priority1,
          frogpilot_toggles.speed_limit_priority2,
          frogpilot_toggles.speed_limit_priority3
        ]
        for priority_source in priorities:
          if priority_source is not None and priority_source in filtered_limits:
            self.source = priority_source
            chosen_limit = filtered_limits[priority_source]
            break # Stop once the highest defined priority is found

      # If a limit was chosen from sources, apply offset *here* if desired,
      # or ensure the consuming planner applies offsets appropriately.
      # Example: if frogpilot_toggles.apply_offset_here:
      #    offset = self.get_offset(chosen_limit, frogpilot_toggles)
      #    chosen_limit += offset
      #    chosen_limit = max(1.1, chosen_limit) # Ensure offset doesn't make it invalid

    # If no valid source found after priority logic
    if chosen_limit <= 1.0:
        self.source = "None"
        # Apply fallback logic
        if frogpilot_toggles.slc_fallback_previous_speed_limit and self.previous_speed_limit > 1.0:
          chosen_limit = self.previous_speed_limit
          self.source = "Fallback (Previous)"
        elif frogpilot_toggles.slc_fallback_set_speed and max_allowed_speed > 1.0:
          # Fallback to current v_cruise if set speed fallback is enabled and v_cruise is valid
          chosen_limit = max_allowed_speed
          self.source = "Fallback (Set Speed)"
        else:
            chosen_limit = 0.0 # No valid limit or fallback

    # Final check: ensure the chosen limit doesn't exceed the max allowed speed (v_cruise when enabled)
    # This prevents recommending a speed higher than the user's set speed.
    if max_allowed_speed > 1.0 and chosen_limit > max_allowed_speed:
       # If we only clip here, the 'source' might be misleading.
       # Consider if clipping should happen earlier or if the source reflects the origin before clipping.
       # For simplicity, we clip here.
       chosen_limit = max_allowed_speed
       # Optionally update source: self.source += " (Clipped to Set Speed)"

    return max(0.0, chosen_limit) # Ensure non-negative return

  # get_desired_speed_limit method is removed as its logic is integrated into update()