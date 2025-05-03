# Procedure for Simulating Lead Vehicle Deceleration (-4.0 m/s²) in ACC Mode

This document outlines the steps to simulate the response of the openpilot longitudinal control system (specifically for the Kia EV6 HDA2 CANFD setup described in `longitudinal_control_summary.md`, operating in standard ACC mode) to a lead vehicle decelerating at a constant -4.0 m/s².

The goal is to understand how the system *should* react based on the code logic, by providing controlled inputs and observing the outputs at various stages of the control pipeline. This focuses on setting up the simulation inputs and identifying key outputs, not running a full replay.

**Assumptions:**

*   System Configuration: Matches the `longitudinal_control_summary.md` (Kia EV6 HDA2 CANFD, ACC mode, non-radarless, relevant toggles/params enabled, HKG Tuning active via `"HKGtuning"` and `"HKGBraking"` Params).
*   Simulation Environment: A Python environment capable of instantiating and calling methods from relevant openpilot modules (`longitudinal_planner.py`, `carcontroller.py`, `longitudinal_tuning.py`, `hyundaicanfd.py`, etc.). Requires access to or mock implementations of `CarParams`, CAN packer, `log.capnp` schemas, and relevant config files (e.g., `longitudinal_config.py` for HKG tuning).
*   Simulation Time Step: `DT_CTRL = 0.01s` (standard control loop rate, often `self.dt` in code).
*   Perfect Actuation Assumption: The simulation assumes the vehicle perfectly achieves the commanded acceleration from the previous step (`a_ego_sim(t) = a_cmd(t-DT_CTRL)`). This intentionally bypasses potential real-world ECU limitations, delays, or discrepancies (Summary Phase 5) to isolate the behavior of the openpilot software stack (Phases 2, 3, 4).

**Simulation Setup:**

1.  **Define Initial Conditions:**
    *   Ego Speed (`v_ego_initial`): e.g., 30 m/s
    *   Lead Distance (`d_rel_initial`): e.g., 50 m
    *   Lead Relative Speed (`v_rel_initial`): 0 m/s (lead initially matches ego speed)
    *   Lead Absolute Speed (`v_lead_initial`): `v_ego_initial + v_rel_initial` = 30 m/s
    *   Lead Acceleration (`a_lead_actual`): -4.0 m/s² (constant for the scenario)
    *   Cruise Set Speed (`v_cruise_set`): e.g., 35 m/s (must be higher than initial `v_ego`)
    *   Follow Time Setting (`t_follow`): e.g., 1.8 s (Corresponds to `frogpilotPlan.tFollow` used by MPC).
    *   Other relevant parameters: Ensure FrogPilot costs (`accelerationJerk`, `dangerJerk`, `speedJerk`) and limits (`minAcceleration`, `maxAcceleration`, `vEgoStopping`) are set in the mocked `frogpilotPlan` message. Ensure HKG configuration values (e.g., `brake_response`, `comfy_decel`, `accel_limits`, `jerk_limits`) from `longitudinal_config.py` (referenced in `HKGLongitudinalTuning`) are available or mocked appropriately for the `CarController`'s tuning instance.

2.  **Instantiate Core Components:**
    *   `LongitudinalPlanner`: Initialize with relevant `CarParams` (`CP`).
        ```python
        # Example (pseudo-code)
        from selfdrive.controls.lib.longitudinal_planner import LongitudinalPlanner
        # from selfdrive.car.<make>.values import CarParams # Load appropriate CP
        # planner = LongitudinalPlanner(CP)
        ```
    *   `CarController` (and implicitly `HKGLongitudinalController`, `HKGLongitudinalTuning`): Initialize with relevant `CarParams` (`CP`) and CAN packer (`packer`). Ensure HKG Params (`HKGtuning`, `HKGBraking`) are considered enabled for the tuning logic to be active.
        ```python
        # Example (pseudo-code)
        from selfdrive.car.hyundai.carcontroller import CarController
        # from selfdrive.car.hyundai.values import CarParams # Load appropriate CP
        # from panda.python.cansend import CanBus # or mock
        # from opendbc.can.packer import Packer # or mock
        # car_controller = CarController(CP, packer, CanBus(0))
        # # Ensure HKG params are mocked/set if needed for tuning init (e.g., via Params().put_bool)
        # # The HKGLongitudinalTuning instance is created within CarController.__init__ if HKGtuning Param is True
        ```

3.  **Simulation Loop (Iterate over time `t = n * DT_CTRL`):**

    *   **A. Update Simulated Lead Vehicle State:**
        *   Calculate the *true* physical state of the lead vehicle at time `t`.
        *   `v_lead_actual(t) = v_lead_initial + a_lead_actual * t`
        *   Keep track of the simulated ego state (`v_ego_sim(t)`, `a_ego_sim(t)`). Initially, `v_ego_sim(0) = v_ego_initial`, `a_ego_sim(0) = 0`. For subsequent steps `t > 0`, use the *commanded* acceleration from the *previous* step (`a_cmd(t-DT_CTRL)`):
            *   `a_ego_sim(t) = a_cmd(t-DT_CTRL)` (Assumption: Perfect actuation, bypassing Phase 5 ECU behavior)
            *   `v_ego_sim(t) = v_ego_sim(t-DT_CTRL) + a_ego_sim(t) * DT_CTRL`
        *   Calculate the *true* relative state:
            *   `v_rel_actual(t) = v_lead_actual(t) - v_ego_sim(t)`
            *   `d_rel_actual(t) = d_rel_actual(t-DT_CTRL) + v_rel_actual(t) * DT_CTRL` (Euler integration, using `v_rel_actual` for distance update)

    *   **B. Prepare Input Messages (Mock `SubMaster` / `sm`):**
        *   **`radarState`**: Create a `log.capnp:RadarState` struct (or dictionary mimicking it). Populate `leadOne` based on the *simulated physical reality* from Step A.
            *   **Important Bypass Note:** This step intentionally feeds *ideal, ground-truth* values (`d_rel_actual`, `v_rel_actual`, `a_lead_actual`, `v_lead_actual`) directly into the `leadOne` message fields. This bypasses the complexities of `radard.py`'s Kalman filtering (`KF2D`), the associated state estimation delays, and the potential discrepancy between the distance-derived `vRel` (used by HKG Tuner) and the KF-velocity-derived `aLeadK` (used by MPC) described in Summary Phase 1 (Points 4, 7). The purpose is to isolate the planner (Phase 2) and controller/tuner (Phase 3) response to a *known, perfect* lead vehicle perception.
            *   `sm['radarState'].leadOne.status = True`
            *   `sm['radarState'].leadOne.radar = True` # Assume radar detection for ACC mode logic paths
            *   `sm['radarState'].leadOne.dRel = d_rel_actual(t)`
            *   `sm['radarState'].leadOne.vRel = v_rel_actual(t)` # Feed true value. Used by `HKGLongitudinalTuning.calculate_limited_accel` for `a_req`.
            *   `sm['radarState'].leadOne.aLeadK = a_lead_actual` # Feed true value (-4.0). Used by `LongitudinalMpc.update` via `planner.update`.
            *   `sm['radarState'].leadOne.vLead = v_lead_actual(t)` # Feed true value. Used by `LongitudinalMpc.update` via `planner.update`.
            *   `sm['radarState'].leadOne.vLeadK = v_lead_actual(t)` # Feed true value (consistency, though `vLead` is primary for MPC).
            *   `sm['radarState'].leadOne.aLeadTau = 0.3` # Reasonable default, though not directly used by planner/tuner logic being tested here.
            *   `sm['radarState'].leadOne.yRel = 0.0` # Assume perfect alignment
            *   Set `sm['radarState'].leadTwo.status = False` # Focus on single lead scenario
        *   **`carState`**: Create `log.capnp:CarState`.
            *   `sm['carState'].vEgo = v_ego_sim(t)` # Used by planner and HKG tuner
            *   `sm['carState'].aEgo = a_ego_sim(t)` # Used by HKG tuner (`make_jerk` for CAN limits, but also conceptually for rate limit start point)
            *   `sm['carState'].standstill = (v_ego_sim(t) < 0.1)`
            *   `sm['carState'].cruiseState.enabled = True` # Assume cruise active
            *   `sm['carState'].cruiseState.available = True`
            *   `sm['carState'].gasPressed = False` # Assume no override
            *   `sm['carState'].brakePressed = False` # Assume no override
            *   Populate other fields as needed (e.g., `steeringAngleDeg = 0`).
        *   **`controlsState`**: Create `log.capnp:ControlsState`.
            *   `sm['controlsState'].longControlState = log.ControlsState.LongControlState.pid` # Assuming active following
            *   `sm['controlsState'].vCruise = v_cruise_set`
            *   `sm['controlsState'].experimentalMode = False` # For standard ACC mode
            *   `sm['controlsState'].personality = log.ControlsState.Personality.standard` # Or other if testing
            *   `sm['controlsState'].forceDecel = False` # Assume not active
        *   **`frogpilotPlan`**: Create `log.capnp:FrogPilotPlan`.
            *   Set FrogPilot costs (`accelerationJerk`, `dangerJerk`, `speedJerk`), limits (`minAcceleration`, `maxAcceleration`), `vEgoStopping` etc. matching the configuration under test (Summary Phase 2, Point 2). These are read in `planner.update` to set MPC weights (`self.mpc.set_weights`) and base limits (`accel_limits`).
            *   `sm['frogpilotPlan'].tFollow = t_follow` # Used by `planner.update` -> `mpc.update`.
            *   `sm['frogpilotPlan'].vCruise = v_cruise_set` # Used by `planner.update` -> `mpc.update`.
            *   `sm['frogpilotPlan'].frogpilotToggles`: Populate with relevant toggle values (e.g., `taco_tune` affects `parse_model`).
        *   **`frogpilotCarState`**: Create `log.capnp:FrogPilotCarState`.
            *   `sm['frogpilotCarState'].trafficModeActive = False` # Used by `planner.update` -> `mpc.update`.
        *   **`modelV2`**: Create `log.capnp:ModelDataV2`. For ACC mode simulation, provide minimal valid data unless testing specific model interactions.
            *   If `frogpilot_toggles.taco_tune` is enabled, ensure `modelV2.orientationRate.z` is populated for `parse_model`.
            *   If testing throttle allowance logic (Summary Phase 2, Point 3), ensure `modelV2.meta.disengagePredictions.gasPressProbs` is populated.
            *   Otherwise, can potentially use zero arrays for position/velocity/accel if `taco_tune` is off.
        *   **`liveParameters`**: Mock `angleOffsetDeg` if `limit_accel_in_turns` is relevant.
        *   **`carControl`**: Mock `orientationNED[1]` (pitch) if coasting accel (`accel_coast`) calculation in throttle allowance logic is relevant.

    *   **C. Execute Planner (`LongitudinalPlanner.update`):**
        *   Call `planner.update(False, sm, frogpilot_toggles)` (assuming `radarless_model=False`, pass mocked FrogPilot toggles struct if needed).
        *   **Internal Steps (Summary Phase 2, Point 3):**
            *   Mode set to 'acc'.
            *   `parse_model` processes `sm['modelV2']`.
            *   MPC weights set using costs from `sm['frogpilotPlan']`.
            *   Base accel limits set from `sm['frogpilotPlan'].min/maxAcceleration`.
            *   `limit_accel_in_turns` potentially reduces upper limit.
            *   Throttle allowance logic potentially reduces upper limit.
            *   Final limits `accel_limits_turns` passed to `planner.mpc.set_accel_limits`.
            *   `planner.mpc.update` called with leads (`sm['radarState'].leadOne.vLead`, `sm['radarState'].leadOne.aLeadK`), `sm['frogpilotPlan'].vCruise`, model predictions, `sm['frogpilotPlan'].tFollow`, etc. MPC solves for optimal acceleration trajectory (`planner.mpc.a_solution`).
        *   Retrieve planner's immediate target acceleration for this step by interpolating the solution: `a_planner_target = planner.a_desired`.
        *   **Crucial Note:** The value `a_planner_target` (derived from `planner.mpc.a_solution`) is inherently constrained by the `minAcceleration` and `maxAcceleration` limits provided to the MPC via `sm['frogpilotPlan']`. The planner cannot request acceleration outside these bounds.

    *   **D. Prepare Controller Inputs:**
        *   Create `log.capnp:CarControl` (`CC`).
        *   `CC.enabled = True`
        *   `CC.cruiseControl.override = False`
        *   `CC.actuators.accel = a_planner_target` # Planner's target accel for this step (already constrained by planner limits)
        *   `CC.actuators.longControlState = sm['controlsState'].longControlState`
        *   Create `HUDControl` object for `CC.hudControl` (e.g., `leadDistanceBars` used in CAN message).

    *   **E. Execute Controller/Tuner (`CarController.update` -> HKG Tuning Logic):**
        *   Call `car_controller.update(CC, sm['carState'])`. This internally orchestrates several steps, including the HKG acceleration modification.
        *   **HKG Acceleration Calculation Path (Summary Phase 3, Steps 1-3):**
            1.  `CarController.update` retrieves `lead_one = sm['radarState'].leadOne` (using its internal `self.sm.update(0)`).
            2.  It calls `accel_command = self.calculate_accel(CC.actuators, sm['carState'], frogpilot_toggles, lead_one)` (method inherited from `HKGLongitudinalController`).
            3.  Inside `calculate_accel`, if `HKGBraking` Param is True and `self.tuning` exists, it calls `accel_command = self.tuning.calculate_accel(CC.actuators, sm['carState'], frogpilot_toggles, lead_one)`.
            4.  Inside `HKGLongitudinalTuning.calculate_accel`:
                *   Calls `accel_after_rate_limit = self.calculate_limited_accel(CC.actuators, sm['carState'], lead_one)`.
                *   **Inside `calculate_limited_accel` (Dynamic Jerk Limiting Logic):**
                    *   Input `accel_request = CC.actuators.accel` (which is `a_planner_target` from Step C).
                    *   Checks if `CS.out.vEgo > 1.0` and `accel_request < 0.15`.
                    *   If true (braking ramp active):
                        *   `baseline_jerk` = Akima interp based on `accel_request`, `self.car_config.accel_limits[0]`, and `self.car_config.brake_response`.
                        *   `stop_buffer` calculated.
                        *   `d_gap = max(lead_one.dRel - stop_buffer, 0.1)`
                        *   `a_req = (max(vEgo, 0.0)**2 + 0.3 * (-min(lead_one.vRel, 0.0))**2) / (2.0 * d_gap)` (Uses `lead_one.vRel` from mocked `sm['radarState']`).
                        *   `urgency` = Calculated based on `a_req` vs `self.car_config.comfy_decel` and `self.car_config.accel_limits[0]`.
                        *   `jerk_needed = abs((accel_request - self.accel_last) / DT_CTRL)`
                        *   `jerk_ceiling = max(baseline_jerk, baseline_jerk + urgency * (1.5 * MAX_ALLOWABLE_JERK - baseline_jerk))`
                        *   `effective_jerk = min(max(baseline_jerk, jerk_needed), jerk_ceiling)`
                        *   **Rate Limit Applied:** `accel_after_rate_limit = max(accel_request, self.accel_last - effective_jerk * DT_CTRL)` (Stores result in `self.accel_last` for next step).
                    *   If false (not applying ramp): `accel_after_rate_limit = accel_request` (updates `self.accel_last`).
                *   Returns `accel_after_rate_limit`.
                *   **Final Clipping:** `HKGLongitudinalTuning.calculate_accel` takes `accel_after_rate_limit` and applies final clipping using car-specific limits: `a_cmd_final = clip(accel_after_rate_limit, self.car_config.accel_limits[0], self.car_config.accel_limits[1])`.
            5.  `HKGLongitudinalTuning.calculate_accel` returns `a_cmd_final`.
            6.  `calculate_accel` (in `HKGLongitudinalController`) returns `a_cmd_final`.
        *   Store the final command for this step: `a_cmd(t) = a_cmd_final`.
        *   **CAN Packing Information:** The `car_controller.update` method later prepares CAN messages. Specifically, `hyundaicanfd.create_acc_control` will be called with `accel=a_cmd(t)`. This `a_cmd(t)` value will be packed into both the `aReqRaw` and `aReqValue` fields of the `SCC_CONTROL` (0x1CF) message. As noted in Summary Phase 4, this message uses a hardcoded `ACC_ObjDist=1` and lacks `Lead_Objspd` for CAN FD.

    *   **F. Record Outputs:**
        *   Store `t`, `d_rel_actual(t)`, `v_rel_actual(t)`, `v_ego_sim(t)`, `a_ego_sim(t)`.
        *   Store planner output: `a_planner_target` (value of `planner.a_desired` for this step).
        *   Store HKG tuner intermediate values (instrument `HKGLongitudinalTuning` or extract from calculation): `baseline_jerk`, `a_req`, `urgency`, `jerk_needed`, `jerk_ceiling`, `effective_jerk`, `accel_after_rate_limit` (value returned by `calculate_limited_accel` before final clipping).
        *   Store final command: `a_cmd(t)` (the final value after rate limiting and clipping, sent as `aReqRaw`).
        *   Optionally record CAN Jerk Limits: If needed, call `car_controller.calculate_and_get_jerk(...)` after `calculate_accel` (as done in `CarController.update`) and record the returned `jerk_upper_limit` and `jerk_lower_limit` from `tuning.make_jerk`. Note these are based on simulated `aEgo` change (`a_ego_sim(t) - a_ego_sim(t-DT_CTRL)` effectively) and config, not directly limiting `a_cmd(t)`.

    *   **G. Loop Continuation:** Use `a_cmd(t)` (the final command from Step E, representing the output of the HKG tuner and clipper) to calculate `a_ego_sim(t+DT_CTRL)` and `v_ego_sim(t+DT_CTRL)` for the *next* iteration's Step A, based on the perfect actuation assumption:
        *   `a_ego_sim(t+DT_CTRL) = a_cmd(t)`
        *   `v_ego_sim(t+DT_CTRL) = v_ego_sim(t) + a_ego_sim(t) * DT_CTRL`

**Analysis:**

By running this simulation loop, you can plot the time series of:

*   Planner's desired acceleration (`a_planner_target`).
*   The final commanded acceleration after HKG tuning/rate-limiting/clipping (`a_cmd(t)`).
*   Intermediate HKG tuner values (e.g., `urgency`, `effective_jerk`, `accel_after_rate_limit`).
*   The simulated ego vehicle response (`v_ego_sim`, `a_ego_sim`).
*   The relative distance and velocity (`d_rel_actual`, `v_rel_actual`).

Comparing `a_planner_target` to `a_cmd(t)` reveals the impact of the HKG tuning logic (Summary Phase 3), specifically the dynamic jerk limiting in `HKGLongitudinalTuning.calculate_limited_accel` and the final clipping defined in `longitudinal_config.py`. Plotting the intermediate tuner values shows how `urgency` and `effective_jerk` evolve based on the simulated state (`v_ego_sim`, `lead_one.dRel`, `lead_one.vRel`). **Note that if `a_planner_target` consistently hits the `sm['frogpilotPlan'].minAcceleration` limit, this planner-level constraint becomes the bottleneck, regardless of the tuner's behavior.** Any discrepancy between `a_cmd(t)` and `a_ego_sim(t+DT_CTRL)` is zero *by the simulation's perfect actuation assumption*, but `a_cmd(t)` represents the value sent to the CAN bus (`aReqRaw`), which would face potential ECU limitations (Summary Phase 5) or actuator delays in reality. Analyzing the evolution of `d_rel_actual` shows how effectively the system *commands* gap closure under the simulated -4.0 m/s² deceleration, subject *only* to the planner and HKG tuner software logic (including planner limits).