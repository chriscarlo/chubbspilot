import numpy as np
import math  # Needed for isnan, isinf
from cereal import car, messaging, log, custom
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.params import Params
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.common.realtime import DT_CTRL
from openpilot.selfdrive.car.hyundai.values import HyundaiFlags, CarControllerParams

# -----------------------------------------------------------------------------
# Lazy singleton publisher for chauffeurHKGTuning, so we bind exactly once
_PUB_CHAUFFEUR_HKG = None
# -----------------------------------------------------------------------------

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
    # quintic hermite blend: 1 - 10*t^3 + 15*t^4 - 6*t^5
    return (
        fp[i] * (1 - 10 * t3 + 15 * t2 * t2 - 6 * t3 * t2)
        + fp[i + 1] * (10 * t3 - 15 * t2 * t2 + 6 * t3 * t2)
    )


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

        # postpone binding until first send
        self.pm = None

    def _get_pubmaster(self):
        global _PUB_CHAUFFEUR_HKG
        if _PUB_CHAUFFEUR_HKG is None:
            _PUB_CHAUFFEUR_HKG = messaging.PubMaster(['chauffeurHKGTuning'])
        return _PUB_CHAUFFEUR_HKG

    def _setup_controllers(self) -> None:
        self.long_control = LongControl(self.CP)
        self.sm = messaging.SubMaster(['controlsState'])
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
        from openpilot.selfdrive.car.hyundai.chubbs.longitudinal_config import CarTuning
        self.car_config = CarTuning.get_car_config(self.CP)

    def update_mpc_mode(self, sm: messaging.SubMaster, dat: custom.ChauffeurHKGTuning) -> None:
        if not sm.valid['controlsState']:
            dat.longControlsStateExperimentalMode = False
            return

        controls_state = sm['controlsState']
        dat.longControlsStateExperimentalMode = controls_state.experimentalMode
        new_mode = 'blended' if controls_state.experimentalMode else 'acc'

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

        dat.longCurrentMode = self.current_mode
        dat.longTransitioning = self.transitioning
        dat.longModeTransitionTimer = self.mode_transition_timer

    def make_jerk(
        self,
        CS: car.CarState,
        actuators: car.CarControl.Actuators,
        dat: custom.ChauffeurHKGTuning
    ) -> float:
        self.jerk_count += 1
        if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
            self.accel_last_jerk = 0.0
            self.jerk = 0.0
            self.jerk_count = 0.0
            self.jerk_upper_limit = 0.0
            self.jerk_lower_limit = 0.0
            self.cb_upper = self.cb_lower = 0.0
            dat.longRawJerk = 0.0
            dat.longCalculatedJerk = 0.0
            dat.longJerkUpperLimit = 0.0
            dat.longJerkLowerLimit = 0.0
            dat.longCbUpper = 0.0
            dat.longCbLower = 0.0
            return 0.0

        if actuators.longControlState == LongCtrlState.stopping:
            raw_jerk_val = self.car_config.jerk_limits[0] / 2 - CS.out.aEgo
        else:
            current_accel = CS.out.aEgo
            raw_jerk_val = current_accel - self.accel_last_jerk
            self.accel_last_jerk = current_accel

        dat.longRawJerk = float(raw_jerk_val)
        self.jerk = raw_jerk_val  # Store pre-akima for logging

        base_jerk = self.jerk
        xp = np.array([-3.5, -2.0, -1.0, 0.0, 1.0, 2.0])
        fp = np.array([-2.5, -1.0, -0.5, 0.0, 0.5, 1.0])
        self.jerk = akima_interp(base_jerk, xp, fp)
        dat.longCalculatedJerk = float(self.jerk) if self.jerk is not None else 0.0
        jerk_max = self.car_config.jerk_limits[1]

        if self.CP.flags & HyundaiFlags.CANFD.value:
            self.jerk_upper_limit = min(
                max(self.car_config.jerk_limits[0], self.jerk * 2.0), jerk_max
            )
            self.jerk_lower_limit = min(
                max(self.car_config.jerk_limits[0], -self.jerk * 4.0), jerk_max
            )
            self.cb_upper = self.cb_lower = 0.0
        else:
            self.jerk_upper_limit = min(
                max(self.car_config.jerk_limits[0], self.jerk * 2.0), jerk_max
            )
            self.jerk_lower_limit = min(
                max(self.car_config.jerk_limits[0], -self.jerk * 2.0), jerk_max
            )
            if self.CP.radarUnavailable:
                self.cb_upper = self.cb_lower = 0.0
            else:
                if not dat.longHkgBrakingEnabled and CS.out.vEgo > 5.0:
                    self.cb_upper = float(
                        np.clip(0.20 + actuators.accel * 0.20, 0.0, 1.0)
                    )
                    self.cb_lower = float(
                        np.clip(0.10 + actuators.accel * 0.20, 0.0, 1.0)
                    )
                else:
                    self.cb_upper = self.cb_lower = 0.0

        dat.longJerkUpperLimit = float(self.jerk_upper_limit)
        dat.longJerkLowerLimit = float(self.jerk_lower_limit)
        dat.longCbUpper = float(self.cb_upper)
        dat.longCbLower = float(self.cb_lower)
        return self.jerk

    def handle_cruise_cancel(self, CS: car.CarState) -> bool:
        if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
            self.accel_last = 0.0
            self.brake_ramp = 0.0
            return True
        return False

    def should_delay_cancel(self, CS: car.CarState) -> bool:
        if CS.out.aEgo < -0.1:
            self.last_decel_time = DT_CTRL * self.jerk_count
        current_time = DT_CTRL * self.jerk_count
        return (
            current_time - self.last_decel_time < self.min_cancel_delay
            and CS.out.aEgo < 0
        )

    def calculate_limited_accel(
        self,
        actuators: car.CarControl.Actuators,
        CS: car.CarState,
        lead_one: log.RadarState.LeadData,
        dat: custom.ChauffeurHKGTuning
    ) -> float:
        """Adaptive acceleration limiting with dynamic jerk based on TTC urgency."""
        dat.longLongControlState = actuators.longControlState
        dat.longVEgo = CS.out.vEgo
        dat.longAEgo = CS.out.aEgo
        dat.longTargetAccelInput = actuators.accel

        if self.handle_cruise_cancel(CS):
            dat.longAccelLast = self.accel_last  # Ensure it's logged even on early exit
            return actuators.accel

        # Populate jerk limits (side-effect) and update mode
        self.make_jerk(CS, actuators, dat)
        self.update_mpc_mode(self.sm, dat)
        target_accel = actuators.accel

        # Mode transition smoothing
        if (
            self.transitioning
            and self.prev_mode == 'acc'
            and self.current_mode == 'blended'
        ):
            if CS.out.vEgo > 4.0 and target_accel < 0.0 and target_accel < self.accel_last:
                hard_brake_threshold = CarControllerParams.ACCEL_MIN * 0.7
                if target_accel < hard_brake_threshold:
                    progress = min(
                        1.0, self.mode_transition_timer / (self.mode_transition_duration * 0.5)
                    )
                    target_accel = self.accel_last + (
                        target_accel - self.accel_last
                    ) * progress
                else:
                    progress = min(
                        1.0, self.mode_transition_timer / self.mode_transition_duration
                    )
                    brake_intensity = abs(target_accel / CarControllerParams.ACCEL_MIN)
                    xp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
                    if brake_intensity < 0.3:
                        fp = np.array([0.0, 0.1, 0.3, 0.7, 1.0])
                    elif brake_intensity < 0.6:
                        fp = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
                    else:
                        fp = np.array([0.0, 0.3, 0.6, 0.9, 1.0])
                    smooth_progress = akima_interp(progress, xp, fp)
                    target_accel = self.accel_last + (
                        target_accel - self.accel_last
                    ) * smooth_progress
            accel_request = target_accel
        else:
            accel_request = target_accel

        dat.longAccelRequest = accel_request
        dat.longBrakingRateLimitActive = False  # Default, set true if condition met

        if CS.out.vEgo > 1.0 and accel_request < 0.15:
            dat.longBrakingRateLimitActive = True
            brake_ratio_val = np.clip(
                abs(accel_request / self.car_config.accel_limits[0]), 0.0, 1.0
            )
            dat.longBrakeRatio = float(brake_ratio_val) if brake_ratio_val is not None else 0.0
            baseline_jerk_val = akima_interp(
                brake_ratio_val,
                np.array([0.25, 0.5, 0.75, 1.0]),
                np.array(self.car_config.brake_response),
            )
            dat.longBaselineJerk = float(baseline_jerk_val) if baseline_jerk_val is not None else 0.0
            effective_jerk = baseline_jerk_val

            v_ego_valid = (
                isinstance(CS.out.vEgo, float) and math.isfinite(CS.out.vEgo)
            )
            accel_last_valid = (
                isinstance(self.accel_last, float)
                and math.isfinite(self.accel_last)
            )
            accel_request_valid = (
                isinstance(accel_request, float)
                and math.isfinite(accel_request)
            )

            v_rel_val = getattr(lead_one, "vRel", 0.0) if lead_one is not None else 0.0
            raw_d_rel_val = (
                getattr(lead_one, "dRel", float("inf")) if lead_one is not None else float("inf")
            )
            a_lead_k_val = getattr(lead_one, "aLeadK", 0.0) if lead_one is not None else 0.0
            lead_ok_val = (
                lead_one is not None
                and getattr(lead_one, "status", 0) > 0
                and math.isfinite(raw_d_rel_val)
                and raw_d_rel_val > 0.0
            )
            dat.longLeadValid = lead_ok_val
            dat.longVRel = v_rel_val
            dat.longDRel = raw_d_rel_val
            dat.longALeadK = a_lead_k_val

            stop_buffer_val = max(1.0, 0.5 + 0.1 * CS.out.vEgo)
            dat.longStopBuffer = stop_buffer_val
            d_gap_val = max(raw_d_rel_val - stop_buffer_val, 0.1)
            dat.longDGap = d_gap_val

            if v_ego_valid and accel_last_valid and accel_request_valid and DT_CTRL > 1e-6:
                _comfy_decel_raw = getattr(self.car_config, "comfy_decel", 2.0)
                a_nom_val = (
                    abs(_comfy_decel_raw)
                    if isinstance(_comfy_decel_raw, (int, float)) and _comfy_decel_raw > 0
                    else 2.0
                )
                dat.longANom = a_nom_val

                _accel_limits_raw = getattr(self.car_config, "accel_limits", (-6.0, 4.5))
                if (
                    isinstance(_accel_limits_raw, (tuple, list))
                    and len(_accel_limits_raw) >= 1
                    and isinstance(_accel_limits_raw[0], (int, float))
                    and _accel_limits_raw[0] < 0
                ):
                    a_max_val = abs(_accel_limits_raw[0])
                else:
                    log.warning(
                        f"long_tuning: Invalid car_config.accel_limits[0]: {_accel_limits_raw}. Using fallback max decel."
                    )
                    a_max_val = 6.0
                dat.longAMax = a_max_val

                # base urgency
                a_req_val = (
                    (max(CS.out.vEgo, 0.0) ** 2 + 0.3 * (-min(v_rel_val, 0.0)) ** 2)
                    / (2.0 * d_gap_val)
                )
                dat.longAReq = a_req_val

                denom = a_max_val - a_nom_val
                urgency_val = 0.0
                if denom > 1e-3:
                    if a_req_val > a_nom_val:
                        urgency_val = min((a_req_val - a_nom_val) / denom, 1.0)
                elif a_req_val > a_nom_val:
                    urgency_val = 1.0

                # TTC-based urgency
                ttc_physics_val = float("inf")
                urg_ttc_val = 0.0
                if lead_ok_val and v_rel_val < -0.5:
                    ttc_physics_val = d_gap_val / max(-v_rel_val, 1e-3)
                    urg_ttc_val = np.clip((3.0 - ttc_physics_val) / 2.0, 0.0, 1.0)
                dat.longTtcPhysics = ttc_physics_val
                dat.longUrgTtc = urg_ttc_val

                # lead decel urgency
                urg_lead_decel_val = 0.0
                if a_lead_k_val < -a_nom_val:
                    urg_lead_decel_val = np.clip(
                        (-a_lead_k_val - a_nom_val) / (a_max_val - a_nom_val), 0.0, 1.0
                    )
                dat.longUrgLeadDecel = urg_lead_decel_val

                urgency_val = max(urgency_val, urg_ttc_val, urg_lead_decel_val)
                dat.longUrgency = urgency_val

                jerk_needed_val = (
                    abs((accel_request - self.accel_last) / DT_CTRL)
                    if accel_request < self.accel_last
                    else 0.0
                )
                dat.longJerkNeeded = jerk_needed_val

                combined_factor_val = max(urgency_val, brake_ratio_val)
                dat.longCombinedFactor = combined_factor_val

                target_max_jerk = 1.5 * MAX_ALLOWABLE_JERK
                jerk_ceiling_val = baseline_jerk_val + combined_factor_val * (
                    target_max_jerk - baseline_jerk_val
                )
                dat.longJerkCeiling = float(jerk_ceiling_val)

                jerk_ceiling_val = np.clip(jerk_ceiling_val, baseline_jerk_val, MAX_ALLOWABLE_JERK)
                dat.longJerkCeiling = float(jerk_ceiling_val)

                effective_jerk = min(max(baseline_jerk_val, jerk_needed_val), jerk_ceiling_val)
            else:
                # invalid / skip physics
                dat.longAReq = float("nan")
                dat.longUrgency = urgency_val
                dat.longTtcPhysics = ttc_physics_val
                dat.longUrgTtc = urg_ttc_val
                dat.longUrgLeadDecel = urg_lead_decel_val
                dat.longJerkNeeded = jerk_needed_val
                dat.longCombinedFactor = combined_factor_val
                dat.longJerkCeiling = float("nan")

            if not (isinstance(effective_jerk, float) and math.isfinite(effective_jerk) and effective_jerk >= 0):
                log.warning(
                    f"long_tuning: Invalid effective_jerk: {effective_jerk}. Reverting to baseline {baseline_jerk_val}."
                )
                effective_jerk = baseline_jerk_val

            dat.longEffectiveJerk = effective_jerk
            max_delta_val = effective_jerk * DT_CTRL
            dat.longMaxDelta = max_delta_val
            if isinstance(self.accel_last, float) and math.isfinite(self.accel_last):
                accel = max(accel_request, self.accel_last - max_delta_val)
            else:
                log.warning(f"long_tuning: accel_last invalid ({self.accel_last}). Using accel_request.")
                accel = accel_request
        else:
            accel = accel_request
            # defaults
            dat.longBrakeRatio = float("nan")
            dat.longBaselineJerk = float("nan")
            dat.longEffectiveJerk = float("nan")
            dat.longMaxDelta = float("nan")
            dat.longLeadValid = False
            dat.longVRel = float("nan")
            dat.longDRel = float("nan")
            dat.longALeadK = float("nan")
            dat.longStopBuffer = float("nan")
            dat.longDGap = float("nan")
            dat.longANom = float("nan")
            dat.longAMax = float("nan")
            dat.longAReq = float("nan")
            dat.longUrgency = float("nan")
            dat.longUrgTtc = float("nan")
            dat.longUrgLeadDecel = float("nan")
            dat.longTtcPhysics = float("nan")
            dat.longJerkNeeded = float("nan")
            dat.longCombinedFactor = float("nan")
            dat.longJerkCeiling = float("nan")

        # --- Overreaction Mitigation Logging (Placeholder) ---
        # TODO: Implement actual overreaction mitigation logic and populate these accurately.
        dat.longOverreactionMitigationActive = False
        dat.longOverreactionMitigationAccelLimited = False
        dat.longOverreactionMitigationOriginalAccel = 0.0
        dat.longOverreactionMitigationLimit = 0.0
        dat.longOverreactionMitigationVRel = 0.0
        dat.longOverreactionMitigationLeadDecel = 0.0
        dat.longOverreactionMitigationDRel = 0.0
        dat.longOverreactionMitigationTtcEst = 0.0
        dat.longOverreactionMitigationClosingFast = False
        dat.longOverreactionMitigationSafeTtc = False
        dat.longOverreactionMitigationDelta = 0.0
        # --- End Overreaction Mitigation Logging ---

        # At end of calculate_limited_accel:
        dat.longAccelPreClip = accel
        self.accel_last = accel
        dat.longAccelLast = self.accel_last
        return accel

    def calculate_accel(
        self,
        actuators: car.CarControl.Actuators,
        CS: car.CarState,
        hkg_tuning_enabled: bool,  # Passed from controller
        hkg_braking_enabled: bool,  # Passed from controller
        lead_one: log.RadarState.LeadData = None
    ) -> float:
        """Calculate acceleration with cruise control status handling and final clipping."""
        msg = messaging.new_message('chauffeurHKGTuning')

        # Explicitly initialise the struct; relying on the implicit pointer has
        # proven unreliable on some capnp/runtime combinations. This always
        # returns a valid builder, so subsequent field assignments cannot fail.
        dat_to_pass = msg.init('chauffeurHKGTuning')

        # Populate parameters
        dat_to_pass.longHkgTuningEnabled = hkg_tuning_enabled
        dat_to_pass.longHkgBrakingEnabled = hkg_braking_enabled
        dat_to_pass.longAccelLast = self.accel_last

        # Mark message as valid before publishing
        msg.valid = True

        if self.handle_cruise_cancel(CS):
            dat_to_pass.longFinalAccel = 0.0
            dat_to_pass.longAccelPreClip = 0.0
            self._get_pubmaster().send('chauffeurHKGTuning', msg)
            return 0.0

        accel = self.calculate_limited_accel(actuators, CS, lead_one, dat_to_pass)
        final_accel = float(
            np.clip(accel, self.car_config.accel_limits[0], self.car_config.accel_limits[1])
        )
        dat_to_pass.longFinalAccel = final_accel

        # Mark message as valid before publishing (redundant, but ensures validity)
        msg.valid = True

        # Publish
        self._get_pubmaster().send('chauffeurHKGTuning', msg)
        return final_accel

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
        self.hkg_tuning_enabled = self.param("HKGtuning")
        self.tuning = HKGLongitudinalTuning(CP) if self.hkg_tuning_enabled else None
        self.jerk_upper_limit = 0.0
        self.jerk_lower_limit = 0.0
        self.cb_upper = 0.0
        self.cb_lower = 0.0

    def apply_tune(self, CP: car.CarParams):
        if self.hkg_tuning_enabled and self.tuning is not None:
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
                self.tuning.cb_lower
            )
        else:
            return JerkOutput(
                self.jerk_upper_limit,
                self.jerk_lower_limit,
                self.cb_upper,
                self.cb_lower
            )

    def calculate_and_get_jerk(
        self,
        actuators: car.CarControl.Actuators,
        CS: car.CarState,
        long_control_state: LongCtrlState,
        lead_one: log.RadarState.LeadData = None
    ) -> JerkOutput:
        if self.hkg_tuning_enabled and self.tuning is not None:
            # main path handles logging and publishing
            return self.get_jerk()
        else:
            jerk_limit = 3.0 if long_control_state == LongCtrlState.pid else 1.0
            self.jerk_upper_limit = jerk_limit
            self.jerk_lower_limit = jerk_limit
            self.cb_upper = 0.0
            self.cb_lower = 0.0
            return self.get_jerk()

    def calculate_accel(
        self,
        actuators: car.CarControl.Actuators,
        CS: car.CarState,
        frogpilot_toggles,  # unused by tuning module now
        lead_one: log.RadarState.LeadData = None
    ) -> float:
        hkg_braking_enabled = self.param("HKGBraking")
        if self.hkg_tuning_enabled and self.tuning is not None:
            return self.tuning.calculate_accel(
                actuators, CS, self.hkg_tuning_enabled, hkg_braking_enabled, lead_one
            )
        else:
            max_accel_upper_limit = CarControllerParams.ACCEL_MAX
            return float(
                np.clip(actuators.accel, CarControllerParams.ACCEL_MIN, max_accel_upper_limit)
            )