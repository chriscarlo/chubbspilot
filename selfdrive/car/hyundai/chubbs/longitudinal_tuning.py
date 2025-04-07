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

# In HKGLongitudinalTuning class:
class HKGLongitudinalTuning:
    """Longitudinal tuning methodology for Hyundai vehicles."""
    # FIX: Rename init to __init__
    def __init__(self, CP: car.CarParams) -> None:
        self.CP = CP
        # Ensure params is initialized early if needed by other setup methods
        self._setup_controllers() # Sets self.params
        self._init_state()
        self._mode_setup()
        self._setup_car_config()

    def _setup_controllers(self) -> None:
        self.mpc = LongitudinalMpc # Reference, not instance
        self.long_control = LongControl(self.CP)
        # SubMaster initialization moved to where it's used to avoid issues if not run in a process
        self.sm = None
        self.DT_CTRL = DT_CTRL
        # FIX: Ensure Params() is initialized here
        self.params = Params()

    # ... (rest of HKGLongitudinalTuning methods remain largely the same)

    # Example: Fix within calculate_accel if it needed its own check (it already has one)
    def calculate_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, frogpilot_toggles, sm_dict: dict) -> float:
        """Calculate acceleration with cruise control status handling and dynamic limits."""
        # Make sure params is available if needed within methods
        if self.params is None: # Good practice, though __init__ should guarantee it
            print("WARN: HKGLongitudinalTuning.params was None, re-initializing.")
            self.params = Params()

        if self.handle_cruise_cancel(CS):
            # On cancel, return 0 or a safe value, reset last accel state
            self.accel_last = 0.0
            return 0.0

        # Calculate rate-limited acceleration based on planner input and current state
        accel = self.calculate_limited_accel(actuators, CS, sm_dict)

        # --- Dynamic Acceleration Limits ---
        normal_decel_limit = self.car_config.accel_limits[0]
        # Use frogpilot_toggles.max_desired_acceleration if available, else use car_config or default
        default_car_accel_limit = self.car_config.accel_limits[1] if hasattr(self.car_config, 'accel_limits') else CarControllerParams.ACCEL_MAX
        normal_accel_limit = min(getattr(frogpilot_toggles, 'max_desired_acceleration', default_car_accel_limit), default_car_accel_limit)


        # Define desired acceleration points for limit transition
        xp_limit = sorted([normal_decel_limit * 1.5, normal_decel_limit * 0.9])
        fp_limit = [PANIC_DECEL_LIMIT, normal_decel_limit]

        effective_decel_limit = np.interp(actuators.accel, xp_limit, fp_limit)

        final_accel = float(np.clip(accel, effective_decel_limit, normal_accel_limit)) # Start with normal accel limit

        # Apply sport mode / HKGBraking adjustments if necessary
        # Check if params object exists before using get_bool
        hkg_braking_param = self.params.get_bool("HKGBraking") if self.params else False

        # Use getattr for frogpilot_toggles attributes for safety
        sport_plus_active = getattr(frogpilot_toggles, 'sport_plus', False)
        max_desired_accel_fp = getattr(frogpilot_toggles, 'max_desired_acceleration', CarControllerParams.ACCEL_MAX)

        if sport_plus_active:
            # Regardless of HKGBraking, Sport+ uses dynamic decel and potentially higher accel limit
            sport_accel_limit = min(max_desired_accel_fp, get_max_allowed_accel(CS.out.vEgo))
            final_accel = float(np.clip(accel, effective_decel_limit, sport_accel_limit))
        # Note: The original code had slightly complex conditions for HKGBraking without sport+.
        # The current logic applies dynamic decel always, and sport+ overrides the upper limit.
        # If HKGBraking without sport+ needs a *different* upper limit than standard, add condition here.
        # Example:
        # elif hkg_braking_param:
        #     # Apply specific HKGBraking upper limit if needed (currently handled by normal_accel_limit)
        #     pass


        # self.accel_last was updated in calculate_limited_accel
        return final_accel

# ---

# In JerkOutput class:
class JerkOutput:
    # FIX: Rename init to __init__
    def __init__(self, jerk_upper_limit, jerk_lower_limit, cb_upper, cb_lower):
        self.jerk_upper_limit = jerk_upper_limit
        self.jerk_lower_limit = jerk_lower_limit
        self.cb_upper = cb_upper
        self.cb_lower = cb_lower

# ---

# In HKGLongitudinalController class:
class HKGLongitudinalController:
    """Longitudinal controller which gets injected into CarControllerParams."""
    @staticmethod
    def param(key: str) -> bool:
        # Use a temporary Params() instance if needed, or ensure it's initialized
        val = Params().get(key)
        return val is not None and val == b"1"

    # FIX: Rename init to __init__
    def __init__(self, CP: car.CarParams):
        self.CP = CP
        # Initialize Params instance for the controller
        self.params = Params() # Now self.params is correctly initialized
        # Ensure HKGtuning param check uses the instance's params
        # FIX: Use self.params which is now guaranteed to be a Params object
        self.tuning = HKGLongitudinalTuning(CP) if self.params.get_bool("HKGtuning") else None
        self.jerk = None # Is this used? Seems overshadowed by tuning's jerk
        self.jerk_upper_limit = 0.0 # Redundant? get_jerk uses tuning's values
        self.jerk_lower_limit = 0.0 # Redundant?
        self.cb_upper = 0.0 # Redundant?
        self.cb_lower = 0.0 # Redundant?
        # Initialize SubMaster here for use in calculate_accel
        self.sm = messaging.SubMaster(['controlsState'])

    def apply_tune(self, CP: car.CarParams):
        # Use instance's params object (guaranteed by __init__)
        if self.params.get_bool("HKGtuning") and self.tuning is not None:
            self.tuning.apply_tune(CP)
        else:
            # Default fallback values
            CP.vEgoStopping = 0.5
            CP.vEgoStarting = 0.1
            CP.startingState = True
            CP.startAccel = 1.0
            CP.longitudinalActuatorDelay = 0.5

    def get_jerk(self) -> JerkOutput:
        if self.tuning is not None:
            # Values should be populated by the call to tuning.calculate_accel
            return JerkOutput(
                self.tuning.jerk_upper_limit,
                self.tuning.jerk_lower_limit,
                self.tuning.cb_upper,
                self.tuning.cb_lower,
            )
        else:
            # Fallback if tuning is disabled
            default_jerk = 3.0 # Example default
            # Maybe update self members if these are used elsewhere?
            self.jerk_upper_limit = default_jerk
            self.jerk_lower_limit = default_jerk
            self.cb_upper = 0.0
            self.cb_lower = 0.0
            return JerkOutput(default_jerk, default_jerk, 0.0, 0.0)

    # This method seems redundant if get_jerk exists and make_jerk is called within calculate_accel path
    # def calculate_and_get_jerk(self, actuators: car.CarControl.Actuators, CS: car.CarState, long_control_state: LongCtrlState) -> JerkOutput:
    #     """Calculate jerk based on tuning and return JerkOutput."""
    #     # ... (Implementation depends on whether this needs to calculate or just retrieve)
    #     # For now, assume get_jerk() is sufficient after calculate_accel runs.
    #     return self.get_jerk()


    def calculate_accel(self, actuators: car.CarControl.Actuators, CS: car.CarState, frogpilot_toggles) -> float:
        """Calculate acceleration based on tuning and return the value."""
        # FIX: Update SubMaster *before* accessing data
        self.sm.update(0)
        # Use empty dict if not updated, pass it down regardless
        sm_dict = self.sm.data if self.sm.updated['controlsState'] else {}

        # FIX: self.params is now guaranteed to be a Params object from __init__
        if self.params.get_bool("HKGtuning") and self.tuning is not None:
            # Pass sm_dict down for mode transition logic
            # This call will handle all the dynamic limiting logic internally
            accel = self.tuning.calculate_accel(actuators, CS, frogpilot_toggles, sm_dict)
        else:
            # Default behavior without HKGtuning
            # Apply basic panic clipping logic similar to the tuned version

            # Basic Panic Decel Limit application
            normal_decel_limit = CarControllerParams.ACCEL_MIN # Use generic limit
            xp_limit = sorted([normal_decel_limit * 1.5, normal_decel_limit * 0.9])
            fp_limit = [PANIC_DECEL_LIMIT, normal_decel_limit]
            effective_decel_limit = np.interp(actuators.accel, xp_limit, fp_limit)

            # Determine upper limit based on frogpilot toggles or defaults
            # Use getattr for safety
            sport_plus_active = getattr(frogpilot_toggles, 'sport_plus', False)
            max_desired_accel_fp = getattr(frogpilot_toggles, 'max_desired_acceleration', CarControllerParams.ACCEL_MAX)

            if sport_plus_active:
                accel_max = min(max_desired_accel_fp, get_max_allowed_accel(CS.out.vEgo))
            else:
                # Use max_desired_acceleration if available, otherwise default ACCEL_MAX
                accel_max = min(max_desired_accel_fp, CarControllerParams.ACCEL_MAX)

            # Apply simple clipping (rate limiting could be added if desired for non-tuned mode)
            accel = float(np.clip(actuators.accel, effective_decel_limit, accel_max))

        return accel