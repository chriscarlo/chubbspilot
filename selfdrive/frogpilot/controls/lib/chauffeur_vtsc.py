import math
import numpy as np
import cereal.messaging as messaging

from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip, interp
from openpilot.selfdrive.modeld.constants import ModelConstants

# Import the curvature-based lat accel function from MTSC
from openpilot.selfdrive.frogpilot.controls.lib.chauffeur_mtsc import curvature_based_lat_accel

# Determine actual available points from ModelConstants and set target
AVAILABLE_POINTS = len(ModelConstants.T_IDXS)
N_POINTS_TARGET = min(50, AVAILABLE_POINTS) # Use up to 50 points, but no more than available
# Print the determined target points for debugging if needed
# print(f"[VTSC] Using N_POINTS_TARGET = {N_POINTS_TARGET} based on available {AVAILABLE_POINTS} points.")

CRUISING_SPEED = 5.0  # m/s

def nonlinear_lat_accel(v_ego_ms: float, turn_aggressiveness: float = 1.0) -> float:
    """
    Compute lateral acceleration limit based on speed and an aggressiveness factor.
    This version uses a flatter logistic curve centered around 20 mph,
    leveling off near 3.2 m/s².
    """
    v_ego_mph = v_ego_ms * CV.MS_TO_MPH
    base = 1.5
    span = 2.18
    center = 25.0
    k = 0.10  # Flattened gain

    lat_acc = base + span / (1.0 + math.exp(-k * (v_ego_mph - center)))
    return lat_acc * turn_aggressiveness

def margin_time_fn(v_ego_ms: float) -> float:
    """
    Returns a 'margin time' used in backward-pass speed planning.
    The faster you go, the more margin time is used.
    """
    v_low = 0.0
    t_low = 1.0
    v_med = 15.0     # ~34 mph
    t_med = 3.0
    v_high = 31.3    # ~70 mph
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


# --------------------
# DYNAMIC SCALING LOGIC
# --------------------
def dynamic_decel_scale(v_ego_ms: float) -> float:
    min_speed = 3.0   # below this speed => max scaling
    max_speed = 35.0  # above this speed => 1.0
    scale = 9.0 # Default for v_ego <= min_speed
    if v_ego_ms >= max_speed:
        scale = 2.0
    elif v_ego_ms > min_speed: # Only calculate if between min and max
        ratio = (v_ego_ms - min_speed) / (max_speed - min_speed)
        scale = 8.0 + (1.0 - 8.0) * ratio

    return min(scale, 3.0) # Clamp the final scale

def dynamic_jerk_scale(v_ego_ms: float) -> float:
    """
    Same doubling logic for jerk scaling.
    """
    return dynamic_decel_scale(v_ego_ms)


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
        # Allow ~2x acceleration than deceleration
        self.MAX_ACCEL = max_accel if max_accel is not None else 2.0 * max_decel
        self.MAX_JERK_ACCEL = max_jerk_accel if max_jerk_accel is not None else 2.0 * max_jerk

        self.current_accel = 0.0
        self.prev_target_speed = 0.0

        self.planned_speeds = np.zeros(N_POINTS_TARGET, dtype=float) # Use new horizon length
        self.sm = messaging.SubMaster(['modelV2'])

        self.prev_v_cruise_cluster = 0.0

        # ------------------------------
        # Additional state for curvature extrapolation
        # and filtering/hysteresis (Recommendations 1 & 6) - Hysteresis removed, planning always active
        # ------------------------------
        # EMA (exponential moving average) for curvature filtering - Keeping curvature filtering for potential future use/analysis
        self.curvature_ema_ratio = 0.3  # lower = more smoothing
        self._filtered_curvature = None  # filtered maximum curvature value

        # For speed smoothing: filter speed increases only (avoid overshoot when exiting curves)
        self.speed_up_ema_ratio = 0.2
        self._last_model_speed = None

    def reset(self, v_ego: float) -> None:
        """
        Reset internal state so the controller is ready for fresh speed planning.
        """
        self.prev_target_speed = v_ego
        self.current_accel = 0.0
        self.planned_speeds[:] = v_ego

        # Reset filtering state
        self._filtered_curvature = None
        # self.curve_active = False # Removed
        self._last_model_speed = None

    def update(self, v_ego: float, v_cruise_cluster: float,
               map_speed_profile: tuple[np.ndarray, np.ndarray] | None = None,
               turn_aggressiveness=1.0) -> float:
        """
        Main entry point for the turn speed controller logic. Called every cycle.
        Accepts an optional map_speed_profile (distances_m, speeds_mps).
        """
        self.sm.update()
        modelData = self.sm['modelV2']

        # If below a certain speed, just reset and do nothing fancy
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
            # Fallback if the model data isn't available
            raw_target = self._single_step_fallback(v_ego, 0.0, turn_aggressiveness)
        else:
            orientation_rate = np.abs(np.array(orientation_rate_raw, dtype=float))
            velocity_pred = np.array(velocity_pred_raw, dtype=float)

            n_points = min(len(orientation_rate), len(velocity_pred))
            # Interpolate or slice to exactly N_POINTS_TARGET points
            target_indices = np.linspace(0, n_points - 1, N_POINTS_TARGET)
            if n_points < N_POINTS_TARGET:
                src_indices = np.linspace(0, n_points - 1, n_points)
                orientation_rate_target = np.interp(target_indices, src_indices, orientation_rate[:n_points])
                velocity_pred_target = np.interp(target_indices, src_indices, velocity_pred[:n_points])
            else:
                # If we have enough points, interpolate from the source array directly
                src_indices = np.linspace(0, len(orientation_rate) - 1, len(orientation_rate)) # Assume lengths match or take min
                orientation_rate_target = np.interp(target_indices, src_indices, orientation_rate)
                src_indices_vel = np.linspace(0, len(velocity_pred) - 1, len(velocity_pred))
                velocity_pred_target = np.interp(target_indices, src_indices_vel, velocity_pred)
                # Ensure we don't exceed original length if interpolating slice
                orientation_rate_target = orientation_rate_target[:N_POINTS_TARGET]
                velocity_pred_target = velocity_pred_target[:N_POINTS_TARGET]

            # Ensure times corresponds to the target number of points
            times_target = np.array(ModelConstants.T_IDXS[:N_POINTS_TARGET], dtype=float)

            # Compute curvature array
            eps = 1e-9
            curvature_target = orientation_rate_target / np.clip(velocity_pred_target, eps, None)

            # ------------------------------
            # Optional: Keep filtering curvature for analysis or other features, but it no longer gates planning
            # ------------------------------
            current_max_curvature = float(np.max(curvature_target)) # Use target array
            if self._filtered_curvature is None:
                self._filtered_curvature = current_max_curvature
            else:
                self._filtered_curvature = (1 - self.curvature_ema_ratio) * self._filtered_curvature + self.curvature_ema_ratio * current_max_curvature

            # Curvature extrapolation logic removed - planning always active, so no need to force curve_active based on far point.
            # if current_max_curvature >= self.curv_thresh_enter:
            #     far_point_curvature = curvature_33[-1]
            #     if far_point_curvature >= self.curv_thresh_enter:
            #         # Maintain curve control even if vision ends – assume curve continues.
            #         self.curve_active = True

            # --- Always plan speed trajectory using vision and map data (if available) ---
            is_bump_up = (
                (v_cruise_cluster > self.prev_v_cruise_cluster)
                or (self.prev_v_cruise_cluster == 0 and v_cruise_cluster > 0)
            )
            # Resize planned_speeds if it doesn't match the target size
            if len(self.planned_speeds) != N_POINTS_TARGET:
                self.planned_speeds = np.resize(self.planned_speeds, N_POINTS_TARGET)
                self.planned_speeds[:] = self.prev_target_speed # Re-initialize with current speed

            self.planned_speeds = self._plan_speed_trajectory(
                orientation_rate_target, # Use target array
                velocity_pred_target,  # Use target array
                times_target,          # Use target array
                init_speed=self.prev_target_speed,
                map_speed_profile=map_speed_profile,
                turn_aggressiveness=turn_aggressiveness,
                skip_accel_limit=is_bump_up
            )
            raw_target = self.planned_speeds[0]

        # Always clamp raw_target to at most v_cruise_cluster
        # raw_target = min(raw_target, v_cruise_cluster) # NOTE: Speed up EMA filter removed above
        dt = 0.05  # ~20Hz

        # Resume events: when ACC is resumed (or target speed changes), skip smoothing.
        if (v_cruise_cluster > self.prev_v_cruise_cluster) or (self.prev_v_cruise_cluster == 0 and v_cruise_cluster > 0):
            final_target_speed = v_cruise_cluster
            self.current_accel = 0.0  # reset current acceleration
        else:
            scale_decel = dynamic_decel_scale(v_ego) # Keep for deceleration limit
            scale_jerk = dynamic_jerk_scale(v_ego) # Keep for jerk limits

            # Compute acceleration command
            accel_cmd = (raw_target - self.prev_target_speed) / dt

            # Additional "boost" if we see a big difference to planned max
            planned_max = np.max(self.planned_speeds)
            if v_cruise_cluster > self.prev_target_speed:
                ratio = (planned_max - self.prev_target_speed) / max((v_cruise_cluster - self.prev_target_speed), 1e-3)
                ratio = clip(ratio, 0.0, 1.0)
                boost_factor = 1.0 + ratio
            else:
                boost_factor = 1.0

            # Apply limits: Use scale_decel ONLY for negative limit
            pos_limit = self.MAX_ACCEL * boost_factor # Removed scale_decel multiplication here
            neg_limit = self.MAX_DECEL * scale_decel # Keep scale_decel here
            accel_cmd = clip(accel_cmd, -neg_limit, pos_limit)

            # Jerk-limit the change in acceleration
            jerk_mult = 1.0  # or dynamic if needed
            accel_diff = accel_cmd - self.current_accel

            if accel_diff > 0:
                # Use scale_jerk for positive jerk limit? Assume yes for symmetry.
                max_delta = (self.MAX_JERK_ACCEL * scale_jerk * boost_factor * jerk_mult) * dt
                if accel_diff > max_delta:
                    self.current_accel += max_delta
                else:
                    self.current_accel = accel_cmd
            elif accel_diff < 0:
                max_delta = (self.MAX_JERK * scale_jerk * boost_factor * jerk_mult) * dt # Keep scale_jerk here
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
        map_speed_profile: tuple[np.ndarray, np.ndarray] | None,
        turn_aggressiveness: float,
        skip_accel_limit: bool = False
    ) -> np.ndarray:
        """
        Build a future speed plan based on curvature.
        Now incorporates map_speed_profile.
        """
        n = len(orientation_rate)
        eps = 1e-9
        dt_array = np.diff(times)

        # (1) Compute curvature
        curvature = np.array([
            orientation_rate[i] / max(velocity_pred[i], eps)
            for i in range(n)
        ], dtype=float)

        # (1.5) Estimate distance at each time step based on velocity predictions
        distances_m = np.zeros(n, dtype=float)
        if n > 1:
            # Calculate cumulative distance using trapezoidal rule on velocity profile
            distances_m[1:] = np.cumsum((velocity_pred[:-1] + velocity_pred[1:]) / 2.0 * dt_array)
        # distances_m[i] is the estimated distance travelled *at* times[i]

        # (1.6) Interpolate map speed limits at these estimated distances
        map_safe_speeds = np.full(n, 70.0) # Default to high speed if no map profile
        if map_speed_profile is not None:
            map_dist, map_speeds = map_speed_profile
            # Check if both map_dist and map_speeds are valid arrays before using them
            if map_dist is not None and map_speeds is not None and len(map_dist) > 1 and len(map_speeds) > 1:
                # Use numpy interp: interp(x_new, x_existing, y_existing)
                # Ensure map speeds extend far enough, or handle extrapolation
                # np.interp handles points outside range by using boundary values
                map_safe_speeds = interp(distances_m, map_dist, map_speeds)
                # Clamp map speeds just in case interpolation gives weird values
                map_safe_speeds = np.clip(map_safe_speeds, 0.0, 70.0)

        # (2) Compute safe speeds from lateral accel AND map data
        safe_speeds = np.zeros(n, dtype=float)
        for i in range(n):
            # Calculate vision-based safe speed using curvature_based_lat_accel
            abs_curv_vision = abs(curvature[i])
            if abs_curv_vision < 1e-9:
                vision_safe_speed = 70.0 # Max speed for straight
            else:
                # Get base lat accel from curvature
                base_lat_accel = curvature_based_lat_accel(abs_curv_vision)
                # Apply turn aggressiveness multiplier
                lat_acc_limit = base_lat_accel * turn_aggressiveness
                # Calculate speed limit v = sqrt(a / k)
                vision_safe_speed = math.sqrt(lat_acc_limit / abs_curv_vision)

            vision_safe_speed = clip(vision_safe_speed, 0.0, 70.0)
            # Mild tweak around ~30-45 mph range - Keep this empirical tweak?
            # If the goal is pure physics, maybe remove this?
            # Let's keep it for now, as it might smooth behavior.
            if 13.4 <= vision_safe_speed <= 20.1:
                vision_safe_speed *= 0.93

            # Final safe speed is the minimum of vision limit and map limit for this step
            # NOTE: If map data seems ignored, check the incoming map_speed_profile from MTSC
            # or log vision_safe_speed vs map_safe_speeds[i] here.
            safe_speeds[i] = min(vision_safe_speed, map_safe_speeds[i])

        # (3) Apex-based shaping pass (using fixed parameters)
        apex_idxs = find_apexes(curvature, threshold=5e-5)
        margin_factor = 4.0      # Substantially increased (from 3.5) to force much earlier deceleration initiation
        decel_mult = 1.0
        accel_mult = 1.2         # Small increase from original (1.0) for better accel feel - REVERTED from 1.6
        apex_decel_factor = 0.45   # Increased further (from 0.35) to start decel ramp earlier, hitting speed sooner
        apex_spool_factor = 0.15   # Increased from 0.10 to start accel slightly sooner post-apex and smooth transition
        pre_apex_spool_fract = 0.1 # Start spooling much closer to the apex (was 0.5)

        planned = safe_speeds.copy()

        for apex_i in apex_idxs:
            apex_speed = planned[apex_i]
            safe_apex_speed = safe_speeds[apex_i] # Use the calculated safe speed for duration timing

            # Calculate decel/spool duration based on SAFE speed at apex
            decel_sec = safe_apex_speed * apex_decel_factor
            spool_sec = safe_apex_speed * apex_spool_factor

            # Find start of decel ramp relative to apex time
            decel_start = self._find_time_index(times, times[apex_i] - decel_sec)

            # Ramp down to apex_speed (clamp downward) from decel_start to apex_i
            if apex_i > decel_start:
                v_decel_start = planned[decel_start]
                steps_decel = apex_i - decel_start
                if steps_decel > 0: # Avoid division by zero
                    for idx in range(decel_start, apex_i): # Ramp up to apex_i
                        f = (idx - decel_start) / float(steps_decel)
                        decel_val = v_decel_start * (1 - f) + apex_speed * f
                        planned[idx] = min(planned[idx], decel_val)

            # Ensure apex is clamped
            planned[apex_i] = min(planned[apex_i], apex_speed)

            # --- Modified Spool-up Logic ---
            # Find spool start time slightly before apex
            spool_start_time = times[apex_i] - spool_sec * pre_apex_spool_fract
            spool_start = self._find_time_index(times, spool_start_time)
            spool_start = max(0, min(spool_start, apex_i)) # Ensure spool_start is valid and not after apex

            # Find spool end time after apex
            spool_end_time = times[apex_i] + spool_sec * (1.0 - pre_apex_spool_fract) # Ensure total spool duration is still spool_sec
            spool_end = self._find_time_index(times, spool_end_time, clip_high=True)
            spool_end = max(spool_start + 1, spool_end) # Ensure spool_end is after spool_start

            # Spool up starting from spool_start (clamp upward)
            if spool_end > spool_start:
                steps_spool = spool_end - spool_start
                # Start spool from the potentially modified speed at spool_start
                v_spool_start = planned[spool_start]
                # Target speed at the end of the spool window - aim for the MAX of planned/safe speed
                v_planned_at_spool_end = planned[spool_end - 1] if spool_end > 0 else v_spool_start
                v_safe_at_spool_end = safe_speeds[spool_end - 1] if spool_end > 0 else v_spool_start
                v_spool_target = max(v_planned_at_spool_end, v_safe_at_spool_end)

                if steps_spool > 0: # Avoid division by zero
                    for idx in range(spool_start, spool_end):
                        # Interpolate from v_spool_start towards the potentially higher v_spool_target
                        f = (idx - spool_start) / float(steps_spool)
                        spool_val = v_spool_start * (1 - f) + v_spool_target * f
                        # Apply spool-up clamp (only allow speed to increase)
                        planned[idx] = max(planned[idx], spool_val)
            # --- End Modified Spool-up ---

        # (4) Standard backward pass to avoid abrupt decel
        # Limit decel based on COMFORT_DECEL as well
        COMFORT_DECEL = 1.0 # Define COMFORT_DECEL here, before it's used in Step 4 limit
        COMFORT_DECEL_STEP4_FACTOR = 1.5
        for i in range(n - 2, -1, -1):
            # Robust dt calculation
            dt_i = dt_array[i] if i < len(dt_array) else (times[i+1] - times[i] if i+1 < n else 0.05)
            if dt_i < 1e-5: dt_i = 0.05 # Avoid division by zero

            v_next = planned[i + 1]
            err = planned[i] - v_next
            # Apply combined decel limit correctly using COMFORT_DECEL defined above
            max_neg_accel = -min(self.MAX_DECEL * decel_mult, COMFORT_DECEL_STEP4_FACTOR * COMFORT_DECEL)
            desired_acc = clip(err / dt_i, max_neg_accel, self.MAX_DECEL * decel_mult)
            feasible_speed = v_next - desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # (5) Margin-based backward pass prioritizing comfort decel
        # COMFORT_DECEL = 1.0 # No need to redefine here
        base_margin = margin_time_fn(init_speed)
        margin_t = base_margin * margin_factor # Use the large margin_factor (e.g., 3.5)

        for i in range(n - 2, -1, -1):
            # Original Step 5 logic based on margin time
            j = self._find_time_index(times, times[i] + margin_t, clip_high=True)
            if j <= i:
                continue
            dt_ij = times[j] - times[i]
            if dt_ij < 1e-3:
                continue

            v_future = planned[j]
            err = planned[i] - v_future
            # Clip required acceleration between -COMFORT_DECEL and MAX_ACCEL for this long-horizon check
            desired_acc = clip(err / dt_ij, -COMFORT_DECEL, self.MAX_ACCEL * accel_mult)
            feasible_speed = v_future - desired_acc * dt_ij
            planned[i] = min(planned[i], feasible_speed)
            # Removed the incorrect re-application of Step 4 logic from here

        # (6) Forward pass for accel limit (skip positive limit if skip_accel_limit is True)
        planned[0] = min(planned[0], safe_speeds[0])
        dt_0 = dt_array[0] if len(dt_array) > 0 else (times[1] - times[0] if n > 1 else 0.05) # Robust dt_0
        if dt_0 < 1e-5: dt_0 = 0.05
        err0 = planned[0] - init_speed

        if skip_accel_limit and err0 > 0:
            accel0 = clip(err0 / dt_0, -self.MAX_DECEL * decel_mult, 9999.0)
        else:
            accel0 = clip(err0 / dt_0, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)

        planned[0] = init_speed + accel0 * dt_0

        for i in range(1, n):
            # Robust dt calculation
            dt_i = dt_array[i - 1] if (i - 1 < len(dt_array)) else (times[i] - times[i-1] if i > 0 else 0.05)
            if dt_i < 1e-5: dt_i = 0.05
            v_prev = planned[i - 1]
            err = planned[i] - v_prev

            if skip_accel_limit and err > 0:
                desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, 9999.0)
            else:
                desired_acc = clip(err / dt_i, -self.MAX_DECEL * decel_mult, self.MAX_ACCEL * accel_mult)

            feasible_speed = v_prev + desired_acc * dt_i
            planned[i] = min(planned[i], feasible_speed)

        # (7) "Emergency" decel override (final pass)
        EMERGENCY_DECEL_THRESHOLD = 6.0   # [m/s^2]
        EMERGENCY_SPEED_TOLERANCE = 2.0   # [m/s] over safe speed triggers emergency
        EMERGENCY_LOOKAHEAD_FRAMES = 15    # how far to check (relative to N_POINTS_TARGET)

        emergency_braking = False
        lookahead_limit = min(n, EMERGENCY_LOOKAHEAD_FRAMES) # Ensure lookahead doesn't exceed actual plan length
        for i in range(lookahead_limit):
            if planned[i] > (safe_speeds[i] + EMERGENCY_SPEED_TOLERANCE):
                emergency_braking = True
                break

        if emergency_braking:
            for i in range(n - 2, -1, -1):
                # Robust dt calculation
                dt_i = dt_array[i] if i < len(dt_array) else (times[i+1] - times[i] if i+1 < n else 0.05)
                if dt_i < 1e-5: dt_i = 0.05
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
        Fallback if model data isn't available.
        Uses curvature_based_lat_accel now.
        """
        # Original fallback using nonlinear_lat_accel - REMOVED
        # lat_acc = nonlinear_lat_accel(v_ego, turn_aggressiveness)
        # c = max(curvature, 1e-9)
        # safe_speed = math.sqrt(lat_acc / c) if c > 1e-9 else 70.0
        # safe_speed = clip(safe_speed, 0.0, 70.0)
        # --- End REMOVED ---

        # New fallback using curvature_based_lat_accel
        abs_curv = abs(curvature)
        if abs_curv < 1e-9:
            safe_speed = 70.0
        else:
            base_lat_acc = curvature_based_lat_accel(abs_curv)
            lat_acc = base_lat_acc * turn_aggressiveness
            safe_speed = math.sqrt(lat_acc / abs_curv)
        safe_speed = clip(safe_speed, 0.0, 70.0)

        # Smoothing logic remains the same, using the calculated safe_speed
        current_lat_acc = curvature * (v_ego ** 2) # Use actual measured curvature for smoothing trigger
        if current_lat_acc > self.LOW_LAT_ACC:
            if current_lat_acc < self.HIGH_LAT_ACC:
                alpha = 0.1 # Less smoothing when entering curve
            else:
                alpha = self.turn_smoothing_alpha # More smoothing when deep in curve
            raw_target = alpha * self.prev_target_speed + (1 - alpha) * safe_speed
        else:
            # Use reaccel alpha when not actively turning
            alpha = self.reaccel_alpha
            raw_target = alpha * self.prev_target_speed + (1 - alpha) * safe_speed

        return raw_target