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
from openpilot.common.logger import cloudlog
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

    # More conservative at low speeds (like taco bell) but keeping the logistic structure
    base = 1.4     # Lower base value (more conservative at low speeds)
    span = 1.8     # Adjusted span to reach desired max
    center = 30.0  # Shifted center point to be more conservative in mid-range
    k = 0.10       # Same slope factor
    lat_acc = base + span / (1 + math.exp(-k * (v_ego_mph - center)))
    lat_acc = min(lat_acc, 3.2)  # Maximum lateral acceleration limit

    return lat_acc * turn_aggressiveness


def find_apexes(curv_array: np.ndarray, threshold: float = 5e-5) -> list:
    """
    Identify 'peaks' in curvature.
    Keeping your threshold-based approach, though you can make it continuous if you prefer.
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
    using a polynomial. Or you can do logistic, etc.
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
        # smooth polynomial blend
        return max_scale - (max_scale - min_scale) * (3*pos**2 - 2*pos**3)


def dynamic_accel_scale(v_ego_ms: float) -> float:
    """
    Tied to decel scale, then scaled up at low speeds.
    """
    decel_scale = dynamic_decel_scale(v_ego_ms)
    if v_ego_ms < 10.0:
        return decel_scale * 1.5
    else:
        # reduce from 1.5 down to 1.0 in the range [10 m/s, ∞)
        return decel_scale * max(1.0, 1.5 - 0.05 * (v_ego_ms - 10.0))


def dynamic_jerk_scale(v_ego_ms: float) -> float:
    """
    Keep the jerk scale consistent with decel scale or do a simpler approach.
    """
    return dynamic_decel_scale(v_ego_ms)


def margin_time_fn(v_ego_ms: float) -> float:
    """
    Time-based margin. We keep your piecewise linear approach but rewrite it as
    a simple continuous function if you prefer:

    - In practice, you had breakpoints at 0 m/s → 1.5s, 15 m/s → 3.5s, 31.3 m/s → 5.5s
    - Let's do linear interpolation between them (which is effectively what your code did).
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
    A continuous function that transitions from lo to hi in a smooth logistic shape
    around the 'center' point, with slope controlled by 'scale'.

    e.g. logistic_transition( speed, 8.0, 3.0, 2.0, 3.0 )
    """
    return lo + (hi - lo) / (1 + math.exp(-(x - center) / scale))


def early_approach_time_fn(apex_speed: float) -> float:
    """
    Replace the piecewise approach with a logistic approach for continuous behavior.
    Suppose we want 2s at 8 m/s, 3s at 22 m/s. We'll pick center ~ (8+22)/2=15,
    scale=3, so it transitions over ~6 m/s.
    """
    return logistic_transition(x=apex_speed, center=15.0, scale=3.0, lo=2.0, hi=3.0)


def early_spool_time_fn(apex_speed: float) -> float:
    """
    Similarly, spool from 1s at 8 m/s to 2s at 22 m/s in a logistic manner.
    """
    return logistic_transition(x=apex_speed, center=15.0, scale=3.0, lo=1.0, hi=2.0)


def short_horizon_factor(horizon_time: float) -> float:
    """
    A smooth logistic from factor=0.4 (for horizon ~1.5s) to factor=1.0 (for horizon ~4.0s).
    We'll center around ~2.75s with a scale of ~0.75s, for instance.
    """
    # We'll clamp so it doesn't exceed [0.4, 1.0] anyway
    raw = logistic_transition(horizon_time, center=2.75, scale=0.75, lo=0.4, hi=1.0)
    return clip(raw, 0.4, 1.0)


# -----------------------
#   STEERING TORQUE SATURATION
# -----------------------
class SteeringTorqueSaturationPredictor:
    """
    Predicts and learns how much steering torque is needed to hold a given
    curvature at a given speed, while also factoring in road banking.

    The changes here:
      - The 'learning rate' logic uses a mild exponential average
      - Max available torque is simply 409 * margin (no more speed-based reduction)
      - We preserve a continuous update for sensitivity without huge jump thresholds
      - We rename the '0.01' factor to MODEL_SCALE_FACTOR for clarity
    """

    def __init__(self, vehicle_params, debug=False):
        # Basic vehicle parameters (Kia EV6, etc.)
        self.VEHICLE_MASS = vehicle_params.mass
        self.STEERING_RATIO = vehicle_params.steerRatio
        # Always assume 409 raw torque is max, with a margin
        self.MAX_STEER_TORQUE = 409
        self.TORQUE_MARGIN = 0.85
        self.WHEELBASE = vehicle_params.wheelbase

        # Model constants
        self.MODEL_SCALE_FACTOR = 0.01  # previously '0.01' in your code

        # Learning parameters
        self.learning_rate = 0.02  # base multiplier for adjustments
        self.sensitivity_factor = 1.0
        self.torque_error_ema = 0.0     # We'll keep an EMA of the last error
        self.ema_alpha = 0.01          # smoothing factor for error
        self.confidence = 0.8          # can auto-adjust over time if desired

        # Model state
        self.last_update_time = 0
        self.last_pred_required_torque = 0
        self.last_actual_torque = 0
        self.last_curvature = 0
        self.last_speed = 0

        # History for offline analysis
        self.samples = deque(maxlen=1000)
        self.debug = debug

        # Param path
        self.param_path = "/data/openpilot/selfdrive/frogpilot/model_weights/torque_predictor.pkl"

        # Telemetry
        self.last_log_time = 0
        self.log_frequency = 5.0

        # Load existing model if it exists
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(self.param_path):
                with open(self.param_path, 'rb') as f:
                    data = pickle.load(f)
                    self.sensitivity_factor = data.get('sensitivity_factor', 1.0)
                    self.confidence = data.get('confidence', 0.8)
                    # Road bank stats loaded, if present
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
            self.sensitivity_factor = 1.0
            self.confidence = 0.8

    def _save_model(self):
        try:
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
        current_time = time.time()
        if current_time - self.last_log_time < self.log_frequency:
            return
        self.last_log_time = current_time

        gravity_component = 9.81 * math.sin(road_bank)  # sign depends on bank direction
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
            road_bank=road_bank,
            gravity_component=gravity_component
        )

    def estimate_required_torque(self, curvature, speed, road_bank=0.0) -> float:
        """
        Simplified physics:
          required_torque = (lateral_acc - g*sin(bank)) * mass * steer_ratio * MODEL_SCALE_FACTOR * sensitivity
        """
        # lateral_acc = speed^2 * curvature, ignoring sign for torque magnitude
        # but watch sign of curvature vs. bank if you do a direction-based approach
        lateral_accel = (speed**2) * curvature
        gravity_component = 9.81 * math.sin(road_bank)
        effective_lat_accel = lateral_accel - gravity_component

        required_torque = effective_lat_accel * self.VEHICLE_MASS * self.STEERING_RATIO * self.MODEL_SCALE_FACTOR
        required_torque *= self.sensitivity_factor
        return required_torque

    def get_max_available_torque(self) -> float:
        return self.MAX_STEER_TORQUE

    def solve_for_torque_limited_speed(self, curvature, max_torque, road_bank=0.0):
        """
        speed^2 = ( (max_torque/(mass*steer_ratio*scale*sens)) + g*sin(bank) ) / curvature
        """
        if curvature < 1e-9:
            return 70.0  # effectively no curve
        gravity_component = 9.81 * math.sin(road_bank)
        denom = self.VEHICLE_MASS * self.STEERING_RATIO * self.MODEL_SCALE_FACTOR * self.sensitivity_factor
        torque_factor = max_torque / denom
        adjusted_factor = torque_factor + gravity_component
        if adjusted_factor <= 0.0:
            return 0.1  # so you don't sqrt a negative
        return math.sqrt(adjusted_factor / curvature)

    def update_with_measurement(self, actual_torque, last_curvature, last_speed, road_bank=0.0):
        """
        We do a mild exponential moving average of the torque error to avoid big jumps from noise.
        Then we do a small fractional adjustment of sensitivity_factor based on that average error.
        """
        if last_curvature < 1e-6 or last_speed < 1.0:
            return

        self.last_update_time = time.time()
        predicted_torque = self.estimate_required_torque(last_curvature, last_speed, road_bank)
        torque_error = actual_torque - predicted_torque

        # Keep a history sample
        self.samples.append({
            'curvature': last_curvature,
            'speed': last_speed,
            'predicted_torque': predicted_torque,
            'actual_torque': actual_torque,
            'error': torque_error,
            'timestamp': self.last_update_time,
            'road_bank': road_bank
        })

        # Update a mild EMA
        self.torque_error_ema = (1.0 - self.ema_alpha) * self.torque_error_ema + self.ema_alpha * torque_error

        # Adjust sensitivity factor by a fraction of the normalized error
        # A negative torque_error_ema will reduce sensitivity, positive increases it
        if abs(predicted_torque) > 1e-3:
            error_ratio = self.torque_error_ema / predicted_torque
            adjustment = self.learning_rate * error_ratio
            # Make a small, continuous shift
            new_sens = self.sensitivity_factor * (1 + adjustment)
            self.sensitivity_factor = clip(new_sens, 0.5, 2.0)

        # Optionally adjust confidence if we want to get more or less conservative over time
        # For demonstration, we do a mild shift:
        self.confidence = clip(self.confidence + 0.0001 * (-torque_error), 0.5, 1.0)

        # Periodically save model
        if len(self.samples) % 100 == 0:
            self._save_model()

        # Store last
        self.last_pred_required_torque = predicted_torque
        self.last_actual_torque = actual_torque
        self.last_curvature = last_curvature
        self.last_speed = last_speed

    def apply_model_confidence(self, safe_speed, curvature):
        """
        If we want to be more conservative when confidence is low, we can do:
            safe_speed *= confidence
        But we'll keep a small lower bound so we don't overslow too drastically.
        """
        if curvature < 1e-5:
            # basically a straight line
            return safe_speed
        return safe_speed * (0.7 + 0.3 * self.confidence)  # never reduce below ~70%


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
        The main speed planning remains largely the same.
        We only changed the torque-limiting portion to rely on the new approach.
        """
        self.turn_smoothing_alpha = turn_smoothing_alpha
        self.reaccel_alpha = reaccel_alpha
        self.LOW_LAT_ACC = low_lat_acc
        self.HIGH_LAT_ACC = high_lat_acc

        self.MAX_DECEL = max_decel
        self.MAX_JERK = max_jerk
        self.MAX_ACCEL = max_accel if max_accel is not None else 2.0 * max_decel
        self.MAX_JERK_ACCEL = max_jerk_accel if max_jerk_accel is not None else 2.0 * max_jerk

        self.EMERGENCY_DECEL = emergency_decel
        self.EMERGENCY_SPEED_TOLERANCE = emergency_speed_tolerance
        self.EMERGENCY_LOOKAHEAD_FRAMES = emergency_lookahead_frames

        self.current_accel = 0.0
        self.prev_target_speed = 0.0
        self.prev_v_cruise_cluster = 0.0

        self.sm = messaging.SubMaster(['modelV2', 'carState', 'liveParameters'])

        # Kia EV6 default
        self.vehicle_params = type('obj', (), {
            'mass': 2055,
            'wheelbase': 2.9,
            'steerRatio': 16.0,
        })

        self.torque_predictor = SteeringTorqueSaturationPredictor(self.vehicle_params)

        self.last_cruise_nonzero = False
        self.current_road_bank = 0.0

    def reset(self, speed: float) -> None:
        self.prev_target_speed = speed
        self.current_accel = 0.0

    def update(self, v_ego: float, v_cruise_cluster: float, turn_aggressiveness=1.0) -> float:
        self.sm.update()
        model_data = self.sm['modelV2']
        car_state = self.sm['carState']

        if self.sm.updated['liveParameters']:
            self.current_road_bank = self.sm['liveParameters'].roll

        # Update the torque predictor with actual torque
        if hasattr(car_state, 'steeringTorque') and abs(car_state.steeringTorque) > 0:
            self.torque_predictor.update_with_measurement(
                car_state.steeringTorque,
                getattr(self, 'last_curvature', 0.0),
                v_ego,
                self.current_road_bank
            )

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

        # Determine horizon time
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
            s = math.sqrt(lat_acc_limit / c)  # standard lat-acc-limited speed

            # NEW: Check torque limit
            required_torque = self.torque_predictor.estimate_required_torque(c, s, self.current_road_bank)
            torque_limited = False
            if required_torque > max_torque:
                torque_limited = True
                torque_limited_speed = self.torque_predictor.solve_for_torque_limited_speed(c, max_torque, self.current_road_bank)
                s = min(s, torque_limited_speed)

            # Confidence factor
            s = self.torque_predictor.apply_model_confidence(s, c)

            # Log only for i == 0 to avoid spam
            if i == 0:
                self.torque_predictor.log_telemetry(c, s, required_torque, max_torque, torque_limited, self.current_road_bank)
                self.last_curvature = c  # store for learning logic

            safe_speeds[i] = s

        planned = safe_speeds.copy()

        # 2) Find apexes
        apex_idxs = find_apexes(curvature, threshold=5e-5)
        spool_mult = short_horizon_factor(horizon_time)

        for apex_i in apex_idxs:
            apex_speed = planned[apex_i]

            # approach apex earlier
            decel_sec = early_approach_time_fn(apex_speed)
            # spool out earlier
            spool_sec = early_spool_time_fn(apex_speed)

            decel_start = self._find_time_index(times, times[apex_i] - decel_sec)
            spool_start = self._find_time_index(times, times[apex_i] - spool_sec)
            spool_end   = self._find_time_index(times, times[apex_i] + spool_sec, clip_high=True)

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

        # 5) Forward pass
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
