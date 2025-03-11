import math
from typing import Any

from cereal import car
from openpilot.common.numpy_fast import clip
from openpilot.common.params import Params
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.car.hyundai.values import HyundaiFlags, CarControllerParams
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc

LongCtrlState = car.CarControl.Actuators.LongControlState

class JerkOutput:
  def __init__(self, jerk_upper_limit, jerk_lower_limit, cb_upper, cb_lower):
    self.jerk_upper_limit = jerk_upper_limit
    self.jerk_lower_limit = jerk_lower_limit
    self.cb_upper = cb_upper
    self.cb_lower = cb_lower

class HKGLongitudinalTuning:
  def __init__(self, CP) -> None:
    self.CP = CP
    self._setup_controllers()
    self._init_state()

  def _setup_controllers(self) -> None:
    self.mpc = LongitudinalMpc(mode='acc')
    self.long_control = LongControl(self.CP)
    self.DT_CTRL = DT_CTRL
    self.params = Params()
    self.hkg_tuning = self.params.get_bool('HKGtuning')
    self.has_radar = self.params.get_bool("HyundaiRadarTracks")

  def _init_state(self) -> None:
    self.last_accel = 0.0
    self.brake_ramp = 0.0
    self.accel_last = 0.0
    self.using_e2e = False
    self.accel_raw = 0.0
    self.accel_last_jerk = 0.0
    self.jerk = 0.0
    self.jerk_count = 0.0
    self.jerk_upper_limit = 0.0
    self.jerk_lower_limit = 0.0
    self.cb_upper = 0.0
    self.cb_lower = 0.0

  def make_jerk(self, CS, accel, actuators):
    """Calculate the instantaneous jerk and update jerk limits."""
    state = getattr(actuators, "longControlState", LongCtrlState.pid)
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.jerk_upper_limit = 0.0
      self.jerk_lower_limit = 0.0
      self.cb_upper = self.cb_lower = 0.0
      self.accel_last_jerk = 0.0
      return 0.0

    current_accel = clip(actuators.accel, CarControllerParams.ACCEL_MIN, CarControllerParams.ACCEL_MAX)
    self.jerk = (current_accel - self.accel_last_jerk) / self.DT_CTRL
    self.accel_last_jerk = current_accel

    # Start with a base jerk limit
    jerk_max = 5.0
    v_error = abs(CS.out.vEgo - CS.out.cruiseState.speed)

    if self.CP.flags & HyundaiFlags.CANFD.value:
      # Slight reduction in max jerk as v_error decreases, done smoothly
      # Example continuous function with mild shaping
      jerk_reduction = 1.0 - (0.7 / (v_error + 1.0))  # saturates as v_error grows
      jerk_reduction = clip(jerk_reduction, 0.3, 1.0)
      jerk_max *= jerk_reduction

      self.jerk_upper_limit = min(max(0.5, self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(1.0, -self.jerk * 4.0), jerk_max)
      self.cb_upper = self.cb_lower = 0.0

    else:
      # Calculate a continuous error factor
      # Example: logistic from 0.0 -> 1.0 around v_error=2.5
      error_factor = 1.0 / (1.0 + math.exp(-1.8*(v_error - 2.5)))
      error_factor = clip(error_factor, 0.0, 1.0)

      self.jerk_upper_limit = min(max(0.5, self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(1.0, -self.jerk * 2.0), jerk_max)

      # Acceleration-based continuous factor
      accel_abs = abs(accel)
      accel_factor = 0.2 - 0.1*(accel_abs/(accel_abs+1.0))  # from ~0.2 at 0 accel -> 0.1 at large accel

      # Weighted blend based on sign of accel
      # Ranges from 0..1
      accel_blend = 0.5 * (1.0 + accel / (accel_abs + 0.1))

      # We'll keep these "comfort band" base values but feed them continuous factors
      cb_upper_pos = 0.8 * error_factor + accel * accel_factor
      cb_upper_neg = 1.0 * error_factor + accel * accel_factor
      cb_lower_pos = 0.6 * error_factor + accel * accel_factor
      cb_lower_neg = 0.8 * error_factor + accel * accel_factor

      # Weighted final
      self.cb_upper = clip(accel_blend * cb_upper_pos + (1.0 - accel_blend) * cb_upper_neg, 0.0, 1.2)
      self.cb_lower = clip(accel_blend * cb_lower_pos + (1.0 - accel_blend) * cb_lower_neg, 0.0, 1.2)

    return self.jerk

  def handle_cruise_cancel(self, CS):
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last = 0.0
      self.brake_ramp = 0.0
      return True
    return False

  def calculate_emergency_factor(self, CS):
    """
    Continuous factor for how urgently we need to brake.
    Combines deltaV, distance, and TTC with no discrete 'new lead' logic.
    """
    emergency_factor = 0.0
    try:
      if hasattr(CS.out, 'vEgo') and hasattr(CS.out, 'leadOne'):
        lead = CS.out.leadOne
        if lead.status and lead.dRel > 0.1:
          delta_v = max(0.0, CS.out.vEgo - lead.vLead)
          ttc = lead.dRel / max(delta_v, 0.01)

          # Example: continuous logistic function for TTC
          # More negative (small) TTC => bigger factor
          ttc_factor = clip(1.0 / (1.0 + math.exp((ttc - 3.0) * 1.2)), 0.0, 1.0)

          # Another continuous factor for deltaV
          # More deltaV => bigger factor
          dv_factor = clip(delta_v * delta_v / (delta_v * delta_v + 9.0), 0.0, 1.0)

          # Weighted combination
          combined_factor = ttc_factor * (0.6 + 0.4 * dv_factor) * 1.4

          # Distance-based factor
          dist_factor = clip(1.0 - (lead.dRel / (CS.out.vEgo * 1.8 + 4.0)), 0.0, 1.0)

          # Delta_v activation
          delta_v_activation = delta_v / (delta_v + 0.1)

          # Final emergency factor with no discrete step
          emergency_factor = max(combined_factor, dist_factor * 0.9) * delta_v_activation
    except:
      emergency_factor = 0.0

    return emergency_factor

  def calculate_limited_accel(self, accel, actuators, CS):
    if self.handle_cruise_cancel(CS):
      return accel

    # Calculate jerk, for consistent jerk-limiting logic
    self.make_jerk(CS, accel, actuators)

    # We'll handle transitions from current accel to new accel
    accel_delta = accel - self.accel_last

    # Continuous measure of urgency
    emergency_factor = self.calculate_emergency_factor(CS)

    # If we are closing on a lead (vEgo > vLead), add a continuous "proactive" braking scale
    if hasattr(CS.out, 'leadOne') and CS.out.leadOne.status and CS.out.vEgo > CS.out.leadOne.vLead:
      closing_speed = max(CS.out.vEgo - CS.out.leadOne.vLead, 0.1)
      ttc = CS.out.leadOne.dRel / closing_speed
      # Example logistic for TTC
      ttc_urgency = clip(4.0 / (ttc + 0.3) - 0.7, 0.0, 1.0)
      speed_urgency = clip(closing_speed * 0.15, 0.0, 1.0)
      anticipation_factor = 1.0 + ttc_urgency * speed_urgency * 0.8

      if accel < 0:
        accel *= anticipation_factor
        accel_delta = accel - self.accel_last

    # We blend negative and positive accel deltas
    # brake_blend goes from ~1.0 if accel < 0 to ~0.0 if accel > 0
    brake_blend = 0.5 - 0.5 * accel / (abs(accel) + 0.2)

    # If we switch from non-negative to negative accel, jump-start braking
    if accel < 0 and self.accel_last >= 0:
      # No discrete "new lead" condition—always scale by emergency_factor
      initial_brake_level = clip(emergency_factor * 0.7, 0.0, 0.7)
      self.accel_last = -initial_brake_level
      accel_delta = accel - self.accel_last
      self.brake_ramp = clip(emergency_factor * 0.8, 0.3, 0.8)

    # ----- Enhanced Braking Logic -----
    brake_ratio = clip(abs(accel / CarControllerParams.ACCEL_MIN), 0.0, 1.0)
    # Simple continuous function for "aggressiveness"
    brake_aggressiveness = brake_ratio  # can refine if needed

    # Replace old discrete breakpoints with a linear function (or mild polynomial):
    # For low-speed ramp:
    low_speed_ramp = 0.7 + 1.1 * brake_aggressiveness  # from 0.7..1.8 as ratio goes 0..1
    # For high-speed ramp:
    high_speed_ramp = 0.5 + 1.1 * brake_aggressiveness  # from 0.5..1.6

    # speed_blend is already continuous
    speed_blend = (CS.out.vEgo**2) / (CS.out.vEgo**2 + 20.0)
    braking_ramp_rate = low_speed_ramp * (1.0 - speed_blend) + high_speed_ramp * speed_blend

    # Instead of discrete breakpoints, use a continuous scale for emergency
    emergency_scale = 1.0 + 1.2 * emergency_factor
    emergency_scale = clip(emergency_scale, 1.0, 2.2)  # saturate at ~2.2

    braking_ramp_rate *= emergency_scale

    # If we haven't just switched from accel to brake, modest ramp
    if self.accel_last >= 0:
      transition_factor = 1.0 + 0.3 * emergency_factor
      braking_ramp_rate *= transition_factor

    # Ramp up from 0..1 quickly if needed
    self.brake_ramp = min(1.0, self.brake_ramp + (braking_ramp_rate * self.DT_CTRL))

    # A smaller smoothing factor in emergencies
    base_brake_smooth = 0.85
    emergency_response = 0.5 + 0.5 * emergency_factor
    brake_smooth_factor = base_brake_smooth - 0.45 * (abs(accel) / (abs(accel) + 0.4))
    brake_smooth_factor *= (1.0 - 0.5 * emergency_response)

    # Apply to the negative delta
    brake_accel_delta = accel_delta * (brake_smooth_factor * self.brake_ramp)

    # ----- Positive Accel Logic -----
    # Example continuous function for base ramp rate vs vEgo
    base_ramp_rate = 1.0 + 1.0 * math.exp(-0.3 * CS.out.vEgo)  # ~2.0 at 0 m/s, ~1.17 by 6 m/s
    # Keep a small "start boost" if we are near 0 and going positive
    start_boost = 0.7 * max(0.0, 1.0 - self.accel_last * 2.0)
    # Continuous function for big positive accel
    accel_boost = (accel**2) * 0.15
    accel_ramp_rate = base_ramp_rate + start_boost + accel_boost

    accel_accel_delta = clip(accel - self.accel_last, -10.0, accel_ramp_rate * self.DT_CTRL)

    # ----- Jerk Limits -----
    # We already have jerk_upper_limit (self.jerk_upper_limit) and jerk_lower_limit (self.jerk_lower_limit)
    # Scale the negative jerk limit by emergency_factor
    emergency_jerk_scale = 1.0 + 2.0 * emergency_factor
    emergency_jerk_scale = clip(emergency_jerk_scale, 1.0, 3.0)
    jerk_lower = self.jerk_lower_limit * emergency_jerk_scale
    jerk_upper = self.jerk_upper_limit

    # Blend negative/positive
    final_delta = brake_blend * brake_accel_delta + (1.0 - brake_blend) * accel_accel_delta
    # Apply jerk limit
    final_delta = clip(final_delta, -jerk_lower * self.DT_CTRL, jerk_upper * self.DT_CTRL)

    accel_out = self.accel_last + final_delta
    self.accel_last = accel_out
    return accel_out

  def calculate_accel(self, accel, actuators, CS, frogpilot_toggles):
    if self.handle_cruise_cancel(CS):
      return 0.0
    accel = self.calculate_limited_accel(accel, actuators, CS)
    # Final clip to ensure we don't exceed hardware-limited min
    return clip(accel,
                CarControllerParams.ACCEL_MIN,
                min(frogpilot_toggles.max_desired_acceleration, CarControllerParams.ACCEL_MAX))

  def apply_tune(self, CP: Any) -> None:
    CP.vEgoStopping = 0.2
    CP.vEgoStarting = 0.05
    CP.stoppingDecelRate = 0.01
    CP.startAccel = 3.5
    CP.startingState = True

  def get_jerk(self) -> JerkOutput:
    return JerkOutput(
      self.jerk_upper_limit,
      self.jerk_lower_limit,
      self.cb_upper,
      self.cb_lower,
    )

  def calculate_and_get_jerk(self, CS, accel, actuators):
    if self.hkg_tuning:
      self.make_jerk(CS, accel, actuators)
      return self.get_jerk()
    else:
      normal_jerk = self.calculate_normal_jerk(actuators.longControlState)
      return JerkOutput(normal_jerk, normal_jerk, 0.0, 0.0)

  def calculate_normal_jerk(self, long_control_state):
    return 3.0 if long_control_state == LongCtrlState.pid else 1.0


class HKGLongitudinalController:
  def __init__(self, CP):
    self.CP = CP
    self.tuning = HKGLongitudinalTuning(CP) if Params().get_bool("HKGtuning") else None
    self.jerk = None

  def apply_tune(self, CP):
    if self.tuning:
      self.tuning.apply_tune(CP)

  def calculate_normal_jerk(self, long_control_state):
    return 3.0 if long_control_state == LongCtrlState.pid else 1.0
