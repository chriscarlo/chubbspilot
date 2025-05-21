import math
import numpy as np
import cereal.messaging as messaging
from msgq import MultiplePublishersError

from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip, interp
from openpilot.selfdrive.modeld.constants import ModelConstants

# Add necessary imports if not already present at the top of chauffeur_vtsc.py
from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip

# Determine actual available points from ModelConstants and set target
AVAILABLE_POINTS = len(ModelConstants.T_IDXS)
N_POINTS_TARGET = min(50, AVAILABLE_POINTS)  # Use up to 50 points, but no more than available

CRUISING_SPEED = 5.0  # m/s

def _original_curvature_based_lat_accel(abs_curvature_scaled: float) -> float:
    """Internal function replicating the original tuned lateral accel logic."""
    high_accel = 3.2
    low_accel = 1.5
    span = high_accel - low_accel
    center_curvature = 0.064
    k = 60
    reduction = span / (1.0 + math.exp(-k * (abs_curvature_scaled - center_curvature)))
    lat_acc = high_accel - reduction
    return clip(lat_acc, low_accel, high_accel)

CURV_CORR_FACTOR = (CV.MS_TO_MPH ** 2)
MAX_SPEED_DEFAULT = 70.0  # m/s (~156 mph)
SPEED_INCREASE_FACTOR = 1.0

def curvature_to_speed(abs_curvature_meters: float) -> float:
    """
    Calculates a target speed (m/s) directly from curvature (1/radius in meters).
    """
    if abs_curvature_meters < 1e-7:
        return MAX_SPEED_DEFAULT

    abs_curvature_scaled = abs_curvature_meters / CURV_CORR_FACTOR
    base_lat_accel = _original_curvature_based_lat_accel(abs_curvature_scaled)

    if base_lat_accel < 0:
        base_lat_accel = 0
    try:
        base_speed_mps = math.sqrt(base_lat_accel / abs_curvature_meters)
    except (ValueError, ZeroDivisionError):
        base_speed_mps = 0.0

    target_speed_mps = base_speed_mps * SPEED_INCREASE_FACTOR
    return clip(target_speed_mps, 0.0, MAX_SPEED_DEFAULT)

def nonlinear_lat_accel(v_ego_ms: float, turn_aggressiveness: float = 1.0) -> float:
    """
    Compute lateral acceleration limit based on speed and an aggressiveness factor.
    """
    v_ego_mph = v_ego_ms * CV.MS_TO_MPH
    base = 1.5
    span = 2.18
    center = 25.0
    k = 0.10

    lat_acc = base + span / (1.0 + math.exp(-k * (v_ego_mph - center)))
    return lat_acc * turn_aggressiveness

def margin_time_fn(v_ego_ms: float) -> float:
    """
    Returns a 'margin time' used in backward-pass speed planning.
    """
    v_low = 0.0
    t_low = 1.0
    v_med = 15.0
    t_med = 3.0
    v_high = 31.3
    t_high = 5.0

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

def find_apexes(curv_array: np.ndarray, threshold: float = 5e-5) -> list:
    """
    Identify indices where curvature spikes above a threshold and is a local maximum.
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

def dynamic_decel_scale(v_ego_ms: float) -> float:
    min_speed = 3.0
    max_speed = 35.0
    scale = 9.0
    if v_ego_ms >= max_speed:
        scale = 2.0
    elif v_ego_ms > min_speed:
        ratio = (v_ego_ms - min_speed) / (max_speed - min_speed)
        scale = 8.0 + (1.0 - 8.0) * ratio

    return min(scale, 3.0)

def dynamic_jerk_scale(v_ego_ms: float) -> float:
    return dynamic_decel_scale(v_ego_ms)

class VisionTurnSpeedController:
    def __init__(
        self,
        turn_smoothing_alpha=0.3,
        reaccel_alpha=0.2,
        low_lat_acc=0.20,
        high_lat_acc=0.40,
        max_decel=3.5,
        max_jerk=6.0,
        max_accel=None,
        max_jerk_accel=None
    ):
        self.turn_smoothing_alpha = turn_smoothing_alpha
        self.reaccel_alpha = reaccel_alpha
        self.LOW_LAT_ACC = low_lat_acc
        self.HIGH_LAT_ACC = high_lat_acc

        self.MAX_DECEL = max_decel
        self.MAX_JERK = max_jerk
        self.MAX_ACCEL = max_accel if max_accel is not None else 1.3 * max_decel
        self.MAX_JERK_ACCEL = max_jerk_accel if max_jerk_accel is not None else 2.0 * max_jerk

        self.current_accel = 0.0
        self.prev_target_speed = 0.0

        self.planned_speeds = np.zeros(N_POINTS_TARGET, dtype=float)
        self.sm = messaging.SubMaster(['modelV2'])

        self.prev_v_cruise_cluster = 0.0

        # State for curvature filtering
        self.curvature_ema_ratio = 0.3
        self._filtered_curvature = 0.0

        self.speed_up_ema_ratio = 0.2
        self._last_model_speed = None

        # Logging fields
        self.vtsc_is_enabled_log = False
        self.vtsc_raw_target_speed_log = 0.0
        self.vtsc_vision_curvatures_log = []
        self.vtsc_vision_velocities_log = []
        self.vtsc_safe_speeds_vision_log = []
        self.vtsc_safe_speeds_map_log = []
        self.vtsc_final_safe_speeds_log = []
        self.vtsc_apex_indices_log = []
        self.vtsc_planner_init_speed_log = 0.0
        self.vtsc_used_vision_velocities_log = []
        self.vtsc_planner_skip_accel_limit_log = False

    def reset(self, v_ego: float) -> None:
        """
        Reset internal state so the controller is ready for fresh speed planning.
        """
        self.prev_target_speed = v_ego
        self.current_accel = 0.0
        self.planned_speeds[:] = v_ego

        self._filtered_curvature = 0.0
        self._last_model_speed = None

        self.vtsc_is_enabled_log = False
        self.vtsc_raw_target_speed_log = v_ego
        self.vtsc_vision_curvatures_log = []
        self.vtsc_vision_velocities_log = []
        self.vtsc_safe_speeds_vision_log = []
        self.vtsc_safe_speeds_map_log = []
        self.vtsc_final_safe_speeds_log = []
        self.vtsc_apex_indices_log = []
        self.vtsc_planner_init_speed_log = v_ego
        self.vtsc_used_vision_velocities_log = []
        self.vtsc_planner_skip_accel_limit_log = False

    def update(
        self,
        v_ego: float,
        v_cruise_cluster: float,
        map_speed_profile: tuple[np.ndarray, np.ndarray] | None = None,
        turn_aggressiveness=1.0
    ) -> float:
        """
        Main entry point for the turn speed controller logic. Called every cycle.
        """
        self.sm.update()
        modelData = self.sm['modelV2']
        self.vtsc_is_enabled_log = False

        if v_ego < CRUISING_SPEED:
            self.reset(v_ego)
            self.prev_v_cruise_cluster = v_cruise_cluster
            return v_ego

        orientation_rate_raw = modelData.orientationRate.z
        velocity_pred_raw = modelData.velocity.x

        MIN_POINTS = 3
        if (
            orientation_rate_raw is None or velocity_pred_raw is None
            or len(orientation_rate_raw) < MIN_POINTS
            or len(velocity_pred_raw) < MIN_POINTS
        ):
            raw_target = self._single_step_fallback(v_ego, 0.0, turn_aggressiveness)
            self.vtsc_is_enabled_log = False
        else:
            self.vtsc_is_enabled_log = True
            orientation_rate = np.abs(np.array(orientation_rate_raw, dtype=float))
            velocity_pred = np.array(velocity_pred_raw, dtype=float)

            self.vtsc_vision_velocities_log = list(velocity_pred_raw)[:N_POINTS_TARGET]

            n_points = min(len(orientation_rate), len(velocity_pred))
            target_indices = np.linspace(0, n_points - 1, N_POINTS_TARGET)

            if n_points < N_POINTS_TARGET:
                src_indices = np.linspace(0, n_points - 1, n_points)
                orientation_rate_target = np.interp(target_indices, src_indices, orientation_rate[:n_points])
                velocity_pred_target = np.interp(target_indices, src_indices, velocity_pred[:n_points])
            else:
                src_indices = np.linspace(0, len(orientation_rate) - 1, len(orientation_rate))
                orientation_rate_target = np.interp(target_indices, src_indices, orientation_rate)
                src_indices_vel = np.linspace(0, len(velocity_pred) - 1, len(velocity_pred))
                velocity_pred_target = np.interp(target_indices, src_indices_vel, velocity_pred)
                orientation_rate_target = orientation_rate_target[:N_POINTS_TARGET]
                velocity_pred_target = velocity_pred_target[:N_POINTS_TARGET]

            times_target = np.array(ModelConstants.T_IDXS[:N_POINTS_TARGET], dtype=float)
            self.vtsc_used_vision_velocities_log = velocity_pred_target.tolist()

            eps = 1e-9
            curvature_target = orientation_rate_target / np.clip(velocity_pred_target, eps, None)
            self.vtsc_vision_curvatures_log = curvature_target.tolist()

            current_max_curvature = float(np.max(curvature_target))
            self._filtered_curvature = (
                (1 - self.curvature_ema_ratio) * self._filtered_curvature
                + self.curvature_ema_ratio * current_max_curvature
            )

            is_bump_up = (
                (v_cruise_cluster > self.prev_v_cruise_cluster)
                or (self.prev_v_cruise_cluster == 0 and v_cruise_cluster > 0)
            )

            if len(self.planned_speeds) != N_POINTS_TARGET:
                self.planned_speeds = np.resize(self.planned_speeds, N_POINTS_TARGET)
                self.planned_speeds[:] = self.prev_target_speed

            self.vtsc_planner_init_speed_log = self.prev_target_speed
            self.vtsc_planner_skip_accel_limit_log = is_bump_up

            self.planned_speeds = self._plan_speed_trajectory(
                orientation_rate_target,
                velocity_pred_target,
                times_target,
                init_speed=self.prev_target_speed,
                map_speed_profile=map_speed_profile,
                skip_accel_limit=is_bump_up
            )

            raw_target = (
                min(self.planned_speeds[0], self.planned_speeds[1])
                if len(self.planned_speeds) >= 2
                else self.planned_speeds[0]
            )

        self.vtsc_raw_target_speed_log = raw_target
        dt = 0.05  # ~20Hz

        if (
            (v_cruise_cluster > self.prev_v_cruise_cluster)
            or (self.prev_v_cruise_cluster == 0 and v_cruise_cluster > 0)
        ):
            final_target_speed = v_cruise_cluster
            self.current_accel = 0.0
        else:
            scale_decel = dynamic_decel_scale(v_ego)
            scale_jerk = dynamic_jerk_scale(v_ego)

            accel_cmd = (raw_target - self.prev_target_speed) / dt

            planned_max = np.max(self.planned_speeds) if len(self.planned_speeds) > 0 else raw_target
            if v_cruise_cluster > self.prev_target_speed:
                ratio = (planned_max - self.prev_target_speed) / max((v_cruise_cluster - self.prev_target_speed), 1e-3)
                ratio = clip(ratio, 0.0, 1.0)
                boost_factor = 1.0 + ratio
            else:
                boost_factor = 1.0

            pos_limit = self.MAX_ACCEL * boost_factor
            neg_limit = self.MAX_DECEL * scale_decel
            accel_cmd = clip(accel_cmd, -neg_limit, pos_limit)

            accel_diff = accel_cmd - self.current_accel
            if accel_diff > 0:
                max_delta = (self.MAX_JERK_ACCEL * scale_jerk * boost_factor * dt)
                self.current_accel += min(accel_diff, max_delta)
            elif accel_diff < 0:
                max_delta = (self.MAX_JERK * scale_jerk * boost_factor * dt)
                self.current_accel -= min(-accel_diff, max_delta)
            else:
                self.current_accel = accel_cmd

            final_target_speed = self.prev_target_speed + self.current_accel * dt

        if not (
            (v_cruise_cluster > self.prev_v_cruise_cluster)
            or (self.prev_v_cruise_cluster == 0 and v_cruise_cluster > 0)
        ):
            final_target_speed *= turn_aggressiveness

        final_target_speed = min(final_target_speed, v_cruise_cluster)

        self.prev_target_speed = final_target_speed
        self.prev_v_cruise_cluster = v_cruise_cluster

        return final_target_speed

    def _plan_speed_trajectory(
        self,
        orientation_rate: np.ndarray,
        velocity_pred: np.ndarray,
        times: np.ndarray,
        init_speed: float,
        map_speed_profile: tuple[np.ndarray, np.ndarray] | None,
        skip_accel_limit: bool = False
    ) -> np.ndarray:
        """
        Build a future speed plan based on curvature and optional map data.
        """
        n = len(orientation_rate)
        eps = 1e-9
        dt_array = np.diff(times)

        curvature = np.array([
            orientation_rate[i] / max(velocity_pred[i], eps)
            for i in range(n)
        ], dtype=float)

        distances_m = np.zeros(n, dtype=float)
        if n > 1:
            distances_m[1:] = np.cumsum((velocity_pred[:-1] + velocity_pred[1:]) / 2.0 * dt_array)

        map_safe_speeds = np.full(n, 70.0)
        if map_speed_profile is not None:
            map_dist, map_speeds = map_speed_profile
            if map_dist is not None and map_speeds is not None and len(map_dist) > 1 and len(map_speeds) > 1:
                map_safe_speeds = interp(distances_m, map_dist, map_speeds)
                map_safe_speeds = np.clip(map_safe_speeds, 0.0, 70.0)
        self.vtsc_safe_speeds_map_log = map_safe_speeds.tolist()

        safe_speeds_vision_only = np.zeros(n, dtype=float)
        safe_speeds = np.zeros(n, dtype=float)
        for i in range(n):
            vision_safe_speed = curvature_to_speed(abs(curvature[i]))
            safe_speeds_vision_only[i] = vision_safe_speed
            safe_speeds[i] = min(vision_safe_speed, map_safe_speeds[i])

        self.vtsc_safe_speeds_vision_log = safe_speeds_vision_only.tolist()
        self.vtsc_final_safe_speeds_log = safe_speeds.tolist()

        apex_idxs = find_apexes(curvature, threshold=5e-5)
        self.vtsc_apex_indices_log = apex_idxs

        margin_factor = 4.0
        decel_mult = 1.0
        accel_mult = 1.2
        apex_decel_factor = 0.45
        apex_spool_factor = 0.25
        pre_apex_spool_fract = 0.3

        planned = safe_speeds.copy()

        for apex_i in apex_idxs:
            apex_speed = planned[apex_i]
            safe_apex_speed = safe_speeds[apex_i]

            decel_sec = safe_apex_speed * apex_decel_factor
            spool_sec = safe_apex_speed * apex_spool_factor

            decel_start = self._find_time_index(times, times[apex_i] - decel_sec)

            if apex_i > decel_start:
                v_decel_start = planned[decel_start]
                steps_decel = apex_i - decel_start
                if steps_decel > 0:
                    for idx in range(decel_start, apex_i):
                        f = (idx - decel_start) / float(steps_decel)
                        decel_val = v_decel_start * (1 - f) + apex_speed * f
                        planned[idx] = min(planned[idx], decel_val)

            planned[apex_i] = min(planned[apex_i], apex_speed)

            spool_start_time = times[apex_i] - spool_sec * pre_apex_spool_fract
            spool_start = self._find_time_index(times, spool_start_time)
            spool_start = max(0, min(spool_start, apex_i))

            spool_end_time = times[apex_i] + spool_sec * (1.0 - pre_apex_spool_fract)
            spool_end = self._find_time_index(times, spool_end_time, clip_high=True)
            spool_end = max(spool_start + 1, spool_end)

            if spool_end > spool_start:
                steps_spool = spool_end - spool_start
                v_spool_start = planned[spool_start]
                v_planned_at_spool_end = planned[spool_end - 1] if spool_end > 0 else v_spool_start
                v_safe_at_spool_end = safe_speeds[spool_end - 1] if spool_end > 0 else v_spool_start
                v_spool_target = max(v_planned_at_spool_end, v_safe_at_spool_end)

                if steps_spool > 0:
                    for idx in range(spool_start, spool_end):
                        f = (idx - spool_start) / float(steps_spool)
                        spool_val = v_spool_start * (1 - f) + v_spool_target * f
                        planned[idx] = max(planned[idx], spool_val)

        COMFORT_DECEL = 1.0
        COMFORT_DECEL_STEP4_FACTOR = 1.5
        MIN_DT_PROPAGATION = 0.05
        for i in range(n - 2, -1, -1):
            dt_i = dt_array[i] if i < len(dt_array) else (times[i+1] - times[i] if i+1 < n else 0.05)
            effective_dt_i = max(dt_i, MIN_DT_PROPAGATION)
            if effective_dt_i < 1e-5:
                effective_dt_i = MIN_DT_PROPAGATION

            v_next = planned[i + 1]
            err = planned[i] - v_next
            max_neg_accel = -min(self.MAX_DECEL * decel_mult, COMFORT_DECEL_STEP4_FACTOR * COMFORT_DECEL)
            desired_acc = clip(err / effective_dt_i, max_neg_accel, self.MAX_DECEL * decel_mult)
            feasible_speed = v_next - desired_acc * effective_dt_i
            planned[i] = min(planned[i], feasible_speed)

        base_margin = margin_time_fn(init_speed)
        margin_t = base_margin * margin_factor
        for i in range(n - 2, -1, -1):
            j = self._find_time_index(times, times[i] + margin_t, clip_high=True)
            if j <= i:
                continue
            dt_ij = times[j] - times[i]
            effective_dt_ij = max(dt_ij, MIN_DT_PROPAGATION)
            if effective_dt_ij < 1e-3:
                continue

            v_future = planned[j]
            err = planned[i] - v_future
            desired_acc = clip(err / effective_dt_ij, -COMFORT_DECEL, self.MAX_ACCEL * accel_mult)
            feasible_speed = v_future - desired_acc * effective_dt_ij
            planned[i] = min(planned[i], feasible_speed)

        planned[0] = min(planned[0], safe_speeds[0])
        dt_0 = dt_array[0] if len(dt_array) > 0 else (times[1] - times[0] if n > 1 else 0.05)
        effective_dt_0 = max(dt_0, MIN_DT_PROPAGATION)
        if effective_dt_0 < 1e-5:
            effective_dt_0 = MIN_DT_PROPAGATION
        err0 = planned[0] - init_speed

        if skip_accel_limit and err0 > 0:
            accel0 = clip(err0 / effective_dt_0, -self.MAX_DECEL * decel_mult, 9999.0)
        else:
            accel0 = clip(err0 / effective_dt_0, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)

        planned[0] = init_speed + accel0 * effective_dt_0

        for i in range(1, n):
            dt_i = dt_array[i - 1] if (i - 1 < len(dt_array)) else (times[i] - times[i-1] if i > 0 else 0.05)
            effective_dt_i = max(dt_i, MIN_DT_PROPAGATION)
            if effective_dt_i < 1e-5:
                effective_dt_i = MIN_DT_PROPAGATION
            v_prev = planned[i - 1]
            err = planned[i] - v_prev

            if skip_accel_limit and err > 0:
                desired_acc = clip(err / effective_dt_i, -self.MAX_DECEL * decel_mult, 9999.0)
            else:
                desired_acc = clip(err / effective_dt_i, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)

            feasible_speed = v_prev + desired_acc * effective_dt_i
            planned[i] = min(planned[i], feasible_speed)

        EMERGENCY_DECEL_THRESHOLD = 6.0
        EMERGENCY_SPEED_TOLERANCE = 2.0
        EMERGENCY_LOOKAHEAD_FRAMES = 15

        emergency_braking = False
        lookahead_limit = min(n, EMERGENCY_LOOKAHEAD_FRAMES)
        for i in range(lookahead_limit):
            if planned[i] > (safe_speeds[i] + EMERGENCY_SPEED_TOLERANCE):
                emergency_braking = True
                break

        if emergency_braking:
            for i in range(n - 2, -1, -1):
                dt_i = dt_array[i] if i < len(dt_array) else (times[i+1] - times[i] if i+1 < n else 0.05)
                effective_dt_i = max(dt_i, MIN_DT_PROPAGATION)
                if effective_dt_i < 1e-5:
                    effective_dt_i = MIN_DT_PROPAGATION
                v_next = planned[i + 1]
                err = planned[i] - v_next
                desired_acc = clip(err / effective_dt_i, -EMERGENCY_DECEL_THRESHOLD, EMERGENCY_DECEL_THRESHOLD)
                feasible_speed = v_next - desired_acc * effective_dt_i
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
        return n - 1 if clip_high else n - 2

    def _single_step_fallback(self, v_ego, curvature, turn_aggressiveness):
        """
        Fallback if model data isn't available.
        """
        abs_curv = abs(curvature)
        safe_speed = curvature_to_speed(abs_curv)

        self.vtsc_vision_curvatures_log = [curvature] * N_POINTS_TARGET
        self.vtsc_safe_speeds_vision_log = [safe_speed] * N_POINTS_TARGET
        self.vtsc_final_safe_speeds_log = [safe_speed] * N_POINTS_TARGET
        self.planned_speeds = np.full(N_POINTS_TARGET, safe_speed)
        self.vtsc_planner_init_speed_log = v_ego
        self.vtsc_used_vision_velocities_log = [v_ego] * N_POINTS_TARGET
        self.vtsc_planner_skip_accel_limit_log = False

        current_lat_acc = curvature * (v_ego ** 2)
        if current_lat_acc > self.LOW_LAT_ACC:
            if current_lat_acc < self.HIGH_LAT_ACC:
                alpha = 0.1
            else:
                alpha = self.turn_smoothing_alpha
            raw_target = alpha * self.prev_target_speed + (1 - alpha) * safe_speed
        else:
            alpha = self.reaccel_alpha
            raw_target = alpha * self.prev_target_speed + (1 - alpha) * safe_speed

        return raw_target

class _VTSCPublisher:
    _instance = None
    _pub_master = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def chauffeurTurnSpeedControl(self, msg):
        # Publishing disabled
        return
