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

# Define panic braking constants
PANIC_DECEL_LIMIT = -6.0  # m/s^2, the full potential
PANIC_JERK_LIMIT = 50.0   # m/s^3, very high jerk limit for immediate response

def akima_interp(x, xp, fp):
    """Akima-inspired quintic polynomial interpolation using numpy."""
    # Handle boundary conditions
    if x <= xp[0]:
        return fp[0]
    elif x >= xp[-1]:
        return fp[-1]

    # Find the interval
    i = np.searchsorted(xp, x) - 1
    i = max(0, min(i, len(xp)-2))  # Safety bounds check

    # Calculate normalized position within interval
    t = (x - xp[i]) / float(xp[i+1] - xp[i]) if (xp[i+1] - xp[i]) != 0 else 0 # Prevent division by zero

    # Modified quintic polynomial that approximates Akima behavior
    # This provides smoother transitions with less possible overshoot
    t2 = t*t
    t3 = t2*t

    # Quintic Hermite form with zero second derivatives at endpoints
    return fp[i]*(1-10*t3+15*t2*t2-6*t3*t2) + fp[i+1]*(10*t3-15*t2*t2+6*t3*t2)

class JerkOutput:
  def __init__(self, jerk_upper_limit, jerk_lower_limit, cb_upper, cb_lower):
    self.jerk_upper_limit = jerk_upper_limit
    self.jerk_lower_limit = jerk_lower_limit
    self.cb_upper = cb_upper
    self.cb_lower = cb_lower

class HKGLongitudinalTuning:
  """Longitudinal tuning methodology for Hyundai vehicles."""
  def __init__(self, CP: car.CarParams) -> None:
    self.CP = CP
    self._setup_controllers()
    self._init_state()
    self._mode_setup()
    self._setup_car_config()

  def _setup_controllers(self) -> None:
    self.mpc = LongitudinalMpc # Reference, not instance
    self.long_control = LongControl(self.CP)
    # SubMaster initialization moved to where it's used to avoid issues if not run in a process
    self.sm = None
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
    self.prev_mode = 'acc'  # Default mode
    self.current_mode = 'acc'
    self.mode_transition_filter = FirstOrderFilter(0.0, 0.5, DT_CTRL)  # 0.5s time constant
    self.mode_transition_timer = 0.0
    self.mode_transition_duration = 1.5  # time to transition
    self.transitioning = False

  def _setup_car_config(self) -> None:
    self.car_config = Cartuning.get_car_config(self.CP)
    # Ensure brake_response exists and has at least one value
    if not hasattr(self.car_config, 'brake_response') or not self.car_config.brake_response:
       # Provide a default if missing, e.g., [1.0, 2.0, 3.0, 5.0]
       self.car_config.brake_response = [1.0, 2.0, 3.0, 5.0]
    # Ensure accel_limits exist
    if not hasattr(self.car_config, 'accel_limits'):
        # Provide default if missing
        self.car_config.accel_limits = [-3.5, 2.0]


  def update_mpc_mode(self, sm_dict: dict) -> None:
    """Update MPC mode with transition handling. Takes sm_dict instead of SubMaster."""
    if 'controlsState' not in sm_dict:
        return # Do nothing if controlsState isn't available

    new_mode = 'blended' if sm_dict['controlsState'].experimentalMode else 'acc'

    # Detect mode change
    if new_mode != self.current_mode:
      self.prev_mode = self.current_mode
      self.transitioning = True
      self.mode_transition_timer = 0.0
      self.mode_transition_filter.x = self.accel_last

      # Update the MPC mode directly (Note: This affects the class variable, shared instance if any)
      # This might need adjustment depending on how MPC instances are managed.
      # Assuming MPC mode is set elsewhere or this is informational for transitions.
      # self.mpc.mode = new_mode
      self.current_mode = new_mode

    # Update transition state
    if self.transitioning:
      self.mode_transition_timer += DT_CTRL
      if self.mode_transition_timer >= self.mode_transition_duration:
        self.transitioning = False

  def make_jerk(self, CS: car.CarState, actuators: car.CarControl.Actuators) -> float:
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

    # Use actuators.accel for desired jerk calculation during active control
    # Use aEgo otherwise (e.g., during state changes or stopping)
    # This aligns jerk limits better with control intent, especially during hard braking requests.
    current_accel_metric = actuators.accel if actuators.longControlState != LongCtrlState.off else CS.out.aEgo

    if actuators.longControlState == LongCtrlState.stopping:
      # Maintain some baseline jerk capability when stopping
      self.jerk = self.car_config.jerk_limits[0] / 2 - current_accel_metric
    else:
      # Calculate jerk based on the change in the chosen metric
      self.jerk = (current_accel_metric - self.accel_last_jerk) / self.DT_CTRL if self.DT_CTRL > 1e-5 else 0.0 # Jerk in m/s^3
      self.accel_last_jerk = current_accel_metric


    # Akima interp remains for smoothing the *reported* jerk value if needed,
    # but the core panic logic will rely on direct rate limiting changes.
    # Using raw jerk calculation before Akima might be more representative for limits.
    # Let's stick to the original Akima for reported jerk value for now.
    base_jerk = self.jerk * self.DT_CTRL # Convert back to accel diff for original akima scale
    xp = np.array([-3.5, -2.0, -1.0, 0.0, 1.0, 2.0])
    fp = np.array([-2.5, -1.0, -0.5, 0.0, 0.5, 1.0])
    interp_jerk_val = akima_interp(base_jerk, xp, fp) # This is more like a smoothed accel change?

    # Keep original logic for calculating reported jerk limits for backward compatibility
    jerk_max = self.car_config.jerk_limits[1]
    if self.CP.flags & HyundaiFlags.CANFD.value:
      self.jerk_upper_limit = min(max(self.car_config.jerk_limits[0], interp_jerk_val * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(self.car_config.jerk_limits[0], -interp_jerk_val * 4.0), jerk_max)
      self.cb_upper = self.cb_lower = 0.0
    else:
      self.jerk_upper_limit = min(max(self.car_config.jerk_limits[0], interp_jerk_val * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(self.car_config.jerk_limits[0], -interp_jerk_val * 2.0), jerk_max)
      if self.CP.radarUnavailable:
        self.cb_upper = self.cb_lower = 0.0
      else:
        hkg_braking_param = self.params.get_bool("HKGBraking") if self.params else False # Check if params is initialized
        if not hkg_braking_param and (CS.out.vEgo > 5.0):
          self.cb_upper = float(np.clip(0.20 + actuators.accel * 0.20, 0.0, 1.0))
          self.cb_lower = float(np.clip(0.10 + actuators.accel * 0.20, 0.0, 1.0))
        else:
          self.cb_upper = self.cb_lower = 0.0

    # Return the *calculated* jerk (m/s^3), not the interpolated value used for limits
    return self.jerk

  def handle_cruise_cancel(self, CS: car.CarState):
    """Handle cruise control cancel to prevent faults."""
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last = 0.0
      self.last_accel = 0.0
      self.brake_ramp = 0.0
      # Reset transition state on cancel
      self.transitioning = False
      self.mode_transition_timer = 0.0
      return True
    return False

  def should_delay_cancel(self, CS: car.CarState):
    """Check if cancel button press should be delayed based on recent deceleration."""
    # This logic seems unrelated to panic braking, keeping as is.
    if CS.out.aEgo < -0.1:
      self.last_decel_time = self.DT_CTRL * self.jerk_count
    current_time = self.DT_CTRL * self.jerk_count
    return (current_time - self.last_decel_time) < self.min_cancel_delay and CS.out.aEgo < 0

  def calculate_limited_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, sm_dict: dict) -> float:
    """Adaptive acceleration limiting with panic braking capability."""
    if self.handle_cruise_cancel(CS):
      return actuators.accel # Return raw planner accel on cancel

    # Update mode transition state - requires sm_dict
    self.update_mpc_mode(sm_dict)

    # Calculate reported jerk values (doesn't limit accel here)
    # Note: This call increments jerk_count used by should_delay_cancel
    self.make_jerk(CS, actuators)

    target_accel = actuators.accel
    current_accel = self.accel_last # The previously applied acceleration

    # Apply transition smoothing when switching modes (keep original logic)
    if self.transitioning and self.prev_mode == 'acc' and self.current_mode == 'blended':
        # ... (original transition logic remains unchanged) ...
      if CS.out.vEgo > 4.0 and target_accel < 0.0 and target_accel < self.accel_last:
        hard_brake_threshold = CarControllerParams.ACCEL_MIN * 0.7
        if target_accel < hard_brake_threshold:
          progress = min(1.0, self.mode_transition_timer / (self.mode_transition_duration * 0.5))
          smoothed_target_accel = self.accel_last + (target_accel - self.accel_last) * progress
        else:
          progress = min(1.0, self.mode_transition_timer / self.mode_transition_duration)
          brake_intensity = abs(target_accel / CarControllerParams.ACCEL_MIN)
          xp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
          if brake_intensity < 0.3:  # Light braking
            fp = np.array([0.0, 0.1, 0.3, 0.7, 1.0])
          elif brake_intensity < 0.6: # Moderate braking
            fp = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
          else:  # Heavy braking
            fp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
          smooth_progress = akima_interp(progress, xp, fp)
          smoothed_target_accel = self.accel_last + (target_accel - self.accel_last) * smooth_progress
        target_accel = smoothed_target_accel # Apply smoothing

    # --- Dynamic Rate Limiting (Jerk Control) ---
    # Determine the maximum allowed change in acceleration (jerk * DT_CTRL)
    # Based on the *target* acceleration request from the planner

    normal_decel_limit = self.car_config.accel_limits[0]
    # Ensure brake_response has valid data
    max_normal_brake_resp = self.car_config.brake_response[-1] if self.car_config.brake_response else 5.0

    # Define the desired acceleration points for rate transition
    # Start increasing rate limit slightly before normal limit, reach panic rate when planner demands it
    # Ensure xp_rate is increasing
    xp_rate = sorted([normal_decel_limit * 1.2, normal_decel_limit * 0.8]) # Transition around normal limit
    # Corresponding rate limits (accel change per step = jerk * DT_CTRL)
    # Panic rate allows very fast change, normal rate uses config
    fp_rate = [PANIC_JERK_LIMIT * self.DT_CTRL, max_normal_brake_resp * self.DT_CTRL]

    # Interpolate the downward acceleration rate limit
    effective_rate_down = np.interp(target_accel, xp_rate, fp_rate)

    # Apply rate limiting
    # Allow acceleration increase relatively freely (using config upper limit)
    # Limit deceleration based on the dynamic rate
    accel_change_upper = self.car_config.jerk_limits[1] * self.DT_CTRL # Max normal positive change
    accel_change_lower = -effective_rate_down # Max negative change (dynamic)

    # Calculate the potential next acceleration based on rate limits
    accel = current_accel + np.clip(target_accel - current_accel, accel_change_lower, accel_change_upper)

    # Store the rate-limited acceleration before final clipping
    self.accel_last = accel
    return accel

  def calculate_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, frogpilot_toggles, sm_dict: dict) -> float:
    """Calculate acceleration with cruise control status handling and dynamic limits."""
    # Make sure params is available if needed within methods
    if self.params is None:
       self.params = Params()

    if self.handle_cruise_cancel(CS):
      # On cancel, return 0 or a safe value, reset last accel state
      self.accel_last = 0.0
      return 0.0

    # Calculate rate-limited acceleration based on planner input and current state
    accel = self.calculate_limited_accel(actuators, CS, sm_dict)

    # --- Dynamic Acceleration Limits ---
    # Determine the final acceleration limits based on planner's request

    normal_decel_limit = self.car_config.accel_limits[0]
    normal_accel_limit = min(frogpilot_toggles.max_desired_acceleration, self.car_config.accel_limits[1])

    # Define desired acceleration points for limit transition
    # Start allowing more decel slightly before normal limit, reach panic limit when requested
    # Ensure xp_limit is increasing
    xp_limit = sorted([normal_decel_limit * 1.5, normal_decel_limit * 0.9]) # e.g., [-5.25, -3.15] if normal is -3.5
    # Corresponding acceleration lower bounds
    fp_limit = [PANIC_DECEL_LIMIT, normal_decel_limit] # e.g., [-6.0, -3.5]

    # Interpolate the effective lower acceleration limit
    effective_decel_limit = np.interp(actuators.accel, xp_limit, fp_limit)

    # Apply final clipping with the dynamic lower bound and normal upper bound
    final_accel = float(np.clip(accel, effective_decel_limit, normal_accel_limit))

    # Handle specific frogpilot toggles / sport mode after dynamic limits if needed
    # (Current logic seems to just apply standard clipping already handled above)
    # Keeping the structure in case of future specific logic needed here.
    hkg_braking_param = self.params.get_bool("HKGBraking") if self.params else False
    if hkg_braking_param:
       # The dynamic limits already handle the core requirement.
       # If Sport Plus needs *even higher* accel limits, that could be adjusted here,
       # but the panic *decel* is handled by effective_decel_limit.
       if frogpilot_toggles.sport_plus:
           # Example: Potentially allow higher *positive* acceleration in sport plus
           sport_accel_limit = min(frogpilot_toggles.max_desired_acceleration, get_max_allowed_accel(CS.out.vEgo))
           final_accel = float(np.clip(accel, effective_decel_limit, sport_accel_limit))
       # else: # Normal HKGBraking case already covered by initial clip
           # pass
    elif frogpilot_toggles.sport_plus:
        # Non-HKGBraking + Sport Plus: Apply dynamic decel, sport accel limit
        sport_accel_limit = min(frogpilot_toggles.max_desired_acceleration, get_max_allowed_accel(CS.out.vEgo))
        final_accel = float(np.clip(accel, effective_decel_limit, sport_accel_limit))
    else:
        # Non-HKGBraking, Non-Sport Plus: Apply dynamic decel, standard accel limit
        standard_accel_limit = min(frogpilot_toggles.max_desired_acceleration, CarControllerParams.ACCEL_MAX)
        # Ensure we still respect the panic decel limit calculated earlier
        final_accel = float(np.clip(accel, effective_decel_limit, standard_accel_limit))


    # Update accel_last *after* final clipping? No, update was done in calculate_limited_accel
    # This ensures rate limiting is based on the previously *applied* value.
    # self.accel_last = final_accel # Reconsider if this should be updated here

    return final_accel

  def apply_tune(self, CP: car.CarParams) -> None:
    # Initialize params here if not already done elsewhere
    if self.params is None:
        self.params = Params()

    config = self.car_config
    CP.vEgoStopping = config.vego_stopping
    CP.vEgoStarting = config.vego_starting
    CP.stoppingDecelRate = config.stopping_decel_rate
    CP.startAccel = config.start_accel
    CP.startingState = True
    # Note: longitudinalActuatorDelay is often car-specific, ensure 0.5 is appropriate or tuned.
    CP.longitudinalActuatorDelay = getattr(config, 'longitudinalActuatorDelay', 0.5) # Use config value if available


class HKGLongitudinalController:
  """Longitudinal controller which gets injected into CarControllerParams."""
  @staticmethod
  def param(key: str) -> bool:
    # Use a temporary Params() instance if needed, or ensure it's initialized
    # This static method might be called before __init__? Unlikely in normal flow.
    val = Params().get(key)
    return val is not None and val == b"1"

  def __init__(self, CP: car.CarParams):
    self.CP = CP
    # Initialize Params instance for the controller
    self.params = Params()
    # Ensure HKGtuning param check uses the instance's params
    self.tuning = HKGLongitudinalTuning(CP) if self.params.get_bool("HKGtuning") else None
    self.jerk = None
    self.jerk_upper_limit = 0.0
    self.jerk_lower_limit = 0.0
    self.cb_upper = 0.0
    self.cb_lower = 0.0
    # Initialize SubMaster here for use in calculate_accel
    self.sm = messaging.SubMaster(['controlsState'])


  def apply_tune(self, CP: car.CarParams):
    # Use instance's params object
    if self.params.get_bool("HKGtuning") and self.tuning is not None:
      self.tuning.apply_tune(CP)
    else:
      CP.vEgoStopping = 0.5
      CP.vEgoStarting = 0.1
      CP.startingState = True
      CP.startAccel = 1.0
      CP.longitudinalActuatorDelay = 0.5 # Default fallback

  def get_jerk(self) -> JerkOutput:
    if self.tuning is not None:
       # Ensure make_jerk has been called recently if these values are needed fresh
       # It's called within calculate_limited_accel, which is called by calculate_accel
      return JerkOutput(
        self.tuning.jerk_upper_limit,
        self.tuning.jerk_lower_limit,
        self.tuning.cb_upper,
        self.tuning.cb_lower,
      )
    else:
      # Fallback if tuning is disabled
      # Provide some default reasonable jerk limits if needed elsewhere
      default_jerk = 3.0 # Example default
      return JerkOutput(default_jerk, default_jerk, 0.0, 0.0)


  def calculate_and_get_jerk(self, actuators: car.CarControl.Actuators, CS: car.CarState, long_control_state: LongCtrlState) -> JerkOutput:
    """Calculate jerk based on tuning and return JerkOutput."""
    if self.tuning is not None:
      # make_jerk is called inside calculate_accel -> calculate_limited_accel
      # Calling it here again might double-count jerk_count etc.
      # If this function is called *before* calculate_accel, then call make_jerk here.
      # If it's called *after*, the values are already populated.
      # Assuming it might be called independently or before, let's call it,
      # but be mindful of potential side effects if called multiple times per frame.
      # Let's rely on it being called within calculate_accel for simplicity.
      # self.tuning.make_jerk(CS, actuators) # Avoid calling again here
      pass # Values populated by calculate_accel call path
    else:
      # Fallback logic if tuning is disabled
      jerk_limit = 3.0 if long_control_state == LongCtrlState.pid else 1.0
      self.jerk_upper_limit = jerk_limit
      self.jerk_lower_limit = jerk_limit
      self.cb_upper = 0.0
      self.cb_lower = 0.0
    return self.get_jerk()

  def calculate_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, frogpilot_toggles) -> float:
    """Calculate acceleration based on tuning and return the value."""
    # Update SubMaster before passing data down
    self.sm.update(0)
    sm_dict = self.sm.data if self.sm.updated else {}

    if self.params.get_bool("HKGtuning") and self.tuning is not None:
      # Pass sm_dict down for mode transition logic
      accel = self.tuning.calculate_accel(actuators, CS, frogpilot_toggles, sm_dict)
    # The logic below is now mostly integrated into the tuning's calculate_accel method.
    # We just call the appropriate method and return its result.
    # Need to handle the case where tuning is None.
    elif self.tuning is None:
        # Default behavior without HKGtuning, potentially add panic logic here too?
        # For now, keep original non-tuned logic but add basic panic clipping.
        # This assumes non-tuned mode should also panic brake if needed.

        # Basic Panic Decel Limit application even without full tuning
        normal_decel_limit = CarControllerParams.ACCEL_MIN # Use generic limit
        xp_limit = sorted([normal_decel_limit * 1.5, normal_decel_limit * 0.9])
        fp_limit = [PANIC_DECEL_LIMIT, normal_decel_limit]
        effective_decel_limit = np.interp(actuators.accel, xp_limit, fp_limit)

        if frogpilot_toggles.sport_plus:
            accel_max = min(frogpilot_toggles.max_desired_acceleration, get_max_allowed_accel(CS.out.vEgo))
        else:
            accel_max = min(frogpilot_toggles.max_desired_acceleration, CarControllerParams.ACCEL_MAX)

        # Apply basic rate limiting? Or just clip? Let's just clip for simplicity here.
        # TODO: Consider adding dynamic rate limiting similar to the tuned version if needed.
        accel = float(np.clip(actuators.accel, effective_decel_limit, accel_max))

    else:
       # Fallback case, should ideally not be reached if HKGtuning param maps correctly
       # to self.tuning being None or not.
       accel = float(np.clip(actuators.accel, CarControllerParams.ACCEL_MIN, CarControllerParams.ACCEL_MAX))


    return accel