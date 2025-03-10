import numpy as np
from cereal import car
from typing import Any
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.realtime import DT_CTRL
from openpilot.common.params import Params
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc
from openpilot.selfdrive.car.hyundai.values import CAR, HyundaiFlags, CarControllerParams
from openpilot.selfdrive.car.hyundai.chubbs.longitudinal_config import get_car_config
from openpilot.selfdrive.frogpilot.controls.lib.frogpilot_acceleration import get_max_allowed_accel

LongCtrlState = car.CarControl.Actuators.LongControlState

class JerkOutput:
  def __init__(self, jerk_upper_limit, jerk_lower_limit, cb_upper, cb_lower):
    self.jerk_upper_limit = jerk_upper_limit
    self.jerk_lower_limit = jerk_lower_limit
    self.cb_upper = cb_upper
    self.cb_lower = cb_lower

class HKGLongitudinalTuning:
  """Longitudinal tuning methodology for Hyundai vehicles."""
  def __init__(self, CP) -> None:
    self.CP = CP
    self._setup_controllers()
    self._init_state()
    self._mode_setup()
    self._setup_car_config()

  def _setup_controllers(self) -> None:
    self.mpc = LongitudinalMpc
    self.long_control = LongControl(self.CP)
    self.DT_CTRL = DT_CTRL
    self.params = Params()
    self.hkg_tuning = self.params.get_bool('HKGtuning')
    self.has_radar = self.params.get_bool("HyundaiRadarTracks")

  def _init_state(self) -> None:
    self.last_accel = 0.0
    self.brake_ramp = 0.0
    self.accel_last = 0.0
    self.accel_last_jerk = 0.0
    self.jerk = 0.0
    self.jerk_count = 0.0
    self.jerk_upper_limit = 0.0
    self.jerk_lower_limit = 0.0
    self.cb_upper = self.cb_lower = 0.0
    self.last_decel_time = 0.0
    self.min_cancel_delay = 0.1

  def _mode_setup(self) -> None:
    self.prev_mode = 'acc'  # Default mode
    self.current_mode = 'acc'
    self.mode_transition_filter = FirstOrderFilter(0.0, 0.5, DT_CTRL)  # 0.5s time constant
    self.mode_transition_timer = 0.0
    self.mode_transition_duration = 2.0  # time to transition
    self.transitioning = False

  def _setup_car_config(self) -> None:
    self.car_config = get_car_config(self.CP)

  def update_mpc_mode(self, sm):
    """Update MPC mode with transition handling."""
    new_mode = 'blended' if sm['controlsState'].experimentalMode else 'acc'

    # Detect mode change
    if new_mode != self.current_mode:
      self.prev_mode = self.current_mode
      self.transitioning = True
      self.mode_transition_timer = 0.0
      self.mode_transition_filter.x = self.accel_last

      # Update the MPC mode directly
      self.mpc.mode = new_mode
      self.current_mode = new_mode

    # Update transition state
    if self.transitioning:
      self.mode_transition_timer += DT_CTRL
      if self.mode_transition_timer >= self.mode_transition_duration:
        self.transitioning = False

  def make_jerk(self, CS, actuators):
    self.jerk_count += 1
    # Handle cancel state to prevent cruise fault
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last_jerk = 0.0
      self.jerk = 0.0
      self.jerk_count = 0.0
      self.jerk_upper_limit = 0.0
      self.jerk_lower_limit = 0.0
      self.cb_upper = self.cb_lower = 0.0
      return 0.0

    current_accel = np.clip(actuators.accel, self.car_config.accel_limits[0], self.car_config.accel_limits[1])
    self.jerk = (current_accel - self.accel_last_jerk) / self.DT_CTRL
    self.accel_last_jerk = current_accel
    jerk_max = self.car_config.jerk_limits[1]

    if self.CP.flags & HyundaiFlags.CANFD.value:
      self.jerk_upper_limit = min(max(self.car_config.jerk_limits[0], self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(self.car_config.jerk_limits[0], -self.jerk * 4.0), jerk_max)
      self.cb_upper = self.cb_lower = 0.0
    else:
      self.jerk_upper_limit = min(max(self.car_config.jerk_limits[0], self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(self.car_config.jerk_limits[0], -self.jerk * 2.0), jerk_max)
      if self.CP.radarUnavailable:
        self.cb_upper = self.cb_lower = 0.0
      else:
        if CS.out.vEgo > 5.0:
          self.cb_upper = float(np.clip(0.25 + CS.out.aEgo * 0.20, 0.0, 1.0))
          self.cb_lower = float(np.clip(0.30 + CS.out.aEgo * 0.20, 0.0, 1.0))
        else:
          # When at low speeds, we don't want ComfortBands to be affecting stopping control.
          self.cb_upper = self.cb_lower = 0.0

    return self.jerk

  def handle_cruise_cancel(self, CS):
    """Handle cruise control cancel to prevent faults."""
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last = 0.0
      self.last_accel = 0.0
      self.brake_ramp = 0.0
      return True
    return False

  def should_delay_cancel(self, CS):
    """Check if cancel button press should be delayed based on recent deceleration."""
    if CS.out.aEgo < -0.1:
      self.last_decel_time = self.DT_CTRL * self.jerk_count
    current_time = self.DT_CTRL * self.jerk_count
    return (current_time - self.last_decel_time) < self.min_cancel_delay and CS.out.aEgo < 0

  def calculate_limited_accel(self, accel, actuators, CS):
    """Adaptive acceleration limiting."""
    if self.handle_cruise_cancel(CS):
      return accel
    self.make_jerk(CS, actuators)

    target_accel = accel

    # Apply transition smoothing when switching modes
    if self.transitioning and self.prev_mode == 'acc' and self.current_mode == 'blended':
      if (CS.out.vEgo > 2.69 and (target_accel < 0 and target_accel < self.accel_last)):
        progress = min(1.0, self.mode_transition_timer / self.mode_transition_duration)
        blend_factor = 1.0 - (1.0 - progress) * (1.0 - abs(target_accel / CarControllerParams.ACCEL_MIN))
        target_accel = self.accel_last + (target_accel - self.accel_last) * blend_factor

    # For braking, vary rate based on braking intensity
    if (CS.out.vEgo > 3.5 and target_accel < 0.01):
      brake_ratio = np.clip(abs(target_accel / self.car_config.accel_limits[0]), 0.0, 1.0)
      # Gentler for light braking, more responsive for harder braking
      accel_rate_down = self.DT_CTRL * np.interp(brake_ratio,
                                            [0.0, 0.3, 0.7, 1.0],
                                            self.car_config.brake_response)
      accel = max(target_accel, self.accel_last - accel_rate_down)
    else:
      accel = target_accel

    self.accel_last = accel
    return accel

  def calculate_accel(self, accel, actuators, CS, frogpilot_toggles):
    """Calculate acceleration with cruise control status handling."""
    if self.handle_cruise_cancel(CS):
      return 0.0
    accel = self.calculate_limited_accel(accel, actuators, CS)
    # Use car config accel limits, but still respect frogpilot max acceleration setting
    return float(np.clip(accel, self.car_config.accel_limits[0],
               min(frogpilot_toggles.max_desired_acceleration, self.car_config.accel_limits[1])))


  def apply_tune(self, CP: Any) -> None:
    config = self.car_config
    CP.vEgoStopping = config.vego_stopping
    CP.vEgoStarting = config.vego_starting
    CP.stoppingDecelRate = config.stopping_decel_rate
    CP.startAccel = config.start_accel
    CP.startingState = True
    CP.longitudinalActuatorDelay = 0.5


class HKGLongitudinalController:
  """Longitudinal controller which gets injected into CarControllerParams."""
  def __init__(self, CP):
    self.CP = CP
    self.tuning = HKGLongitudinalTuning(CP) if Params().get_bool("HKGtuning") else None
    self.jerk = None
    self.jerk_upper_limit = 0.0
    self.jerk_lower_limit = 0.0
    self.cb_upper = 0.0
    self.cb_lower = 0.0

  def apply_tune(self, CP):
    if self.tuning is not None:
      self.tuning.apply_tune(CP)
    else:
      CP.vEgoStopping = 0.5
      CP.vEgoStarting = 0.1
      CP.startingState = True
      CP.startAccel = 1.0
      CP.longitudinalActuatorDelay = 0.5

  def get_jerk(self) -> JerkOutput:
    if self.tuning is not None:
      return JerkOutput(
        self.tuning.jerk_upper_limit,
        self.tuning.jerk_lower_limit,
        self.tuning.cb_upper,
        self.tuning.cb_lower,
      )
    else:
      return JerkOutput(
        self.jerk_upper_limit,
        self.jerk_lower_limit,
        self.cb_upper,
        self.cb_lower,
      )

  def calculate_and_get_jerk(self, actuators, CP: CarControllerParams, CS, long_control_state: LongCtrlState) -> JerkOutput:
    """Calculate jerk based on tuning and return JerkOutput."""
    if self.tuning is not None:
      self.tuning.make_jerk(CS, actuators)
    else:
      if CP.carFingerprint in (CAR.HYUNDAI_KONA_EV):
        jerk_limit = 8.0 if long_control_state == LongCtrlState.pid else 6.0
      else:
        jerk_limit = 3.0 if long_control_state == LongCtrlState.pid else 1.0

      self.jerk_upper_limit = jerk_limit
      self.jerk_lower_limit = jerk_limit
      self.cb_upper = 0.0
      self.cb_lower = 0.0
    return self.get_jerk()

  def calculate_accel(self, accel, actuators, CS, frogpilot_toggles) -> float:
    """Calculate acceleration based on tuning and return the value."""
    if Params().get_bool("HKGBraking") and self.tuning is not None:
      accel = self.tuning.calculate_accel(actuators.accel, actuators, CS, frogpilot_toggles)
    elif Params().get_bool("HKGBraking") and self.tuning is not None and frogpilot_toggles.sport_plus:
      accel = self.tuning.calculate_accel(actuators.accel, actuators, CS, frogpilot_toggles)
      accel = float(np.clip(accel, CarControllerParams.ACCEL_MIN, min(frogpilot_toggles.max_desired_acceleration, get_max_allowed_accel(CS.out.vEgo))))
    elif frogpilot_toggles.sport_plus:
      accel = float(np.clip(actuators.accel, CarControllerParams.ACCEL_MIN, min(frogpilot_toggles.max_desired_acceleration, get_max_allowed_accel(CS.out.vEgo))))
    else:
      accel = float(np.clip(actuators.accel, CarControllerParams.ACCEL_MIN, min(frogpilot_toggles.max_desired_acceleration, CarControllerParams.ACCEL_MAX)))

    return accel
