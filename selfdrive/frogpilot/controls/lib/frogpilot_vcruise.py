import numpy as np
from openpilot.common.realtime import DT_MDL   # model loop time constant (~0.05s)
from openpilot.common.conversions import Conversions as CV
from openpilot.selfdrive.frogpilot.frogpilot_variables import CRUISING_SPEED, PLANNER_TIME, params_memory
from openpilot.selfdrive.frogpilot.controls.lib.map_turn_speed_controller import MapTurnSpeedController
from openpilot.selfdrive.frogpilot.controls.lib.speed_limit_controller import SpeedLimitController
from openpilot.selfdrive.controls.lib.drive_helpers import V_CRUISE_UNSET

# Constants for speed planning
TARGET_LAT_A = 3.02  # lateral acceleration threshold for turn speed calculation

class FrogPilotVCruise:
  def __init__(self, FrogPilotPlanner):
    self.frogpilot_planner = FrogPilotPlanner
    # Initialize sub-controllers
    self.mtsc = MapTurnSpeedController()    # Map Turn Speed Controller
    self.slc = SpeedLimitController()       # Speed Limit Controller

    # State variables
    self.forcing_stop = False
    self.override_force_stop = False
    self.override_slc = False
    self.force_stop_timer = 0.0
    self.mtsc_target = 0.0
    self.overridden_speed = 0.0
    self.override_force_stop_timer = 0.0
    self.slc_offset = 0.0
    self.slc_target = 0.0
    self.speed_limit_timer = 0.0
    self.tracked_model_length = 0.0
    self.vtsc_target = 0.0

    # New ramp state variables for SLC
    self.slc_ramp_active = False
    self.slc_ramp_start_speed = 0.0
    self.slc_ramp_end_speed = 0.0
    self.slc_ramp_speed = 0.0

  def update(self, carControl, carState, controlsState, frogpilotCarControl, frogpilotCarState, frogpilotNavigation, v_cruise, v_ego, frogpilot_toggles, sm):
    # Safely fetch toggles so we don't crash if any attribute is missing
    force_stops = getattr(frogpilot_toggles, 'force_stops', False)
    force_standstill = getattr(frogpilot_toggles, 'force_standstill', False)
    map_turn_speed_controller = getattr(frogpilot_toggles, 'map_turn_speed_controller', False)
    mtsc_curvature_check = getattr(frogpilot_toggles, 'mtsc_curvature_check', False)
    speed_limit_controller = getattr(frogpilot_toggles, 'speed_limit_controller', False)

    # CRITICAL FIX: Handle case where car won't accelerate
    # Enable a system for detecting if we're stuck below our target speed
    allow_acceleration_boost = v_cruise > v_ego + 2.0 and not (self.forcing_stop or self.override_force_stop)

    # ---- Force Stop (red light/stop sign logic) ----
    force_stop = force_stops and self.frogpilot_planner.cem.stop_light_detected and controlsState.enabled
    force_stop &= self.frogpilot_planner.model_length < 100
    force_stop &= self.override_force_stop_timer <= 0
    self.force_stop_timer = (self.force_stop_timer + DT_MDL) if force_stop else 0.0
    force_stop_enabled = self.force_stop_timer >= 1.0

    # Conditions to override (cancel) forced stop (e.g., user input)
    self.override_force_stop |= (not force_standstill and carState.standstill and self.frogpilot_planner.tracking_lead)
    self.override_force_stop |= carState.gasPressed or frogpilotCarControl.accelPressed
    self.override_force_stop &= force_stop_enabled
    if self.override_force_stop:
      self.override_force_stop_timer = 10.0  # maintain override for a short duration
    elif self.override_force_stop_timer > 0:
      self.override_force_stop_timer -= DT_MDL

    # Synchronize cruise speeds between cluster (display) and control
    v_cruise_cluster = max(controlsState.vCruiseCluster * CV.KPH_TO_MS, v_cruise)
    v_cruise_diff = v_cruise_cluster - v_cruise
    v_ego_cluster = max(carState.vEgoCluster, v_ego)
    v_ego_diff = v_ego_cluster - v_ego

    # ---- VCRUISE ADJUSTMENTS SECTION ----

    # Get targets from various controllers
    mtsc_target = self.get_mtsc_target(carControl, carState, map_turn_speed_controller, mtsc_curvature_check, v_cruise, v_ego, frogpilot_toggles)
    slc_target = self.get_slc_target(carControl, carState, controlsState, frogpilotCarControl, frogpilotNavigation, speed_limit_controller, v_cruise, v_cruise_cluster, v_ego, v_ego_cluster, frogpilot_toggles)
    vtsc_target = self.get_vtsc_target(carControl, frogpilot_toggles, v_cruise, v_ego)

    # Combine targets to get final cruise speed
    if speed_limit_controller:
      # When SLC is active, include SLC (or override) in the targets list
      targets = [
        mtsc_target,
        slc_target,
        vtsc_target
      ]
    else:
      # SLC not active, only consider turn controllers
      targets = [mtsc_target, vtsc_target]

    # CRITICAL FIX: Don't allow targets to constantly reduce speed when they shouldn't
    if allow_acceleration_boost:
      # If we need to accelerate because we're below cruise speed,
      # filter out any targets that would be limiting us from accelerating
      # unless they are explicitly required (like speed limits that should be enforced)
      valid_targets = []
      for target in targets:
        # Only consider targets that are active (not default v_cruise)
        # and significantly below current set speed (at least 1 m/s lower)
        if abs(target - v_cruise) > 0.5 and target < v_cruise - 0.5:
          valid_targets.append(target)
        else:
          valid_targets.append(v_cruise)  # Use original v_cruise if the target isn't actually limiting
      targets = valid_targets

    # Pick the minimum target that's above the minimum cruising speed
    filtered_targets = [target for target in targets if target > CRUISING_SPEED]
    if filtered_targets:
      v_cruise = float(min(filtered_targets))
    # Account for any difference between cluster and actual cruise (smooth transition)
    v_cruise += v_cruise_diff

    # Update the planner's cruise speed for output
    self.frogpilot_planner.v_cruise = v_cruise

    # Always return a valid float, never None
    return float(v_cruise)

  # Helper methods to modularize the target calculations
  def get_mtsc_target(self, carControl, carState, map_turn_speed_controller, mtsc_curvature_check, v_cruise, v_ego, frogpilot_toggles):
    if map_turn_speed_controller and v_ego > CRUISING_SPEED and carControl.longActive:
        mtsc_active = self.mtsc_target < v_cruise
        self.mtsc_target = clip(
            self.mtsc.target_speed(v_ego, getattr(carState, 'aEgo', 0.0), frogpilot_toggles),
            CRUISING_SPEED, v_cruise
        )

        curve_detected = (1 / self.frogpilot_planner.road_curvature) ** 0.5 < v_ego
        if curve_detected and mtsc_active:
            self.mtsc_target = self.frogpilot_planner.v_cruise
        elif not curve_detected and mtsc_curvature_check:
            self.mtsc_target = v_cruise

        if self.mtsc_target == CRUISING_SPEED:
            self.mtsc_target = v_cruise
    else:
        self.mtsc_target = v_cruise if v_cruise != V_CRUISE_UNSET else 0

    return self.mtsc_target

  def get_slc_target(self, carControl, carState, controlsState, frogpilotCarControl, frogpilotNavigation, speed_limit_controller, v_cruise, v_cruise_cluster, v_ego, v_ego_cluster, frogpilot_toggles):
    # If we need acceleration and are under SLC speed + offset, prevent SLC from limiting acceleration
    need_accel = v_cruise > v_ego + 2.0

    if speed_limit_controller or frogpilot_toggles.show_speed_limits:
      # Update the SpeedLimitController with current data
      self.slc.update(frogpilotCarState.dashboardSpeedLimit, controlsState.enabled,
                      frogpilotNavigation.navigationSpeedLimit, v_cruise_cluster, v_ego, frogpilot_toggles)

      if self.slc.speed_limit_changed:
        # Handle speed limit changes (acceptance logic)
        self.handle_speed_limit_change(carControl, controlsState, frogpilotCarControl, v_cruise, frogpilot_toggles)
      elif self.slc_target == 0:
        # Initialize if no previous speed limit was set
        self.initialize_slc_target(carControl, controlsState, v_cruise, frogpilot_toggles)
      else:
        # No change in speed limit; reset confirmation timer
        self.speed_limit_timer = 0.0

      if speed_limit_controller:
        # Determine if the speed limit should be overridden
        self.handle_slc_override(carState, controlsState, v_cruise_cluster, v_ego_cluster, frogpilot_toggles)

        # Get offset for the current speed limit
        self.slc_offset = self.slc.get_offset(self.slc_target, frogpilot_toggles)

        # Handle ramping logic
        if self.slc_ramp_active:
          self.update_slc_ramp(frogpilot_toggles)
        else:
          # Not ramping, use the final target speed directly
          self.slc_ramp_speed = self.slc_target + self.slc_offset

        # CRITICAL FIX: Don't let SLC prevent acceleration when we're well below the limit
        if need_accel and v_ego < (self.slc_target + self.slc_offset - 1.0):
          return max(v_cruise, self.overridden_speed, self.slc_ramp_speed) - v_ego_diff
        else:
          return max(self.overridden_speed, self.slc_ramp_speed) - v_ego_diff
      else:
        # Speed Limit Controller is disabled; reset SLC-related outputs
        self.reset_slc_outputs()
    else:
      # Neither SLC nor speed limits display is enabled
      self.reset_slc_outputs()

    return v_cruise  # Default to current cruise speed if SLC inactive

  def get_vtsc_target(self, carControl, frogpilot_toggles, v_cruise, v_ego):
    if frogpilot_toggles.vision_turn_speed_controller and carControl.longActive and self.frogpilot_planner.road_curvature_detected:
      # Compute desired turn speed based on vision curvature
      curvature = abs(self.frogpilot_planner.road_curvature)
      if curvature > 0:
        self.vtsc_target = ((TARGET_LAT_A * frogpilot_toggles.turn_aggressiveness) / (curvature * frogpilot_toggles.curve_sensitivity)) ** 0.5
      else:
        self.vtsc_target = v_cruise  # no curvature, no change
    else:
      self.vtsc_target = v_cruise

    # Clip VTSC target between a minimum safe speed and current cruise
    return np.clip(self.vtsc_target, CRUISING_SPEED, v_cruise)

  # Helper methods for SLC management
  def handle_speed_limit_change(self, carControl, controlsState, frogpilotCarControl, v_cruise, frogpilot_toggles):
    desired_slc_target = self.slc.desired_speed_limit  # posted speed limit (m/s) if a change is detected, else 0

    # Determine if user accepted or denied new limit (for confirmation mode)
    speed_limit_accepted = (frogpilotCarControl.accelPressed and carControl.longActive) or params_memory.get_bool("SpeedLimitAccepted")
    speed_limit_denied = (frogpilotCarControl.decelPressed and carControl.longActive) or (self.speed_limit_timer >= 30)

    if speed_limit_accepted:
      # User confirmed the new speed limit
      self.slc_target = desired_slc_target
      params_memory.remove("SpeedLimitAccepted")
      # Start ramp towards new speed limit
      self.start_slc_ramp(controlsState, carControl, desired_slc_target, v_cruise, frogpilot_toggles)
    elif desired_slc_target < self.slc_target and not frogpilot_toggles.speed_limit_confirmation_lower:
      # Automatically accept a lower speed limit (no confirmation needed)
      self.slc_target = desired_slc_target
      self.start_slc_ramp(controlsState, carControl, desired_slc_target, v_cruise, frogpilot_toggles)
    elif desired_slc_target > self.slc_target and not frogpilot_toggles.speed_limit_confirmation_higher:
      # Automatically accept a higher speed limit (no confirmation needed)
      self.slc_target = desired_slc_target
      self.start_slc_ramp(controlsState, carControl, desired_slc_target, v_cruise, frogpilot_toggles)
    else:
      # Awaiting confirmation or denied; start/continue timer
      self.speed_limit_timer += DT_MDL

    # Update changed flag for next cycle (stays true if not yet accepted/denied)
    self.slc.speed_limit_changed = (self.slc_target != desired_slc_target) and not speed_limit_denied

  def initialize_slc_target(self, carControl, controlsState, v_cruise, frogpilot_toggles):
    desired_slc_target = self.slc.desired_speed_limit
    self.slc_target = desired_slc_target
    self.start_slc_ramp(controlsState, carControl, desired_slc_target, v_cruise, frogpilot_toggles)

  def start_slc_ramp(self, controlsState, carControl, desired_slc_target, v_cruise, frogpilot_toggles):
    if frogpilot_toggles.speed_limit_controller and controlsState.enabled and carControl.longActive:
      self.slc_ramp_active = True
      self.slc_ramp_start_speed = v_cruise
      new_offset = self.slc.get_offset(desired_slc_target, frogpilot_toggles)
      self.slc_ramp_end_speed = desired_slc_target + new_offset
      self.slc_ramp_speed = self.slc_ramp_start_speed
    else:
      self.slc_ramp_active = False
      self.slc_ramp_speed = 0.0

  def update_slc_ramp(self, frogpilot_toggles):
    # Choose acceleration limit based on whether increasing or decreasing speed
    accel_limit = 1.5  # m/s^2 for accelerating
    decel_limit = 0.67  # m/s^2 for decelerating
    sign = 1.0 if self.slc_ramp_end_speed > self.slc_ramp_start_speed else -1.0

    # Calculate allowed change this cycle (limit to ~2 mph per cycle)
    delta_v = (accel_limit if sign > 0 else decel_limit) * DT_MDL * sign
    if abs(delta_v) > 0.9:  # cap delta to ~0.9 m/s (~2 mph)
      delta_v = 0.9 * sign

    new_speed = self.slc_ramp_speed + delta_v

    # Prevent overshooting the final target
    if sign > 0 and new_speed > self.slc_ramp_end_speed:
      new_speed = self.slc_ramp_end_speed
    if sign < 0 and new_speed < self.slc_ramp_end_speed:
      new_speed = self.slc_ramp_end_speed

    # Round the ramp speed to nearest whole mph for smooth HUD display
    current_mph = self.slc_ramp_speed * CV.MS_TO_MPH
    new_mph = new_speed * CV.MS_TO_MPH
    new_mph_round = round(new_mph)
    last_mph_round = round(current_mph)

    # Ensure we don't jump more than 2 mph from last displayed value
    if sign > 0 and new_mph_round > last_mph_round + 2:
      new_mph_round = last_mph_round + 2
    if sign < 0 and new_mph_round < last_mph_round - 2:
      new_mph_round = last_mph_round - 2

    # Update ramp speed in m/s
    self.slc_ramp_speed = new_mph_round * CV.MPH_TO_MS

    # Check if ramp has completed
    if self.slc_ramp_speed == self.slc_ramp_end_speed:
      self.slc_ramp_active = False

  def handle_slc_override(self, carState, controlsState, v_cruise_cluster, v_ego_cluster, frogpilot_toggles):
    # Determine if the speed limit should be overridden (user acceleration)
    self.override_slc = self.overridden_speed > (self.slc_target + self.slc_offset)
    self.override_slc |= carState.gasPressed and v_ego_cluster > (self.slc_target + self.slc_offset)
    self.override_slc &= controlsState.enabled

    if self.override_slc:
      # If overriding SLC, set overridden speed to either current speed or user set speed
      if frogpilot_toggles.speed_limit_controller_override_manual:
        if carState.gasPressed:
          self.overridden_speed = v_ego_cluster
        self.overridden_speed = np.clip(self.overridden_speed,
                                      self.slc_target + self.slc_offset, v_cruise_cluster)
      elif frogpilot_toggles.speed_limit_controller_override_set_speed:
        self.overridden_speed = v_cruise_cluster
      else:
        self.overridden_speed = 0.0
    else:
      # Not overriding SLC
      self.override_slc = False
      self.overridden_speed = 0.0

  def reset_slc_outputs(self):
    self.slc_offset = 0.0
    self.slc_target = 0.0
    self.slc_ramp_active = False
    self.slc_ramp_speed = 0.0
    self.overridden_speed = 0.0
