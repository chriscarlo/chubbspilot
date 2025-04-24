# PFEIFER - SLC - Modified by FrogAi for FrogPilot
#!/usr/bin/env python3
import cereal.messaging as messaging

from openpilot.selfdrive.frogpilot.frogpilot_variables import params # Keep params for PreviousSpeedLimit

class SpeedLimitController:
  def __init__(self):
    self.experimental_mode = False
    self.speed_limit_changed = False

    self.desired_speed_limit = 0
    # self.map_speed_limit = 0 # Removed, will be determined in update
    self.speed_limit = 0
    # self.upcoming_speed_limit = 0 # Removed, will be determined in update

    self.source = "None"

    self.previous_speed_limit = params.get_float("PreviousSpeedLimit")

    # Add SubMaster for liveMapData
    self.sm = messaging.SubMaster(['liveMapData'], poll='liveMapData')

  def update(self, dashboard_speed_limit, enabled, navigation_speed_limit, v_cruise, v_ego, frogpilot_toggles):
    self.sm.update(0) # Update SubMaster

    # Extract data from liveMapData message
    liveMapData = self.sm['liveMapData']
    map_speed_limit = liveMapData.speedLimit if liveMapData.speedLimitValid else 0
    upcoming_speed_limit = liveMapData.speedLimitAhead if liveMapData.speedLimitAheadValid else 0
    upcoming_distance = liveMapData.speedLimitAheadDistance if liveMapData.speedLimitAheadValid else 0

    # Determine effective map speed limit considering lookahead
    effective_map_limit = map_speed_limit
    if upcoming_speed_limit > 1 and upcoming_distance > 0:
      # Use lookahead logic based on toggles
      if map_speed_limit < upcoming_speed_limit:
        # Speed limit increases ahead
        max_distance = frogpilot_toggles.map_speed_lookahead_higher * v_ego
      else:
        # Speed limit decreases ahead
        max_distance = frogpilot_toggles.map_speed_lookahead_lower * v_ego

      if upcoming_distance < max_distance:
        effective_map_limit = upcoming_speed_limit

    max_speed_limit = v_cruise if enabled else 0

    self.speed_limit = self.get_speed_limit(dashboard_speed_limit, effective_map_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles)
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

  def get_offset(self, speed_limit, frogpilot_toggles):
    if speed_limit < 13.5:
      return frogpilot_toggles.speed_limit_offset1
    if speed_limit < 24:
      return frogpilot_toggles.speed_limit_offset2
    if speed_limit < 29:
      return frogpilot_toggles.speed_limit_offset3
    return frogpilot_toggles.speed_limit_offset4

  def get_speed_limit(self, dashboard_speed_limit, effective_map_limit, max_speed_limit, navigation_speed_limit, frogpilot_toggles):
    limits = {
      "Dashboard": dashboard_speed_limit,
      "Map Data": effective_map_limit, # Use the calculated effective map limit
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
