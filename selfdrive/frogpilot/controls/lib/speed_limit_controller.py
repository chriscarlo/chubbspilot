import json
from openpilot.common.params import Params
# Params instance for persistent storage
params = Params()
# params_memory for volatile storage (imported from FrogPilot utilities)
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
    # Load previous speed limit from persistent params (for original tracking)
    self.previous_speed_limit = params.get_float("PreviousSpeedLimit")

  def update(self, dashboard_speed_limit, enabled, navigation_speed_limit, v_cruise, v_ego, frogpilot_toggles):
    # Update map-based speed limit (lookahead for upcoming changes)
    self.update_map_speed_limit(v_ego, frogpilot_toggles)
    # Determine the active speed limit from available sources (dashboard, map, navigation)
    max_speed_limit = v_cruise if enabled else 0  # optional cap when engaged
    self.speed_limit = self.get_speed_limit(dashboard_speed_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles)
    # Determine if there's a new desired speed limit
    self.desired_speed_limit = self.get_desired_speed_limit()
    # Determine if experimental mode should engage as fallback (if no limit found)
    self.experimental_mode = frogpilot_toggles.slc_fallback_experimental_mode and self.speed_limit == 0

  def get_desired_speed_limit(self):
    if self.speed_limit > 1:
      # If the speed limit has changed significantly (more than ~1 m/s ~ 2.2 mph)
      if abs(self.speed_limit - self.previous_speed_limit) > 1:
        # Store the previous speed limit persistently for reference
        params.put_float_nonblocking("PreviousSpeedLimit", self.speed_limit)
        self.previous_speed_limit = self.speed_limit
        self.speed_limit_changed = True
        return self.speed_limit
      else:
        # No significant change in speed limit
        self.speed_limit_changed = False
        return 0
    else:
      # No valid speed limit available
      self.speed_limit_changed = False
      return 0

  def update_map_speed_limit(self, v_ego, frogpilot_toggles):
    position = json.loads(params_memory.get("LastGPSPosition") or "{}")
    if not position:
      # No GPS position available, cannot get map data
      self.map_speed_limit = 0
      return
    # Get current map speed limit (if any) from memory (set by navd or other process)
    self.map_speed_limit = params_memory.get_float("MapSpeedLimit")
    next_map_speed_limit = json.loads(params_memory.get("NextMapSpeedLimit") or "{}")
    self.upcoming_speed_limit = next_map_speed_limit.get("speedlimit", 0)
    if self.upcoming_speed_limit > 1:
      # If an upcoming speed limit is known, calculate distance to it
      current_latitude = position.get("latitude")
      current_longitude = position.get("longitude")
      upcoming_latitude = next_map_speed_limit.get("latitude")
      upcoming_longitude = next_map_speed_limit.get("longitude")
      distance_to_upcoming = calculate_distance_to_point(current_latitude * TO_RADIANS,
                                                         current_longitude * TO_RADIANS,
                                                         upcoming_latitude * TO_RADIANS,
                                                         upcoming_longitude * TO_RADIANS)
      # Choose lookahead distance based on whether the upcoming limit is higher or lower
      if self.previous_speed_limit < self.upcoming_speed_limit:
        max_distance = frogpilot_toggles.map_speed_lookahead_higher * v_ego
      else:
        max_distance = frogpilot_toggles.map_speed_lookahead_lower * v_ego
      # If within lookahead distance, adopt the upcoming speed limit as current map speed limit
      if distance_to_upcoming < max_distance:
        self.map_speed_limit = self.upcoming_speed_limit

  def get_offset(self, speed_limit, frogpilot_toggles):
    # Determine user-set offset based on speed limit range
    if speed_limit < 13.5:   # ~0-30 mph
      return frogpilot_toggles.speed_limit_offset1
    if speed_limit < 24:     # ~30-54 mph
      return frogpilot_toggles.speed_limit_offset2
    if speed_limit < 29:     # ~54-65 mph
      return frogpilot_toggles.speed_limit_offset3
    return frogpilot_toggles.speed_limit_offset4

  def get_speed_limit(self, dashboard_speed_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles):
    # Combine available speed limit sources
    limits = {
      "Dashboard": dashboard_speed_limit,
      "Map Data": self.map_speed_limit,
      "Navigation": navigation_speed_limit
    }
    filtered_limits = {source: float(limit) for source, limit in limits.items() if limit > 1}
    if filtered_limits:
      # Apply priority policy to choose which source to trust
      if frogpilot_toggles.speed_limit_priority_highest:
        # Choose the highest speed limit available
        self.source = max(filtered_limits, key=filtered_limits.get)
        return filtered_limits[self.source]
      if frogpilot_toggles.speed_limit_priority_lowest:
        # Choose the lowest speed limit available
        self.source = min(filtered_limits, key=filtered_limits.get)
        return filtered_limits[self.source]
      # Use custom priority order if set
      for priority in [frogpilot_toggles.speed_limit_priority1,
                       frogpilot_toggles.speed_limit_priority2,
                       frogpilot_toggles.speed_limit_priority3]:
        if priority is not None and priority in filtered_limits:
          self.source = priority
          return filtered_limits[priority]
      # If none of the priority conditions matched, no valid limit from preferred sources
      self.source = "None"
    else:
      # No speed limit data available from any source
      self.source = "None"
    # Fallback behaviors if no active speed limit:
    if frogpilot_toggles.slc_fallback_previous_speed_limit:
      # Use the last known speed limit as fallback
      return self.previous_speed_limit
    if frogpilot_toggles.slc_fallback_set_speed:
      # Fallback to the current set speed (max_speed_limit)
      return max_speed_limit
    # Default: no speed limit
    return 0
