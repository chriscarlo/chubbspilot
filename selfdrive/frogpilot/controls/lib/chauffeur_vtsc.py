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
    """
    Compute lateral acceleration limit based on speed and an aggressiveness factor.
    Typically, 'v_ego_ms' is the model's predicted speed, not the actual car speed.
    """
    v_ego_mph = v_ego_ms * CV.MS_TO_MPH
    base = 1.62
    span = 2.38
    center = 35.0
    k = 0.10  # Steepness

    lat_acc = base + span / (1.0 + math.exp(-k * (v_ego_mph - center)))
    lat_acc = min(lat_acc, 3.02)  # Hard cap
    return lat_acc * turn_aggressiveness

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

# --------------------
#   DECEL/ACCEL SCALES
# --------------------
def dynamic_decel_scale(v_ego_ms: float) -> float:
    """
    Scale deceleration based on *current* speed, for comfort/safety timing.
    This does NOT affect the curvature-based apex speed—only how quickly we reach it.
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
        # Normalized position in the transition range [0, 1]
        pos = (v_ego_ms - min_speed) / (max_speed - min_speed)
        # Sigmoid-like function
        return max_scale - (max_scale - min_scale) * (3 * pos * pos - 2 * pos * pos * pos)

def dynamic_accel_scale(v_ego_ms: float) -> float:
    """
    Scale for acceleration exit from corners, also based on current speed.
    """
    # We can keep it linked to dynamic_decel_scale if we like
    decel_scale = dynamic_decel_scale(v_ego_ms)
    if v_ego_ms < 10.0:
        return decel_scale * 1.5
    else:
        # Gradually taper down the boost
        return decel_scale * max(1.0, 1.5 - 0.05 * (v_ego_ms - 10.0))

def dynamic_jerk_scale(v_ego_ms: float) -> float:
    """
    Scale jerk limits (smoothness) based on speed.
    """
    return dynamic_decel_scale(v_ego_ms)

def margin_time_fn(v_ego_ms: float) -> float:
    """
    Returns a 'margin time' used in backward-pass speed planning.
    This is a purely timing-based convenience.
    """
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

# --------------------------
#   MAIN TURN SPEED CONTROLLER
# --------------------------
class VisionTurnSpeedController:
    def __init__(
        self,
        # Comfort / performance knobs
        turn_smoothing_alpha=0.3,
        reaccel_alpha=0.2,
        low_lat_acc=0.20,
        high_lat_acc=0.40,
        # Normal decel/accel/jerk limits
        max_decel=3.0,
        max_jerk=6.0,
        max_accel=None,
        max_jerk_accel=None,
        # Additional "emergency" clamp
        emergency_decel=6.0,
        emergency_speed_tolerance=2.0,
        emergency_lookahead_frames=8,
    ):
        """
        A simpler, safer structure:
          - We'll compute an internal 'safe turn speed' from the curvature, ignoring
            driver input or v_cruise.
          - We'll do one final pass that merges it with v_cruise and applies jerk-limited smoothing.
        """
        self.turn_smoothing_alpha = turn_smoothing_alpha
        self.reaccel_alpha = reaccel_alpha
        self.LOW_LAT_ACC = low_lat_acc
        self.HIGH_LAT_ACC = high_lat_acc

        self.MAX_DECEL = max_decel
        self.MAX_JERK = max_jerk
        self.MAX_ACCEL = max_accel if max_accel is not None else 2.0 * max_decel
        self.MAX_JERK_ACCEL = max_jerk_accel if max_jerk_accel is not None else 2.0 * max_jerk

        # "Emergency" clamp for big overshoot
        self.EMERGENCY_DECEL = emergency_decel
        self.EMERGENCY_SPEED_TOLERANCE = emergency_speed_tolerance
        self.EMERGENCY_LOOKAHEAD_FRAMES = emergency_lookahead_frames

        self.current_accel = 0.0
        self.prev_target_speed = 0.0
        self.prev_v_cruise_cluster = 0.0

        # Model reading
        self.sm = messaging.SubMaster(['modelV2'])

        # Keep track if we were effectively "off" or at zero
        # to detect real "resume" events (not just a small bump)
        self.last_cruise_nonzero = False

    def reset(self, speed: float) -> None:
        """
        Reset internal states to a fresh starting speed.
        """
        self.prev_target_speed = speed
        self.current_accel = 0.0

    def update(self, v_ego: float, v_cruise_cluster: float, turn_aggressiveness=1.0) -> float:
        """
        1) Read model, plan a raw safe-turn speed ignoring cruise
        2) Merge that raw safe speed with v_cruise_cluster
        3) Apply one jerk-limited smoothing
        4) Return final target speed
        """
        self.sm.update()
        model_data = self.sm['modelV2']

        # ---------------------------------------------------------------------
        # 1) Possibly detect a "resume" from standstill or from no set speed.
        #    If we truly are going from 0 => non-zero, that is a "resume."
        # ---------------------------------------------------------------------
        is_real_resume = (not self.last_cruise_nonzero) and (v_cruise_cluster > 1e-1)

        # We'll update the memory for "last_cruise_nonzero"
        self.last_cruise_nonzero = (v_cruise_cluster > 1e-1)

        # If it is a real resume, do a full reset.
        # That means we jump directly to the new setpoint, ignoring old smoothing states.
        if is_real_resume:
            self.reset(v_cruise_cluster)
            self.prev_v_cruise_cluster = v_cruise_cluster
            return v_cruise_cluster

        # ---------------------------------------------------------------------
        # 2) Build a "raw safe speed" from curvature, ignoring v_cruise for the moment.
        # ---------------------------------------------------------------------
        raw_safe_speed = self._compute_raw_safe_speed(model_data, v_ego, turn_aggressiveness)

        # ---------------------------------------------------------------------
        # 3) Merge raw safe speed with driver set speed
        # ---------------------------------------------------------------------
        final_raw = min(raw_safe_speed, v_cruise_cluster)

        # ---------------------------------------------------------------------
        # 4) Apply a single jerk-limited smoothing step
        #    - If we are significantly above raw safe speed => "emergency" decel
        # ---------------------------------------------------------------------

        dt = 0.05  # ~20Hz
        scale_decel = dynamic_decel_scale(v_ego)
        scale_accel = dynamic_accel_scale(v_ego)
        scale_jerk  = dynamic_jerk_scale(v_ego)

        # We check if we are in "emergency" territory:
        # e.g. if final_raw is X m/s, but we are still Y m/s above that, beyond some tolerance.
        # We'll incorporate that as "skip or relax the jerk limit" for decel.
        emergency_decel_active = (self.prev_target_speed > final_raw + self.EMERGENCY_SPEED_TOLERANCE)

        # Normal decel or accel limit
        max_decel_now = self.MAX_DECEL * scale_decel
        max_accel_now = self.MAX_ACCEL * scale_accel
        max_jerk_now  = self.MAX_JERK * scale_jerk
        max_jerk_accel_now = self.MAX_JERK_ACCEL * scale_jerk

        if emergency_decel_active:
            # Use a bigger decel clamp to slow down faster
            max_decel_now = max(max_decel_now, self.EMERGENCY_DECEL)

        # We do the normal jerk-limited single-step to get next speed
        # Desired accel cmd:
        accel_cmd = (final_raw - self.prev_target_speed) / dt

        # Clip by decel or accel
        if accel_cmd >= 0.0:
            accel_cmd = clip(accel_cmd, 0.0, max_accel_now)
        else:
            accel_cmd = clip(accel_cmd, -max_decel_now, 0.0)

        # Then jerk-limit
        accel_diff = accel_cmd - self.current_accel
        if accel_diff > 0:
            # Positive accel (speeding up)
            max_delta = max_jerk_accel_now * dt
            if accel_diff > max_delta:
                self.current_accel += max_delta
            else:
                self.current_accel = accel_cmd
        elif accel_diff < 0:
            # Negative accel (slowing down)
            max_delta = max_jerk_now * dt
            if accel_diff < -max_delta:
                self.current_accel -= max_delta
            else:
                self.current_accel = accel_cmd

        # Finally, the next target speed:
        next_target_speed = self.prev_target_speed + self.current_accel * dt

        # Make sure we don't exceed the driver set speed or the raw safe speed
        # (Though normally final_raw was already min(...) so it shouldn't exceed that)
        next_target_speed = min(next_target_speed, v_cruise_cluster, raw_safe_speed)

        # Update stored values for next iteration
        self.prev_target_speed = next_target_speed
        self.prev_v_cruise_cluster = v_cruise_cluster

        return next_target_speed

    # --------------------------------
    #   Compute raw safe speed from curvature
    # --------------------------------
    def _compute_raw_safe_speed(self, model_data, v_ego, turn_aggressiveness) -> float:
        """
        Build a speed plan ignoring the driver set speed. Just use road curvature
        to produce a 'safe speed', do standard forward/backward passes, then
        return plan[0].
        """
        orientation_rate_raw = model_data.orientationRate.z
        velocity_pred_raw = model_data.velocity.x

        if orientation_rate_raw is None or velocity_pred_raw is None:
            # Fallback if no model data: ~30 m/s (67 mph)
            return 30.0

        orientation_rate = np.abs(np.array(orientation_rate_raw, dtype=float))
        velocity_pred = np.array(velocity_pred_raw, dtype=float)
        n_points = min(len(orientation_rate), len(velocity_pred))
        if n_points < 5:
            # Not enough data
            return 30.0

        # Interpolate to 33 points if needed
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

        # If there's effectively no curvature, no forced slowdown
        if max(curvature_33) < 1e-5:
            return 30.0

        planned_speeds = self._plan_speed_trajectory(
            orientation_rate_33,
            velocity_pred_33,
            curvature_33,
            times_33,
            v_ego,
            turn_aggressiveness
        )
        return planned_speeds[0]

    def _plan_speed_trajectory(
        self,
        orientation_rate: np.ndarray,
        velocity_pred: np.ndarray,
        curvature: np.ndarray,
        times: np.ndarray,
        v_ego: float,
        turn_aggressiveness: float
    ) -> np.ndarray:
        """
        Classic curvature-based speed plan (backward, forward passes, apex shaping)
        ignoring the driver's set speed. We'll do a final clamp later.
        """
        n = len(orientation_rate)
        dt_array = np.diff(times)
        eps = 1e-9

        # (1) Compute curvature-limited speeds
        safe_speeds = np.zeros(n, dtype=float)
        for i in range(n):
            lat_acc_limit = nonlinear_lat_accel(velocity_pred[i], turn_aggressiveness)
            c = max(curvature[i], eps)
            s = math.sqrt(lat_acc_limit / c)
            s = clip(s, 0.0, 70.0)
            safe_speeds[i] = s

        # (2) Identify apexes & shape speed
        apex_idxs = find_apexes(curvature, threshold=5e-5)

        # You can adjust these as you like
        apex_decel_factor = 0.18
        apex_spool_factor = 0.08

        planned = safe_speeds.copy()
        for apex_i in apex_idxs:
            apex_speed = planned[apex_i]

            # Some extra "look-back/forward" time
            decel_sec = velocity_pred[apex_i] * apex_decel_factor + 2.0
            spool_sec = velocity_pred[apex_i] * apex_spool_factor

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

            # Force apex zone to apex_speed
            for idx in range(spool_start, apex_i + 1):
                planned[idx] = min(planned[idx], apex_speed)

            # Spool up after apex
            if spool_end > apex_i:
                steps_spool = spool_end - apex_i
                v_spool_end = planned[spool_end - 1]
                for idx in range(apex_i, spool_end):
                    f = (idx - apex_i) / float(steps_spool)
                    f_curve = math.sqrt(f)
                    spool_val = apex_speed * (1 - f_curve) + v_spool_end * f_curve
                    planned[idx] = max(planned[idx], spool_val)

        # (3) Standard backward pass
        decel_mult = 1.0
        for i in range(n - 2, -1, -1):
            dt_i = dt_array[i] if i < len(dt_array) else 0.05
            v_next = planned[i + 1]
            err = planned[i] - v_next
            desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, self.MAX_DECEL * decel_mult)
            feasible_speed = v_next - desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # (4) Margin-based backward pass, using v_ego for timing only
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

        # (5) Forward pass just to ensure no silly negative accelerations for each step
        accel_mult = 1.0
        for i in range(1, n):
            dt_i = dt_array[i - 1] if (i - 1 < len(dt_array)) else 0.05
            v_prev = planned[i - 1]
            err = planned[i] - v_prev
            desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)
            feasible_speed = v_prev + desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # (6) Final emergency pass inside the plan itself
        # But keep it small so we don't overshadow the single-step smoothing in update().
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
        """
        Helper to find an index in 'times' that is closest to 'target_time'.
        If clip_high=True, clamp to the last index if target_time > times[-1].
        """
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
