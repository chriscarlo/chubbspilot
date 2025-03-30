import math
import numpy as np
import cereal.messaging as messaging

from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip
from openpilot.selfdrive.modeld.constants import ModelConstants

# -----------------------
#   LATERAL ACCELERATION
# -----------------------
def nonlinear_lat_accel(v_ego_ms: float, turn_aggressiveness: float = 1.0) -> float:
    v_ego_mph = v_ego_ms * CV.MS_TO_MPH
    base = 1.5
    span = 2.38
    center = 25.0
    k = 0.10
    lat_acc = base + span / (1.0 + math.exp(-k * (v_ego_mph - center)))
    lat_acc = min(lat_acc, 3.25)
    return lat_acc * turn_aggressiveness

def find_apexes(curv_array: np.ndarray, threshold: float = 5e-5) -> list:
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
    min_speed = 2.0
    max_speed = 40.0
    min_scale = 2.0
    max_scale = 8.0

    if v_ego_ms <= min_speed:
        return max_scale
    elif v_ego_ms >= max_speed:
        return min_scale
    else:
        pos = (v_ego_ms - min_speed) / (max_speed - min_speed)
        return max_scale - (max_scale - min_scale) * (3 * pos * pos - 2 * pos * pos * pos)

def dynamic_accel_scale(v_ego_ms: float) -> float:
    decel_scale = dynamic_decel_scale(v_ego_ms)
    if v_ego_ms < 10.0:
        return decel_scale * 1.5
    else:
        return decel_scale * max(1.0, 1.5 - 0.05 * (v_ego_ms - 10.0))

def dynamic_jerk_scale(v_ego_ms: float) -> float:
    return dynamic_decel_scale(v_ego_ms)

def margin_time_fn(v_ego_ms: float) -> float:
    v_low = 0.0
    t_low = 1.5
    v_med = 15.0
    t_med = 3.5
    v_high = 31.3
    t_high = 5.5

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
def early_approach_time_fn(apex_speed: float) -> float:
    """
    Dynamically return how many seconds *before* the apex we want to reach
    the target speed (about 2–3 s).
    """
    lo_speed = 8.0   # ~18 mph
    hi_speed = 22.0  # ~49 mph
    lo_time = 2.0
    hi_time = 3.0

    if apex_speed <= lo_speed:
        return lo_time
    elif apex_speed >= hi_speed:
        return hi_time
    else:
        ratio = (apex_speed - lo_speed) / (hi_speed - lo_speed)
        return lo_time + ratio * (hi_time - lo_time)

def early_spool_time_fn(apex_speed: float) -> float:
    """
    Dynamically return how many seconds *before/after* the apex we begin spooling up.
    We'll spool out of apex about 1–2 s earlier depending on speed.
    """
    lo_speed = 8.0
    hi_speed = 22.0
    lo_time = 1.0
    hi_time = 2.0

    if apex_speed <= lo_speed:
        return lo_time
    elif apex_speed >= hi_speed:
        return hi_time
    else:
        ratio = (apex_speed - lo_speed) / (hi_speed - lo_speed)
        return lo_time + ratio * (hi_time - lo_time)

# --- ADDED/CHANGED ---
def short_horizon_factor(horizon_time: float) -> float:
    """
    Returns a multiplier in [0.4, 1.0] based on how short the model horizon is.
    If horizon is under ~1.5 s, we drastically reduce spool (factor ~ 0.4).
    If horizon is >= ~4 s, we allow normal spool (factor = 1.0).
    """
    min_horizon = 1.5
    max_horizon = 4.0
    lo_factor = 0.4
    hi_factor = 1.0

    if horizon_time <= min_horizon:
        return lo_factor
    elif horizon_time >= max_horizon:
        return hi_factor
    else:
        ratio = (horizon_time - min_horizon) / (max_horizon - min_horizon)
        return lo_factor + ratio * (hi_factor - lo_factor)

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

        self.sm = messaging.SubMaster(['modelV2'])

        # Tracks if we had a nonzero cruise last cycle
        # so we can detect real "resume from standstill."
        self.last_cruise_nonzero = False

    def reset(self, speed: float) -> None:
        self.prev_target_speed = speed
        self.current_accel = 0.0

    def update(self, v_ego: float, v_cruise_cluster: float, turn_aggressiveness=1.0) -> float:
        self.sm.update()
        model_data = self.sm['modelV2']

        is_real_resume = (not self.last_cruise_nonzero) and (v_cruise_cluster > 1e-1)
        self.last_cruise_nonzero = (v_cruise_cluster > 1e-1)

        if is_real_resume:
            self.reset(v_cruise_cluster)
            self.prev_v_cruise_cluster = v_cruise_cluster
            return v_cruise_cluster

        raw_safe_speed = self._compute_raw_safe_speed(model_data, v_ego, turn_aggressiveness)
        final_raw = min(raw_safe_speed, v_cruise_cluster)

        # Single-step jerk-limited smoothing:
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
            return 30.0  # fallback

        orientation_rate = np.abs(np.array(orientation_rate_raw, dtype=float))
        velocity_pred = np.array(velocity_pred_raw, dtype=float)
        n_points = min(len(orientation_rate), len(velocity_pred))

        # --- ADDED/CHANGED ---
        # Instead of requiring 5 points, let’s require at least 3.
        # If fewer than 3, fallback to a more moderate safe speed (e.g. ~22 m/s).
        if n_points < 3:
            return 22.0  # ~49 mph fallback

        # We'll still aim for 33 points if possible
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

        # If even with interpolation the curvature is essentially zero, fallback.
        if max(curvature_33) < 1e-5:
            return 30.0

        # --- ADDED/CHANGED ---
        # Determine how far into the future we actually have valid data.
        valid_pts = np.where(velocity_pred_33 > 0.01)[0]
        if len(valid_pts) == 0:
            # No valid velocity points at all, fallback.
            return 30.0
        horizon_idx = valid_pts[-1]
        horizon_time = times_33[horizon_idx]

        # Pass horizon_time into the planner
        planned_speeds = self._plan_speed_trajectory(
            orientation_rate_33,
            velocity_pred_33,
            curvature_33,
            times_33,
            v_ego,
            turn_aggressiveness,
            horizon_time  # <--- new param
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
        horizon_time: float  # --- ADDED ---
    ) -> np.ndarray:
        n = len(orientation_rate)
        dt_array = np.diff(times)
        eps = 1e-9

        # 1) Basic curvature-limited speeds
        safe_speeds = np.zeros(n, dtype=float)
        for i in range(n):
            lat_acc_limit = nonlinear_lat_accel(velocity_pred[i], turn_aggressiveness)
            c = max(curvature[i], eps)
            s = math.sqrt(lat_acc_limit / c)
            s = clip(s, 0.0, 70.0)
            safe_speeds[i] = s

        # 2) Find apexes
        apex_idxs = find_apexes(curvature, threshold=5e-5)
        planned = safe_speeds.copy()

        # We'll compute a short-horizon factor just once
        spool_mult = short_horizon_factor(horizon_time)  # --- ADDED ---

        for apex_i in apex_idxs:
            apex_speed = planned[apex_i]

            # "Arrive early" to the apex speed by 2–3 s, scaled by apex_speed
            decel_sec = early_approach_time_fn(apex_speed)
            # "Spool out" earlier, 1–2 s, scaled by apex_speed
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
                    f_curve = f * f
                    decel_val = v_decel_start * (1 - f_curve) + apex_speed * f_curve
                    planned[idx] = min(planned[idx], decel_val)

            # Force apex zone
            for idx in range(spool_start, apex_i + 1):
                planned[idx] = min(planned[idx], apex_speed)

            # Spool up out of apex - but *reduce* if horizon is short
            if spool_end > apex_i:
                steps_spool = spool_end - apex_i
                v_spool_end = planned[spool_end - 1]
                for idx in range(apex_i, spool_end):
                    f = (idx - apex_i) / float(steps_spool)
                    f_curve = math.sqrt(f)
                    spool_val = apex_speed * (1 - f_curve) + v_spool_end * f_curve
                    # --- ADDED: multiply by spool_mult to be more conservative if horizon is short
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
        return n - 1 if clip_high else n - 2