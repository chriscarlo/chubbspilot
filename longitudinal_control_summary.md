# Longitudinal Control Path Analysis Summary (Kia EV6 HDA2 CANFD - Standard Profile - ACC Mode)

This document summarizes the analysis of the longitudinal control system in openpilot for a Kia EV6 (2023, HDA2 CANFD) using the standard longitudinal personality, **Adaptive Cruise Control (ACC) mode only (non-e2e longitudinal)**, and non-radarless model, focusing on potential causes for insufficient deceleration during aggressive lead vehicle braking.

**Vehicle Configuration:**
*   Car: Kia EV6 2023 (Hyundai HDA2 CANFD Platform) - Identified via `fingerprint` in `interface.py`.
*   Interface: `selfdrive.car.hyundai.radar_interface` (`is_hyundai_interface = True` set in `radard.py` `main` function based on the imported module path, not a toggle).
*   Model: Non-radarless (`frogpilot_toggles.radarless_model = False`).
*   Longitudinal Control Mode: `openpilotLongitudinalControl = True` (set in `interface.py`), `pcmCruise = False`. Stock SCC ECU disabled via `disable_ecu` in `interface.py`.
*   Longitudinal Personality: Standard (influences initial MPC cost weights if not overridden).
*   FrogPilot Toggles (Relevant for ACC path):
    *   `lead_detection_probability`: Threshold for vision-only lead detection (`get_lead`).
    *   `increased_stopped_distance`: Added buffer to `dRel` at low speeds (`get_lead`).
    *   `allow_far_lead_tracking`: Allows using far radar tracks if no vision match (`get_lead`).
    *   `adjacent_lead_tracking`: Enables tracking leads in adjacent lanes (populates `leadLeft`/`Right` etc. in `radarState`).
    *   `taco_tune`: Enables curvature-based speed limiting in planner.
    *   `accelerationJerk`, `dangerJerk`, `speedJerk`: Costs used by MPC.
    *   `minAcceleration`, `maxAcceleration`: Base acceleration limits for MPC.
    *   `vCruise`, `tFollow`: Cruise speed and follow time inputs for MPC.
    *   `vEgoStopping`: Speed threshold used in `longitudinalPlan.shouldStop` calculation.
*   HKG Tuning Params (from Params): `"HKGtuning"` = True, `"HKGBraking"` = True assumed enabled to activate the custom rate-limiting logic.
*   KF Tuning: Defaults (`Q=diag([0.3*dt, 0.3*dt])**2`, `R=diag([1.0, 2.0])`) used directly in `radard.py` `KF2D`.

**Phase 1: Radar Data Processing (`selfdrive/controls/radard.py`)**

1.  **Main Loop & Initialization (`main`)**:
    *   Determines `is_hyundai_interface = True` by checking the module path of the imported `RadarInterface` (from `CarParams`).
    *   Subscribes to `can`, `modelV2`, `carState`, `frogpilotCarState`, `frogpilotPlan`.
    *   Initializes `RadarInterface` (`RI`) and `RadarD`.
    *   Runs a loop at `1.0 / CP.radarTimeStep` Hz.
2.  **Data Acquisition & Preprocessing (`main` loop -> `RI.update` -> `RadarD.update`)**:
    *   Receives raw CAN data (`can_strings`).
    *   `RI.update` (`selfdrive/car/hyundai/radar_interface.py`) processes CAN data using `opendbc` and the platform's DBC (`hyundaicanfd`). It parses forward radar messages (`RADAR_TRACK_...`) and, if `CP.flags & HyundaiFlags.CORNER_RADAR` is set (likely for HDA2), also parses corner radar messages (`RADAR_POINTS_...`, `BLINDSPOTS_FRONT_CORNER_...`) from different CAN buses. It populates a `car.RadarData` object (`rr`) containing a list of `RadarPoint` objects (`rr.points`) and potential errors (`rr.errors`). Each point is assigned a unique `trackId`:
        *   0-999: Forward radar tracks.
        *   1000-1999: Rear left corner radar points.
        *   2000-2999: Rear right corner radar points.
        *   3000-3999: Front left corner radar points (simplified data).
        *   4000-4999: Front right corner radar points (simplified data).
        Each point contains `dRel`, `yRel`, `vRel`, `measured`.
    *   `RadarD.update` reads subscribed messages (`sm`).
    *   Updates internal `v_ego` from `sm['carState'].vEgo` and maintains a history (`self.v_ego_hist`) using a `deque` with length based on `RI.delay`.
    *   Calculates `model_v_ego` using `sm['modelV2'].velocity.x` as the primary source. If `frogpilot_toggles.classic_model` is true and `sm['modelV2'].temporalPose.trans` is available, it uses that instead. If neither is available, it falls back to the current `self.v_ego`.
    *   Reads `sm['modelV2'].laneLines` for later use in adjacent/far lead checks.
3.  **Track Management (`RadarD.update`)**:
    *   Parses `rr.points` into `ar_pts` dictionary keyed by `trackId`.
    *   Removes tracks from internal `self.tracks` if their `trackId` is no longer present in `ar_pts`.
    *   Iterates through `ar_pts`:
        *   If `trackId` is new, creates a new `Track` object (`self.tracks[ids] = Track(...)`), initializing its KF state with the first measurement.
        *   Calls `self.tracks[ids].update(...)` with the latest point data (`d_rel`, `y_rel`, `v_rel`, `measured`) and historical `v_ego` (`self.v_ego_hist[0]`).
4.  **Track Object (`Track`)**:
    *   Stores `identifier` (track ID), raw measurements (`dRel`, `yRel`, `vRel`, `vLead`, `measured`), internal counter (`cnt`), and `is_hyundai_interface` flag.
    *   Maintains a `KF2D` Kalman Filter (`self.kf`) for state `[dRel_K, vRel_K]`. Initial state (`x`) is set from the first raw measurement (`d_rel_init`, `v_rel_init`). Initial uncertainty `P=diag([10.0, 10.0])`. KF uses default process noise `Q` and measurement noise `R` values (defined in `KF2D`).
    *   Stores the latest KF-filtered states (`dRel_K`, `vRel_K`) and the KF-derived lead velocity (`vLeadK = vRel_K + v_ego` using the delayed `v_ego` passed to `update`). Also stores previous filtered values (`prev_dRel_K`, `prev_vRel_K`) for derivative calculations.
    *   **KF Update (`Track.update`)**:
        *   Stores latest raw measurements.
        *   Predicts next KF state: `self.kf.predict()`.
        *   Updates KF with current raw measurements: `self.kf.update(z)` where `z = np.array([d_rel, v_rel])`.
        *   Extracts the updated `dRel_K` and `vRel_K` from `self.kf.x`.
    *   **Hyundai-Specific `vRel` Calculation (`Track.update`)**: Because `is_hyundai_interface=True`, the `Track` calculates a `calculated_vRel = (current_dRel_K - prev_dRel_K) / dt`. This uses the *derivative of the filtered distance (`dRel_K`)*, not the KF's filtered velocity (`vRel_K`). If `is_hyundai_interface=False`, `calculated_vRel` is set to `vRel_K`. This `calculated_vRel` is stored.
    *   **Lead Acceleration (`aLeadK`) Calculation (`Track.update`)**: Calculated *always* as `aLeadK = (vRel_K - prev_vRel_K) / dt`. This uses the derivative of the *KF's filtered velocity (`vRel_K`)*, *not* the distance-derived `calculated_vRel` (even for Hyundai). Stores `aLeadK` and updates `prev_vRel_K`.
    *   **`aLeadTau` Adaptation (`Track.update`)**: Adapts `self.aLeadTau` based on `aLeadK` magnitude (increases if `abs(aLeadK) < 0.5`, decreases otherwise, bounded by `_LEAD_ACCEL_TAU = 0.6`).
    *   **Potential Issue**: Confirmed mismatch between the reported `vRel` (which is `calculated_vRel` derived from `dRel_K` for Hyundai) used downstream in `get_RadarState`, and the source for `aLeadK` (which is always derived from the KF's `vRel_K`).
5.  **Lead Selection (`RadarD.update` -> `get_lead`)**:
    *   Filters tracks to only consider `forward_radar_tracks` (track ID < 1000) for `leadOne` and `leadTwo`.
    *   Calls `get_lead` separately for `leadOne` (from `leadsV3[0]`, `low_speed_override=True`) and `leadTwo` (from `leadsV3[1]`, `low_speed_override=False`).
    *   **Inside `get_lead`** (arguments: `v_ego`, `ready`, `tracks`, `lead_msg`, `model_v_ego`, `model_data`, `frogpilot_toggles`, `frogpilotCarState`, `low_speed_override`):
        *   Requires `ready` (model seen) and vision `prob > frogpilot_toggles.lead_detection_probability` to attempt matching or use vision-only.
        *   Attempts to match vision lead (`lead_msg`) to a forward radar track using `match_vision_to_track`.
            *   `match_vision_to_track` compares vision lead data (distance adjusted by `RADAR_TO_CAMERA`) against *raw* radar track values (`c.dRel`, `c.yRel`, `c.vRel`) - **not** the KF filtered states - using Laplacian PDF probabilities. Returns the matching `Track` object if probability is highest and sanity checks (`dist_sane`, `vel_sane`, also using raw values) pass, otherwise `None`.
        *   If matched (`track is not None`), uses `track.get_RadarState(lead_msg.prob)` to populate `lead_dict` (using filtered states internally).
        *   If no match but vision `prob` is high enough (`ready and lead_msg.prob > ...`), uses `get_RadarState_from_vision(lead_msg, v_ego, model_v_ego)` (uses vision data directly, sets `aLeadTau=0.3`, `radar=False`).
        *   (If `low_speed_override=True`): Checks the `forward_radar_tracks` passed into `get_lead` using `Track.potential_low_speed_lead(v_ego)`. If any found, picks the closest one by raw `dRel` and uses its `get_RadarState()` to **overwrite** `lead_dict` if no lead was found yet OR if this low-speed track is closer than the current `lead_dict['dRel']`.
        *   (Nested within `low_speed_override=True` block): If `frogpilot_toggles.allow_far_lead_tracking` is enabled and `lead_dict['status']` is still `False`, checks the `forward_radar_tracks` using `Track.potential_far_lead(model_data)`. If any found, picks the closest one by raw `dRel` and uses its `get_RadarState()` to **overwrite** `lead_dict`. **Note:** Explicitly overwrites `lead_dict['vLead']` with `lead_dict['vLeadK']` in this specific case.
        *   Applies `frogpilot_toggles.increased_stopped_distance` by subtracting it from the final `lead_dict['dRel']` if `frogpilotCarState.trafficModeActive` is `False`.
        *   Returns the final `lead_dict`.
6.  **Adjacent Lead Selection (`RadarD.update` -> `get_adjacent_lead`)**:\
    *   Only runs if `frogpilot_toggles.adjacent_lead_tracking` is enabled and model is ready.
    *   Calls `get_adjacent_lead` for `leadLeft`, `leadLeftFar`, `leadRight`, `leadRightFar` using all tracks, `model_data` (`sm['modelV2']`), `standstill` status.
    *   **Inside `get_adjacent_lead`**:
        *   Filters *all* tracks (not just forward) using `Track.potential_adjacent_lead(...)` based on lane lines from `model_data` and `standstill` status.
        *   If any tracks match, picks the closest one by `dRel` and uses its `get_RadarState()` to populate the `lead_dict`.
        *   Returns the `lead_dict`.
7.  **Lead State Packaging (`Track.get_RadarState`)**: Argument `model_prob=0.0`.
    *   Returns lead dictionary for `radarState` message.
    *   `dRel`: Filtered `dRel_K`.
    *   `yRel`: Raw `yRel`.
    *   `vRel`: Value stored in `self.vRel` (distance-derived `calculated_vRel` for Hyundai interface, or KF-filtered `vRel_K` otherwise).
    *   `vLead`: `self.vRel + v_ego_t_read`. `v_ego_t_read` is estimated within `get_RadarState` as `self.vLeadK - self.vRel_K` to approximate the `v_ego` at the time of the KF update corresponding to `self.vRel_K`, ensuring `vLead` corresponds correctly to `self.vRel`.
    *   `vLeadK`: KF-filtered `vLeadK` (from `self.vRel_K + v_ego_delayed` in `Track.update`).
    *   `aLeadK`: KF-velocity-derived `aLeadK` (stored in `self.aLeadK`).
    *   `aLeadTau`: Adapted `aLeadTau`.
    *   `ttc`: Calculated using `safe_ttc(self.dRel_K, self.vRel)`. Returns `d / (-v)` if `v < -0.1` and `d > 0.1`, else `1000.0`.
    *   `status`: Always `True` (validity of track is checked before calling `get_RadarState`).
    *   `fcw`: Calculated via `self.is_potential_fcw(model_prob)`. This function returns `True` if `model_prob > 0.9` AND internal checks pass (`self.dRel < 120`, `abs(self.vRel*3.6) < 120`, `abs(self.aLeadK) < 10`, `self.valid`).
    *   `modelProb`: Probability from vision model (`model_prob` passed in, defaults to 0.0 if called without matching vision lead).
    *   `radar`: Always `True`.
    *   `radarTrackId`: Track identifier (`self.identifier`).
8.  **Other Calculations (`RadarD.update`)**:
    *   Calculates forward blindspot status (`leftForwardBlindspot`, `rightForwardBlindspot`) using `get_forward_blindspot`:
        *   Iterates through `self.tracks`.
        *   If a track has `identifier >= 3000` (front corner radar points) and meets proximity criteria (`dRel < 4.5`, `abs(yRel) < 1.0` relative to the side), sets the corresponding flag (`leftForwardBlindspot` or `rightForwardBlindspot`) to `True`.
    *   Updates internal `frogpilot_toggles` struct from `sm['frogpilotPlan'].frogpilotToggles` if `sm.updated['frogpilotPlan']` and `sm['frogpilotPlan'].togglesUpdated` are true.
9.  **Output (`RadarD.publish`)**:
    *   Publishes `radarState` message containing:
        *   `leadOne`, `leadTwo` (populated by `get_lead`).
        *   `leadLeft`, `leadRight`, `leadLeftFar`, `leadRightFar` (populated by `get_adjacent_lead`).
        *   Timestamps (`mdMonoTime` from `modelV2`, `canMonoTime` from `carState`), Errors (`radarErrors` from `RI.update`), Lag (`cumLagMs` based on `modelExecutionTime`), Blindspot status (`leftForwardBlindspot`, `rightForwardBlindspot`).
    *   Publishes `liveTracks` message containing filtered state data for all currently active tracks (`self.tracks.values()`) for UI/debugging:
        *   `dRel`: Filtered `trk.dRel_K`.
        *   `yRel`: Raw `trk.yRel`.
        *   `vRel`: `trk.vRel` (distance-derived for Hyundai).
        *   `aRel`: `trk.aLeadK` (KF-velocity-derived).
        *   `vLead`: `trk.vLeadK` (KF-velocity-derived).
        *   `aLead`: `trk.aLeadK` (KF-velocity-derived).
        *   `vLat`: 0.0.
        *   `measured`: `trk.measured`.
        *   `status`: 1 (hardcoded).
        *   `fcw`: `trk.potential_fcw()`.
        *   `stationary`: `trk.stationary` (checks `abs(trk.vRel) < 0.1`).
        *   `label`: 'hostile' (hardcoded).
        *   `trackId`: `trk.identifier`.
        *   `radarType`: Derived from `trackId` range (0: Front, 1: Rear Left, 2: Rear Right, 3: Front Left, 4: Front Right).
        *   `isCornerRadar`: Boolean based on `trackId >= 1000`.

**Phase 2: Longitudinal Planning (`selfdrive/controls/plannerd.py` -> `selfdrive/controls/lib/longitudinal_planner.py`)**

1.  **Initialization**: The `LongitudinalPlanner` object is initialized in `plannerd.py` with the `CarParams` (`CP`). Internally, it initializes state variables like `a_desired` and `v_desired_filter`, and creates a `LongitudinalMpc` instance.
2.  **Input**: Subscribed messages via SubMaster (`sm`) in `plannerd.py`. The `plannerd_thread` subscribes to `carControl`, `carState`, `controlsState`, `liveParameters`, `radarState`, `modelV2`, `frogpilotCarState`, and `frogpilotPlan`. The planner accesses data from these messages within the `update` method, specifically using:
    *   `radarState`: `leadOne`, `leadTwo` (when `radarless_model=False`).
    *   `carState`: `vEgo`, `aEgo`, `standstill`, `steeringAngleDeg`.
    *   `controlsState`: `vCruise`, `longControlState`, `forceDecel`, `personality`, `experimentalMode`.
    *   `modelV2`: Contains model predictions (position, velocity, acceleration, orientation rate, metadata like `gasPressProbs`).
    *   `frogpilotPlan`: `minAcceleration`, `maxAcceleration`, `accelerationJerk`, `dangerJerk`, `speedJerk`, `vCruise`, `tFollow`, `frogpilotToggles` struct (including `vEgoStopping`).
    *   `frogpilotCarState`: `trafficModeActive`.
    *   `liveParameters`: `angleOffsetDeg`.
    *   `carControl`: `orientationNED` (specifically pitch, `orientationNED[1]`, used for coasting calculation).
    FrogPilot toggles (`frogpilot_toggles`) are read initially in `plannerd` and updated dynamically if `frogpilotPlan.togglesUpdated` is true, then passed into the planner's `update` method.
3.  **Planner Update (`LongitudinalPlanner.update`)**:
    *   Receives `radarless_model` boolean, `sm` object, and `frogpilot_toggles` struct as arguments.
    *   Determines `mpc.mode` ('acc' or 'blended'). Set to 'acc' mode as `sm['controlsState'].experimentalMode` is false.
    *   Handles state reset logic on disengagement (`longControlState.off`) or if cruise is not yet initialized (`vCruise == V_CRUISE_UNSET`). If reset, planner state (`v_desired_filter`, `a_desired`) is re-initialized based on current `v_ego`/`a_ego` (clipped to accel limits). Sets `prev_accel_constraint` flag based on reset state and `standstill`.
    *   Calculates `v_model_error` using `get_speed_error(sm['modelV2'], v_ego)`.
    *   Parses model predictions (`modelV2`) using `parse_model`, adjusting position and velocity based on `v_model_error`. Model outputs (`x`, `v`, `a`) are interpolated (`np.interp`) onto the MPC time indices (`T_IDXS_MPC`).
        *   If `frogpilot_toggles.taco_tune` is enabled, `parse_model` further limits the interpolated predicted velocity (`v`) based on curvature (`modelV2.orientationRate.z` interpolated onto `T_IDXS_MPC`) and current `v_ego` to implement curve speed limiting within the planner.
        *   Extracts `throttle_prob` from `modelV2.meta.disengagePredictions.gasPressProbs`.
    *   Sets MPC weights using costs from `sm['frogpilotPlan']` (`accelerationJerk`, `dangerJerk`, `speedJerk`), the `prev_accel_constraint` flag, and `sm['controlsState'].personality`.
    *   Sets initial MPC accel limits (`accel_limits`) using `sm['frogpilotPlan'].minAcceleration` and `sm['frogpilotPlan'].maxAcceleration` (for 'acc' mode).
    *   Applies turn speed limiting: Calls `limit_accel_in_turns` which calculates max longitudinal acceleration based on lateral acceleration (derived from `v_ego`, `steeringAngleDeg` adjusted by `angleOffsetDeg`, and `CP` geometry). Reduces the upper accel limit. Stores result in `accel_limits_turns`.
    *   Applies throttle allowance constraint: Calculates `allow_throttle` based on model `throttle_prob` (> `ALLOW_THROTTLE_THRESHOLD`) and `v_ego` (> `MIN_ALLOW_THROTTLE_SPEED`). If `allow_throttle` is false, further reduces the upper accel limit in `accel_limits_turns`. This reduction interpolates between the current upper limit and a calculated coasting acceleration (`accel_coast`, derived from vehicle pitch `sm['carControl'].orientationNED[1]`) based on `v_ego` relative to `MIN_ALLOW_THROTTLE_SPEED`.
    *   Handles `force_slow_decel` constraint: If `sm['controlsState'].forceDecel` is true, a *local* variable `v_cruise` is set to 0.0. **Crucially, this modified local `v_cruise` is *not* passed to the MPC.** The MPC receives `sm['frogpilotPlan'].vCruise` directly via the `mpc.update` call arguments.
    *   Clips `accel_limits_turns` slightly based on previous `a_desired` (`min(..., self.a_desired + 0.05)`, `max(..., self.a_desired - 0.05)`) before passing to MPC.
    *   Passes final `accel_limits_turns` to `self.mpc.set_accel_limits`.
    *   Sets current MPC state using filtered velocity (`self.v_desired_filter.x`) and previous desired acceleration (`self.a_desired`).
    *   Selects lead data: Uses `sm['radarState'].leadOne` and `leadTwo` directly (since `radarless_model=False`).
    *   Calls `self.mpc.update()` with lead data (`self.lead_one`, `self.lead_two`), cruise speed from `sm['frogpilotPlan'].vCruise`, adjusted model predictions (`x, v, a, j`), `radarless_model` flag, follow time from `sm['frogpilotPlan'].tFollow`, `sm['frogpilotCarState'].trafficModeActive`, and `sm['controlsState'].personality`.
    *   *Inside `mpc.update`*: Solves optimization problem to find `a_solution` minimizing costs subject to limits/constraints, using lead `vLead` (potentially distance-derived) and `aLeadK` (KF-velocity-derived) from `radarState` for prediction over the MPC horizon. Stores solution trajectories (`v_solution`, `a_solution`, `j_solution`).
    *   Updates current desired acceleration (`self.a_desired`). First, the MPC solution (`self.mpc.a_solution`) is interpolated onto the `CONTROL_N` time indices (`CONTROL_N_T_IDX`) to create `self.a_desired_trajectory`. Then, `self.a_desired` is calculated by interpolating `self.a_desired_trajectory` at the current time step (`self.dt`).
    *   **Constraint Note:** The calculated `self.a_desired` is inherently bounded by the `minAcceleration` and `maxAcceleration` limits provided via `sm['frogpilotPlan']` during the MPC optimization process. The acceleration request sent to the controller (Phase 3) cannot exceed these planner-defined bounds.
    *   Updates `v_desired_filter` using Euler integration with the average of the previous and current `a_desired`: `self.v_desired_filter.x = self.v_desired_filter.x + self.dt * (self.a_desired + a_prev) / 2.0`.
4.  **Planner Publication (`LongitudinalPlanner.publish`)**:
    *   Publishes `longitudinalPlan` message containing MPC solution trajectories interpolated onto `CONTROL_N` indices (`speeds`, `accels`, `jerks`), `hasLead` (from `self.lead_one.status`), `fcw` flag (from `self.mpc.crash_cnt`), `longitudinalPlanSource` (from `self.mpc.source`), `solverExecutionTime`, and the calculated `allowThrottle` flag.
    *   Calculates `aTarget` using `get_accel_from_plan` (or `_classic`). This function interpolates the planned acceleration trajectory (`longitudinalPlan.accels`) considering the actuator delay (`CP.longitudinalActuatorDelay + DT_MDL`) and uses `frogpilot_toggles.vEgoStopping` for stop detection logic. This value is primarily for the `longitudinalPlan` message.
    *   Calculates `shouldStop` (also inside `get_accel_from_plan` or `_classic`) based on the planned speed trajectory and `frogpilot_toggles.vEgoStopping`.
    *   Sets `allowBrake = True` (hardcoded) and `allowThrottle` (from the value calculated in the `update` method).
    *   Sends the `longitudinalPlan` message via the `PubMaster` (`pm`).

**Phase 3: Control Application and HKG Tuning Override (`selfdrive/car/hyundai/carcontroller.py` & `selfdrive/car/hyundai/chubbs/longitudinal_tuning.py`)**

*Note: This phase assumes the `"HKGtuning"` and `"HKGBraking"` Params are enabled by the user. `"HKGtuning"` is checked in `hyundai/interface.py` (potentially modifying `CP`) and in `hyundai/chubbs/longitudinal_tuning.py` (`HKGLongitudinalController.__init__`) to enable the tuning logic object. `"HKGBraking"` is checked within `HKGLongitudinalController.calculate_accel` to conditionally apply the tuning logic and also within `HKGLongitudinalTuning` itself.*

1.  **Control Interception (`CarController.update`)**:
    *   Inherits `HKGLongitudinalController` (from `hyundai/chubbs/longitudinal_tuning.py`).
    *   Subscribes to `radarState` via `self.sm = messaging.SubMaster(['radarState'])` in `__init__` and calls `self.sm.update(0)` at the start of `update`.
    *   Retrieves latest `radarState.leadOne` into local variable `lead_one` (if `self.sm.valid['radarState']`).
    *   Receives `CC` (CarControl) and `CS` (CarState) as arguments.
    *   Calls `self.calculate_accel(actuators, CS, frogpilot_toggles, lead_one)` (method inherited from `HKGLongitudinalController`) instead of directly using `CC.actuators.accel`. This call initiates the HKG tuning logic.
2.  **HKG Tuning Calculation (`HKGLongitudinalController.calculate_accel` -> `HKGLongitudinalTuning.calculate_accel`)**:
    *   The call originates in `CarController.update`.
    *   `HKGLongitudinalController.calculate_accel` first checks if `HKGBraking` Param is enabled and the `tuning` object exists. If not, it clips `actuators.accel` with default limits and returns. Otherwise, it proceeds.
    *   Calls `self.tuning.calculate_accel(actuators, CS, frogpilot_toggles, lead_one)`.
    *   Inside `HKGLongitudinalTuning.calculate_accel`:
        *   Checks cruise cancel/override conditions via `self.handle_cruise_cancel(CS)`. If cancelled/overridden, returns `0.0`.
        *   Calls `self.calculate_limited_accel(actuators, CS, lead_one)` to get the potentially rate-limited acceleration (`accel`).
        *   **Clips the rate-limited `accel`** using car-specific `accel_limits` loaded from `longitudinal_config.py` (via `self.car_config`) before returning the final value.
3.  **HKG Jerk/Rate Limiting (`HKGLongitudinalTuning.calculate_limited_accel`)**:
    *   Input `accel_request` starts as `actuators.accel` (MPC's target from planner).
    *   Checks cruise cancel/override again; if active, returns `accel_request` unmodified.
    *   Calls `self.make_jerk(CS, actuators)` - *Note: This calculates jerk limits based on measured `aEgo` change primarily for the CAN message (see Step 5), not directly used for rate limiting here.*
    *   Calls `self.update_mpc_mode(self.sm)` - Handles mode transitions (ACC vs Blended). For ACC mode, transition logic is inactive, `accel_request` remains planner's target.
    *   **Dynamic Jerk Limiting (Applied only if `CS.out.vEgo > 1.0` and `accel_request < 0.15`)**: If conditions met:
        *   Calculates `baseline_jerk` using Akima interpolation based on `accel_request` ratio relative to `accel_limits[0]` and car-specific `brake_response` config (from `longitudinal_config.py`).
        *   Performs validity checks on inputs and lead data (`lead_one` from `radarState`).
        *   Calculates dynamic stop buffer (`stop_buffer`) and distance gap (`d_gap = max(lead_one.dRel - stop_buffer, 0.1)`).
        *   Calculates physics urgency `a_req = (max(vEgo, 0.0)**2 + 0.3 * (-min(vRel, 0.0))**2) / (2.0 * d_gap)` using `CS.vEgo`, `lead_one.vRel` (potentially distance-derived/lagged), and calculated `d_gap`.
        *   Calculates `urgency` based on `a_req` vs car-specific `comfy_decel` config and `accel_limits[0]` config (both from `longitudinal_config.py`).
        *   Calculates `jerk_needed = abs((accel_request - self.accel_last) / DT_CTRL)` (if braking harder).
        *   Determines `jerk_ceiling = max(baseline_jerk, baseline_jerk + urgency * (1.5 * MAX_ALLOWABLE_JERK - baseline_jerk))`, where `MAX_ALLOWABLE_JERK` is 20.0 m/s³.
        *   Determines final `effective_jerk = min(max(baseline_jerk, jerk_needed), jerk_ceiling)`.
        *   **Applies Jerk Rate Limit (Downward Only)**: `accel = max(accel_request, self.accel_last - effective_jerk * DT_CTRL)`. This prevents the acceleration from decreasing faster than `effective_jerk` allows.
    *   If dynamic braking conditions are *not* met, `accel = accel_request` (no rate limiting applied).
    *   Stores the potentially rate-limited `accel` in `self.accel_last` for the next iteration.
    *   Returns the potentially rate-limited `accel` (to be clipped in the calling function, Step 2).
4.  **Final Clipping (`CarController.update`)**: **Incorrect in original summary.** The final clipping using car config `accel_limits` happens *inside* `HKGLongitudinalTuning.calculate_accel` (Step 2 above), not separately in `CarController.update`.
5.  **Jerk Calculation for CAN (`CarController.update` -> `HKGLongitudinalController.calculate_and_get_jerk` -> `HKGLongitudinalTuning.make_jerk`)**:
    *   `CarController.update` calls `self.calculate_and_get_jerk(actuators, CS, actuators.longControlState, lead_one)` **after** `calculate_accel` but passes the *original* `actuators` object (containing the planner's `a_desired`), not the final rate-limited `accel`.
    *   `calculate_and_get_jerk` calls `self.tuning.make_jerk(CS, actuators)` (if tuning enabled).
    *   `make_jerk` calculates CAN message jerk limits:
        *   It calculates a base jerk primarily based on the change in *measured* `CS.out.aEgo` (`self.jerk = (CS.out.aEgo - self.accel_last_jerk)`).
        *   It interpolates this measured jerk (`self.jerk = akima_interp(...)`) for smoothness.
        *   It calculates `jerk_upper_limit` and `jerk_lower_limit` based on this interpolated *measured* jerk and car-specific `jerk_limits` config (from `longitudinal_config.py`).
        *   (Non-CAN FD only: It also calculates `cb_upper`/`cb_lower` limits, which *do* use the planner's `actuators.accel` if `HKGBraking` is false).
    *   The limits (`tuning.jerk_upper_limit`, `tuning.jerk_lower_limit`) are stored within the `tuning` object.
    *   `calculate_and_get_jerk` retrieves these limits using `self.get_jerk()` and returns them in a `JerkOutput` object, which is stored in `self.jerk` within `CarController.update`.
    *   **Conclusion:** The jerk limits sent in the CAN message (Phase 4) primarily reflect the *measured vehicle response jerk*, interpolated and bounded by config, rather than directly commanding or limiting the requested acceleration/jerk from the planner or the HKG tuner.

**Phase 4: CAN Command Generation (`carcontroller.py` -> `hyundaicanfd.py`)**

1.  **Message Trigger (`CarController.update`)**: Executes every 2nd frame (`if self.frame % 2 == 0`), corresponding to 50Hz (assuming `DT_CTRL` = 0.01s).
2.  **Function Call**: Calls `hyundaicanfd.create_acc_control()` with necessary parameters.
3.  **Parameter Mapping to `create_acc_control`**:
    *   `packer`, `CAN` (CanBus instance), `CS` (`CarState`).
    *   `enabled` (`CC.enabled`).
    *   `accel_last`: The previous frame's final acceleration (`self.accel_last`) is passed, **but this argument is unused inside `create_acc_control`**.
    *   `accel`: The *current* frame's final `accel` (output of Phase 3 - HKG-tuned, rate-limited, and clipped).
    *   `jerk_upper_limit`, `jerk_lower_limit`: Values from `self.jerk` (result of `calculate_and_get_jerk` in Phase 3, Step 5, based on measured `aEgo` change).
    *   `stopping`: Boolean `actuators.longControlState == LongCtrlState.stopping`.
    *   `gas_override`: Boolean `CC.cruiseControl.override`.
    *   `set_speed`: Cruise set speed in native units (`set_speed_in_units` converted from `hud_control.setSpeed`).
    *   `hud_control`: The `HUDControl` object (`CC.hudControl`).
4.  **CAN Message Packing (`hyundaicanfd.create_acc_control`)**:
    *   Selects CAN bus: `CAN.ECAN` (verified for HDA2 via `CanBus` logic).
    *   Message ID: `0x1CF` (`SCC_CONTROL`).
    *   **No redundant clipping:** The input `accel` is assumed to be final. Code comments confirm reliance on Phase 3 tuning/limiting: `"Use the already calculated accel value from the tuning module for both fields."`
    *   Packs primary fields:
        *   `aReqRaw` / `aReqValue`: **Both set to the input `accel` value from Phase 3.**
        *   `JerkLowerLimit` / `JerkUpperLimit`: Set to the input `jerk_lower` and `jerk_upper` parameters (calculated in Phase 3, Step 5, based on measured `aEgo` change).
        *   `StopReq`: Set based on the input `stopping` flag.
        *   `ACC_ObjDist`: **Hardcoded to 1.** **Not** from `lead_one.dRel`.
        *   `Lead_Objspd`: **Does not exist in CAN FD `SCC_CONTROL` message.** Verified via DBC.
        *   Status flags (`ACCMode` based on `enabled`/`gas_override`, `MainMode_ACC` based on `CS.out.cruiseState.available`), override flags (`ACCMode` incorporates `gas_override`), set speed (`VSetDis` from input `set_speed`), `DISTANCE_SETTING` (from `hud_control.leadDistanceBars`), and other hardcoded filler values (`ObjValid`, `OBJ_STATUS`, `SET_ME_...`).
5.  **Output**: Returns a packed CAN message `[0x1CF, 0, packed_data, CAN.ECAN]` which is appended to the `can_sends` list in `CarController.update` destined for the vehicle's ECAN bus.

**Phase 5: Vehicle Execution**

*Verification Note: This phase describes the expected behavior of the vehicle's internal ECUs based on the CAN messages sent by openpilot. As this involves proprietary OEM software, the exact internal logic cannot be verified directly from the openpilot codebase. The description below represents a logical interpretation based on the known inputs and general automotive control principles.*

1.  **ECU Reception**: The vehicle's relevant ECU (likely the ADAS/Drive control unit) receives the `SCC_CONTROL` (0x1CF) message on the ECAN bus at approximately 50Hz (every 2nd openpilot control frame).
2.  **Input Interpretation**: The ECU reads the following key fields from the message:
    *   `aReqRaw` / `aReqValue`: This is the primary acceleration command from openpilot, representing the final desired acceleration after HKG tuning, rate limiting, and clipping.
    *   `JerkLowerLimit` / `JerkUpperLimit`: These represent limits based on the *measured* change in vehicle acceleration (`aEgo`) from the previous frame, interpolated and bounded by configuration values. It's unclear if the ECU uses these as hard limits, soft suggestions, or primarily for internal diagnostics/smoothness control.
    *   `StopReq`: A flag indicating openpilot's intent for the vehicle to come to a stop.
    *   `ACC_ObjDist`: **Hardcoded to 1 meter.** This value does not reflect the actual distance to the lead vehicle detected by openpilot's radar/vision system.
    *   `Lead_Objspd`: **This field is absent** in the CAN FD `SCC_CONTROL` message definition used by openpilot for this platform. The ECU does not receive relative speed information via this specific field.
    *   Other fields: Status flags (`ACCMode`, `MainMode_ACC`), override indicators, cruise set speed (`VSetDis`), and driver-selected follow distance (`DISTANCE_SETTING`).
3.  **Control Actuation (Inferred Logic)**: The ECU attempts to achieve the target acceleration specified by `aReqRaw` / `aReqValue` by commanding the vehicle's actuators (powertrain for acceleration/regen, friction brakes for deceleration). The ECU's internal control loops likely perform the following actions:
    *   **Target Tracking**: It translates the `aReqRaw` into targets for motor torque, regenerative braking, and/or friction brake pressure.
    *   **Internal Limiting**: It likely applies its own internal safety limits, potentially based on vehicle speed, stability control status, system temperature, hardware capabilities, and potentially its *own* interpretation of the driving situation.
    *   **Potential Conflict/Fusion**: It's unknown how the ECU reconciles the received `aReqRaw` with the hardcoded `ACC_ObjDist` (1m) and the missing `Lead_Objspd`.
        *   *Speculation 1*: The ECU might primarily trust `aReqRaw` when `ACCMode` indicates openpilot is active, using `ACC_ObjDist` only for display purposes or low-level safety checks.
        *   *Speculation 2*: The ECU might have a fallback logic where if `ACC_ObjDist` is unreasonably small (like 1m), it could potentially limit the commanded deceleration or trigger warnings, regardless of `aReqRaw`. This could contribute to less aggressive braking than requested if the ECU deems the situation unsafe based on its limited inputs from this specific message.
        *   *Speculation 3*: The ECU might still use data from other sensors (e.g., corner radars if not fully disabled, wheel speeds, G-sensors) to validate or moderate the request from openpilot.
    *   **Jerk Influence**: The received `JerkLowerLimit`/`JerkUpperLimit` (based on measured `aEgo` change) might influence the *smoothness* of the ECU's response rather than acting as strict boundaries on the *rate of change* applied towards the `aReqRaw` target, especially since the HKG tuner already applied its own rate limiting to `aReqRaw`.
    *   **StopReq Handling**: The `StopReq` flag likely influences the ECU's low-speed control behavior, potentially enabling smoother stops or engaging brake hold features.
4.  **Final Vehicle Response**: The actual physical acceleration/deceleration of the vehicle results from the complex interaction between the ECU's interpretation of the `SCC_CONTROL` message, its internal control strategies and safety limits, the current vehicle state (speed, mass, tire grip, etc.), and the physical limitations of the powertrain and braking system. Discrepancies between openpilot's requested `accel` (Phase 3/4) and the actual `aEgo` (measured by `carState`) can arise from any part of this inferred ECU logic or physical limitations.

**Updated Potential Causes for Slow Deceleration (ACC Mode):**

1.  **`vRel` Lag (Radar -> Planner -> HKG Urgency)**: **Valid.** Using the distance-derived `vRel` in `radard.py` delays detection. This lagged `vRel` is confirmed to be used in the HKG tuning's `a_req` (urgency) calculation in `longitudinal_tuning.py`, making the urgency factor react slower to sudden lead braking.
2.  **`aLeadK` Mismatch/Lag (Radar -> Planner)**: **Valid.** The acceleration feedforward (`aLeadK`) used by the MPC in `longitudinal_planner.py` is derived from the KF's internal velocity state, potentially mismatching the distance-derived `vRel`/`vLead` used for lead following calculations and HKG urgency. Lag in `aLeadK` reduces the MPC's proactiveness.
3.  **HKG Jerk Limit Application**: **Valid.** The dynamic jerk limiting (`effective_jerk`) in `HKGLongitudinalTuning.calculate_limited_accel` directly limits how quickly the requested acceleration *can decrease*. Even if the planner requests strong braking instantly, this tuner enforces a ramp-down based on its calculated urgency and baseline jerk, potentially slowing the initial response.
4.  **ECU Interpretation/Limitation (Phase 5)**: **Potentially Valid (Speculative).** The vehicle's ECU might internally limit the braking force based on its own safety criteria, potentially influenced by the hardcoded/missing lead information (`ACC_ObjDist=1`, no `Lead_Objspd`) in the `SCC_CONTROL` message, or other internal factors not visible to openpilot. It might not fully trust or be able to achieve the `aReqRaw` sent by openpilot under all conditions, especially during rapid deceleration events.
5.  **Missing/Hardcoded CAN Data**: **Potentially Valid (Speculative).** The hardcoded `ACC_ObjDist=1` and the complete absence of `Lead_Objspd` in the CAN FD message *could* lead the ECU to operate in a less informed state, potentially causing it to be more conservative or rely on less precise internal estimations, thereby limiting deceleration capability compared to the stock system which has richer information.
6.  **Planner `minAcceleration` Limit:** **Potentially Valid.** The configured minimum acceleration limit (`sm['frogpilotPlan'].minAcceleration`) passed to the MPC might be too high (not negative enough), preventing the planner from requesting sufficiently strong deceleration even if the MPC cost function determines it's necessary for safety. This can become the bottleneck if the HKG tuner's rate limiting is no longer the most restrictive factor.