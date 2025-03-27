#!/usr/bin/env python3
"""
Manages following distance and jerk factor logic in FrogPilot, integrating both traffic-mode and
personality-based approaches. Provides specialized 'assertive-from-stop' behavior at low speeds.
"""

import numpy as np
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import (
    COMFORT_BRAKE, STOP_DISTANCE, desired_follow_distance, get_jerk_factor, get_T_FOLLOW
)
from openpilot.selfdrive.frogpilot.frogpilot_variables import CITY_SPEED_LIMIT

# Breakpoints for traffic-mode behavior
TRAFFIC_MODE_BP = [0., CITY_SPEED_LIMIT]

# Low-speed 'assertive-from-stop' constants
LOW_SPEED_THRESHOLD = 11.4       # Speed threshold in m/s (~25 mph)
MIN_T_FOLLOW_AT_LOW_SPEED = 0.7  # Reduced minimum time-gap for low speeds
LEAD_ACCEL_THRESHOLD = 0.2       # Lead acceleration threshold (m/s^2)
ACCEL_OVERSHOOT_RATIO = 0.9      # Fraction of lead's accel to apply
DECAY_RATE = 0.1                 # Rate at which t_follow decays to baseline

class FrogPilotFollowing:
    """
    Implements logic for determining desired following distances and setting
    jerk parameters (acceleration, speed, 'danger') in FrogPilot. This class
    also handles specialized low-speed following behavior.
    """

    def __init__(self, FrogPilotPlanner):
        """
        Initializes the FrogPilotFollowing instance with relevant planners and
        sets up variables tracking lead presence, jerk factors, and time-gap.
        """
        self.frogpilot_planner = FrogPilotPlanner

        # Track lead states
        self.following_lead = False
        self.slower_lead = False

        # Jerk/follow parameters
        self.acceleration_jerk = 0
        self.base_acceleration_jerk = 0
        self.base_speed_jerk = 0
        self.base_danger_jerk = 0
        self.danger_jerk = 0
        self.speed_jerk = 0

        self.desired_follow_distance = 0
        self.t_follow = 0
        self.personality_t_follow = 0

        self.acceleration_override = None

    def update(self, aEgo, controlsState, frogpilotCarState,
               lead_distance, v_ego, v_lead, frogpilot_toggles):
        """
        Updates following parameters each control loop:
          1. Determines baseline jerk factors and time-gap from traffic-mode or personality.
          2. Checks lead presence and applies special logic at lower speeds.
          3. Calculates final desired follow distance based on current state.
        """

        # Determine baseline jerk/time-gap from traffic-mode or personality-based logic
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

        # Set initial parameters
        self.t_follow = self.personality_t_follow
        self.acceleration_jerk = self.base_acceleration_jerk
        self.danger_jerk = self.base_danger_jerk
        self.speed_jerk = self.base_speed_jerk

        # Assess lead presence and update following variables
        self.following_lead = (
            self.frogpilot_planner.tracking_lead
            and lead_distance < (self.t_follow + 1.) * v_ego
        )

        if self.frogpilot_planner.tracking_lead:
            lead_accel_est = self.frogpilot_planner.lead_one.aLeadK
            self.update_follow_values(lead_distance, v_ego, v_lead, lead_accel_est, frogpilot_toggles)
            self.desired_follow_distance = int(desired_follow_distance(v_ego, v_lead, self.t_follow))
        else:
            self.desired_follow_distance = 0

    def update_follow_values(self, lead_distance, v_ego, v_lead, lead_accel, frogpilot_toggles):
        """
        Refines follow distance and jerk parameters for low-speed scenarios when the lead
        may be accelerating away. Gradually returns to baseline values otherwise.
        """
        # Gradually revert t_follow to baseline
        self.t_follow = (1.0 - DECAY_RATE) * self.t_follow + DECAY_RATE * self.personality_t_follow
        self.acceleration_override = None

        if v_ego < LOW_SPEED_THRESHOLD and v_lead > v_ego:
            alpha = np.clip(v_ego / LOW_SPEED_THRESHOLD, 0., 1.)
            reduced_t_follow = ((1. - alpha) * MIN_T_FOLLOW_AT_LOW_SPEED
                                + alpha * self.personality_t_follow)
            self.t_follow = min(self.t_follow, reduced_t_follow)

            if lead_accel > LEAD_ACCEL_THRESHOLD:
                override_accel = ACCEL_OVERSHOOT_RATIO * lead_accel
                self.acceleration_override = override_accel
                # Slightly increase acceleration jerk if lead is pulling away quickly
                self.acceleration_jerk *= 1.2
