import math
import numpy as np
import cereal.messaging as messaging

from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip
from openpilot.selfdrive.modeld.constants import ModelConstants

def nonlinear_lat_accel(v_ego_ms: float, turn_aggressiveness: float = 1.0) -> float:
    """
    Compute lateral acceleration limit based on speed and an aggressiveness factor.
    Modified to increase target speeds at all curvatures by 7-8%.
    """
    v_ego_mph = v_ego_ms * CV.MS_TO_MPH
    base = 1.62  # was 1.5
    span = 2.38
    center = 35.0
    # Kept steepness factor the same
    k = 0.10

    lat_acc = base + span / (1.0 + math.exp(-k * (v_ego_mph - center)))
    lat_acc = min(lat_acc, 3.02)
    return lat_acc * turn_aggressiveness


def margin_time_fn(v_ego_ms: float) -> float:
    """
    Returns a 'margin time' used in backward-pass speed planning.
    The faster you go, the more margin time is used.
    Increased low and medium speed margins for earlier slowing.
    """
    v_low = 0.0
    t_low = 1.5     # Was 1.0 - increased for earlier braking at low speeds
    v_med = 15.0    # ~34 mph
    t_med = 3.5     # Was 3.0 - increased for earlier braking at medium speeds
    v_high = 31.3   # ~70 mph
    t_high = 5.5    # Was 5.0 - increased for earlier braking at high speeds

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


# --------------------
# DYNAMIC SCALING LOGIC
# --------------------
def dynamic_decel_scale(v_ego_ms: float) -> float:
    """
    Scale deceleration based on speed with a continuous function.
    Higher scale at lower speeds for more responsive braking.
    """
    min_speed = 5.0
    max_speed = 25.0
    min_scale = 2.0
    max_scale = 8.0

    # Continuous sigmoid-based transition function
    if v_ego_ms <= min_speed:
        return max_scale
    elif v_ego_ms >= max_speed:
        return min_scale
    else:
        # Normalized position in the transition range [0, 1]
        pos = (v_ego_ms - min_speed) / (max_speed - min_speed)
        # Sigmoid function that smoothly transitions from max_scale to min_scale
        return max_scale - (max_scale - min_scale) * (3*pos*pos - 2*pos*pos*pos)


def dynamic_accel_scale(v_ego_ms: float) -> float:
    """
    Separate scaling for acceleration vs deceleration.
    Allow more aggressive acceleration, especially when exiting turns.
    """
    # Base on the decel scale but allow higher values for acceleration
    decel_scale = dynamic_decel_scale(v_ego_ms)

    # Allow more aggressive acceleration at lower speeds
    if v_ego_ms < 10.0:
        return decel_scale * 1.5
    else:
        # Smoothly reduce the multiplier as speed increases
        return decel_scale * (1.5 - 0.05 * (v_ego_ms - 10.0))


def dynamic_jerk_scale(v_ego_ms: float) -> float:
    """
    Scale jerk limits based on speed.
    """
    return dynamic_decel_scale(v_ego_ms)


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
        max_jerk_accel=None
    ):
        self.turn_smoothing_alpha = turn_smoothing_alpha
        self.reaccel_alpha = reaccel_alpha
        self.LOW_LAT_ACC = low_lat_acc
        self.HIGH_LAT_ACC = high_lat_acc

        self.MAX_DECEL = max_decel
        self.MAX_JERK = max_jerk
        # Allow ~2x acceleration than deceleration
        self.MAX_ACCEL = max_accel if max_accel is not None else 2.0 * max_decel
        self.MAX_JERK_ACCEL = max_jerk_accel if max_jerk_accel is not None else 2.0 * max_jerk

        self.current_accel = 0.0
        self.prev_target_speed = 0.0

        self.planned_speeds = np.zeros(33, dtype=float)
        self.sm = messaging.SubMaster(['modelV2'])

        self.prev_v_cruise_cluster = 0.0

    def reset(self, speed: float) -> None:
        """
        Reset internal state for fresh speed planning.
        """
        self.prev_target_speed = speed
        self.current_accel = 0.0
        self.planned_speeds[:] = speed

    def update(self, v_ego: float, v_cruise_cluster: float, turn_aggressiveness=1.0) -> float:
        """
        Main entry point for the turn speed controller logic.
        Only function is to report max safe target speed for curves.
        """
        self.sm.update()
        modelData = self.sm['modelV2']

        # Always calculate target based on curvature regardless of current speed
        is_resume_event = (v_cruise_cluster > self.prev_v_cruise_cluster) or (self.prev_v_cruise_cluster == 0 and v_cruise_cluster > 0)

        # For resume events, immediately return v_cruise_cluster without any planning
        if is_resume_event:
            self.reset(v_cruise_cluster)
            self.prev_v_cruise_cluster = v_cruise_cluster
            return v_cruise_cluster

        orientation_rate_raw = modelData.orientationRate.z
        velocity_pred_raw = modelData.velocity.x

        MIN_POINTS = 3
        if (
            orientation_rate_raw is None or velocity_pred_raw is None
            or len(orientation_rate_raw) < MIN_POINTS
            or len(velocity_pred_raw) < MIN_POINTS
        ):
            # Fallback if the model data isn't available
            raw_target = self._single_step_fallback(v_ego, 0.0, turn_aggressiveness)
        else:
            orientation_rate = np.abs(np.array(orientation_rate_raw, dtype=float))
            velocity_pred = np.array(velocity_pred_raw, dtype=float)

            n_points = min(len(orientation_rate), len(velocity_pred))
            # Interpolate or slice to exactly 33 points
            if n_points < 33:
                src_indices = np.linspace(0, n_points - 1, n_points)
                dst_indices = np.linspace(0, n_points - 1, 33)
                orientation_rate_33 = np.interp(dst_indices, src_indices, orientation_rate[:n_points])
                velocity_pred_33 = np.interp(dst_indices, src_indices, velocity_pred[:n_points])
            else:
                orientation_rate_33 = orientation_rate[:33]
                velocity_pred_33 = velocity_pred[:33]

            times_33 = np.array(ModelConstants.T_IDXS[:33], dtype=float)

            # Compute curvature array
            eps = 1e-9
            curvature_33 = orientation_rate_33 / np.clip(velocity_pred_33, eps, None)

            # Plan speed trajectory using curvature-based calculation
            self.planned_speeds = self._plan_speed_trajectory(
                orientation_rate_33,
                velocity_pred_33,
                times_33,
                init_speed=v_ego,  # Use current speed for planning
                turn_aggressiveness=turn_aggressiveness
            )
            raw_target = self.planned_speeds[0]

        # Always clamp raw_target to at most v_cruise_cluster
        raw_target = min(raw_target, v_cruise_cluster)
        dt = 0.05  # ~20Hz

        # Apply scaling for acceleration vs deceleration
        scale_decel = dynamic_decel_scale(v_ego)
        scale_jerk = dynamic_jerk_scale(v_ego)
        scale_accel = dynamic_accel_scale(v_ego)

        # Compute acceleration command
        accel_cmd = (raw_target - self.prev_target_speed) / dt

        # Apply different scaling based on whether we're accelerating or decelerating
        if accel_cmd >= 0:
            boost_factor = 1.0
            pos_limit = self.MAX_ACCEL * scale_accel * boost_factor
            accel_cmd = clip(accel_cmd, 0.0, pos_limit)
        else:
            neg_limit = self.MAX_DECEL * scale_decel
            accel_cmd = clip(accel_cmd, -neg_limit, 0.0)

        # Jerk-limit the change in acceleration with different scaling for accel vs decel
        accel_diff = accel_cmd - self.current_accel

        if accel_diff > 0:  # Increasing acceleration
            straightness_factor = 1.0
            max_delta = (self.MAX_JERK_ACCEL * scale_jerk * straightness_factor) * dt
            if accel_diff > max_delta:
                self.current_accel += max_delta
            else:
                self.current_accel = accel_cmd
        elif accel_diff < 0:  # Decreasing acceleration (or increasing deceleration)
            max_delta = (self.MAX_JERK * scale_jerk) * dt
            if accel_diff < -max_delta:
                self.current_accel -= max_delta
            else:
                self.current_accel = accel_cmd
        else:
            self.current_accel = accel_cmd

        final_target_speed = self.prev_target_speed + self.current_accel * dt

        # Always clamp final target speed to the cruise set speed
        final_target_speed = min(final_target_speed, v_cruise_cluster)

        # Save states
        self.prev_target_speed = final_target_speed
        self.prev_v_cruise_cluster = v_cruise_cluster

        return final_target_speed

    def _plan_speed_trajectory(
        self,
        orientation_rate: np.ndarray,
        velocity_pred: np.ndarray,
        times: np.ndarray,
        init_speed: float,
        turn_aggressiveness: float,
        skip_accel_limit: bool = False
    ) -> np.ndarray:
        """
        Build a future speed plan based on curvature.
        Modified to use increased margin factor for earlier deceleration into turns.
        """
        n = len(orientation_rate)
        eps = 1e-9
        dt_array = np.diff(times)

        # (1) Compute curvature
        curvature = np.array([
            orientation_rate[i] / max(velocity_pred[i], eps)
            for i in range(n)
        ], dtype=float)

        # (2) Compute safe speeds from lateral accel
        safe_speeds = np.zeros(n, dtype=float)
        for i in range(n):
            lat_acc_limit = nonlinear_lat_accel(velocity_pred[i], turn_aggressiveness)
            c = max(curvature[i], 1e-9)
            s = math.sqrt(lat_acc_limit / c) if c > 1e-9 else 70.0
            s = clip(s, 0.0, 70.0)
            safe_speeds[i] = s

        # (3) Apex-based shaping pass (using fixed parameters)
        apex_idxs = find_apexes(curvature, threshold=5e-5)
        # Increased margin factor for earlier deceleration into turns
        margin_factor = 2.2  # was 1.85
        decel_mult = 1.0
        accel_mult = 1.0
        # Increased deceleration window for smoother entry into turns
        apex_decel_factor = 0.18  # was 0.14
        apex_spool_factor = 0.08

        planned = safe_speeds.copy()

        for apex_i in apex_idxs:
            apex_speed = planned[apex_i]

            decel_sec = velocity_pred[apex_i] * apex_decel_factor
            spool_sec = velocity_pred[apex_i] * apex_spool_factor

            decel_start = self._find_time_index(times, times[apex_i] - decel_sec)
            spool_start = self._find_time_index(times, times[apex_i] - spool_sec)
            spool_end = self._find_time_index(times, times[apex_i] + spool_sec, clip_high=True)

            # Ramp down to apex_speed (clamp downward)
            if spool_start > decel_start:
                v_decel_start = planned[decel_start]
                steps_decel = spool_start - decel_start
                for idx in range(decel_start, spool_start):
                    f = (idx - decel_start) / float(steps_decel)
                    # Use a non-linear profile for smoother deceleration approach
                    f_curve = f * f  # Quadratic approach feels more natural
                    decel_val = v_decel_start * (1 - f_curve) + apex_speed * f_curve
                    planned[idx] = min(planned[idx], decel_val)

            # Ensure apex zone is clamped to apex_speed
            for idx in range(spool_start, apex_i + 1):
                planned[idx] = min(planned[idx], apex_speed)

            # Spool up after apex (clamp upward) - more aggressive exit from turns
            if spool_end > apex_i:
                steps_spool = spool_end - apex_i
                v_spool_end = planned[spool_end - 1]
                for idx in range(apex_i, spool_end):
                    f = (idx - apex_i) / float(steps_spool)
                    # Use non-linear profile for quicker initial acceleration out of apex
                    f_curve = math.sqrt(f)  # Square root for quicker initial acceleration
                    spool_val = apex_speed * (1 - f_curve) + v_spool_end * f_curve
                    planned[idx] = max(planned[idx], spool_val)

        # (4) Standard backward pass to avoid abrupt decel
        for i in range(n - 2, -1, -1):
            dt_i = dt_array[i] if i < len(dt_array) else 0.05
            v_next = planned[i + 1]
            err = planned[i] - v_next
            desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, self.MAX_DECEL * decel_mult)
            feasible_speed = v_next - desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # (5) Margin-based backward pass with increased margin for earlier slowing
        base_margin = margin_time_fn(init_speed)
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

        # (6) Forward pass for accel limit
        planned[0] = min(planned[0], safe_speeds[0])
        dt_0 = dt_array[0] if len(dt_array) > 0 else 0.05
        err0 = planned[0] - init_speed
        accel0 = clip(err0 / dt_0, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)
        planned[0] = init_speed + accel0 * dt_0

        for i in range(1, n):
            dt_i = dt_array[i - 1] if (i - 1 < len(dt_array)) else 0.05
            v_prev = planned[i - 1]
            err = planned[i] - v_prev
            desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)
            feasible_speed = v_prev + desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # (7) "Emergency" decel override (final pass)
        EMERGENCY_DECEL_THRESHOLD = 6.0
        EMERGENCY_SPEED_TOLERANCE = 3.25
        EMERGENCY_LOOKAHEAD_FRAMES = 8

        emergency_braking = False
        for i in range(min(n, EMERGENCY_LOOKAHEAD_FRAMES)):
            if planned[i] > (safe_speeds[i] + EMERGENCY_SPEED_TOLERANCE):
                emergency_braking = True
                break

        if emergency_braking:
            for i in range(n - 2, -1, -1):
                dt_i = dt_array[i] if i < len(dt_array) else 0.05
                v_next = planned[i + 1]
                err = planned[i] - v_next
                desired_acc = clip(err / dt_i, -EMERGENCY_DECEL_THRESHOLD, EMERGENCY_DECEL_THRESHOLD)
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

    def _single_step_fallback(self, v_ego, curvature, turn_aggressiveness):
        """
        Fallback if model data isn't available - purely curvature based.
        """
        lat_acc = nonlinear_lat_accel(v_ego, turn_aggressiveness)
        c = max(curvature, 1e-9)
        safe_speed = math.sqrt(lat_acc / c) if c > 1e-9 else 70.0
        safe_speed = clip(safe_speed, 0.0, 70.0)

        # Just apply minimal smoothing regardless of speed
        alpha = self.turn_smoothing_alpha
        raw_target = alpha * self.prev_target_speed + (1 - alpha) * safe_speed

        return raw_target
