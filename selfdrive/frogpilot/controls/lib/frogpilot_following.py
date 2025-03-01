#!/usr/bin/env python3
import numpy as np

from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import (
  COMFORT_BRAKE, STOP_DISTANCE, desired_follow_distance, get_jerk_factor, get_T_FOLLOW
)
from openpilot.selfdrive.frogpilot.frogpilot_variables import CITY_SPEED_LIMIT

TRAFFIC_MODE_BP = [0., CITY_SPEED_LIMIT]

class FrogPilotFollowing:
  def __init__(self, FrogPilotPlanner):
    self.frogpilot_planner = FrogPilotPlanner

    self.following_lead = False
    self.slower_lead = False

    self.acceleration_jerk = 0
    self.base_acceleration_jerk = 0
    self.base_speed_jerk = 0
    self.base_danger_jerk = 0
    self.danger_jerk = 0
    self.desired_follow_distance = 0
    self.speed_jerk = 0
    self.t_follow = 0
    self.personality_t_follow = 0  # Baseline personality setting for t_follow

  def update(self, aEgo, controlsState, frogpilotCarState, lead_distance, v_ego, v_lead, frogpilot_toggles):
    # Compute the baseline personality t_follow from the personality settings.
    if frogpilotCarState.trafficModeActive:
      if aEgo >= 0:
        self.base_acceleration_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_acceleration)
        self.base_speed_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_speed)
      else:
        self.base_acceleration_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_deceleration)
        self.base_speed_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_speed_decrease)
      self.base_danger_jerk = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_danger)
      self.personality_t_follow = np.interp(v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_follow)
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
      self.personality_t_follow = get_T_FOLLOW(
        frogpilot_toggles.aggressive_follow,
        frogpilot_toggles.standard_follow,
        frogpilot_toggles.relaxed_follow,
        frogpilot_toggles.custom_personalities, controlsState.personality
      )
    # Start each update cycle with the personality baseline.
    self.t_follow = self.personality_t_follow

    # Set the jerk values based on the base personality factors.
    self.acceleration_jerk = self.base_acceleration_jerk
    self.danger_jerk = self.base_danger_jerk
    self.speed_jerk = self.base_speed_jerk

    # Determine if a lead is being tracked.
    self.following_lead = self.frogpilot_planner.tracking_lead and lead_distance < (self.t_follow + 1) * v_ego

    if self.frogpilot_planner.tracking_lead:
      self.update_follow_values(lead_distance, v_ego, v_lead, frogpilot_toggles)
      self.desired_follow_distance = int(desired_follow_distance(v_ego, v_lead, self.t_follow))
    else:
      self.desired_follow_distance = 0

  def update_follow_values(self, lead_distance, v_ego, v_lead, frogpilot_toggles):
    # Only adjust t_follow based on lead dynamics (ignore speed-only triggers)
    if (frogpilot_toggles.conditional_slower_lead or frogpilot_toggles.human_following) and (v_lead < v_ego):
      closing_speed = max(v_ego - v_lead, 0.1)
      ttc = lead_distance / closing_speed

      # Define a reaction factor based on time-to-collision (TTC).
      # When TTC is below 3.5 seconds, scale up t_follow modestly (up to roughly 50% increase).
      ttc_factor = np.clip((3.5 - ttc) / 3.5, 0.0, 1.0)
      braking_scaling = 1.0 + ttc_factor * 0.5

      # Apply scaling to t_follow based solely on lead dynamics.
      self.t_follow *= braking_scaling

      # Mark a slowed-lead scenario if the scaling is significant.
      self.slower_lead = braking_scaling > 1.05
    else:
      self.slower_lead = False

    # Decay t_follow back to the personality baseline when aggressive scaling isn't reinforced.
    decay_rate = 0.1  # Adjust the decay rate as needed.
    self.t_follow = (1 - decay_rate) * self.t_follow + decay_rate * self.personality_t_follow