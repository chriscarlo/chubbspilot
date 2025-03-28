#!/usr/bin/env python3
# PFEIFER - SLC - Modified by FrogAi for FrogPilot

import json
import time
import numpy as np  # For clip function

from openpilot.selfdrive.frogpilot.frogpilot_utilities import calculate_distance_to_point
from openpilot.selfdrive.frogpilot.frogpilot_variables import TO_RADIANS, params, params_memory

# --- Constants for Speed Limit Smoothing ---
TARGET_ACCEL = 1.0   # m/s^2 - Desired acceleration/deceleration rate for smoothing
RAMP_THRESHOLD = 0.1
SIGNIFICANT_CHANGE_THRESHOLD = 1.0

class SpeedLimitController:
  def __init__(self):
    self.experimental_mode = False
    self.speed_limit_changed = False  # Flag indicating a significant change occurred this cycle

    # Speed limit sources state
    self.map_speed_limit = 0.0
    self.upcoming_speed_limit = 0.0
    self.source = "None"

    # PATCH: Safely load previous speed limit as float
    self.previous_speed_limit = params.get_float("PreviousSpeedLimit")
    if self.previous_speed_limit is None:
      self.previous_speed_limit = 0.0

    # --- Ramping State ---
    self.smoothed_desired_speed = 0.0
    self.target_speed_limit = 0.0
    self.last_update_time = 0.0
    self.initialized = False

  def _calculate_dt(self):
    """Calculates the time delta since the last update."""
    now = time.monotonic()
    dt = (now - self.last_update_time) if self.last_update_time > 0 else 0.1
    self.last_update_time = now
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
    max_allowed_speed = v_cruise if enabled else 0.0
    raw_limit = self.get_speed_limit(dashboard_speed_limit, max_allowed_speed, navigation_speed_limit, frogpilot_toggles)

    # --- Handle Initialization ---
    if not self.initialized:
      self.smoothed_desired_speed = v_ego
      self.target_speed_limit = raw_limit if raw_limit > 1.0 else v_ego
      self.previous_speed_limit = raw_limit if raw_limit > 1.0 else 0.0
      self.initialized = True
      if abs(self.target_speed_limit - self.smoothed_desired_speed) < RAMP_THRESHOLD:
        self.smoothed_desired_speed = self.target_speed_limit

    # --- Detect changes in the raw limit and update the final target ---
    new_final_target = raw_limit if raw_limit > 1.0 else 0.0

    if abs(new_final_target - self.previous_speed_limit) > SIGNIFICANT_CHANGE_THRESHOLD:
      params.put_float_nonblocking("PreviousSpeedLimit", new_final_target)
      self.previous_speed_limit = new_final_target
      self.speed_limit_changed = True
    else:
      self.speed_limit_changed = False

    if abs(new_final_target - self.target_speed_limit) > 0.1:
      self.target_speed_limit = new_final_target

    # --- Perform Ramping ---
    delta_to_target = self.target_speed_limit - self.smoothed_desired_speed
    if abs(delta_to_target) > RAMP_THRESHOLD:
      max_step = TARGET_ACCEL * dt
      step = np.clip(delta_to_target, -max_step, max_step)
      self.smoothed_desired_speed += step
    else:
      self.smoothed_desired_speed = self.target_speed_limit

    # --- Final Output ---
    self.desired_speed_limit = max(0.0, self.smoothed_desired_speed) if self.target_speed_limit > 0 else 0.0

    # --- Update Experimental Mode ---
    self.experimental_mode = (frogpilot_toggles.slc_fallback_experimental_mode and raw_limit <= 1.0)

  def update_map_speed_limit(self, v_ego, frogpilot_toggles):
    position = json.loads(params_memory.get("LastGPSPosition") or "{}")
    if not position:
      self.map_speed_limit = 0.0
      return

    # PATCH: Safely convert to float
    self.map_speed_limit = params_memory.get_float("MapSpeedLimit") or 0.0

    next_map_speed_limit = json.loads(params_memory.get("NextMapSpeedLimit") or "{}")
    # PATCH: Safely convert to float
    self.upcoming_speed_limit = float(next_map_speed_limit.get("speedlimit", 0.0) or 0.0)

    if self.upcoming_speed_limit > 1.0:
      current_latitude = position.get("latitude")
      current_longitude = position.get("longitude")
      upcoming_latitude = next_map_speed_limit.get("latitude")
      upcoming_longitude = next_map_speed_limit.get("longitude")

      if all(v is not None for v in [current_latitude, current_longitude, upcoming_latitude, upcoming_longitude]):
        distance_to_upcoming = calculate_distance_to_point(
          current_latitude * TO_RADIANS,
          current_longitude * TO_RADIANS,
          upcoming_latitude * TO_RADIANS,
          upcoming_longitude * TO_RADIANS
        )

        if self.previous_speed_limit < self.upcoming_speed_limit:
          max_distance = frogpilot_toggles.map_speed_lookahead_higher * v_ego
        else:
          max_distance = frogpilot_toggles.map_speed_lookahead_lower * v_ego

        if distance_to_upcoming < max_distance:
          self.map_speed_limit = self.upcoming_speed_limit
      else:
        # Handle missing coordinate data if necessary
        pass

  def get_offset(self, speed_limit, frogpilot_toggles):
    # Currently unused. If needed, ensure no None usage.
    if speed_limit < 13.5:
      return frogpilot_toggles.speed_limit_offset1
    if speed_limit < 24:
      return frogpilot_toggles.speed_limit_offset2
    if speed_limit < 29:
      return frogpilot_toggles.speed_limit_offset3
    return frogpilot_toggles.speed_limit_offset4

  def get_speed_limit(self, dashboard_speed_limit, max_allowed_speed, navigation_speed_limit, frogpilot_toggles):
    """Determines the single speed limit value based on available sources and priority settings."""
    # PATCH: Convert to float if not None, filter invalid
    limits = {
      "Dashboard": float(dashboard_speed_limit) if dashboard_speed_limit is not None else 0.0,
      "Map Data": float(self.map_speed_limit),
      "Navigation": float(navigation_speed_limit) if navigation_speed_limit is not None else 0.0
    }

    filtered_limits = {src: val for src, val in limits.items() if val > 1.0}

    chosen_limit = 0.0
    self.source = "None"

    if filtered_limits:
      if frogpilot_toggles.speed_limit_priority_highest:
        self.source = max(filtered_limits, key=filtered_limits.get)
        chosen_limit = filtered_limits[self.source]
      elif frogpilot_toggles.speed_limit_priority_lowest:
        self.source = min(filtered_limits, key=filtered_limits.get)
        chosen_limit = filtered_limits[self.source]
      else:
        priorities = [
          frogpilot_toggles.speed_limit_priority1,
          frogpilot_toggles.speed_limit_priority2,
          frogpilot_toggles.speed_limit_priority3
        ]
        for priority_source in priorities:
          if priority_source is not None and priority_source in filtered_limits:
            self.source = priority_source
            chosen_limit = filtered_limits[priority_source]
            break

    if chosen_limit <= 1.0:
      self.source = "None"
      if frogpilot_toggles.slc_fallback_previous_speed_limit and self.previous_speed_limit > 1.0:
        chosen_limit = self.previous_speed_limit
        self.source = "Fallback (Previous)"
      elif frogpilot_toggles.slc_fallback_set_speed and max_allowed_speed > 1.0:
        chosen_limit = max_allowed_speed
        self.source = "Fallback (Set Speed)"
      else:
        chosen_limit = 0.0

    if max_allowed_speed > 1.0 and chosen_limit > max_allowed_speed:
      chosen_limit = max_allowed_speed

    return max(0.0, chosen_limit)