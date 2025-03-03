#!/usr/bin/env python3
import numpy as np

from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import (
  COMFORT_BRAKE, STOP_DISTANCE, desired_follow_distance, get_jerk_factor, get_T_FOLLOW
)
from openpilot.selfdrive.frogpilot.frogpilot_variables import CITY_SPEED_LIMIT

TRAFFIC_MODE_BP = [0., CITY_SPEED_LIMIT]

# -- Constants for "assertive-from-stop" logic --
LOW_SPEED_THRESHOLD = 11.4     # ~25 mph in m/s
MIN_T_FOLLOW_AT_LOW_SPEED = 0.7
LEAD_ACCEL_THRESHOLD = 0.2    # m/s^2 threshold to consider "lead is accelerating"
ACCEL_OVERSHOOT_RATIO = 0.9  # fraction of lead accel we’ll use
DECAY_RATE = 0.1              # how quickly t_follow decays back to baseline each cycle

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
    self.personality_t_follow = 0  # Baseline personality setting for t_follow

    # (Optional) If you want to store an override acceleration you can feed to your planner
    # or to the MPC, define it here. By default, set to None.
    self.acceleration_override = None

  def update(self, aEgo, controlsState, frogpilotCarState,
             lead_distance, v_ego, v_lead, frogpilot_toggles):
    """
    Main entry point each loop. It:
      1. Figures out your baseline personality-based jerk factors & t_follow
      2. Determines if a lead is present
      3. Calls update_follow_values() to do special low-speed logic
      4. Sets the final desired_follow_distance
    """
    # 1) Baseline personality or traffic-mode logic
    if frogpilotCarState.trafficModeActive:
      # Traffic Mode logic
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
      # Normal / Personality-based logic
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

    # Start each update cycle with the personality baseline
    self.t_follow = self.personality_t_follow

    # Set the jerk values based on the base personality factors
    self.acceleration_jerk = self.base_acceleration_jerk
    self.danger_jerk = self.base_danger_jerk
    self.speed_jerk = self.base_speed_jerk

    # 2) Determine if a lead is being tracked
    self.following_lead = self.frogpilot_planner.tracking_lead \
                          and lead_distance < (self.t_follow + 1.) * v_ego

    # 3) If lead is present, do the special follow logic
    if self.frogpilot_planner.tracking_lead:
      # Get the Kalman-filtered lead acceleration directly
      lead_accel_est = self.frogpilot_planner.lead_one.aLeadK

      # Pass it into update_follow_values
      self.update_follow_values(lead_distance, v_ego, v_lead, lead_accel_est, frogpilot_toggles)

      # 4) Finally, compute the desired follow distance from t_follow
      self.desired_follow_distance = int(desired_follow_distance(v_ego, v_lead, self.t_follow))
    else:
      self.desired_follow_distance = 0

  def update_follow_values(self, lead_distance, v_ego, v_lead, lead_accel, frogpilot_toggles):
    """
    Adjust t_follow for a more assertive launch from low speed.
    If the lead is actively accelerating, we reduce follow gap and/or
    override acceleration to "catch up" in a humanlike way.
    """

    # By default, decay t_follow back to personality baseline
    self.t_follow = (1.0 - DECAY_RATE) * self.t_follow + DECAY_RATE * self.personality_t_follow

    # Reset override each cycle by default; we'll set it if conditions apply
    self.acceleration_override = None

    # If we are below LOW_SPEED_THRESHOLD and the lead is pulling away, reduce t_follow
    if v_ego < LOW_SPEED_THRESHOLD:
      # Check if lead is faster than ego
      if v_lead > v_ego:
        # 1) Shrink t_follow linearly from MIN_T_FOLLOW_AT_LOW_SPEED up to baseline
        alpha = np.clip(v_ego / LOW_SPEED_THRESHOLD, 0., 1.)
        reduced_t_follow = (1. - alpha) * MIN_T_FOLLOW_AT_LOW_SPEED + alpha * self.personality_t_follow
        self.t_follow = min(self.t_follow, reduced_t_follow)

        # 2) If the lead acceleration estimate is above threshold, let's override
        #    some of our normal acceleration logic to "catch up"
        if lead_accel > LEAD_ACCEL_THRESHOLD:
          # We'll command a fraction of the lead's observed acceleration
          override_accel = ACCEL_OVERSHOOT_RATIO * lead_accel

          # Assign it to self.acceleration_override, which you can feed into your
          # final acceleration command or MPC. The actual usage depends on how
          # your system is structured.
          self.acceleration_override = override_accel

          # Optionally: bump up jerk a bit if you want. For instance:
          self.acceleration_jerk *= 1.2

    # Else, once you're above LOW_SPEED_THRESHOLD, the standard personality-based
    # t_follow behavior applies, thanks to the decay back to self.personality_t_follow.
    # The override is None, so no special forced-acceleration.

    # Additional safety checks or logic to handle quick re-stops can go here:
    # e.g., if lead_accel < 0 or lead_distance is small, you might revert to baseline instantly.
