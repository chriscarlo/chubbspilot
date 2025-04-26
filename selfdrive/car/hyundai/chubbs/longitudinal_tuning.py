import numpy as np
import math # Needed for isnan, isinf
from cereal import car, messaging
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.params import Params
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
# from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc # Not used directly here
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.car.hyundai.values import HyundaiFlags, CarControllerParams
# NOTE: Assuming longitudinal_config is accessible
# from openpilot.selfdrive.car.hyundai.chubbs.longitudinal_config import Cartuning
# NOTE: Assuming frogpilot_acceleration is accessible if used elsewhere
# from openpilot.selfdrive.frogpilot.controls.lib.frogpilot_acceleration import get_max_allowed_accel

LongCtrlState = car.CarControl.Actuators.LongControlState

# --- Constants for Dynamic Jerk ---
TTC_RESPONSIVENESS_THRESHOLD = 2.0 # TTC (s) below which we consider increasing jerk response
MAX_ALLOWABLE_JERK = 20.0 # Max downward jerk allowed in urgent situations (m/s^3) - Increased from 10.0
# MIN_CRITICAL_JERK = 15.0 # Removed, superseded by interpolation
# --- End Constants ---


def akima_interp(x, xp, fp):
    """Akima-inspired quintic polynomial interpolation using numpy."""
    if x <= xp[0]: return fp[0]
    if x >= xp[-1]: return fp[-1]
    i = np.searchsorted(xp, x) - 1
    i = max(0, min(i, len(xp)-2))
    t = (x - xp[i]) / float(xp[i+1] - xp[i])
    t2, t3 = t*t, t*t*t
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
    self.long_control = LongControl(self.CP)
    self.sm = messaging.SubMaster(['controlsState'])
    self.DT_CTRL = DT_CTRL
    self.params = Params()

  def _init_state(self) -> None:
    self.last_accel = 0.0
    self.accel_last = 0.0
    # Reset other state variables
    self.brake_ramp = 0.0
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
    # NOTE: Ensure this import path is correct for your setup
    from openpilot.selfdrive.car.hyundai.chubbs.longitudinal_config import Cartuning
    self.car_config = Cartuning.get_car_config(self.CP)

  def update_mpc_mode(self, sm: messaging.SubMaster) -> None:
    # Simplified - ensure sm['controlsState'] is valid
    if 'controlsState' not in sm.keys() or not sm.valid['controlsState']:
        return
    new_mode = 'blended' if sm['controlsState'].experimentalMode else 'acc'
    if new_mode != self.current_mode:
      self.prev_mode = self.current_mode
      self.transitioning = True
      self.mode_transition_timer = 0.0
      self.mode_transition_filter.x = self.accel_last
      self.current_mode = new_mode
    if self.transitioning:
      self.mode_transition_timer += DT_CTRL
      if self.mode_transition_timer >= self.mode_transition_duration:
        self.transitioning = False

  def make_jerk(self, CS: car.CarState, actuators: car.CarControl.Actuators) -> float:
    # This function seems mostly for populating JerkOutput, keeping as is.
    # Its calculated limits aren't directly used by the rate limiting below.
    self.jerk_count += 1
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last_jerk = 0.0; self.jerk = 0.0; self.jerk_count = 0.0
      self.jerk_upper_limit = 0.0; self.jerk_lower_limit = 0.0
      self.cb_upper = self.cb_lower = 0.0
      return 0.0

    if actuators.longControlState == LongCtrlState.stopping:
      self.jerk = self.car_config.jerk_limits[0] / 2 - CS.out.aEgo
    else:
      current_accel = CS.out.aEgo
      self.jerk = (current_accel - self.accel_last_jerk)
      self.accel_last_jerk = current_accel

    base_jerk = self.jerk
    xp = np.array([-3.5, -2.0, -1.0, 0.0, 1.0, 2.0])
    fp = np.array([-2.5, -1.0, -0.5, 0.0, 0.5, 1.0])
    self.jerk = akima_interp(base_jerk, xp, fp)
    jerk_max = self.car_config.jerk_limits[1]

    # Populate limits (might be used by CAN message generation later)
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
        if(not Params().get_bool("HKGBraking")) and (CS.out.vEgo > 5.0):
          self.cb_upper = float(np.clip(0.20 + actuators.accel * 0.20, 0.0, 1.0))
          self.cb_lower = float(np.clip(0.10 + actuators.accel * 0.20, 0.0, 1.0))
        else:
          self.cb_upper = self.cb_lower = 0.0
    return self.jerk

  def handle_cruise_cancel(self, CS: car.CarState):
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last = 0.0
      self.brake_ramp = 0.0
      return True
    return False

  def should_delay_cancel(self, CS: car.CarState):
    # Unchanged
    if CS.out.aEgo < -0.1: self.last_decel_time = self.DT_CTRL * self.jerk_count
    current_time = self.DT_CTRL * self.jerk_count
    return (current_time - self.last_decel_time) < self.min_cancel_delay and CS.out.aEgo < 0

  def calculate_limited_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState) -> float:
    """Adaptive acceleration limiting with dynamic jerk based on TTC urgency."""

    if self.handle_cruise_cancel(CS):
      # Return planner request directly on cancel, as accel_last is reset.
      # Planner should command 0 or appropriate value.
      return actuators.accel

    # NOTE: Calling make_jerk here populates self.jerk_upper/lower_limit but they aren't used below.
    # Consider removing if truly unused by this function's logic or downstream consumers via get_jerk.
    self.make_jerk(CS, actuators)
    self.update_mpc_mode(self.sm) # Handles mode transitions if needed
    target_accel = actuators.accel

    # Apply transition smoothing (Original logic, check if needed)
    # This smoothing happens *before* the rate limiting.
    if self.transitioning and self.prev_mode == 'acc' and self.current_mode == 'blended':
        # ... (original smoothing logic remains here) ...
        if CS.out.vEgo > 4.0 and target_accel < 0.0 and target_accel < self.accel_last:
            hard_brake_threshold = CarControllerParams.ACCEL_MIN * 0.7
            if target_accel < hard_brake_threshold:
                progress = min(1.0, self.mode_transition_timer / (self.mode_transition_duration * 0.5))
                target_accel = self.accel_last + (target_accel - self.accel_last) * progress
            else:
                progress = min(1.0, self.mode_transition_timer / self.mode_transition_duration)
                brake_intensity = abs(target_accel / CarControllerParams.ACCEL_MIN)
                xp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
                if brake_intensity < 0.3: fp = np.array([0.0, 0.1, 0.3, 0.7, 1.0])
                elif brake_intensity < 0.6: fp = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
                else: fp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
                smooth_progress = akima_interp(progress, xp, fp)
                target_accel = self.accel_last + (target_accel - self.accel_last) * smooth_progress
        # Use the smoothed target for subsequent logic in this step
        accel_request = target_accel
    else:
        # Use the direct planner target if not transitioning
        accel_request = target_accel

    # Apply rate limiting for braking, using dynamic jerk based on TTC urgency
    # Use accel_request (potentially smoothed) as the target for rate limiting.
    if (CS.out.vEgo > 1.0 and accel_request < 0.01):
        # Calculate baseline comfortable jerk from config based on the accel_request
        brake_ratio = np.clip(abs(accel_request / self.car_config.accel_limits[0]), 0.0, 1.0)
        baseline_jerk = akima_interp(brake_ratio, np.array([0.25, 0.5, 0.75, 1.0]),
                                     np.array(self.car_config.brake_response))

        # --- START DYNAMIC JERK MODIFICATION ---
        effective_jerk = baseline_jerk # Default to comfortable jerk
        ttc = float('inf')
        jerk_needed_for_target = 0.0 # Initialize here

        # Check for lead and calculate TTC if closing
        if CS.leadOne.status and CS.leadOne.vRel < -0.1 and CS.leadOne.dRel > 0.1:
            lead_ttc = getattr(CS.leadOne, 'ttc', float('inf')) # Get TTC, default to infinity if missing

            # Check if lead_ttc is a valid finite number and positive
            if isinstance(lead_ttc, float) and math.isfinite(lead_ttc) and lead_ttc > 0:
                 ttc = lead_ttc # Use the valid TTC from radarState

                 # --- START DYNAMIC JERK INTERPOLATION ---
                 # Calculate jerk needed *only if* planner wants more braking
                 if accel_request < self.accel_last:
                     if isinstance(accel_request, float) and math.isfinite(accel_request) and \
                        isinstance(self.accel_last, float) and math.isfinite(self.accel_last):
                         jerk_needed_for_target = abs((accel_request - self.accel_last) / self.DT_CTRL)
                     else:
                          cloudlog.warning(f"long_tuning: Invalid accel values for jerk_needed calc: req={accel_request}, last={self.accel_last}")

                 # Define interpolation points
                 ttc_bp = [6.0, 5.0, 4.0]  # Time-to-collision (s) - Max aggression at 4.0s
                 jerk_factor_bp = [0.0, 0.3, 1.0] # Aggressiveness factor (0=baseline, 1=max potential)
                 MAX_POTENTIAL_JERK = MAX_ALLOWABLE_JERK # Use the overall max as the target potential

                 # Interpolate TTC to get aggressiveness factor (clamp TTC within bounds)
                 clamped_ttc = np.clip(ttc, ttc_bp[-1], ttc_bp[0])
                 # np.interp requires x values to be increasing
                 ttc_jerk_factor = np.interp(clamped_ttc, ttc_bp[::-1], jerk_factor_bp[::-1])

                 # Calculate the maximum jerk allowed based purely on TTC aggressiveness
                 max_jerk_from_ttc = baseline_jerk + (MAX_POTENTIAL_JERK - baseline_jerk) * ttc_jerk_factor

                 # Determine the effective jerk:
                 # Must be at least baseline.
                 # If planner requests more braking, consider jerk_needed and max_jerk_from_ttc.
                 # Cap at the absolute maximum allowable jerk.
                 if accel_request < self.accel_last:
                      effective_jerk = min(max(baseline_jerk, jerk_needed_for_target, max_jerk_from_ttc), MAX_ALLOWABLE_JERK)
                      # Optional Logging:
                      # print(f"TTC={ttc:.2f}, Factor={ttc_jerk_factor:.2f}, MaxTTCJ={max_jerk_from_ttc:.2f}, ReqJ={jerk_needed_for_target:.2f}, EffJ={effective_jerk:.2f}")
                 else:
                      # If not requesting harder braking, just use baseline
                      effective_jerk = baseline_jerk
                 # --- END DYNAMIC JERK INTERPOLATION ---

            else: # Invalid TTC from lead
                 ttc = float('inf') # Treat invalid/non-positive TTC as infinite
                 # If planner wants more braking even w/o valid TTC, allow needed jerk up to baseline? Or just baseline?
                 # Sticking to baseline seems safer if TTC is unknown/invalid.
                 effective_jerk = baseline_jerk

        # If no lead closing or status false, effective_jerk remains baseline_jerk from initialization

        # Apply the effective jerk limit
        # Ensure effective_jerk is valid before calculating max_delta_accel
        if isinstance(effective_jerk, float) and math.isfinite(effective_jerk):
            max_delta_accel = effective_jerk * self.DT_CTRL
            # Limit the rate of change from last step's accel
            # Also ensure self.accel_last is valid before the subtraction
            if isinstance(self.accel_last, float) and math.isfinite(self.accel_last):
                 accel = max(accel_request, self.accel_last - max_delta_accel)
            else:
                 cloudlog.warning(f"long_tuning: Invalid self.accel_last={self.accel_last}, using accel_request={accel_request}")
                 accel = accel_request # Fallback if accel_last is invalid
        else:
            cloudlog.warning(f"long_tuning: Invalid effective_jerk={effective_jerk}, using accel_request={accel_request}")
            accel = accel_request # Fallback if jerk is invalid
        # --- END DYNAMIC JERK MODIFICATION ---

    else:
        # If not braking significantly or at very low speed,
        # apply the accel_request directly (no downward rate limit applied).
        # Upward rate limiting might be handled elsewhere or implicitly by planner.
        accel = accel_request

    # Update the last acceleration value for the next iteration's rate limit
    self.accel_last = accel
    return accel

  def calculate_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, frogpilot_toggles) -> float:
    """Calculate acceleration with cruise control status handling and final clipping."""
    if self.handle_cruise_cancel(CS):
      return 0.0 # Return 0 on cancel

    # Get the rate-limited acceleration value using the new logic
    accel = self.calculate_limited_accel(actuators, CS)

    # Final clipping against car config limits
    max_accel_upper_limit = self.car_config.accel_limits[1]
    # NOTE: Add frogpilot toggle integration here if needed, e.g.:
    # if hasattr(frogpilot_toggles, 'max_desired_acceleration'):
    #    max_accel_upper_limit = min(frogpilot_toggles.max_desired_acceleration, max_accel_upper_limit)

    # Clip the final calculated acceleration
    return float(np.clip(accel, self.car_config.accel_limits[0], max_accel_upper_limit))


  def apply_tune(self, CP: car.CarParams) -> None:
    # Unchanged
    config = self.car_config
    CP.vEgoStopping = config.vego_stopping
    CP.vEgoStarting = config.vego_starting
    CP.stoppingDecelRate = config.stopping_decel_rate
    CP.startAccel = config.start_accel
    CP.startingState = True
    CP.longitudinalActuatorDelay = 0.5


# --- HKGLongitudinalController class remains the same as previous version ---
# It will use the modified HKGLongitudinalTuning instance automatically.

class HKGLongitudinalController:
  """Longitudinal controller which gets injected into CarControllerParams."""
  @staticmethod
  def param(key: str) -> bool:
    val = Params().get(key)
    # Robust check for boolean param represented as "1"
    return val is not None and val.decode('utf-8') == "1"

  def __init__(self, CP: car.CarParams):
    self.CP = CP
    # Instantiate the potentially modified tuning class
    self.tuning = HKGLongitudinalTuning(CP) if self.param("HKGtuning") else None
    # Initialize fallback values used if tuning is None
    self.jerk = None
    self.jerk_upper_limit = 0.0
    self.jerk_lower_limit = 0.0
    self.cb_upper = 0.0
    self.cb_lower = 0.0

  def apply_tune(self, CP: car.CarParams):
    if self.param("HKGtuning") and self.tuning is not None:
      self.tuning.apply_tune(CP)
    else:
      # Apply default parameters if tuning is disabled
      CP.vEgoStopping = 0.5
      CP.vEgoStarting = 0.1
      CP.startingState = True
      CP.startAccel = 1.0
      CP.longitudinalActuatorDelay = 0.5

  def get_jerk(self) -> JerkOutput:
    """Returns JerkOutput based on the tuning instance or defaults."""
    if self.tuning is not None:
      # Assumes make_jerk was called recently if these values are needed externally
      # The values are stored within the self.tuning instance
      return JerkOutput(
        self.tuning.jerk_upper_limit,
        self.tuning.jerk_lower_limit,
        self.tuning.cb_upper,
        self.tuning.cb_lower,
      )
    else:
      # Return the controller's fallback values if tuning is off
      return JerkOutput(
          self.jerk_upper_limit,
          self.jerk_lower_limit,
          self.cb_upper,
          self.cb_lower
      )

  def calculate_and_get_jerk(self, actuators: car.CarControl.Actuators, CS: car.CarState, long_control_state: LongCtrlState) -> JerkOutput:
    """Calculate jerk based on tuning (if active) and return JerkOutput."""
    if self.tuning is not None:
      # Delegate jerk calculation to the tuning instance
      self.tuning.make_jerk(CS, actuators) # Updates tuning internal state
    else:
      # Set default jerk limits if tuning is off
      jerk_limit = 3.0 if long_control_state == LongCtrlState.pid else 1.0
      # Update the controller's fallback values
      self.jerk_upper_limit = jerk_limit
      self.jerk_lower_limit = jerk_limit
      self.cb_upper = 0.0
      self.cb_lower = 0.0
    # Return the current jerk state (either from tuning or defaults)
    return self.get_jerk()

  def calculate_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, frogpilot_toggles) -> float:
    """Calculate final acceleration, delegating to tuning instance if active."""
    # Check if the specific tuning logic should be used
    use_tuning_logic = self.param("HKGBraking") and self.tuning is not None

    if use_tuning_logic:
        # Use the potentially modified calculate_accel from the tuning instance
        accel = self.tuning.calculate_accel(actuators, CS, frogpilot_toggles)
    else:
        # --- Fallback logic if tuning is not used ---
        max_accel_upper_limit = CarControllerParams.ACCEL_MAX
        # Example integration for frogpilot toggles (adjust as needed):
        # if hasattr(frogpilot_toggles, 'max_desired_acceleration'):
        #    max_accel_upper_limit = min(frogpilot_toggles.max_desired_acceleration, max_accel_upper_limit)

        # Default clipping if no special modes or tuning active
        accel = float(np.clip(actuators.accel, CarControllerParams.ACCEL_MIN, max_accel_upper_limit))

    return accel