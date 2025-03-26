#!/usr/bin/env python3
import json
import time

from openpilot.selfdrive.frogpilot.frogpilot_utilities import calculate_distance_to_point
from openpilot.selfdrive.frogpilot.frogpilot_variables import TO_RADIANS, params, params_memory

class SpeedLimitController:
  # Make this smaller for gentler changes, larger for faster changes.
  # e.g. 1.0 = 1.0 m/s², 0.5 = 0.5 m/s², etc.
  SMOOTHING_RATE = .67

  def __init__(self):
    self.experimental_mode = False
    self.speed_limit_changed = False

    # Publicly used attributes
    self.desired_speed_limit = 0
    self.map_speed_limit = 0
    self.speed_limit = 0
    self.upcoming_speed_limit = 0

    self.source = "None"
    self.previous_speed_limit = params.get_float("PreviousSpeedLimit")

    # Internal variable to hold our smoothed speed:
    self.smoothed_speed_limit = self.previous_speed_limit

    # For timing between update calls
    self.last_update_time = time.monotonic()

  def update(self, dashboard_speed_limit, enabled, navigation_speed_limit, v_cruise, v_ego, frogpilot_toggles):
    """
    Called periodically. We'll compute a new 'target' speed limit, then smoothly
    adjust our recommended speed toward that target.
    """
    # 1. Normal logic for speed limit
    self.update_map_speed_limit(v_ego, frogpilot_toggles)
    max_speed_limit = v_cruise if enabled else 0

    self.speed_limit = self.get_speed_limit(
      dashboard_speed_limit,
      max_speed_limit,
      navigation_speed_limit,
      frogpilot_toggles
    )

    # 2. This sets desired_speed_limit (and sets the flag if changed),
    #    effectively our new "target" for smoothing.
    new_target_speed = self.get_desired_speed_limit()

    # 3. If the speed limit changed beyond threshold, we note it:
    if self.speed_limit_changed:
      # We can optionally do something special here if needed,
      # but the main smoothing logic is in 'apply_speed_smoothing' below.
      pass

    # 4. Smooth the recommended speed toward 'new_target_speed'
    self.apply_speed_smoothing(new_target_speed)

    # 5. Final “published” value remains desired_speed_limit for downstream code.
    self.desired_speed_limit = self.smoothed_speed_limit

    # 6. From original code: set experimental mode if needed
    self.experimental_mode = (
      frogpilot_toggles.slc_fallback_experimental_mode
      and self.speed_limit == 0
    )

  def apply_speed_smoothing(self, target_speed):
    """
    Gradually move self.smoothed_speed_limit to target_speed at ~SMOOTHING_RATE (m/s²).
    """
    current_time = time.monotonic()
    dt = current_time - self.last_update_time
    self.last_update_time = current_time

    # No time elapsed => no smoothing
    if dt <= 0.0:
      return

    # The maximum change in speed we allow this cycle
    max_delta = self.SMOOTHING_RATE * dt

    speed_diff = target_speed - self.smoothed_speed_limit

    if abs(speed_diff) <= max_delta:
      # Close enough, just snap to the target
      self.smoothed_speed_limit = target_speed
    else:
      # Move by max_delta in direction of target
      direction = 1.0 if speed_diff > 0 else -1.0
      self.smoothed_speed_limit += direction * max_delta

  def get_desired_speed_limit(self):
    """
    Same logic as before: if the speed limit changed beyond some threshold,
    update storage and mark speed_limit_changed. Return the final speed limit
    we want to move toward via smoothing.
    """
    if self.speed_limit > 1:
      if abs(self.speed_limit - self.previous_speed_limit) > 1:
        params.put_float_nonblocking("PreviousSpeedLimit", self.speed_limit)
        self.previous_speed_limit = self.speed_limit
        self.speed_limit_changed = True
      return self.speed_limit
    else:
      self.speed_limit_changed = False
      return 0

  def update_map_speed_limit(self, v_ego, frogpilot_toggles):
    position = json.loads(params_memory.get("LastGPSPosition") or "{}")
    if not position:
      self.map_speed_limit = 0
      return

    self.map_speed_limit = params_memory.get_float("MapSpeedLimit")

    next_map_speed_limit = json.loads(params_memory.get("NextMapSpeedLimit") or "{}")
    self.upcoming_speed_limit = next_map_speed_limit.get("speedlimit", 0)

    if self.upcoming_speed_limit > 1:
      current_latitude = position.get("latitude")
      current_longitude = position.get("longitude")
      upcoming_latitude = next_map_speed_limit.get("latitude")
      upcoming_longitude = next_map_speed_limit.get("longitude")

      distance_to_upcoming = calculate_distance_to_point(
        current_latitude * TO_RADIANS, current_longitude * TO_RADIANS,
        upcoming_latitude * TO_RADIANS, upcoming_longitude * TO_RADIANS
      )

      if self.previous_speed_limit < self.upcoming_speed_limit:
        max_distance = frogpilot_toggles.map_speed_lookahead_higher * v_ego
      else:
        max_distance = frogpilot_toggles.map_speed_lookahead_lower * v_ego

      if distance_to_upcoming < max_distance:
        self.map_speed_limit = self.upcoming_speed_limit

  def get_offset(self, speed_limit, frogpilot_toggles):
    if speed_limit < 13.5:
      return frogpilot_toggles.speed_limit_offset1
    if speed_limit < 24:
      return frogpilot_toggles.speed_limit_offset2
    if speed_limit < 29:
      return frogpilot_toggles.speed_limit_offset3
    return frogpilot_toggles.speed_limit_offset4

  def get_speed_limit(self, dashboard_speed_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles):
    limits = {
      "Dashboard": dashboard_speed_limit,
      "Map Data": self.map_speed_limit,
      "Navigation": navigation_speed_limit
    }
    filtered_limits = {source: float(limit) for source, limit in limits.items() if limit > 1}

    if filtered_limits:
      if frogpilot_toggles.speed_limit_priority_highest:
        self.source = max(filtered_limits, key=filtered_limits.get)
        return filtered_limits[self.source]

      if frogpilot_toggles.speed_limit_priority_lowest:
        self.source = min(filtered_limits, key=filtered_limits.get)
        return filtered_limits[self.source]

      for priority in [
        frogpilot_toggles.speed_limit_priority1,
        frogpilot_toggles.speed_limit_priority2,
        frogpilot_toggles.speed_limit_priority3
      ]:
        if priority is not None and priority in filtered_limits:
          self.source = priority
          return filtered_limits[priority]

    self.source = "None"

    if frogpilot_toggles.slc_fallback_previous_speed_limit:
      return self.previous_speed_limit

    if frogpilot_toggles.slc_fallback_set_speed:
      return max_speed_limit

    return 0
