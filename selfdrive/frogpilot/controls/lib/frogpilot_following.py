#!/usr/bin/env python3
import numpy as np

from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import COMFORT_BRAKE, STOP_DISTANCE, desired_follow_distance, get_jerk_factor, get_T_FOLLOW

from openpilot.selfdrive.frogpilot.frogpilot_variables import CITY_SPEED_LIMIT

# Define constants locally to break circular import
COMFORT_BRAKE = 2.0  # m/s^2 - brake applied when lead car is stopped
STOP_DISTANCE = 5.0  # m - distance to lead car when lead is stopped
TRAFFIC_MODE_BP = [0., CITY_SPEED_LIMIT]

# Define helper functions locally to break circular import
def desired_follow_distance(v_ego, v_lead, t_follow=None):
  return (v_ego * (t_follow or 1.45)) + (v_lead * 0.375)

def get_jerk_factor(aggressive_jerk_acceleration=0.5, aggressive_jerk_danger=0.5, aggressive_jerk_speed=0.5,
                   standard_jerk_acceleration=1.0, standard_jerk_danger=1.0, standard_jerk_speed=1.0,
                   relaxed_jerk_acceleration=1.0, relaxed_jerk_danger=1.0, relaxed_jerk_speed=1.0,
                   custom_personalities=False, personality=0):
  if custom_personalities:
    if personality == 0:  # aggressive
      return aggressive_jerk_acceleration, aggressive_jerk_danger, aggressive_jerk_speed
    elif personality == 1:  # standard
      return standard_jerk_acceleration, standard_jerk_danger, standard_jerk_speed
    elif personality == 2:  # relaxed
      return relaxed_jerk_acceleration, relaxed_jerk_danger, relaxed_jerk_speed
  return 1.0, 1.0, 1.0

def get_T_FOLLOW(aggressive_follow=1.25, standard_follow=1.45, relaxed_follow=1.75, custom_personalities=False, personality=0):
  if custom_personalities:
    if personality == 0:  # aggressive
      return aggressive_follow
    elif personality == 1:  # standard
      return standard_follow
    elif personality == 2:  # relaxed
      return relaxed_follow
  return 1.45


class FrogPilotFollowing:
  def __init__(self, FrogPilotPlanner):
    self.frogpilot_planner = FrogPilotPlanner

    self.following_lead = False
    self.slower_lead = False

    self.acceleration_jerk = 0
    self.base_acceleration_jerk = 0
    self.base_speed_jerk = 0
    self.danger_jerk = 0
    self.desired_follow_distance = 0
    self.speed_jerk = 0
    self.t_follow = 0

  def update(self, aEgo, controlsState, frogpilotCarState, lead_distance, v_ego, v_lead, frogpilot_toggles):
    if frogpilotCarState.trafficModeActive:
      if aEgo >= 0:
        self.base_acceleration_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_acceleration)
        self.base_speed_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_speed)
      else:
        self.base_acceleration_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_deceleration)
        self.base_speed_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_speed_decrease)

      self.base_danger_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_danger)
      self.t_follow = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_follow)
    else:
      if aEgo >= 0:
        self.base_acceleration_jerk, self.base_danger_jerk, self.base_speed_jerk = get_jerk_factor(
          frogpilot_toggles.aggressive_jerk_acceleration, frogpilot_toggles.aggressive_jerk_danger, frogpilot_toggles.aggressive_jerk_speed,
          frogpilot_toggles.standard_jerk_acceleration, frogpilot_toggles.standard_jerk_danger, frogpilot_toggles.standard_jerk_speed,
          frogpilot_toggles.relaxed_jerk_acceleration, frogpilot_toggles.relaxed_jerk_danger, frogpilot_toggles.relaxed_jerk_speed,
          frogpilot_toggles.custom_personalities, controlsState.personality
        )
      else:
        self.base_acceleration_jerk, self.base_danger_jerk, self.base_speed_jerk = get_jerk_factor(
          frogpilot_toggles.aggressive_jerk_deceleration, frogpilot_toggles.aggressive_jerk_danger, frogpilot_toggles.aggressive_jerk_speed_decrease,
          frogpilot_toggles.standard_jerk_deceleration, frogpilot_toggles.standard_jerk_danger, frogpilot_toggles.standard_jerk_speed_decrease,
          frogpilot_toggles.relaxed_jerk_deceleration, frogpilot_toggles.relaxed_jerk_danger, frogpilot_toggles.relaxed_jerk_speed_decrease,
          frogpilot_toggles.custom_personalities, controlsState.personality
        )

      self.t_follow = get_T_FOLLOW(
        frogpilot_toggles.aggressive_follow,
        frogpilot_toggles.standard_follow,
        frogpilot_toggles.relaxed_follow,
        frogpilot_toggles.custom_personalities, controlsState.personality
      )

    self.acceleration_jerk = self.base_acceleration_jerk
    self.danger_jerk = self.base_danger_jerk
    self.speed_jerk = self.base_speed_jerk

    self.following_lead = self.frogpilot_planner.tracking_lead and lead_distance < (self.t_follow + 1) * v_ego

    if self.frogpilot_planner.tracking_lead:
      self.update_follow_values(lead_distance, v_ego, v_lead, frogpilot_toggles)
      self.desired_follow_distance = int(desired_follow_distance(v_ego, v_lead, self.t_follow))
    else:
      self.desired_follow_distance = 0

  def update_follow_values(self, lead_distance, v_ego, v_lead, frogpilot_toggles):
    # Offset by FrogAi for FrogPilot for a more natural approach to a faster lead
    if frogpilot_toggles.human_following and v_lead > v_ego:
      distance_factor = max(lead_distance - (v_ego * self.t_follow), 1)
      standstill_offset = max(STOP_DISTANCE - v_ego, 1)
      acceleration_offset = np.clip((v_lead - v_ego) * standstill_offset - COMFORT_BRAKE, 1, distance_factor)
      self.acceleration_jerk /= acceleration_offset
      self.speed_jerk /= acceleration_offset
      self.t_follow /= acceleration_offset

    # Offset by FrogAi for FrogPilot for a more natural approach to a slower lead
    if (frogpilot_toggles.conditional_slower_lead or frogpilot_toggles.human_following) and v_lead < v_ego:
      distance_factor = max(lead_distance - (v_lead * self.t_follow), 1)
      far_lead_offset = max(v_lead - CITY_SPEED_LIMIT, 1)

      # Calculate speed differential and normalize it
      speed_diff = v_ego - v_lead
      norm_speed_diff = speed_diff / max(v_lead, 1.0)

      # Modified braking offset calculation for earlier, gentler braking
      # Using a direct formula approach instead of importing potentially circular dependencies
      braking_offset = np.clip(
        min(speed_diff, v_lead) * far_lead_offset * (1 + 0.5 * norm_speed_diff) - COMFORT_BRAKE,
        1,
        distance_factor
      )

      # Safer approach for human_following that avoids potential circular dependencies
      if frogpilot_toggles.human_following:
        # Instead of dynamically calculating distance ratios (which might trigger imports),
        # use a simple modifier based on how close we are to the lead vehicle
        distance_closeness = np.clip(1.0 - (lead_distance / (30.0 + v_ego)), 0, 0.2)
        self.t_follow *= (1.0 - distance_closeness)

      self.slower_lead = braking_offset / far_lead_offset > 1
