#!/usr/bin/env python3
import numpy as np

from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import COMFORT_BRAKE, STOP_DISTANCE, desired_follow_distance, get_jerk_factor, get_T_FOLLOW

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
    if frogpilot_toggles.human_following and v_lead > v_ego:
        distance_factor = max(lead_distance - (v_ego * self.t_follow), 1)
        standstill_offset = max(STOP_DISTANCE - v_ego, 1)
        speed_diff = max(v_lead - v_ego, 0.1)
        acceleration_offset = np.clip(speed_diff * standstill_offset - COMFORT_BRAKE, 1, distance_factor)

        self.acceleration_jerk /= acceleration_offset
        self.speed_jerk /= acceleration_offset
        self.t_follow /= acceleration_offset

    if (frogpilot_toggles.conditional_slower_lead or frogpilot_toggles.human_following) and v_lead < v_ego:
        distance_factor = max(lead_distance - (v_lead * self.t_follow), 1)
        closing_speed = max(v_ego - v_lead, 0.1)
        ttc = lead_distance / closing_speed

        # Progressive reaction curve for time-to-collision
        ttc_emergency = np.clip(1.4 - (ttc / 3.5), 0.0, 1.0)
        lead_speed_factor = 1.0 + 2.5 / (1.0 + v_lead * v_lead * 0.8)
        far_lead_offset = lead_speed_factor + ttc_emergency * 4.5

        speed_blend = v_lead / (v_lead + 1.5)
        ego_term = v_ego * (1.3 + 1.4 * ttc_emergency)
        relative_term = min(closing_speed, v_lead) * 1.2
        braking_term = (1.0 - speed_blend) * ego_term + speed_blend * relative_term

        # Dynamic emergency scaling based on closing dynamics
        high_closing_factor = np.clip(closing_speed / 5.0, 1.0, 1.3)
        critical_ttc_factor = np.clip(2.0 / (ttc + 0.5), 1.0, 1.5)
        emergency_scaling = high_closing_factor * critical_ttc_factor - 1.0
        braking_term *= (1.0 + max(0.0, emergency_scaling) * 0.5)

        braking_offset = np.clip(
            braking_term * far_lead_offset - COMFORT_BRAKE,
            1,
            distance_factor
        )

        self.slower_lead = braking_offset / far_lead_offset > 1

        if frogpilot_toggles.human_following:
            base_anticipation = np.clip(closing_speed * 0.04, 0.0, 0.35)
            ttc_scaling = np.clip(1.5 / (ttc + 0.5), 1.0, 1.5)
            anticipation_factor = base_anticipation * ttc_scaling

            self.t_follow *= (1.0 + anticipation_factor)