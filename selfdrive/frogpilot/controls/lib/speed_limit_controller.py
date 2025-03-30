# PFEIFER - SLC - Modified by FrogAi for FrogPilot
#!/usr/bin/env python3
import json

from openpilot.selfdrive.frogpilot.frogpilot_utilities import calculate_distance_to_point
from openpilot.selfdrive.frogpilot.frogpilot_variables import TO_RADIANS, params, params_memory

class SpeedLimitController:
  def __init__(self):
    self.experimental_mode = False
    self.speed_limit_changed = False

    self.desired_speed_limit = 0
    self.map_speed_limit = 0
    self.speed_limit = 0
    self.upcoming_speed_limit = 0

    self.source = "None"

    self.previous_speed_limit = params.get_float("PreviousSpeedLimit")

  def update(self, dashboard_speed_limit, enabled, navigation_speed_limit, v_cruise, v_ego, frogpilot_toggles):
    self.update_map_speed_limit(v_ego, frogpilot_toggles)
    max_speed_limit = v_cruise if enabled else 0

    self.speed_limit = self.get_speed_limit(dashboard_speed_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles)
    self.desired_speed_limit = self.get_desired_speed_limit()

    self.experimental_mode = frogpilot_toggles.slc_fallback_experimental_mode and self.speed_limit == 0

  def get_desired_speed_limit(self):
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

      distance_to_upcoming = calculate_distance_to_point(current_latitude * TO_RADIANS, current_longitude * TO_RADIANS, upcoming_latitude * TO_RADIANS, upcoming_longitude * TO_RADIANS)

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

"""
#!/usr/bin/env python3

import json
import time

from openpilot.selfdrive.frogpilot.frogpilot_utilities import calculate_distance_to_point
from openpilot.selfdrive.frogpilot.frogpilot_variables import TO_RADIANS, params, params_memory

class SpeedLimitController:
  def __init__(self):
    """
    Initialize the speed limit controller with default values and ramping parameters.
    """
    self.experimental_mode = False
    self.speed_limit_changed = False

    self.desired_speed_limit = 0
    self.map_speed_limit = 0
    self.speed_limit = 0
    self.upcoming_speed_limit = 0

    self.source = "None"
    self.previous_speed_limit = params.get_float("PreviousSpeedLimit")

    self.ramp_desired_speed = 0.0
    self.last_update_time = time.monotonic()
    self.initialized = False

    self.accel_rate_up = 1.2
    self.accel_rate_down = 0.67

  def update(self, dashboard_speed_limit, enabled, navigation_speed_limit, v_cruise, v_ego, frogpilot_toggles):
    """
    Main update loop for computing the smoothed desired speed limit.
    """
    self.update_map_speed_limit(v_ego, frogpilot_toggles)
    max_speed_limit = v_cruise if enabled else 0
    self.speed_limit = self.get_speed_limit(dashboard_speed_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles)
    new_desired_speed_limit = self.get_desired_speed_limit()

    if not self.initialized:
      self.ramp_desired_speed = float(v_ego)
      self.initialized = True

    # Check if the new desired speed limit is valid
    if new_desired_speed_limit >= 1:
      self.desired_speed_limit = self._ramp_towards_target(current=self.ramp_desired_speed, target=new_desired_speed_limit)
      self.ramp_desired_speed = self.desired_speed_limit
    else:
      # Set to default 'no data' state
      self.desired_speed_limit = 0.0  # Use 0.0 for no data instead of '--'

    self.experimental_mode = frogpilot_toggles.slc_fallback_experimental_mode and (self.speed_limit == 0)

    self.desired_speed_limit = round(self.desired_speed_limit)
    self.speed_limit = round(self.speed_limit)
    self.map_speed_limit = round(self.map_speed_limit)
    self.upcoming_speed_limit = round(self.upcoming_speed_limit)

  def get_desired_speed_limit(self):
    """
    Returns the current valid speed limit if available and updates change tracking.
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
    """
    Updates map-based speed limit using GPS data and upcoming speed limits if available.
    """
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

  def get_offset(self, speed_limit, frogpilot_toggles):
    """
    Returns the speed limit offset based on the magnitude of the speed limit.
    """
    if speed_limit < 13.5:
      return frogpilot_toggles.speed_limit_offset1
    if speed_limit < 24:
      return frogpilot_toggles.speed_limit_offset2
    if speed_limit < 29:
      return frogpilot_toggles.speed_limit_offset3
    return frogpilot_toggles.speed_limit_offset4

  def get_speed_limit(self, dashboard_speed_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles):
    """
    Determines the speed limit using available sources based on user-configured priorities and fallbacks.
    """
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

  def _ramp_towards_target(self, current: float, target: float) -> float:
    """
    Incrementally adjusts the current smoothed speed toward the target speed
    based on asymmetric acceleration and deceleration rates.
    """
    now = time.monotonic()
    dt = now - self.last_update_time
    self.last_update_time = now

    dt = max(0.01, min(dt, 1.0))

    delta = target - current
    max_step = self.accel_rate_up * dt if delta > 0 else self.accel_rate_down * dt

    if abs(delta) <= max_step:
      return target
    else:
      step = max_step if delta > 0 else -max_step
      return current + step
"""
