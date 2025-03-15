import math
import numpy as np
import cereal.messaging as messaging
import os
import time
import pickle
from collections import deque

from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.controls.lib.drive_helpers import V_CRUISE_MAX
from openpilot.selfdrive.modeld.constants import ModelConstants

# -----------------------
#   LATERAL ACCELERATION
# -----------------------
def nonlinear_lat_accel(v_ego_ms: float, turn_aggressiveness: float = 1.0) -> float:
    """
    Allows up to ~3.2 m/s^2 (≈0.33g) of lateral acceleration at higher speeds,
    with a smooth logistic transition starting from lower values (~1.4 m/s^2) at low speeds.
    This provides more conservative cornering at lower speeds while maintaining
    the desired behavior at highway speeds.
    """
    v_ego_mph = v_ego_ms * CV.MS_TO_MPH

    base = 1.4     # Lower base value (more conservative at low speeds)
    span = 1.8     # Additional range to reach the desired max
    center = 30.0  # Speed (mph) around which the logistic is centered
    k = 0.10       # Slope factor
    lat_acc = base + span / (1 + math.exp(-k * (v_ego_mph - center)))
    lat_acc = min(lat_acc, 3.2)  # Maximum lateral acceleration limit

    return lat_acc * turn_aggressiveness


def find_apexes(curv_array: np.ndarray, threshold: float = 5e-5) -> list:
    """
    Identify 'peaks' in curvature.
    This logic is largely unchanged from your snippet: we look for points
    that exceed the threshold and are local maxima.
    """
    apex_indices = []
    for i in range(1, len(curv_array) - 1):
        if (
            curv_array[i] > threshold
            and curv_array[i] >= curv_array[i + 1]
            and curv_array[i] > curv_array[i - 1]
        ):
            apex_indices.append(i)
    return apex_indices


# --------------------
#   DECEL/ACCEL SCALES
# --------------------
def dynamic_decel_scale(v_ego_ms: float) -> float:
    """
    Smooth function that transitions from 8.0 at 5m/s to 2.0 at 25m/s
    using a polynomial. (No direct torque scaling.)
    """
    min_speed = 5.0
    max_speed = 25.0
    min_scale = 2.0
    max_scale = 8.0

    if v_ego_ms <= min_speed:
        return max_scale
    elif v_ego_ms >= max_speed:
        return min_scale
    else:
        pos = (v_ego_ms - min_speed) / (max_speed - min_speed)
        return max_scale - (max_scale - min_scale) * (3 * pos**2 - 2 * pos**3)


def dynamic_accel_scale(v_ego_ms: float) -> float:
    """
    Similar logic for acceleration scale, referencing the decel scale.
    """
    decel_scale = dynamic_decel_scale(v_ego_ms)
    if v_ego_ms < 10.0:
        return decel_scale * 1.5
    else:
        # reduce from 1.5 down to 1.0 in the range [10 m/s, ∞)
        return decel_scale * max(1.0, 1.5 - 0.05 * (v_ego_ms - 10.0))


def dynamic_jerk_scale(v_ego_ms: float) -> float:
    """
    Keep jerk scale consistent with decel scale (or do your own logic).
    """
    return dynamic_decel_scale(v_ego_ms)


def margin_time_fn(v_ego_ms: float) -> float:
    """
    Time-based margin function.
    - 0 m/s → 1.5s
    - 15 m/s → 3.5s
    - 31.3 m/s (~70 mph) → 5.5s
    """
    v_low, t_low = 0.0, 1.5
    v_med, t_med = 15.0, 3.5
    v_high, t_high = 31.3, 5.5

    if v_ego_ms <= v_low:
        return t_low
    elif v_ego_ms >= v_high:
        return t_high
    elif v_ego_ms <= v_med:
        ratio = (v_ego_ms - v_low) / (v_med - v_low)
        return t_low + ratio * (t_med - t_low)
    else:
        ratio = (v_ego_ms - v_med) / (v_high - v_med)
        return t_med + ratio * (t_high - t_med)


# ------------
#   NEW HELPERS
# ------------
def logistic_transition(x, center, scale, lo, hi):
    """
    A continuous logistic that transitions from lo to hi around 'center'.
    """
    return lo + (hi - lo) / (1 + math.exp(-(x - center) / scale))


def early_approach_time_fn(apex_speed: float) -> float:
    """
    Logistic-based function for how many seconds in advance to start your apex approach decel.
    E.g. from 2.0s at ~8 m/s to 3.0s at ~22 m/s.
    """
    return logistic_transition(x=apex_speed, center=15.0, scale=3.0, lo=2.0, hi=3.0)


def early_spool_time_fn(apex_speed: float) -> float:
    """
    Logistic-based function for how many seconds in advance to start spool-up after an apex.
    E.g. from 1.0s at ~8 m/s to 2.0s at ~22 m/s.
    """
    return logistic_transition(x=apex_speed, center=15.0, scale=3.0, lo=1.0, hi=2.0)


def short_horizon_factor(horizon_time: float) -> float:
    """
    A logistic factor from ~0.4 (horizon=1.5s) up to ~1.0 (horizon=4.0s).
    This can slightly re-limit spool-ups if horizon is short.
    """
    raw = logistic_transition(horizon_time, center=2.75, scale=0.75, lo=0.4, hi=1.0)
    return clip(raw, 0.4, 1.0)


# -----------------------
#   STEERING TORQUE SATURATION
# -----------------------
class SteeringTorqueSaturationPredictor:
    """
    Predicts and learns how much steering torque is needed to hold a given
    curvature at a given speed, factoring in road banking if desired.

    Key points:
    - We do *not* reduce max torque by speed. It's always 409 (with margin).
    - We keep a mild exponential average for error to avoid jitter.
    - We have a short 'calibration phase' for the first N samples that uses a
      higher learning rate.
    - We have a special 'driver intervention learn' to heavily weight user overrides.
    - We load/save basic model state to disk so that learning persists across reboots.
    """

    def __init__(self, vehicle_params, debug=False):
        # Basic vehicle parameters
        self.VEHICLE_MASS = vehicle_params.mass
        self.STEERING_RATIO = vehicle_params.steerRatio
        # Always assume 409 raw torque is max
        self.MAX_STEER_TORQUE = 409
        # If you want a margin, you can do .85, but you can also set it to 1.0 if you prefer
        self.TORQUE_MARGIN = 1.0  # No margin initially - be completely passive
        self.WHEELBASE = vehicle_params.wheelbase

        self.MODEL_SCALE_FACTOR = 0.01  # previously '0.01' in your code

        # Baseline learning parameters
        self.learning_rate = 0.02
        self.ema_alpha = 0.01  # Smoothing factor for error

        # Calibration-phase overrides
        self.initial_calibration_samples = 100  # faster adaptation for the first 100 samples
        self.calibration_learning_rate = 0.10
        self.calibration_ema_alpha = 0.05

        # Internal state - starting very permissive
        self.sensitivity_factor = 2.0  # Start extremely permissive (higher = more permissive)
        self.torque_error_ema = 0.0
        self.confidence = 0.5  # Start with low confidence

        # Passive mode control
        self.passive_mode = True  # Start in passive mode
        self.saturation_count = 0
        self.saturation_threshold_pct = 0.95  # Only consider >95% of max torque as saturation

        self.last_update_time = 0
        self.last_pred_required_torque = 0
        self.last_actual_torque = 0
        self.last_curvature = 0
        self.last_speed = 0

        # For storing recent samples in memory (not on disk)
        self.samples = deque(maxlen=1000)
        self.debug = debug

        # Path to save parameters - use repo-local path
        self.param_path = "selfdrive/frogpilot/model_weights/torque_predictor.pkl"

        # Logging
        self.last_log_time = 0
        self.log_frequency = 5.0

        # Load existing model if it exists
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(self.param_path):
                with open(self.param_path, 'rb') as f:
                    data = pickle.load(f)
                    self.sensitivity_factor = data.get('sensitivity_factor', 2.0)
                    self.confidence = data.get('confidence', 0.5)
                    self.passive_mode = data.get('passive_mode', True)
                    self.saturation_count = data.get('saturation_count', 0)
                    self.saturation_threshold_pct = data.get('saturation_threshold_pct', 0.95)
                    self.TORQUE_MARGIN = data.get('torque_margin', 1.0)
                    road_bank_stats = data.get('road_bank_stats', {})
                    if self.debug and road_bank_stats:
                        print(f"Loaded road bank stats: mean={road_bank_stats.get('mean', 0.0):.4f}, "
                              f"std={road_bank_stats.get('std', 0.0):.4f}, "
                              f"min={road_bank_stats.get('min', 0.0):.4f}, "
                              f"max={road_bank_stats.get('max', 0.0):.4f}")
                    if self.debug:
                        print(f"Loaded torque model: sensitivity={self.sensitivity_factor}, confidence={self.confidence}")
        except Exception as e:
            if self.debug:
                print(f"Error loading torque model: {e}")
            self.sensitivity_factor = 2.0
            self.confidence = 0.5
            self.passive_mode = True
            self.saturation_count = 0
            self.saturation_threshold_pct = 0.95
            self.TORQUE_MARGIN = 1.0

    def _save_model(self):
        try:
            # Summarize road bank in your history if desired
            road_bank_samples = [s['road_bank'] for s in self.samples if 'road_bank' in s]
            road_bank_stats = {
                'mean': np.mean(road_bank_samples) if road_bank_samples else 0.0,
                'std':  np.std(road_bank_samples) if road_bank_samples else 0.0,
                'min':  min(road_bank_samples) if road_bank_samples else 0.0,
                'max':  max(road_bank_samples) if road_bank_samples else 0.0,
            }
            data = {
                'sensitivity_factor': self.sensitivity_factor,
                'confidence': self.confidence,
                'passive_mode': self.passive_mode,
                'saturation_count': self.saturation_count,
                'saturation_threshold_pct': self.saturation_threshold_pct,
                'torque_margin': self.TORQUE_MARGIN,
                'timestamp': time.time(),
                'road_bank_stats': road_bank_stats
            }
            os.makedirs(os.path.dirname(self.param_path), exist_ok=True)
            with open(self.param_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            if self.debug:
                print(f"Error saving torque model: {e}")

    def log_telemetry(self, curvature, speed, required_torque, available_torque, torque_limited=False, road_bank=0.0):
        """
        Rate-limit logging so we don't spam at high frequency.
        """
        current_time = time.time()
        if current_time - self.last_log_time < self.log_frequency:
            return
        self.last_log_time = current_time

        gravity_component = 9.81 * math.sin(road_bank)
        cloudlog.event(
            "torque_predictor",
            curvature=curvature,
            speed=speed,
            required_torque=required_torque,
            available_torque=available_torque,
            torque_limited=torque_limited,
            sensitivity_factor=self.sensitivity_factor,
            confidence=self.confidence,
            samples_count=len(self.samples),
            passive_mode=self.passive_mode,
            saturation_count=self.saturation_count,
            road_bank=road_bank,
            gravity_component=gravity_component
        )

    def estimate_required_torque(self, curvature, speed, road_bank=0.0) -> float:
        """
        Simplified physics approach:
          required_torque = (lateral_acc - g*sin(bank)) * mass * steer_ratio * MODEL_SCALE_FACTOR * sensitivity
        """
        lateral_accel = (speed**2) * curvature
        gravity_component = 9.81 * math.sin(road_bank)
        effective_lat_accel = lateral_accel - gravity_component

        required_torque = effective_lat_accel * self.VEHICLE_MASS * self.STEERING_RATIO * self.MODEL_SCALE_FACTOR
        required_torque *= self.sensitivity_factor
        return required_torque

    def get_max_available_torque(self) -> float:
        # If in passive mode, return very high value effectively disabling limiting
        if self.passive_mode:
            return 9999.0
        # Otherwise apply the margin
        return self.MAX_STEER_TORQUE * self.TORQUE_MARGIN

    def solve_for_torque_limited_speed(self, curvature, max_torque, road_bank=0.0):
        """
        If we are torque-limited, solve speed from:
          speed^2 = ( (max_torque/(mass*steer_ratio*scale*sens)) + g*sin(bank) ) / curvature

        This does *not* reduce torque at higher speeds explicitly. It's purely
        whether you exceed that 409-based limit or not.
        """
        if curvature < 1e-9:
            return 70.0  # effectively no curve, or a very gentle one
        gravity_component = 9.81 * math.sin(road_bank)
        denom = self.VEHICLE_MASS * self.STEERING_RATIO * self.MODEL_SCALE_FACTOR * self.sensitivity_factor
        torque_factor = max_torque / denom
        adjusted_factor = torque_factor + gravity_component
        if adjusted_factor <= 0.0:
            return 0.1  # avoid sqrt of negative
        return math.sqrt(adjusted_factor / curvature)

    def detect_saturation_event(self, actual_torque):
        """
        Detect if we're seeing a potential steering saturation event
        """
        saturation_threshold = self.MAX_STEER_TORQUE * self.saturation_threshold_pct

        if abs(actual_torque) > saturation_threshold:
            self.saturation_count += 1

            # If we detect a saturation event and are in passive mode,
            # start transitioning out of passive mode
            if self.passive_mode and self.saturation_count >= 1:
                self.passive_mode = False
                self.TORQUE_MARGIN = 1.0  # Changed from 0.95 to 1.0 - no margin

            return True
        return False

    def update_with_measurement(self, actual_torque, last_curvature, last_speed, road_bank=0.0):
        """
        Normal streaming updates from observed torque.
        """
        # Check for saturation events
        saturation_detected = self.detect_saturation_event(actual_torque)

        # Filter out cases of very low curvature or speed - these aren't useful for learning
        # Also filter out unrealistically high speeds and extreme road banking
        if (last_curvature < 5e-5 or  # Increased threshold to focus on actual curves
            last_speed < 1.0 or
            last_speed > V_CRUISE_MAX * CV.KPH_TO_MS or  # Using V_CRUISE_MAX converted to m/s
            abs(road_bank) > 0.26):  # ~15 degrees in radians
            return

        self.last_update_time = time.time()
        predicted_torque = self.estimate_required_torque(last_curvature, last_speed, road_bank)
        torque_error = actual_torque - predicted_torque

        # Keep sample
        self.samples.append({
            'curvature': last_curvature,
            'speed': last_speed,
            'predicted_torque': predicted_torque,
            'actual_torque': actual_torque,
            'error': torque_error,
            'timestamp': self.last_update_time,
            'road_bank': road_bank,
            'intervention': False,
            'saturation': saturation_detected,
        })

        # Decide if we're in calibration phase
        if len(self.samples) < self.initial_calibration_samples:
            current_learning_rate = self.calibration_learning_rate
            current_ema_alpha = self.calibration_ema_alpha
        else:
            current_learning_rate = self.learning_rate
            current_ema_alpha = self.ema_alpha

        # Update torque_error_ema
        self.torque_error_ema = (
            (1.0 - current_ema_alpha) * self.torque_error_ema
            + current_ema_alpha * torque_error
        )

        # Adjust sensitivity factor if we've detected saturation or high torque
        high_torque_sample = abs(actual_torque) > (self.MAX_STEER_TORQUE * 0.75)
        if (not self.passive_mode or saturation_detected or high_torque_sample) and abs(predicted_torque) > 1e-3:
            error_ratio = self.torque_error_ema / predicted_torque
            adjustment = current_learning_rate * error_ratio
            new_sens = self.sensitivity_factor * (1 + adjustment)
            self.sensitivity_factor = clip(new_sens, 0.5, 3.0)  # Allow higher upper bound

        # Update confidence - gradually increase with more samples
        if not self.passive_mode:
            sample_confidence_factor = min(1.0, len(self.samples) / 500.0)
            target_confidence = 0.5 + (sample_confidence_factor * 0.4)
            self.confidence = 0.99 * self.confidence + 0.01 * target_confidence

        # Periodically save model or save immediately on saturation
        if len(self.samples) % 100 == 0 or saturation_detected:
            self._save_model()

        # Store last
        self.last_pred_required_torque = predicted_torque
        self.last_actual_torque = actual_torque
        self.last_curvature = last_curvature
        self.last_speed = last_speed

    def driver_intervention_learn(self, intervention_torque, curvature, speed, road_bank=0.0):
        """
        Special heavier weighting if the driver intervenes to correct understeer/oversteer,
        or if they press gas/brake. We treat it like a big update so the system "learns" quickly.
        """
        # Filter out cases of very low curvature or speed - these aren't useful for learning
        # Also filter out unrealistically high speeds and extreme road banking
        if (curvature < 5e-5 or  # Increased threshold to focus on actual curves
            speed < 1.0 or
            speed > V_CRUISE_MAX * CV.KPH_TO_MS or  # Using V_CRUISE_MAX converted to m/s
            abs(road_bank) > 0.26):  # ~15 degrees in radians
            return

        # If they're intervening, exit passive mode immediately
        self.passive_mode = False
        self.TORQUE_MARGIN = 1.0  # Changed from 0.95 to 1.0 - no margin

        predicted_torque = self.estimate_required_torque(curvature, speed, road_bank)
        torque_error = intervention_torque - predicted_torque

        # We scale up the error so it has a bigger effect
        intervention_factor = 5.0
        torque_error *= intervention_factor

        # Big alpha so we push the EMA strongly
        big_alpha = 0.2
        self.torque_error_ema = (
            (1.0 - big_alpha) * self.torque_error_ema
            + big_alpha * torque_error
        )

        # Increase sensitivity factor if error is positive, reduce if negative
        if abs(predicted_torque) > 1e-3:
            error_ratio = self.torque_error_ema / predicted_torque
            # Multiply by 5.0 for a bigger step
            new_sens = self.sensitivity_factor * (1 + self.learning_rate * 5.0 * error_ratio)
            self.sensitivity_factor = clip(new_sens, 0.5, 3.0)

        # Optionally store a sample
        self.samples.append({
            'curvature': curvature,
            'speed': speed,
            'predicted_torque': predicted_torque,
            'actual_torque': intervention_torque,
            'error': torque_error,
            'timestamp': time.time(),
            'road_bank': road_bank,
            'intervention': True,
        })

        # Save the model right away if desired
        self._save_model()

    def apply_model_confidence(self, safe_speed, curvature):
        """
        If you want to reduce safe speed for lower confidence, you can do:
          safe_speed *= (0.7 + 0.3 * self.confidence).
        This is purely optional. It does not scale with speed, just scales by confidence.
        """
        if curvature < 1e-5 or self.passive_mode:
            return safe_speed
        return safe_speed * (0.7 + 0.3 * self.confidence)


# --------------------------
#   MAIN TURN SPEED CONTROLLER
# --------------------------
class VisionTurnSpeedController:
    def __init__(
        self,
        turn_smoothing_alpha=0.3,
        reaccel_alpha=0.2,
        low_lat_acc=0.20,
        high_lat_acc=0.40,
        max_decel=3.0,
        max_jerk=6.0,
        max_accel=None,
        max_jerk_accel=None,
        emergency_decel=6.0,
        emergency_speed_tolerance=2.0,
        emergency_lookahead_frames=8,
    ):
        """
        The main speed planner. We incorporate the updated torque predictor that
        does NOT reduce torque availability at higher speeds. It's always 409-based.

        Also includes a placeholder for calling 'driver_intervention_learn'
        if we detect the driver is overriding.
        """
        self.turn_smoothing_alpha = turn_smoothing_alpha
        self.reaccel_alpha = reaccel_alpha
        self.LOW_LAT_ACC = low_lat_acc
        self.HIGH_LAT_ACC = high_lat_acc

        self.MAX_DECEL = max_decel
        self.MAX_JERK = max_jerk
        self.MAX_ACCEL = max_accel if max_accel is not None else (2.0 * max_decel)
        self.MAX_JERK_ACCEL = max_jerk_accel if max_jerk_accel is not None else (2.0 * max_jerk)

        self.EMERGENCY_DECEL = emergency_decel
        self.EMERGENCY_SPEED_TOLERANCE = emergency_speed_tolerance
        self.EMERGENCY_LOOKAHEAD_FRAMES = emergency_lookahead_frames

        self.current_accel = 0.0
        self.prev_target_speed = 0.0
        self.prev_v_cruise_cluster = 0.0

        self.sm = messaging.SubMaster(['modelV2', 'carState', 'liveParameters'])

        # Example vehicle params (Kia EV6)
        self.vehicle_params = type('obj', (), {
            'mass': 2055,
            'wheelbase': 2.9,
            'steerRatio': 16.0,
        })

        self.torque_predictor = SteeringTorqueSaturationPredictor(self.vehicle_params)

        self.last_cruise_nonzero = False
        self.current_road_bank = 0.0
        self.last_curvature = 0.0

    def reset(self, speed: float) -> None:
        self.prev_target_speed = speed
        self.current_accel = 0.0

    def update(self, v_ego: float, v_cruise_cluster: float, turn_aggressiveness=1.0) -> float:
        """
        Main method for generating a target speed given:
        - current speed (v_ego)
        - cruise set speed (v_cruise_cluster)
        - optional turn aggressiveness
        """
        self.sm.update()
        model_data = self.sm['modelV2']
        car_state = self.sm['carState']

        # Update current road bank if available
        if self.sm.updated['liveParameters']:
            self.current_road_bank = self.sm['liveParameters'].roll

        # Example: if the user is pressing steering, or gas or brake, you might call:
        if car_state.steeringPressed:
            # e.g. if they are actively steering, maybe they are correcting
            self.torque_predictor.driver_intervention_learn(
                intervention_torque=car_state.steeringTorque,
                curvature=self.last_curvature,
                speed=v_ego,
                road_bank=self.current_road_bank
            )
        elif car_state.gasPressed:
            # user wants more speed → treat it as negative error (we under-shot)
            self.torque_predictor.driver_intervention_learn(
                intervention_torque=-999,  # or some big negative
                curvature=self.last_curvature,
                speed=v_ego,
                road_bank=self.current_road_bank
            )
        elif car_state.brakePressed:
            # user wants less speed → treat it as positive error (we over-shot)
            self.torque_predictor.driver_intervention_learn(
                intervention_torque=999,  # or some big positive
                curvature=self.last_curvature,
                speed=v_ego,
                road_bank=self.current_road_bank
            )

        # Now do the normal streaming update with actual torque
        if hasattr(car_state, 'steeringTorque'):
            # We only do an update if there's some meaningful torque
            if abs(car_state.steeringTorque) > 0.5:
                self.torque_predictor.update_with_measurement(
                    car_state.steeringTorque,
                    self.last_curvature,
                    v_ego,
                    self.current_road_bank
                )

        # If we just resumed from 0 → some nonzero speed
        is_real_resume = (not self.last_cruise_nonzero) and (v_cruise_cluster > 1e-1)
        self.last_cruise_nonzero = (v_cruise_cluster > 1e-1)
        if is_real_resume:
            self.reset(v_cruise_cluster)
            self.prev_v_cruise_cluster = v_cruise_cluster
            return v_cruise_cluster

        raw_safe_speed = self._compute_raw_safe_speed(model_data, v_ego, turn_aggressiveness)
        final_raw = min(raw_safe_speed, v_cruise_cluster)

        # Single-step jerk-limited smoothing
        dt = 0.05
        scale_decel = dynamic_decel_scale(v_ego)
        scale_accel = dynamic_accel_scale(v_ego)
        scale_jerk  = dynamic_jerk_scale(v_ego)

        emergency_decel_active = (self.prev_target_speed > final_raw + self.EMERGENCY_SPEED_TOLERANCE)

        max_decel_now = self.MAX_DECEL * scale_decel
        max_accel_now = self.MAX_ACCEL * scale_accel
        max_jerk_now  = self.MAX_JERK * scale_jerk
        max_jerk_accel_now = self.MAX_JERK_ACCEL * scale_jerk

        if emergency_decel_active:
            max_decel_now = max(max_decel_now, self.EMERGENCY_DECEL)

        accel_cmd = (final_raw - self.prev_target_speed) / dt
        if accel_cmd >= 0.0:
            accel_cmd = clip(accel_cmd, 0.0, max_accel_now)
        else:
            accel_cmd = clip(accel_cmd, -max_decel_now, 0.0)

        accel_diff = accel_cmd - self.current_accel
        if accel_diff > 0:
            max_delta = max_jerk_accel_now * dt
            if accel_diff > max_delta:
                self.current_accel += max_delta
            else:
                self.current_accel = accel_cmd
        elif accel_diff < 0:
            max_delta = max_jerk_now * dt
            if accel_diff < -max_delta:
                self.current_accel -= max_delta
            else:
                self.current_accel = accel_cmd

        next_target_speed = self.prev_target_speed + self.current_accel * dt
        next_target_speed = min(next_target_speed, v_cruise_cluster, raw_safe_speed)

        self.prev_target_speed = next_target_speed
        self.prev_v_cruise_cluster = v_cruise_cluster

        return next_target_speed

    # ------------------------
    #  Build raw safe speed
    # ------------------------
    def _compute_raw_safe_speed(self, model_data, v_ego, turn_aggressiveness) -> float:
        orientation_rate_raw = model_data.orientationRate.z
        velocity_pred_raw = model_data.velocity.x

        if orientation_rate_raw is None or velocity_pred_raw is None:
            return 30.0

        orientation_rate = np.abs(np.array(orientation_rate_raw, dtype=float))
        velocity_pred = np.array(velocity_pred_raw, dtype=float)
        n_points = min(len(orientation_rate), len(velocity_pred))
        if n_points < 3:
            return 22.0  # fallback

        # Resample to 33 points if needed
        if n_points < 33:
            src_indices = np.linspace(0, n_points - 1, n_points)
            dst_indices = np.linspace(0, n_points - 1, 33)
            orientation_rate_33 = np.interp(dst_indices, src_indices, orientation_rate[:n_points])
            velocity_pred_33 = np.interp(dst_indices, src_indices, velocity_pred[:n_points])
        else:
            orientation_rate_33 = orientation_rate[:33]
            velocity_pred_33 = velocity_pred[:33]

        times_33 = np.array(ModelConstants.T_IDXS[:33], dtype=float)
        eps = 1e-9
        curvature_33 = orientation_rate_33 / np.clip(velocity_pred_33, eps, None)

        if max(curvature_33) < 1e-5:
            return 30.0

        valid_pts = np.where(velocity_pred_33 > 0.01)[0]
        if len(valid_pts) == 0:
            return 30.0
        horizon_idx = valid_pts[-1]
        horizon_time = times_33[horizon_idx]

        planned_speeds = self._plan_speed_trajectory(
            orientation_rate_33,
            velocity_pred_33,
            curvature_33,
            times_33,
            v_ego,
            turn_aggressiveness,
            horizon_time
        )
        return planned_speeds[0]

    def _plan_speed_trajectory(
        self,
        orientation_rate: np.ndarray,
        velocity_pred: np.ndarray,
        curvature: np.ndarray,
        times: np.ndarray,
        v_ego: float,
        turn_aggressiveness: float,
        horizon_time: float
    ) -> np.ndarray:
        n = len(orientation_rate)
        dt_array = np.diff(times)
        eps = 1e-9

        # 1) Basic curvature-limited speeds + torque limit
        safe_speeds = np.zeros(n, dtype=float)
        max_torque = self.torque_predictor.get_max_available_torque()

        for i in range(n):
            lat_acc_limit = nonlinear_lat_accel(velocity_pred[i], turn_aggressiveness)
            c = max(curvature[i], eps)
            s = math.sqrt(lat_acc_limit / c)  # lat-acc-limited speed

            # Torque-limited check - only if not in passive mode
            required_torque = self.torque_predictor.estimate_required_torque(c, s, self.current_road_bank)
            torque_limited = False

            # Only apply torque limiting if not in passive mode
            if (not self.torque_predictor.passive_mode and required_torque > max_torque):
                torque_limited = True
                torque_limited_speed = self.torque_predictor.solve_for_torque_limited_speed(
                    c, max_torque, self.current_road_bank
                )
                s = min(s, torque_limited_speed)

            # Confidence factor - only if not in passive mode
            if not self.torque_predictor.passive_mode:
                s = self.torque_predictor.apply_model_confidence(s, c)

            # Log only for i == 0 to avoid spam
            if i == 0:
                self.torque_predictor.log_telemetry(
                    c, s, required_torque, max_torque, torque_limited, self.current_road_bank
                )
            safe_speeds[i] = s

        planned = safe_speeds.copy()

        # For learning updates in the next cycle
        self.last_curvature = curvature[0]

        # 2) Identify apexes
        apex_idxs = find_apexes(curvature, threshold=5e-5)
        spool_mult = short_horizon_factor(horizon_time)

        for apex_i in apex_idxs:
            apex_speed = planned[apex_i]

            # approach apex earlier
            decel_sec = early_approach_time_fn(apex_speed)
            # spool out
            spool_sec = early_spool_time_fn(apex_speed)

            decel_start = self._find_time_index(times, times[apex_i] - decel_sec)
            spool_start = self._find_time_index(times, times[apex_i] - spool_sec)
            spool_end = self._find_time_index(times, times[apex_i] + spool_sec, clip_high=True)

            # Ramp down into apex
            if spool_start > decel_start:
                v_decel_start = planned[decel_start]
                steps_decel = spool_start - decel_start
                for idx in range(decel_start, spool_start):
                    f = (idx - decel_start) / float(steps_decel)
                    f_curve = f**2
                    decel_val = v_decel_start * (1 - f_curve) + apex_speed * f_curve
                    planned[idx] = min(planned[idx], decel_val)

            # Force apex zone
            for idx in range(spool_start, apex_i + 1):
                planned[idx] = min(planned[idx], apex_speed)

            # Spool up out of apex
            if spool_end > apex_i:
                steps_spool = spool_end - apex_i
                v_spool_end = planned[spool_end - 1]
                for idx in range(apex_i, spool_end):
                    f = (idx - apex_i) / float(steps_spool)
                    f_curve = math.sqrt(f)
                    spool_val = apex_speed * (1 - f_curve) + v_spool_end * f_curve
                    spool_val *= spool_mult
                    planned[idx] = max(planned[idx], spool_val)

        # 3) Standard backward pass
        decel_mult = 1.0
        for i in range(n - 2, -1, -1):
            dt_i = dt_array[i] if i < len(dt_array) else 0.05
            v_next = planned[i + 1]
            err = planned[i] - v_next
            desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, self.MAX_DECEL * decel_mult)
            feasible_speed = v_next - desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # 4) Margin-based backward pass
        base_margin = margin_time_fn(v_ego)
        margin_factor = 2.2
        margin_t = base_margin * margin_factor

        for i in range(n - 2, -1, -1):
            j = self._find_time_index(times, times[i] + margin_t, clip_high=True)
            if j <= i:
                continue
            dt_ij = times[j] - times[i]
            if dt_ij < 1e-3:
                continue
            v_future = planned[j]
            err = planned[i] - v_future
            desired_acc = clip(err / dt_ij, -self.MAX_DECEL * decel_mult, self.MAX_DECEL * decel_mult)
            feasible_speed = v_future - desired_acc * dt_ij
            planned[i] = min(planned[i], feasible_speed)

        # 5) Forward pass (accel-limit)
        accel_mult = 1.0
        for i in range(1, n):
            dt_i = dt_array[i - 1] if (i - 1 < len(dt_array)) else 0.05
            v_prev = planned[i - 1]
            err = planned[i] - v_prev
            desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)
            feasible_speed = v_prev + desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # 6) Emergency pass
        do_emergency_braking = False
        for i in range(min(n, self.EMERGENCY_LOOKAHEAD_FRAMES)):
            if planned[i] > (safe_speeds[i] + self.EMERGENCY_SPEED_TOLERANCE):
                do_emergency_braking = True
                break

        if do_emergency_braking:
            for i in range(n - 2, -1, -1):
                dt_i = dt_array[i] if i < len(dt_array) else 0.05
                v_next = planned[i + 1]
                err = planned[i] - v_next
                desired_acc = clip(err / dt_i, -self.EMERGENCY_DECEL, self.EMERGENCY_DECEL)
                feasible_speed = v_next - desired_acc * dt_i
                planned[i] = min(planned[i], feasible_speed, safe_speeds[i])

        return planned

    def _find_time_index(self, times: np.ndarray, target_time: float, clip_high=False) -> int:
        n = len(times)
        if target_time <= times[0]:
            return 0
        if target_time >= times[-1] and clip_high:
            return n - 1
        for i in range(n - 1):
            if times[i] <= target_time < times[i + 1]:
                if (target_time - times[i]) < (times[i + 1] - target_time):
                    return i
                else:
                    return i + 1
        return (n - 1) if clip_high else (n - 2)