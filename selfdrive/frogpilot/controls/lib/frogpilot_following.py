#!/usr/bin/env python3
import numpy as np

from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import (
  COMFORT_BRAKE, STOP_DISTANCE, desired_follow_distance, get_jerk_factor, get_T_FOLLOW
)
from openpilot.selfdrive.frogpilot.frogpilot_variables import CITY_SPEED_LIMIT

TRAFFIC_MODE_BP = [0., CITY_SPEED_LIMIT]

# -- Lower decay for less messing with t_follow
DECAY_RATE = 0.02  # was 0.1
LOW_SPEED_THRESHOLD = 11.4
MIN_T_FOLLOW_AT_LOW_SPEED = 0.7
LEAD_ACCEL_THRESHOLD = 0.2
ACCEL_OVERSHOOT_RATIO = 0.9

class FrogPilotFollowing:
  def __init__(self, FrogPilotPlanner):
    self.frogpilot_planner = FrogPilotPlanner

    # Tracking / state booleans
    self.following_lead = False
    self.slower_lead = False

    # Jerk / follow distance / time-gap variables
    self.acceleration_jerk = 0
    self.base_acceleration_jerk = 0
    self.base_speed_jerk = 0
    self.base_danger_jerk = 0
    self.danger_jerk = 0
    self.speed_jerk = 0

    self.desired_follow_distance = 0
    self.t_follow = 0
    self.personality_t_follow = 0

    # Acceleration override: optionally used if catching up
    self.acceleration_override = None

  def update(self, aEgo, controlsState, frogpilotCarState,
             lead_distance, v_ego, v_lead, frogpilot_toggles):
    """
    Main entry point each loop. By default, we do minimal messing with t_follow unless
    frogpilot_toggles.enableCatchUp is True.
    """
    # 1) Baseline personality or traffic-mode logic
    if frogpilotCarState.trafficModeActive:
      if aEgo >= 0:
        self.base_acceleration_jerk = np.interp(
          v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_acceleration
        )
        self.base_speed_jerk = np.interp(
          v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_speed
        )
      else:
        self.base_acceleration_jerk = np.interp(
          v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_deceleration
        )
        self.base_speed_jerk = np.interp(
          v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_speed_decrease
        )

      self.base_danger_jerk = np.interp(
        v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_jerk_danger
      )
      self.personality_t_follow = np.interp(
        v_ego, TRAFFIC_MODE_BP, frogpilot_toggles.traffic_mode_follow
      )

    else:
      if aEgo >= 0:
        (self.base_acceleration_jerk,
         self.base_danger_jerk,
         self.base_speed_jerk) = get_jerk_factor(
           frogpilot_toggles.aggressive_jerk_acceleration,
           frogpilot_toggles.aggressive_jerk_danger,
           frogpilot_toggles.aggressive_jerk_speed,
           frogpilot_toggles.standard_jerk_acceleration,
           frogpilot_toggles.standard_jerk_danger,
           frogpilot_toggles.standard_jerk_speed,
           frogpilot_toggles.relaxed_jerk_acceleration,
           frogpilot_toggles.relaxed_jerk_danger,
           frogpilot_toggles.relaxed_jerk_speed,
           frogpilot_toggles.custom_personalities,
           controlsState.personality
        )
      else:
        (self.base_acceleration_jerk,
         self.base_danger_jerk,
         self.base_speed_jerk) = get_jerk_factor(
           frogpilot_toggles.aggressive_jerk_deceleration,
           frogpilot_toggles.aggressive_jerk_danger,
           frogpilot_toggles.aggressive_jerk_speed_decrease,
           frogpilot_toggles.standard_jerk_deceleration,
           frogpilot_toggles.standard_jerk_danger,
           frogpilot_toggles.standard_jerk_speed_decrease,
           frogpilot_toggles.relaxed_jerk_deceleration,
           frogpilot_toggles.relaxed_jerk_danger,
           frogpilot_toggles.relaxed_jerk_speed_decrease,
           frogpilot_toggles.custom_personalities,
           controlsState.personality
        )

      self.personality_t_follow = get_T_FOLLOW(
        frogpilot_toggles.aggressive_follow,
        frogpilot_toggles.standard_follow,
        frogpilot_toggles.relaxed_follow,
        frogpilot_toggles.custom_personalities,
        controlsState.personality
      )

    self.t_follow = self.personality_t_follow
    self.acceleration_jerk = self.base_acceleration_jerk
    self.danger_jerk = self.base_danger_jerk
    self.speed_jerk = self.base_speed_jerk

    # 2) Determine if a lead is being tracked
    self.following_lead = self.frogpilot_planner.tracking_lead \
                          and lead_distance < (self.t_follow + 1.0) * v_ego

    # 3) If lead is present and user wants catchup logic, do it
    if self.frogpilot_planner.tracking_lead:
      lead_accel_est = self.frogpilot_planner.lead_one.aLeadK
      if frogpilot_toggles.enableCatchUp:
        self.update_follow_values(lead_distance, v_ego, v_lead, lead_accel_est, frogpilot_toggles)
      else:
        # If catch-up is disabled, skip messing with t_follow
        self.acceleration_override = None  # no forced override
      self.desired_follow_distance = int(desired_follow_distance(v_ego, v_lead, self.t_follow))
    else:
      self.desired_follow_distance = 0

  def update_follow_values(self, lead_distance, v_ego, v_lead, lead_accel, frogpilot_toggles):
    """
    Old "low-speed catch-up" logic.
    If you'd like to reduce how often it triggers, you can raise LOW_SPEED_THRESHOLD
    or tighten conditions below.
    """
    global DECAY_RATE

    # By default, decay t_follow from any prior short gap back to personality baseline
    self.t_follow = (1.0 - DECAY_RATE) * self.t_follow + DECAY_RATE * self.personality_t_follow
    self.acceleration_override = None

    if v_ego < LOW_SPEED_THRESHOLD and v_lead > v_ego:
      alpha = np.clip(v_ego / LOW_SPEED_THRESHOLD, 0., 1.)
      reduced_t_follow = (1. - alpha) * MIN_T_FOLLOW_AT_LOW_SPEED + alpha * self.personality_t_follow
      self.t_follow = min(self.t_follow, reduced_t_follow)

      if lead_accel > LEAD_ACCEL_THRESHOLD:
        override_accel = ACCEL_OVERSHOOT_RATIO * lead_accel
        self.acceleration_override = override_accel
        self.acceleration_jerk *= 1.2
