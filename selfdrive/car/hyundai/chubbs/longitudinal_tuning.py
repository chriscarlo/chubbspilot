import numpy as np
from cereal import car, messaging
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.params import Params
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.car.hyundai.values import HyundaiFlags, CarControllerParams
from openpilot.selfdrive.car.hyundai.chubbs.longitudinal_config import Cartuning
from openpilot.selfdrive.frogpilot.controls.lib.frogpilot_acceleration import get_max_allowed_accel

LongCtrlState = car.CarControl.Actuators.LongControlState

COMFORT_DECEL = -2.5
MAX_BRAKE_DECEL = -6.0
EPSILON = 1e-6

def akima_interp(x, xp, fp):
  if x <= xp[0]:
    return fp[0]
  elif x >= xp[-1]:
    return fp[-1]
  i = np.searchsorted(xp, x) - 1
  i = max(0, min(i, len(xp)-2))
  t = (x - xp[i]) / float(xp[i+1] - xp[i])
  t2 = t*t
  t3 = t2*t
  return fp[i]*(1-10*t3+15*t2*t2-6*t3*t2) + fp[i+1]*(10*t3-15*t2*t2+6*t3*t2)

class JerkOutput:
  def __init__(self, jerk_upper_limit, jerk_lower_limit, cb_upper, cb_lower):
    self.jerk_upper_limit = jerk_upper_limit
    self.jerk_lower_limit = jerk_lower_limit
    self.cb_upper = cb_upper
    self.cb_lower = cb_lower

class HKGLongitudinalTuning:
  def __init__(self, CP: car.CarParams) -> None:
    self.CP = CP
    self._setup_controllers()
    self._init_state()
    self._mode_setup()
    self._setup_car_config()

  def _setup_controllers(self) -> None:
    # Instantiate LongitudinalMpc so that self.mpc.mode can be set properly
    self.mpc = LongitudinalMpc(mode='acc')
    self.long_control = LongControl(self.CP)
    self.sm = messaging.SubMaster(['controlsState'])
    self.DT_CTRL = DT_CTRL
    self.params = Params()

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
    self.prev_mode = 'acc'
    self.current_mode = 'acc'
    self.mode_transition_filter = FirstOrderFilter(0.0, 0.5, DT_CTRL)
    self.mode_transition_timer = 0.0
    self.mode_transition_duration = 1.5
    self.transitioning = False

  def _setup_car_config(self) -> None:
    self.car_config = Cartuning.get_car_config(self.CP)

  def update_mpc_mode(self, sm: messaging.SubMaster) -> None:
    new_mode = 'blended' if self.sm['controlsState'].experimentalMode else 'acc'
    if new_mode != self.current_mode:
      self.prev_mode = self.current_mode
      self.transitioning = True
      self.mode_transition_timer = 0.0
      self.mode_transition_filter.x = self.accel_last
      self.mpc.mode = new_mode
      self.current_mode = new_mode
    if self.transitioning:
      self.mode_transition_timer += DT_CTRL
      if self.mode_transition_timer >= self.mode_transition_duration:
        self.transitioning = False

  def make_jerk(self, desired_accel_plan, current_acc, radar_state, jerk_limits, accel_limits, dt):
    desired_accel = float(desired_accel_plan)
    min_accel, max_accel = accel_limits
    ttc = None
    closing_speed = 0.0
    if radar_state is not None and hasattr(radar_state, 'leadOne') and radar_state.leadOne is not None:
      lead = radar_state.leadOne
      if lead.status:
        d_rel = float(lead.dRel)
        v_rel = float(lead.vRel)
        if v_rel < 0:
          closing_speed = -v_rel
          ttc = d_rel / max(closing_speed, 0.01)

    safety_override = False
    new_min_accel = min_accel
    jerk_limits_override = None
    if ttc is not None:
      required_decel_mag = (closing_speed ** 2) / (2 * max(d_rel, EPSILON))
      if required_decel_mag > abs(min_accel):
        safety_override = True
        required_accel = -required_decel_mag
        new_min_accel = max(required_accel, MAX_BRAKE_DECEL)
        if ttc < 1.0:
          jerk_limits_override = (1e6, 1e6)
        else:
          factor = min(required_decel_mag / abs(min_accel), 3.0)
          jerk_limits_override = (jerk_limits[0] * factor, jerk_limits[1] * factor)

    desired_accel_clipped = max(new_min_accel, min(desired_accel, max_accel))
    if safety_override and jerk_limits_override is not None:
      return calculate_limited_accel(current_acc, desired_accel_clipped, (new_min_accel, max_accel), jerk_limits_override, dt)
    else:
      return calculate_limited_accel(current_acc, desired_accel_clipped, (new_min_accel, max_accel), jerk_limits, dt)

  def handle_cruise_cancel(self, CS: car.CarState):
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last = 0.0
      self.last_accel = 0.0
      self.brake_ramp = 0.0
      return True
    return False

  def should_delay_cancel(self, CS: car.CarState):
    if CS.out.aEgo < -0.1:
      self.last_decel_time = self.DT_CTRL * self.jerk_count
    current_time = self.DT_CTRL * self.jerk_count
    return (current_time - self.last_decel_time) < self.min_cancel_delay and CS.out.aEgo < 0

  def calculate_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, frogpilot_toggles) -> float:
    if self.handle_cruise_cancel(CS):
      return 0.0
    accel = actuators.accel
    return float(np.clip(accel, self.car_config.accel_limits[0],
                         min(frogpilot_toggles.max_desired_acceleration, self.car_config.accel_limits[1])))

  def apply_tune(self, CP: car.CarParams) -> None:
    config = self.car_config
    CP.vEgoStopping = config.vego_stopping
    CP.vEgoStarting = config.vego_starting
    CP.stoppingDecelRate = config.stopping_decel_rate
    CP.startAccel = config.start_accel
    CP.startingState = True
    CP.longitudinalActuatorDelay = 0.5

def calculate_limited_accel(current_accel: float, desired_accel: float,
                            accel_limits: tuple, jerk_limits: tuple, dt: float) -> float:
  min_accel, max_accel = accel_limits
  desired_accel = max(min_accel, min(desired_accel, max_accel))
  accel_delta = desired_accel - current_accel
  max_delta = (-jerk_limits[0] if accel_delta < 0 else jerk_limits[1]) * dt
  accel_delta = np.clip(accel_delta, -abs(max_delta), abs(max_delta))
  return max(min_accel, min(current_accel + accel_delta, max_accel))

class HKGLongitudinalController:
  @staticmethod
  def param(key: str) -> bool:
    val = Params().get(key)
    return val in [b"1"]

  def __init__(self, CP: car.CarParams):
    self.CP = CP
    self.tuning = HKGLongitudinalTuning(CP) if self.param("HKGtuning") else None
    self.jerk = None
    self.jerk_upper_limit = 0.0
    self.jerk_lower_limit = 0.0
    self.cb_upper = 0.0
    self.cb_lower = 0.0

  def apply_tune(self, CP: car.CarParams):
    if self.param("HKGtuning"):
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

  def calculate_and_get_jerk(self, actuators: car.CarControl.Actuators,
                             CS: car.CarState,
                             long_control_state: LongCtrlState,
                             radar_state) -> JerkOutput:
    if self.tuning is not None:
      jerk_limits = (3.0, 2.0)
      accel_limits = (COMFORT_DECEL, self.tuning.car_config.accel_limits[1])
      dt = DT_CTRL

      desired_accel = actuators.accel
      current_acc = CS.out.aEgo

      # Fix: actually use the jerk-limited accel instead of discarding it
      jerk_limited_accel = self.tuning.make_jerk(desired_accel,
                                                 current_acc,
                                                 radar_state,
                                                 jerk_limits,
                                                 accel_limits,
                                                 dt)
      # Update the actuators object so future code sees the jerk-limited accel
      actuators.accel = jerk_limited_accel

      self.jerk_upper_limit = jerk_limits[1]
      self.jerk_lower_limit = jerk_limits[0]
      self.cb_upper = 0.0
      self.cb_lower = 0.0
    else:
      jerk_limit = 3.0 if long_control_state == LongCtrlState.pid else 1.0
      self.jerk_upper_limit = jerk_limit
      self.jerk_lower_limit = jerk_limit
      self.cb_upper = 0.0
      self.cb_lower = 0.0

    return self.get_jerk()

  def calculate_accel(self, actuators: car.CarControl.Actuators,
                      CS: car.CarState,
                      frogpilot_toggles) -> float:
    if Params().get_bool("HKGBraking") and self.tuning is not None:
      accel = self.tuning.calculate_accel(actuators, CS, frogpilot_toggles)
    elif Params().get_bool("HKGBraking") and self.tuning is not None and frogpilot_toggles.sport_plus:
      accel = self.tuning.calculate_accel(actuators, CS, frogpilot_toggles)
      accel = float(np.clip(accel,
                            CarControllerParams.ACCEL_MIN,
                            min(frogpilot_toggles.max_desired_acceleration,
                                get_max_allowed_accel(CS.out.vEgo))))
    elif frogpilot_toggles.sport_plus:
      accel = float(np.clip(actuators.accel,
                            CarControllerParams.ACCEL_MIN,
                            min(frogpilot_toggles.max_desired_acceleration,
                                get_max_allowed_accel(CS.out.vEgo))))
    else:
      accel = float(np.clip(actuators.accel,
                            CarControllerParams.ACCEL_MIN,
                            min(frogpilot_toggles.max_desired_acceleration,
                                CarControllerParams.ACCEL_MAX)))
    return accel
