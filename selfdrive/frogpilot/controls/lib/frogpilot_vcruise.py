import numpy as np

# from openpilot.common.realtime import DT_MDL (already included below)
from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip
from openpilot.common.realtime import DT_MDL

from openpilot.selfdrive.controls.lib.drive_helpers import V_CRUISE_UNSET

from openpilot.selfdrive.frogpilot.controls.lib.map_turn_speed_controller import MapTurnSpeedController
from openpilot.selfdrive.frogpilot.controls.lib.speed_limit_controller import SpeedLimitController
from openpilot.selfdrive.frogpilot.frogpilot_variables import CRUISING_SPEED, PLANNER_TIME, params_memory


# -------------------------------------------------------------------------
#  Import the dedicated VTSC module
# -------------------------------------------------------------------------
from openpilot.selfdrive.frogpilot.controls.lib.chauffeur_vtsc import VisionTurnSpeedController


class FrogPilotVCruise:
    def __init__(self, FrogPilotPlanner):
        self.frogpilot_planner = FrogPilotPlanner

        # Sub-controllers
        self.mtsc = MapTurnSpeedController()
        self.slc = SpeedLimitController()

        # Force-stop logic
        self.forcing_stop = False
        self.override_force_stop = False
        self.override_slc = False
        self.speed_limit_changed = False

        # Timers
        self.force_stop_timer = 0
        self.override_force_stop_timer = 0
        self.speed_limit_timer = 0

        # Targets
        self.mtsc_target = 0
        self.slc_target = 0
        self.vtsc_target = 0
        self.overridden_speed = 0

        # Speed Limit tracking
        self.previous_speed_limit = 0
        self.tracked_model_length = 0

        # Additional variable for the new SLC logic
        self.slc_offset = 0

        # Adjust turning threshold
        self.turn_lat_acc_threshold = 0.3  # was 0.5
        global CRUISING_SPEED
        CRUISING_SPEED = 6.7  # ~15 mph in m/s
        self.turn_smoothing_alpha = 0.3

        # Initialize the Vision Turn Speed Controller
        self.vtsc = VisionTurnSpeedController(
            turn_smoothing_alpha=self.turn_smoothing_alpha,
            reaccel_alpha=0.2,
            low_lat_acc=0.20,
            high_lat_acc=0.40,
            max_decel=2.0,
            max_jerk=1.2
        )

    def update(self, carControl, carState, controlsState,
               frogpilotCarControl, frogpilotCarState, frogpilotNavigation,
               v_cruise, v_ego, frogpilot_toggles):

        # Safely fetch toggles so we don't crash if any attribute is missing
        force_stops = getattr(frogpilot_toggles, 'force_stops', False)
        force_standstill = getattr(frogpilot_toggles, 'force_standstill', False)
        map_turn_speed_controller = getattr(frogpilot_toggles, 'map_turn_speed_controller', False)
        speed_limit_controller = getattr(frogpilot_toggles, 'speed_limit_controller', False)
        show_speed_limits = getattr(frogpilot_toggles, 'show_speed_limits', False)
        speed_limit_controller_override_manual = getattr(frogpilot_toggles, 'speed_limit_controller_override_manual', False)
        speed_limit_controller_override_set_speed = getattr(frogpilot_toggles, 'speed_limit_controller_override_set_speed', False)
        speed_limit_confirmation_lower = getattr(frogpilot_toggles, 'speed_limit_confirmation_lower', False)
        speed_limit_confirmation_higher = getattr(frogpilot_toggles, 'speed_limit_confirmation_higher', False)
        vision_turn_speed_controller = getattr(frogpilot_toggles, 'vision_turn_speed_controller', False)
        turn_aggressiveness = getattr(frogpilot_toggles, 'turn_aggressiveness', 1.0)

        # -------------------------------------------------------------
        # Force Stop Logic
        # -------------------------------------------------------------
        force_stop = (
            force_stops
            and self.frogpilot_planner.cem.stop_light_detected
            and controlsState.enabled
        )
        force_stop &= self.frogpilot_planner.model_length < 100
        force_stop &= self.override_force_stop_timer <= 0

        self.force_stop_timer = self.force_stop_timer + DT_MDL if force_stop else 0
        force_stop_enabled = self.force_stop_timer >= 1

        self.override_force_stop |= (
            (not force_standstill
             and _get_attr(carState, 'standstill', False)
             and self.frogpilot_planner.tracking_lead)
            or _get_attr(carState, 'gasPressed', False)
            or frogpilotCarControl.accelPressed
        )
        self.override_force_stop &= force_stop_enabled

        if self.override_force_stop:
            self.override_force_stop_timer = 10
        elif self.override_force_stop_timer > 0:
          self.override_force_stop_timer -= DT_MDL

        # Keep cluster in sync
        v_cruise_cluster = max(controlsState.vCruiseCluster * CV.KPH_TO_MS, v_cruise)
        v_cruise_diff = v_cruise_cluster - v_cruise

        v_ego_cluster = max(_get_attr(carState, 'vEgoCluster', v_ego), v_ego)
        v_ego_diff = v_ego_cluster - v_ego

        # -------------------------------------------------------------
        # Map Turn Speed Controller
        # -------------------------------------------------------------
        if map_turn_speed_controller and v_ego > CRUISING_SPEED and carControl.longActive:
            self.mtsc_target = clip(
                self.mtsc.update(
                    v_ego,
                    v_cruise,
                    turn_aggressiveness
                ),
                CRUISING_SPEED,
                v_cruise_cluster
            )
        else:
            self.mtsc_target = v_cruise if v_cruise != V_CRUISE_UNSET else 0

        # -------------------------------------------------------------
        # Speed Limit Controller (Swapped Logic)
        # -------------------------------------------------------------
        if show_speed_limits or speed_limit_controller:
            self.slc.update(
                frogpilotCarState.dashboardSpeedLimit,
                controlsState.enabled,
                frogpilotNavigation.navigationSpeedLimit,
                v_cruise_cluster,
                v_ego,
                frogpilot_toggles
            )
            desired_slc_target = self.slc.desired_speed_limit

            if self.slc.speed_limit_changed:
                speed_limit_accepted = (
                    (frogpilotCarControl.accelPressed and carControl.longActive)
                    or params_memory.get_bool("SpeedLimitAccepted")
                )
                speed_limit_denied = (
                    (frogpilotCarControl.decelPressed and carControl.longActive)
                    or self.speed_limit_timer >= 30
                )

                if speed_limit_accepted:
                    self.slc_target = desired_slc_target
                    params_memory.remove("SpeedLimitAccepted")
                elif desired_slc_target < self.slc_target and not speed_limit_confirmation_lower:
                    self.slc_target = desired_slc_target
                elif desired_slc_target > self.slc_target and not speed_limit_confirmation_higher:
                    self.slc_target = desired_slc_target
                else:
                    self.speed_limit_timer += DT_MDL

                self.slc.speed_limit_changed = (
                    self.slc_target != desired_slc_target
                    and not speed_limit_denied
                )
            elif self.slc_target == 0:
                self.slc_target = desired_slc_target
            else:
                self.speed_limit_timer = 0

            if speed_limit_controller:
                self.override_slc = self.overridden_speed > self.slc_target + self.slc_offset
                self.override_slc |= (_get_attr(carState, 'gasPressed', False) and v_ego > self.slc_target + self.slc_offset)
                self.override_slc &= controlsState.enabled

                if self.override_slc:
                    if speed_limit_controller_override_manual:
                        if _get_attr(carState, 'gasPressed', False):
                            self.overridden_speed = v_ego_cluster
                            self.overridden_speed = np.clip(
                                self.overridden_speed,
                                self.slc_target + self.slc_offset,
                                v_cruise_cluster
                            )
                    elif speed_limit_controller_override_set_speed:
                        self.overridden_speed = v_cruise_cluster
                    else:
                        self.overridden_speed = 0
                else:
                    self.override_slc = False
                    self.overridden_speed = 0

                self.slc_offset = self.slc.get_offset(self.slc_target, frogpilot_toggles)
        else:
            self.slc_offset = 0
            self.slc_target = 0

        # -------------------------------------------------------------
        # Vision Turn Speed Controller
        # -------------------------------------------------------------
        if vision_turn_speed_controller and v_ego > CRUISING_SPEED and carControl.longActive:
            self.vtsc_target = self.vtsc.update(
                v_ego,
                v_cruise,
                turn_aggressiveness
            )
        else:
            self.vtsc.reset(v_ego)
            self.vtsc_target = v_cruise if v_cruise != V_CRUISE_UNSET else 0

        # -------------------------------------------------------------
        # Force Standstill / Stop
        # -------------------------------------------------------------
        if (force_standstill
            and _get_attr(carState, 'standstill', False)
            and not self.override_force_stop
            and controlsState.enabled):
            # Hard standstill override
            self.forcing_stop = True
            v_cruise = -1
        elif force_stop_enabled and not self.override_force_stop:
            self.forcing_stop |= not _get_attr(carState, 'standstill', False)
            self.tracked_model_length = max(self.tracked_model_length - v_ego * DT_MDL, 0)
            v_cruise = min((self.tracked_model_length // PLANNER_TIME), v_cruise)
        else:
            if not self.frogpilot_planner.cem.stop_light_detected:
                self.override_force_stop = False
            self.forcing_stop = False
            self.tracked_model_length = self.frogpilot_planner.model_length

            # Choose final target among [MapTurn, SpeedLimit, VisionTurn]
        if speed_limit_controller:
          targets = [
            self.mtsc_target,
            max(self.overridden_speed, self.slc_target + self.slc_offset) - v_ego_diff,
            self.vtsc_target
          ]
        else:
          targets = [self.mtsc_target, self.vtsc_target]

        # Don't drop below CRUISING_SPEED unless needed
        v_cruise = float(min([t if t > CRUISING_SPEED else v_cruise for t in targets]))

        # Keep everything in sync w/ cluster differences
        self.mtsc_target += v_cruise_diff
        self.vtsc_target += v_cruise_diff

        return v_cruise

# Add a helper method to handle attribute access
def _get_attr(obj, attr, default=None):
    """Helper to get attribute from an object with fallback to 'out' property"""
    value = getattr(obj, attr, None)
    if value is None and hasattr(obj, 'out'):
        value = getattr(obj.out, attr, default)
    return value if value is not None else default
