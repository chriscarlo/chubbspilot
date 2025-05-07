import numpy as np
import math  # Needed for isnan, isinf
from cereal import car, messaging, log
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.params import Params
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.car.hyundai.values import HyundaiFlags, CarControllerParams

LongCtrlState = car.CarControl.Actuators.LongControlState

MAX_ALLOWABLE_JERK = 20.0  # Max downward jerk


def akima_interp(x, xp, fp):
    """Akima-inspired quintic polynomial interpolation using numpy."""
    if x <= xp[0]:
        return fp[0]
    if x >= xp[-1]:
        return fp[-1]
    i = np.searchsorted(xp, x) - 1
    i = max(0, min(i, len(xp) - 2))
    t = (x - xp[i]) / float(xp[i + 1] - xp[i])
    t2, t3 = t * t, t * t * t
    return fp[i] * (1 - 10 * t3 + 15 * t2 * t2 - 6 * t3 * t2) + fp[i + 1] * (10 * t3 - 15 * t2 * t2 + 6 * t3 * t2)


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
        from openpilot.selfdrive.car.hyundai.chubbs.longitudinal_config import Cartuning
        self.car_config = Cartuning.get_car_config(self.CP)

    def update_mpc_mode(self, sm: messaging.SubMaster) -> None:
        if not sm.valid['controlsState']:
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
        self.jerk_count += 1
        if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
            self.accel_last_jerk = 0.0
            self.jerk = 0.0
            self.jerk_count = 0.0
            self.jerk_upper_limit = 0.0
            self.jerk_lower_limit = 0.0
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
                if not Params().get_bool("HKGBraking") and CS.out.vEgo > 5.0:
                    self.cb_upper = float(np.clip(0.20 + actuators.accel * 0.20, 0.0, 1.0))
                    self.cb_lower = float(np.clip(0.10 + actuators.accel * 0.20, 0.0, 1.0))
                else:
                    self.cb_upper = self.cb_lower = 0.0
        return self.jerk

    def handle_cruise_cancel(self, CS: car.CarState) -> bool:
        if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
            self.accel_last = 0.0
            self.brake_ramp = 0.0
            return True
        return False

    def should_delay_cancel(self, CS: car.CarState) -> bool:
        if CS.out.aEgo < -0.1:
            self.last_decel_time = self.DT_CTRL * self.jerk_count
        current_time = self.DT_CTRL * self.jerk_count
        return (current_time - self.last_decel_time) < self.min_cancel_delay and CS.out.aEgo < 0

    def calculate_limited_accel(self,
                                actuators: car.CarControl.Actuators,
                                CS: car.CarState,
                                frogpilot_toggles,
                                lead_one: log.RadarState.LeadData = None) -> float:
        """Adaptive acceleration limiting with dynamic jerk based on TTC urgency."""

        if self.handle_cruise_cancel(CS):
            return actuators.accel

        # Populate jerk limits (side-effect) and update mode
        self.make_jerk(CS, actuators)
        self.update_mpc_mode(self.sm)
        target_accel = actuators.accel

        # Mode transition smoothing
        if self.transitioning and self.prev_mode == 'acc' and self.current_mode == 'blended':
            if CS.out.vEgo > 4.0 and target_accel < 0.0 and target_accel < self.accel_last:
                hard_brake_threshold = CarControllerParams.ACCEL_MIN * 0.7
                if target_accel < hard_brake_threshold:
                    progress = min(1.0, self.mode_transition_timer / (self.mode_transition_duration * 0.5))
                    target_accel = self.accel_last + (target_accel - self.accel_last) * progress
                else:
                    progress = min(1.0, self.mode_transition_timer / self.mode_transition_duration)
                    brake_intensity = abs(target_accel / CarControllerParams.ACCEL_MIN)
                    xp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
                    if brake_intensity < 0.3:
                        fp = np.array([0.0, 0.1, 0.3, 0.7, 1.0])
                    elif brake_intensity < 0.6:
                        fp = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
                    else:
                        fp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
                    smooth_progress = akima_interp(progress, xp, fp)
                    target_accel = self.accel_last + (target_accel - self.accel_last) * smooth_progress
            accel_request = target_accel
        else:
            accel_request = target_accel

        # --- Dynamic jerk-based braking rate limit ---
        if CS.out.vEgo > 1.0 and accel_request < 0.15:
            # Baseline comfortable jerk
            brake_ratio = np.clip(abs(accel_request / self.car_config.accel_limits[0]), 0.0, 1.0)
            baseline_jerk = akima_interp(brake_ratio,
                                         np.array([0.25, 0.5, 0.75, 1.0]),
                                         np.array(self.car_config.brake_response))

            effective_jerk = baseline_jerk

            # Validity checks
            v_ego_valid = isinstance(CS.out.vEgo, float) and math.isfinite(CS.out.vEgo)
            accel_last_valid = isinstance(self.accel_last, float) and math.isfinite(self.accel_last)
            accel_request_valid = isinstance(accel_request, float) and math.isfinite(accel_request)

            # Radar lead info
            v_rel = getattr(lead_one, "vRel", 0.0) if lead_one is not None else 0.0
            raw_d_rel = getattr(lead_one, "dRel", float("inf")) if lead_one is not None else float("inf")
            lead_ok = (
                lead_one is not None and
                getattr(lead_one, "status", 0) > 0 and
                math.isfinite(raw_d_rel) and
                raw_d_rel > 0.0
            )

            # Dynamic stop buffer scaled by speed
            stop_buffer = max(1.0, 0.5 + 0.1 * CS.out.vEgo)
            d_gap = max(raw_d_rel - stop_buffer, 0.1)

            # Always compute physics-based urgency when data is valid
            if v_ego_valid and accel_last_valid and accel_request_valid and self.DT_CTRL > 1e-6:
                # Nominal vs max deceleration
                _comfy_decel_raw = getattr(self.car_config, "comfy_decel", 2.0)
                a_nom = abs(_comfy_decel_raw) if isinstance(_comfy_decel_raw, (int, float)) and _comfy_decel_raw > 0 else 2.0

                _accel_limits_raw = getattr(self.car_config, "accel_limits", (-6.0, 4.5))
                if (isinstance(_accel_limits_raw, (tuple, list)) and len(_accel_limits_raw) >= 1 and
                   isinstance(_accel_limits_raw[0], (int, float)) and _accel_limits_raw[0] < 0):
                    a_max = abs(_accel_limits_raw[0])
                else:
                    log.warning(f"long_tuning: Invalid car_config.accel_limits[0]: {_accel_limits_raw}. Using fallback max decel.")
                    a_max = 6.0

                try:
                    # Physics-based required deceleration with vRel term
                    a_req = (max(CS.out.vEgo, 0.0)**2 + 0.3 * (-min(v_rel, 0.0))**2) / (2.0 * d_gap)

                    # Compute urgency
                    # Base urgency from energy-gap metric
                    urgency = 0.0
                    denom = a_max - a_nom
                    if denom > 1e-3:
                        if a_req > a_nom:
                            urgency = min((a_req - a_nom) / denom, 1.0)
                    elif a_req > a_nom:
                        urgency = 1.0

                    # -----------------------------------------------------------------
                    # Additional urgency sources to handle fast lead decel / low TTC.
                    # These additions raise urgency ONLY during true hazards, leaving
                    # comfort braking (urgency == 0) untouched.
                    # -----------------------------------------------------------------

                    # 1. Time-to-collision (TTC) based urgency when the gap is closing
                    #    quickly. Uses relative velocity sign < 0 (closing) and gap.
                    urg_ttc = 0.0
                    if lead_ok and v_rel < -0.5:  # ensure meaningful closing rate
                        ttc = d_gap / max(-v_rel, 1e-3)  # seconds to close the gap
                        # Start adding urgency when TTC < 3 s, saturate at TTC <= 1 s
                        urg_ttc = np.clip((3.0 - ttc) / 2.0, 0.0, 1.0)

                    # 2. Lead vehicle decel based urgency. Large negative aLeadK means
                    #    lead is braking hard even before vRel grows.
                    v_lead_acc = getattr(lead_one, "aLeadK", 0.0) if lead_ok else 0.0
                    urg_lead_decel = 0.0
                    if v_lead_acc < -a_nom:  # braking stronger than comfortable decel
                        urg_lead_decel = np.clip((-v_lead_acc - a_nom) / (a_max - a_nom), 0.0, 1.0)

                    # Combine urgencies conservatively (take the maximum).
                    urgency = max(urgency, urg_ttc, urg_lead_decel)

                    # Planner-required jerk (ensure non-negative)
                    jerk_needed = abs((accel_request - self.accel_last) / self.DT_CTRL) if accel_request < self.accel_last else 0.0

                    # Combine factors conservatively: use the greater of urgency or brake_ratio
                    # This allows a faster response if the planner requests strong braking *before* urgency is high
                    combined_factor = max(urgency, brake_ratio)

                    # Scale ceiling up towards a high target based on the combined factor
                    target_max_jerk = 1.5 * MAX_ALLOWABLE_JERK  # Keep original scaling target
                    jerk_ceiling = baseline_jerk + combined_factor * (target_max_jerk - baseline_jerk)

                    # Clip the ceiling to the absolute max allowable jerk for safety/realism
                    # Also ensure it doesn't drop below the baseline
                    jerk_ceiling = np.clip(jerk_ceiling, baseline_jerk, MAX_ALLOWABLE_JERK)

                    # Final effective jerk
                    effective_jerk = min(max(baseline_jerk, jerk_needed), jerk_ceiling)

                except Exception as e:
                    log.error(f"long_tuning: Error in physics jerk calc (lead_ok): {e}")

            # Validate effective jerk
            if not (isinstance(effective_jerk, float) and math.isfinite(effective_jerk) and effective_jerk >= 0):
                log.warning(f"long_tuning: Invalid effective_jerk: {effective_jerk}. Reverting to baseline {baseline_jerk}.")
                effective_jerk = baseline_jerk

            # Apply jerk rate limit
            max_delta = effective_jerk * self.DT_CTRL
            if accel_last_valid:
                accel = max(accel_request, self.accel_last - max_delta)
            else:
                log.warning(f"long_tuning: accel_last invalid ({self.accel_last}). Using accel_request.")
                accel = accel_request

        else:
            # No dynamic braking limit
            accel = accel_request

        # ------------ Overreaction Mitigation -------------
        # Reduce unnecessary heavy braking when the ego is not closing
        # on the lead quickly. This keeps comfort in moderate scenarios
        # while preserving full authority during genuine emergencies.
        try:
            v_rel_local = getattr(lead_one, "vRel", 0.0) if lead_one is not None else 0.0
            lead_dec = getattr(lead_one, "aLeadK", 0.0) if lead_one is not None else 0.0
            raw_d_rel_local = getattr(lead_one, "dRel", float("inf")) if lead_one is not None else float("inf")
            lead_ok_local = (
                lead_one is not None and
                getattr(lead_one, "status", 0) > 0 and
                math.isfinite(raw_d_rel_local) and raw_d_rel_local > 0.0
            )
            if lead_ok_local and accel < 0.0:
                # Estimate simple TTC (only meaningful if v_rel_local < 0)
                ttc_est = raw_d_rel_local / max(-v_rel_local, 1e-3) if v_rel_local < 0 else float("inf")
                # Define thresholds – tuned conservatively for comfort
                closing_fast = v_rel_local < -1.0  # m/s
                safe_ttc = ttc_est > 1.5           # seconds

                if (not closing_fast) and safe_ttc:
                    # --- Dynamic comfort margin ---
                    # Allow the ego to brake only modestly harder than the lead.
                    # Comfort margin (delta) grows linearly with the magnitude of the lead decel,
                    # but is clamped to avoid extreme values and oscillations.

                    # |lead_dec| :   0 → 0.5 m/s² extra
                    #               2.5 → 1.0 m/s² extra
                    #               5.0 → 1.5 m/s² extra (cap)
                    delta = np.clip(0.5 + 0.2 * abs(lead_dec), 0.5, 1.5)

                    # To minimise oscillation from sensor noise, only apply the new limit
                    # if it relaxes braking (i.e., raises accel) by more than 0.05 m/s².
                    accel_limit = lead_dec - delta  # lead_dec is negative
                    if accel < accel_limit - 0.05:
                        accel = accel_limit
        except Exception as e:
            # Fail-safe: never allow mitigation logic to break main control path
            pass

        # Save for next iteration
        self.accel_last = accel
        return accel

    def calculate_accel(self,
                        actuators: car.CarControl.Actuators,
                        CS: car.CarState,
                        frogpilot_toggles,
                        lead_one: log.RadarState.LeadData = None) -> float:
        """Calculate acceleration with cruise control status handling and final clipping."""
        if self.handle_cruise_cancel(CS):
            return 0.0  # Return 0.0 if cruise is cancelled or overridden
        accel = self.calculate_limited_accel(actuators, CS, frogpilot_toggles, lead_one)
        max_accel_upper_limit = self.car_config.accel_limits[1]
        return float(np.clip(accel, self.car_config.accel_limits[0], max_accel_upper_limit))

    def apply_tune(self, CP: car.CarParams) -> None:
        config = self.car_config
        CP.vEgoStopping = config.vego_stopping
        CP.vEgoStarting = config.vego_starting
        CP.stoppingDecelRate = config.stopping_decel_rate
        CP.startAccel = config.start_accel
        CP.startingState = True
        CP.longitudinalActuatorDelay = 0.5


class HKGLongitudinalController:
    """Longitudinal controller which gets injected into CarControllerParams."""
    @staticmethod
    def param(key: str) -> bool:
        val = Params().get(key)
        return val is not None and val.decode('utf-8') == "1"

    def __init__(self, CP: car.CarParams):
        self.CP = CP
        self.tuning = HKGLongitudinalTuning(CP) if self.param("HKGtuning") else None
        self.jerk = None
        self.jerk_upper_limit = 0.0
        self.jerk_lower_limit = 0.0
        self.cb_upper = 0.0
        self.cb_lower = 0.0

    def apply_tune(self, CP: car.CarParams):
        if self.param("HKGtuning") and self.tuning is not None:
            self.tuning.apply_tune(CP)
        else:
            CP.vEgoStopping = 0.5
            CP.vEgoStarting = 0.1
            CP.startingState = True
            CP.startAccel = 1.0
            CP.longitudinalActuatorDelay = 0.5

    def get_jerk(self) -> JerkOutput:
        if self.tuning is not None:
            return JerkOutput(
                self.tuning.jerk_upper_limit,
                self.tuning.jerk_lower_limit,
                self.tuning.cb_upper,
                self.tuning.cb_lower,
            )
        else:
            return JerkOutput(
                self.jerk_upper_limit,
                self.jerk_lower_limit,
                self.cb_upper,
                self.cb_lower
            )

    def calculate_and_get_jerk(self,
                               actuators: car.CarControl.Actuators,
                               CS: car.CarState,
                               long_control_state: LongCtrlState,
                               lead_one: log.RadarState.LeadData = None) -> JerkOutput:
        if self.tuning is not None:
            self.tuning.make_jerk(CS, actuators)
        else:
            jerk_limit = 3.0 if long_control_state == LongCtrlState.pid else 1.0
            self.jerk_upper_limit = jerk_limit
            self.jerk_lower_limit = jerk_limit
            self.cb_upper = 0.0
            self.cb_lower = 0.0
        return self.get_jerk()

    def calculate_accel(self,
                        actuators: car.CarControl.Actuators,
                        CS: car.CarState,
                        frogpilot_toggles,
                        lead_one: log.RadarState.LeadData = None) -> float:
        use_tuning_logic = self.param("HKGBraking") and self.tuning is not None
        if use_tuning_logic:
            accel = self.tuning.calculate_accel(actuators, CS, frogpilot_toggles, lead_one)
        else:
            max_accel_upper_limit = CarControllerParams.ACCEL_MAX
            accel = float(np.clip(actuators.accel, CarControllerParams.ACCEL_MIN, max_accel_upper_limit))
        return accel