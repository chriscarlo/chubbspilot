import math
from typing import Any

from cereal import car
from openpilot.common.numpy_fast import clip
from openpilot.common.params import Params
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.car.hyundai.values import HyundaiFlags, CarControllerParams
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc
from openpilot.selfdrive.controls.lib.longitudinal_planner import calc_emergency_braking_factor

LongCtrlState = car.CarControl.Actuators.LongControlState


class JerkOutput:
  """
  Holds computed jerk limits and blend curves used by the controller.
  """
  def __init__(self, jerk_upper_limit, jerk_lower_limit, cb_upper, cb_lower):
    self.jerk_upper_limit = jerk_upper_limit
    self.jerk_lower_limit = jerk_lower_limit
    self.cb_upper = cb_upper
    self.cb_lower = cb_lower


class HKGLongitudinalTuning:
  """
  Encapsulates brand-specific logic (HKG) for longitudinal tuning, including
  ramp transitions, jerk calculations, and optional emergency braking factors.
  """
  def __init__(self, CP) -> None:
    self.CP = CP
    self._setup_controllers()
    self._init_state()

  def _setup_controllers(self) -> None:
    """Instantiate supporting modules and retrieve parameter toggles."""
    self.mpc = LongitudinalMpc(mode='acc')
    self.long_control = LongControl(self.CP)
    self.DT_CTRL = DT_CTRL
    self.params = Params()
    self.hkg_tuning = self.params.get_bool('HKGtuning')
    self.has_radar = self.params.get_bool("HyundaiRadarTracks")

  def _init_state(self) -> None:
    """Initialize internal state variables for the tuning logic."""
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
    """
    Calculate instantaneous jerk and update jerk limits.
    Adjusts different jerk parameters depending on CAN FD or legacy vehicle logic.
    """
    state = getattr(actuators, "longControlState", LongCtrlState.pid)
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      # Reset jerk constraints if cruise is not active.
      self.jerk_upper_limit = 0.0
      self.jerk_lower_limit = 0.0
      self.cb_upper = self.cb_lower = 0.0
      self.accel_last_jerk = 0.0
      return 0.0

    current_accel = clip(actuators.accel, CarControllerParams.ACCEL_MIN, CarControllerParams.ACCEL_MAX)
    self.jerk = (current_accel - self.accel_last_jerk) / self.DT_CTRL
    self.accel_last_jerk = current_accel

    jerk_max = 6.0
    v_error = abs(CS.out.vEgo - CS.out.cruiseState.speed)

    if self.CP.flags & HyundaiFlags.CANFD.value:
      # Slightly reduce max jerk as v_error changes.
      jerk_reduction = 1.0 - (0.7 / (v_error + 1.0))
      jerk_reduction = clip(jerk_reduction, 0.3, 1.0)
      jerk_max *= jerk_reduction

      self.jerk_upper_limit = min(max(0.5, self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(1.0, -self.jerk * 6.0), jerk_max)
      self.cb_upper = self.cb_lower = 0.0
    else:
      # Apply legacy jerk scaling for non-CAN FD vehicles.
      error_factor = 1.0 / (1.0 + math.exp(-1.8 * (v_error - 2.5)))
      error_factor = clip(error_factor, 0.0, 1.0)

      self.jerk_upper_limit = min(max(0.5, self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(1.0, -self.jerk * 6.0), jerk_max)

      accel_abs = abs(accel)
      accel_factor = 0.2 - 0.1 * (accel_abs / (accel_abs + 1.0))
      accel_blend = 0.5 * (1.0 + accel / (accel_abs + 0.1))

      cb_upper_pos = 0.8 * error_factor + accel * accel_factor
      cb_upper_neg = 1.0 * error_factor + accel * accel_factor
      cb_lower_pos = 0.6 * error_factor + accel * accel_factor
      cb_lower_neg = 0.8 * error_factor + accel * accel_factor

      self.cb_upper = clip(accel_blend * cb_upper_pos + (1.0 - accel_blend) * cb_upper_neg, 0.0, 1.2)
      self.cb_lower = clip(accel_blend * cb_lower_pos + (1.0 - accel_blend) * cb_lower_neg, 0.0, 1.2)

    return self.jerk

  def handle_cruise_cancel(self, CS):
    """
    Check if cruise is canceled or driver inputs override.
    Reset relevant state if so, and return True when cancellation occurs.
    """
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last = 0.0
      self.brake_ramp = 0.0
      return True
    return False

  def calculate_limited_accel(self, accel, actuators, CS):
    """
    Compute brand-specific acceleration limit by applying ramp transitions and jerk constraints.
    Scales negative jerk or transitions based on an emergency factor if closing speed is large.
    """
    if self.handle_cruise_cancel(CS):
      return accel

    self.make_jerk(CS, accel, actuators)
    accel_delta = accel - self.accel_last

    # Calculate an emergency factor if closing on a lead at higher speed.
    emergency_factor = 0.0
    lead = getattr(CS.out, 'leadOne', None)
    if lead and lead.status and CS.out.vEgo > lead.vLead:
      d_rel = lead.dRel
      v_lead = lead.vLead
      emergency_factor = calc_emergency_braking_factor(CS.out.vEgo, d_rel, v_lead)

    # Decide how to blend brake vs. acceleration transitions.
    brake_blend = 0.5 - 0.5 * accel / (abs(accel) + 0.2)

    # Handle sign change from positive accel to negative accel.
    if accel < 0 and self.accel_last >= 0:
      initial_brake_level = clip(emergency_factor * 0.7, 0.0, 0.7)
      self.accel_last = -initial_brake_level
      accel_delta = accel - self.accel_last
      self.brake_ramp = clip(emergency_factor * 0.8, 0.3, 0.8)

    brake_ratio = clip(abs(accel / CarControllerParams.ACCEL_MIN), 0.0, 1.0)
    brake_aggressiveness = brake_ratio

    low_speed_ramp = 0.7 + 1.1 * brake_aggressiveness
    high_speed_ramp = 0.5 + 1.1 * brake_aggressiveness

    # Blend ramp rate according to vehicle speed (higher speed -> different ramp).
    speed_blend = (CS.out.vEgo ** 2) / (CS.out.vEgo ** 2 + 20.0)
    braking_ramp_rate = low_speed_ramp * (1.0 - speed_blend) + high_speed_ramp * speed_blend

    # Scale ramp by emergency if factor is large.
    emergency_scale = 1.0 + 1.2 * emergency_factor
    emergency_scale = clip(emergency_scale, 1.0, 2.2)
    braking_ramp_rate *= emergency_scale

    # Slight bump in ramp rate if we're crossing from accel >= 0 to braking.
    if self.accel_last >= 0:
      transition_factor = 1.0 + 0.3 * emergency_factor
      braking_ramp_rate *= transition_factor

    # Increment the brake ramp up to a maximum of 1.0.
    self.brake_ramp = min(1.0, self.brake_ramp + (braking_ramp_rate * self.DT_CTRL))

    # Smooth negative acceleration transitions.
    base_brake_smooth = 0.85
    emergency_response = 0.5 + 0.5 * emergency_factor
    brake_smooth_factor = base_brake_smooth - 0.45 * (abs(accel) / (abs(accel) + 0.4))
    brake_smooth_factor *= (1.0 - 0.5 * emergency_response)
    brake_accel_delta = accel_delta * (brake_smooth_factor * self.brake_ramp)

    # Positive accel logic is simpler; includes a speed-based ramp-up and a small boost.
    base_ramp_rate = 1.0 + 1.0 * math.exp(-0.3 * CS.out.vEgo)
    start_boost = 0.7 * max(0.0, 1.0 - self.accel_last * 2.0)
    accel_boost = (accel ** 2) * 0.15
    accel_ramp_rate = base_ramp_rate + start_boost + accel_boost
    accel_accel_delta = clip(accel - self.accel_last, -10.0, accel_ramp_rate * self.DT_CTRL)

    # Jerk limits, scaled by emergency factor if needed.
    emergency_jerk_scale = 1.0 + 2.0 * emergency_factor
    emergency_jerk_scale = clip(emergency_jerk_scale, 1.0, 3.0)
    jerk_lower = self.jerk_lower_limit * emergency_jerk_scale
    jerk_upper = self.jerk_upper_limit

    # Blend final delta according to brake_blend, then clamp to jerk limits.
    final_delta = brake_blend * brake_accel_delta + (1.0 - brake_blend) * accel_accel_delta
    final_delta = clip(final_delta, -jerk_lower * self.DT_CTRL, jerk_upper * self.DT_CTRL)

    accel_out = self.accel_last + final_delta
    self.accel_last = accel_out
    return accel_out

  def calculate_accel(self, accel, actuators, CS, frogpilot_toggles):
    """
    Compute the final (clamped) acceleration for HKG vehicles, applying brand-specific
    constraints if HKG tuning is enabled.
    """
    if self.handle_cruise_cancel(CS):
      return 0.0
    accel = self.calculate_limited_accel(accel, actuators, CS)
    return clip(
      accel,
      CarControllerParams.ACCEL_MIN,
      min(frogpilot_toggles.max_desired_acceleration, CarControllerParams.ACCEL_MAX)
    )

  def apply_tune(self, CP: Any) -> None:
    """
    Set additional tuning parameters for HKGLongitudinalTuning objects.
    Adjusts lower-level thresholds and starting conditions.
    """
    CP.vEgoStopping = 0.2
    CP.vEgoStarting = 0.05
    CP.stoppingDecelRate = 0.01
    CP.startAccel = 3.5
    CP.startingState = True

  def get_jerk(self) -> JerkOutput:
    """
    Return the current jerk limits and blend curves.
    Helpful for debugging or real-time display.
    """
    return JerkOutput(
      self.jerk_upper_limit,
      self.jerk_lower_limit,
      self.cb_upper,
      self.cb_lower,
    )

  def calculate_and_get_jerk(self, CS, accel, actuators):
    """
    Convenience method that updates jerk and returns the JerkOutput object.
    If HKG tuning is disabled, uses a fallback calculation.
    """
    if self.hkg_tuning:
      self.make_jerk(CS, accel, actuators)
      return self.get_jerk()
    else:
      normal_jerk = self.calculate_normal_jerk(actuators.longControlState)
      return JerkOutput(normal_jerk, normal_jerk, 0.0, 0.0)

  def calculate_normal_jerk(self, long_control_state):
    """
    Provide a default jerk value when HKG tuning is disabled.
    In PID mode, jerk is higher (3.0); otherwise it is 1.0.
    """
    return 3.0 if long_control_state == LongCtrlState.pid else 1.0


class HKGLongitudinalController:
  """
  Higher-level controller for HKG longitudinal tuning. Conditionally
  uses HKGLongitudinalTuning based on user settings.
  """
  def __init__(self, CP):
    """Wrapper controller that optionally instantiates HKG tuning if toggled."""
    self.CP = CP
    self.tuning = HKGLongitudinalTuning(CP) if Params().get_bool("HKGtuning") else None
    self.jerk = None

  def apply_tune(self, CP):
    """Apply HKG tuning if available."""
    if self.tuning:
      self.tuning.apply_tune(CP)

  def calculate_normal_jerk(self, long_control_state):
    """
    Provide a fallback normal jerk value if the tuning object is not used.
    In PID mode, jerk is higher (3.0); otherwise it is 1.0.
    """
    return 3.0 if long_control_state == LongCtrlState.pid else 1.0
