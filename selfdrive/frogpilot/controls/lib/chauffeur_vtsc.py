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
    with a smooth logistic transition starting from lower values (~1.4 m/s^2)
    at low speeds. This helps corner more gently at lower speed, but remains
    near ~3.2 m/s^2 on highways.
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
    Identify 'peaks' in curvature. We look for points above 'threshold' that
    are local maxima (≥ next point, > previous point).
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
    Smooth function that transitions from 8.0 at 5 m/s to 2.0 at 25 m/s
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
    return logistic_transition(x=apex_speed, center=15.0, scale=3.0, lo=2.0, hi=5.0)


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


# ------------------------------------------------------------
#   STEERING TORQUE SATURATION PREDICTOR (REFINED FOR NEAR SAT)
# ------------------------------------------------------------
class SteeringTorqueSaturationPredictor:
    """
    A data-driven predictor that learns from actual on-road observations:
      - Maintains a 2D map: (speed_bin, curvature_bin) → max observed torque
      - Records ANY torque sample, but pays special attention if torque > 90% of max
      - If torque > 95% of max, we count a 'saturation' event and exit passive_mode.

    The usage is then used in the speed planning code to predict if we might
    saturate or get close to saturating on upcoming curves, and adjust speed.
    """

    def __init__(self, vehicle_params, debug=False):
        self.VEHICLE_MASS = vehicle_params.mass
        self.STEERING_RATIO = vehicle_params.steerRatio
        self.MAX_STEER_TORQUE = 409

        # NEW OR CHANGED:
        self.near_sat_threshold_pct = 0.95  # 95% = near saturation
        self.saturation_threshold_pct = 0.995

        self.TORQUE_MARGIN = 1.0

        # Binning resolution
        self.speed_bin_size = 2.0         # m/s bins
        self.curv_bin_size = 1e-4        # curvature bins
        self.max_speed_bin = 60.0        # clamp speeds at ~60 m/s (~216 km/h)
        self.max_curv_bin = 0.01         # clamp curvature at 0.01 (100 m radius)

        # observed_map: (speed_idx, curv_idx) → max absolute torque
        self.observed_map = {}

        self.samples = deque(maxlen=2000)

        # Passive mode (no speed-limiting from torque) until we see a reason
        self.passive_mode = True

        # Counters
        self.saturation_count = 0
        self.near_saturation_count = 0

        # Track total data stored
        self.total_data_count = 0

        self.debug = debug
        self.last_log_time = 0.0
        self.log_frequency = 5.0

        self.param_path = "selfdrive/frogpilot/model_weights/torque_predictor.pkl"

        # Load from disk
        self._load_model()

    # --------------------------
    #   LOADING & SAVING
    # --------------------------
    def _load_model(self):
        if os.path.exists(self.param_path):
            try:
                with open(self.param_path, "rb") as f:
                    data = pickle.load(f)
                    self.observed_map = data.get("observed_map", {})
                    self.passive_mode = data.get("passive_mode", True)
                    self.saturation_count = data.get("saturation_count", 0)
                    self.near_saturation_count = data.get("near_saturation_count", 0)
                    self.total_data_count = data.get("total_data_count", 0)
                    self.TORQUE_MARGIN = data.get("torque_margin", 1.0)
                if self.debug:
                    print(f"[TorquePredictor] Loaded model: {len(self.observed_map)} bins stored")
            except Exception as e:
                if self.debug:
                    print(f"[TorquePredictor] Error loading: {e}")

    def _save_model(self):
        data = {
            "observed_map": self.observed_map,
            "passive_mode": self.passive_mode,
            "saturation_count": self.saturation_count,
            "near_saturation_count": self.near_saturation_count,
            "total_data_count": self.total_data_count,
            "torque_margin": self.TORQUE_MARGIN,
            "timestamp": time.time()
        }
        try:
            os.makedirs(os.path.dirname(self.param_path), exist_ok=True)
            with open(self.param_path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            if self.debug:
                print(f"[TorquePredictor] Error saving model: {e}")

    # --------------------------
    #   BINNING & LOOKUP
    # --------------------------
    def _get_bin_indices(self, speed, curvature):
        s_clamped = max(0.0, min(speed, self.max_speed_bin))
        c_clamped = max(0.0, min(abs(curvature), self.max_curv_bin))
        i_speed = int(s_clamped // self.speed_bin_size)
        i_curv = int(c_clamped // self.curv_bin_size)
        return (i_speed, i_curv)

    def _record_observation(self, speed, curvature, actual_torque):
        bin_idx = self._get_bin_indices(speed, curvature)
        current_val = self.observed_map.get(bin_idx, 0.0)
        new_val = max(current_val, abs(actual_torque))
        self.observed_map[bin_idx] = new_val
        self.total_data_count += 1

    def _find_bin_max_torque(self, speed, curvature):
        bin_idx = self._get_bin_indices(speed, curvature)
        return self.observed_map.get(bin_idx, 0.0)

    # --------------------------
    #   MAIN API METHODS
    # --------------------------
    def detect_saturation_event(self, actual_torque):
        """
        Distinguish between "near saturation" (>90%) and "full saturation" (>95%).
        If we detect full saturation the first time, exit passive_mode.
        """
        near_threshold = self.MAX_STEER_TORQUE * self.near_sat_threshold_pct
        sat_threshold = self.MAX_STEER_TORQUE * self.saturation_threshold_pct

        near_sat = abs(actual_torque) >= near_threshold
        sat = abs(actual_torque) >= sat_threshold

        if near_sat:
            self.near_saturation_count += 1

        if sat:
            self.saturation_count += 1
            if self.passive_mode:
                self.passive_mode = False
            return True

        return False

    def update_with_measurement(self, actual_torque, curvature, speed, road_bank=0.0):
        """
        Called regularly to log actual on-road torque usage. We record *every*
        torque, but pay special attention when torque is near or above 90%.
        If 95% is exceeded, we log a saturation event.
        """
        if speed < 1.0 or abs(curvature) < 1e-6:
            return

        # Mark if near or saturating
        saturation_detected = self.detect_saturation_event(actual_torque)

        # Always record the new max torque for that bin
        self._record_observation(speed, curvature, actual_torque)

        # Save model only if a full saturation occurred (avoid spamming)
        if saturation_detected:
            self._save_model()

        # Optionally store raw sample
        self.samples.append({
            "speed": speed,
            "curvature": curvature,
            "torque": actual_torque,
            "road_bank": road_bank,
            "ts": time.time(),
            "saturation": (abs(actual_torque) > self.saturation_threshold_pct * self.MAX_STEER_TORQUE),
        })

    def driver_intervention_learn(self, intervention_torque, curvature, speed, road_bank=0.0):
        """
        If the driver forcibly intervenes, treat it as a clue that more or less torque
        might be needed. Record it immediately, exit passive_mode if it's big.
        """
        if speed < 1.0 or abs(curvature) < 1e-6:
            return

        self.passive_mode = False
        self._record_observation(speed, curvature, intervention_torque)
        self.detect_saturation_event(intervention_torque)

        # Save on driver intervention
        self._save_model()

    def get_max_available_torque(self):
        """
        If in passive mode, we return a large "no limit" value.
        Otherwise, hardware limit times margin.
        """
        if self.passive_mode:
            return 9999.0
        else:
            return self.MAX_STEER_TORQUE * self.TORQUE_MARGIN

    def predict_observed_torque(self, speed, curvature):
        """
        Returns the *max observed torque* for the bin (speed, curvature).
        If we have no data, returns 0.0 → no stored torque limit.
        If in passive mode, we also do not try to limit.
        """
        if self.passive_mode:
            return 0.0
        return self._find_bin_max_torque(speed, curvature)

    def log_telemetry(self, curvature, speed, predicted_torque, available_torque, torque_limited=False):
        now = time.time()
        if now - self.last_log_time < self.log_frequency:
            return
        self.last_log_time = now

        cloudlog.event(
            "torque_predictor",
            curvature=curvature,
            speed=speed,
            predicted_torque=predicted_torque,
            available_torque=available_torque,
            torque_limited=torque_limited,
            passive_mode=self.passive_mode,
            saturation_count=self.saturation_count,
            near_saturation_count=self.near_saturation_count,
            total_data_count=self.total_data_count
        )
        if self.debug:
            print(f"[TorquePredictor] speed={speed:.1f} curv={curvature:.6f} pred_torque={predicted_torque:.1f} "
                  f"avail={available_torque:.1f} limited={torque_limited} passive={self.passive_mode}")


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
        max_decel=2.0,
        max_jerk=4.0,
        max_accel=None,
        max_jerk_accel=None,
        emergency_decel=6.0,
        emergency_speed_tolerance=2.0,
        emergency_lookahead_frames=8,
    ):
        """
        Our main speed planner. We incorporate the updated torque predictor
        that does NOT reduce torque unless we see ourselves nearing or hitting
        hardware limits for the given speed/curvature bin.
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

        # Example vehicle params
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
        self.sm.update()
        model_data = self.sm['modelV2']
        car_state = self.sm['carState']

        # Road bank if available
        if self.sm.updated['liveParameters']:
            self.current_road_bank = self.sm['liveParameters'].roll

        # Detect driver interventions
        if car_state.steeringPressed:
            self.torque_predictor.driver_intervention_learn(
                intervention_torque=car_state.steeringTorque,
                curvature=self.last_curvature,
                speed=v_ego,
                road_bank=self.current_road_bank
            )
        elif car_state.gasPressed:
            self.torque_predictor.driver_intervention_learn(
                intervention_torque=-999,  # some large negative
                curvature=self.last_curvature,
                speed=v_ego,
                road_bank=self.current_road_bank
            )
        elif car_state.brakePressed:
            self.torque_predictor.driver_intervention_learn(
                intervention_torque=999,
                curvature=self.last_curvature,
                speed=v_ego,
                road_bank=self.current_road_bank
            )

        # Update the torque predictor with real torque usage
        if hasattr(car_state, 'steeringTorque'):
            if abs(car_state.steeringTorque) > 0.5:
                self.torque_predictor.update_with_measurement(
                    car_state.steeringTorque,
                    self.last_curvature,
                    v_ego,
                    self.current_road_bank
                )

        # Handle resume from zero
        is_real_resume = (not self.last_cruise_nonzero) and (v_cruise_cluster > 1e-1)
        self.last_cruise_nonzero = (v_cruise_cluster > 1e-1)
        if is_real_resume:
            self.reset(v_cruise_cluster)
            self.prev_v_cruise_cluster = v_cruise_cluster
            return v_cruise_cluster

        raw_safe_speed = self._compute_raw_safe_speed(model_data, v_ego, turn_aggressiveness)
        final_raw = min(raw_safe_speed, v_cruise_cluster)

        # Jerk-limited smoothing
        dt = 0.05
        scale_decel = dynamic_decel_scale(v_ego)
        scale_accel = dynamic_accel_scale(v_ego)
        scale_jerk = dynamic_jerk_scale(v_ego)

        emergency_decel_active = (self.prev_target_speed > final_raw + self.EMERGENCY_SPEED_TOLERANCE)

        max_decel_now = self.MAX_DECEL * scale_decel
        max_accel_now = self.MAX_ACCEL * scale_accel
        max_jerk_now = self.MAX_JERK * scale_jerk
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
            return 22.0

        # Resample to 33 points
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

        max_torque = self.torque_predictor.get_max_available_torque()
        safe_speeds = np.zeros(n, dtype=float)

        # 1) Basic curvature-limited speeds + check predicted torque usage
        for i in range(n):
            lat_acc_limit = nonlinear_lat_accel(velocity_pred[i], turn_aggressiveness)
            c = max(curvature[i], eps)
            s = math.sqrt(lat_acc_limit / c)

            # NEW OR CHANGED: more nuanced approach if we find near saturation
            observed_torque = self.torque_predictor.predict_observed_torque(s, c)
            torque_limited = False

            if not self.torque_predictor.passive_mode and observed_torque > 0.0:
                torque_frac = observed_torque / max_torque
                if torque_frac > 1.0:
                    # Full saturation predicted => clamp speed forcibly
                    torque_limited = True
                    s = min(s, 25.0)  # crude cap, or something fancier
                elif torque_frac > 0.9:
                    # near saturation => gently reduce speed, but still allow
                    # approaching the limit
                    torque_limited = True
                    # e.g., linearly scale from 1.0 at 0.9 => 0.85 at 1.0
                    # (example; tweak as you like)
                    scale = 1.0 - 0.15 * max(0.0, torque_frac - 0.9) / 0.1
                    s = min(s, s * scale)

            if i == 0:
                self.torque_predictor.log_telemetry(
                    c, s, observed_torque, max_torque, torque_limited
                )

            safe_speeds[i] = s

        self.last_curvature = curvature[0]

        # 2) Identify apexes for approach/spool
        apex_idxs = find_apexes(curvature, threshold=5e-5)
        spool_mult = short_horizon_factor(horizon_time)

        for apex_i in apex_idxs:
            apex_speed = safe_speeds[apex_i]
            decel_sec = early_approach_time_fn(apex_speed)
            spool_sec = early_spool_time_fn(apex_speed)

            decel_start = self._find_time_index(times, times[apex_i] - decel_sec)
            spool_start = self._find_time_index(times, times[apex_i] - spool_sec)
            spool_end = self._find_time_index(times, times[apex_i] + spool_sec, clip_high=True)

            # Approach decel
            if spool_start > decel_start:
                v_decel_start = safe_speeds[decel_start]
                steps_decel = spool_start - decel_start
                for idx in range(decel_start, spool_start):
                    f = (idx - decel_start) / float(steps_decel)
                    f_curve = f**1.5
                    decel_val = v_decel_start * (1 - f_curve) + apex_speed * f_curve
                    safe_speeds[idx] = min(safe_speeds[idx], decel_val)

            # Force apex
            for idx in range(spool_start, apex_i + 1):
                safe_speeds[idx] = min(safe_speeds[idx], apex_speed)

            # Spool out
            if spool_end > apex_i:
                steps_spool = spool_end - apex_i
                v_spool_end = safe_speeds[spool_end - 1]
                for idx in range(apex_i, spool_end):
                    f = (idx - apex_i) / float(steps_spool)
                    f_curve = f**2
                    spool_val = apex_speed * (1 - f_curve) + v_spool_end * f_curve
                    spool_val *= spool_mult
                    safe_speeds[idx] = max(safe_speeds[idx], spool_val)

        # 3) Standard backward pass (decel-limit)
        for i in range(n - 2, -1, -1):
            dt_i = dt_array[i] if i < len(dt_array) else 0.05
            v_next = safe_speeds[i + 1]
            err = safe_speeds[i] - v_next
            desired_acc = clip(err / dt_i, -2.0, 2.0)  # general limit
            feasible_speed = v_next - desired_acc * dt_i
            safe_speeds[i] = min(safe_speeds[i], feasible_speed)

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
            v_future = safe_speeds[j]
            err = safe_speeds[i] - v_future
            desired_acc = clip(err / dt_ij, -2.0, 2.0)
            feasible_speed = v_future - desired_acc * dt_ij
            safe_speeds[i] = min(safe_speeds[i], feasible_speed)

        # 5) Forward pass (accel-limit)
        for i in range(1, n):
            dt_i = dt_array[i - 1] if (i - 1 < len(dt_array)) else 0.05
            v_prev = safe_speeds[i - 1]
            err = safe_speeds[i] - v_prev
            desired_acc = clip(err / dt_i, -2.0, 2.0)
            feasible_speed = v_prev + desired_acc * dt_i
            safe_speeds[i] = min(safe_speeds[i], feasible_speed)

        # 6) Emergency pass
        do_emergency_braking = False
        for i in range(min(n, self.EMERGENCY_LOOKAHEAD_FRAMES)):
            if i > 0 and safe_speeds[i-1] > (safe_speeds[i] + self.EMERGENCY_SPEED_TOLERANCE):
                do_emergency_braking = True
                break

        if do_emergency_braking:
            for i in range(n - 2, -1, -1):
                dt_i = dt_array[i] if i < len(dt_array) else 0.05
                v_next = safe_speeds[i + 1]
                err = safe_speeds[i] - v_next
                desired_acc = clip(err / dt_i, -self.EMERGENCY_DECEL, self.EMERGENCY_DECEL)
                feasible_speed = v_next - desired_acc * dt_i
                safe_speeds[i] = min(safe_speeds[i], feasible_speed)

        return safe_speeds

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
