from openpilot.common.numpy_fast import clip, interp
from cereal import car
from typing import Any
from openpilot.common.realtime import DT_CTRL
from openpilot.common.params import Params
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc
from openpilot.selfdrive.car.hyundai.values import HyundaiFlags, CarControllerParams


LongCtrlState = car.CarControl.Actuators.LongControlState

class JerkOutput:
  def __init__(self, jerk_upper_limit, jerk_lower_limit, cb_upper, cb_lower):
    self.jerk_upper_limit = jerk_upper_limit
    self.jerk_lower_limit = jerk_lower_limit
    self.cb_upper = cb_upper
    self.cb_lower = cb_lower

class HKGLongitudinalTuning:
  def __init__(self, CP) -> None:
    self.CP = CP
    self._setup_controllers()
    self._init_state()

  def _setup_controllers(self) -> None:
    self.mpc = LongitudinalMpc(mode='acc')
    self.long_control = LongControl(self.CP)
    self.DT_CTRL = DT_CTRL
    self.params = Params()
    self.hkg_tuning = self.params.get_bool('HKGtuning')
    self.has_radar = self.params.get_bool("HyundaiRadarTracks")

  def _init_state(self) -> None:
    self.last_accel = 0.0
    self.brake_ramp = 0.0
    self.accel_last = 0.0
    self.using_e2e = False
    self.accel_raw = 0.0
    self.accel_last_jerk = 0.0
    self.jerk = 0.0
    self.jerk_count = 0.0
    self.jerk_upper_limit = 0.0
    self.jerk_lower_limit = 0.0
    self.cb_upper = self.cb_lower = 0.0


  def make_jerk(self, CS, accel, actuators):
    state = getattr(actuators, "longControlState", LongCtrlState.pid)
    if not CS.out.cruiseState.enabled:
      self.jerk_upper_limit = 0.0
      self.jerk_lower_limit = 0.0
      self.cb_upper = self.cb_lower = 0.0
      self.accel_last_jerk = 0.0
      return 0.0

    current_accel = clip(actuators.accel, CarControllerParams.ACCEL_MIN, CarControllerParams.ACCEL_MAX)
    self.jerk = (current_accel - self.accel_last_jerk) / self.DT_CTRL
    self.accel_last_jerk = current_accel

    jerk_max = 5.0
    v_error = abs(CS.out.vEgo - CS.out.cruiseState.speed)

    if self.CP.flags & HyundaiFlags.CANFD.value:
      # Smoothly reduce jerk_max as v_error decreases below 3.0
      jerk_reduction = 1.0
      if v_error < 3.0:
        # Smooth sigmoid-like function instead of hard cutoff
        jerk_reduction = 0.3 + 0.7 * (v_error * v_error) / (v_error * v_error + 1.0)
      jerk_max *= jerk_reduction

      self.jerk_upper_limit = min(max(0.5, self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(1.0, -self.jerk * 4.0), jerk_max)
      self.cb_upper = self.cb_lower = 0.0
    else:
      self.jerk_upper_limit = min(max(0.5, self.jerk * 2.0), jerk_max)
      self.jerk_lower_limit = min(max(1.0, -self.jerk * 2.0), jerk_max)

      # Make comfort band smaller when close to set speed, bigger when far away
      error_factor = interp(v_error, [0.0, 0.5, 1.0, 5.0], [0.0, 0.1, 0.5, 1.0])
      accel_factor = interp(abs(accel), [0.0, 1.0], [0.2, 0.1])

      # Unified comfort band calculation with smooth transition around accel = 0
      accel_blend = 0.5 * (1.0 + accel / (abs(accel) + 0.1))  # Smoothly goes from 0 to 1 as accel increases

      cb_upper_pos = 0.8 * error_factor + accel * accel_factor
      cb_upper_neg = 1.0 * error_factor + accel * accel_factor
      cb_lower_pos = 0.6 * error_factor + accel * accel_factor
      cb_lower_neg = 0.8 * error_factor + accel * accel_factor

      self.cb_upper = clip(accel_blend * cb_upper_pos + (1.0 - accel_blend) * cb_upper_neg, 0.0, 1.2)
      self.cb_lower = clip(accel_blend * cb_lower_pos + (1.0 - accel_blend) * cb_lower_neg, 0.0, 1.2)

    return self.jerk

  def handle_cruise_cancel(self, CS):
    if not CS.out.cruiseState.enabled or CS.out.gasPressed or CS.out.brakePressed:
      self.accel_last = 0.0
      self.brake_ramp = 0.0
      return True
    return False

  def calculate_emergency_factor(self, CS):
    emergency_factor = 0.0
    lead_accel_factor = 0.0
    new_lead_detected = False

    try:
        if hasattr(CS.out, 'vEgo') and hasattr(CS.out, 'leadOne'):
            lead = CS.out.leadOne
            if lead.status and lead.dRel > 0.1:
                delta_v = max(0.0, CS.out.vEgo - lead.vLead)

                # Detect newly acquired leads with high delta-v
                # Store current lead status for next cycle comparison
                if not hasattr(self, 'prev_lead_status'):
                    self.prev_lead_status = False
                    self.prev_lead_id = 0
                    self.prev_delta_v = 0

                # Consider a lead "new" if it wasn't there before or if delta-v suddenly increased
                lead_id = id(lead)  # Use object id as simple way to track lead identity
                new_lead = (not self.prev_lead_status or lead_id != self.prev_lead_id)
                sudden_delta_v_change = delta_v > max(self.prev_delta_v * 1.5, 2.0)
                new_lead_detected = new_lead or sudden_delta_v_change

                # Update tracking variables for next cycle
                self.prev_lead_status = lead.status
                self.prev_lead_id = lead_id
                self.prev_delta_v = delta_v

                # Create continuous activation based on relative velocity
                delta_v_activation = delta_v / (delta_v + 0.1)

                if delta_v > 0:
                    ttc = lead.dRel / max(delta_v, 0.01)

                    # More responsive TTC factor curve for faster initial response
                    ttc_factor = clip(1.0 / (1.0 + (2.718281828459045 ** ((ttc - 3.0) * 1.2))), 0.0, 1.0)

                    # Enhanced delta-v factor that responds more quickly to high values
                    dv_factor = clip(delta_v * delta_v / (delta_v * delta_v + 9.0), 0.0, 1.0)

                    # Combined factor with higher baseline for faster initial response
                    combined_factor = ttc_factor * (0.6 + 0.4 * dv_factor) * 1.4

                    # Distance factor with more aggressive scaling at closer distances
                    dist_factor = clip(1.0 - (lead.dRel / (CS.out.vEgo * 1.8 + 4.0)), 0.0, 1.0)

                    # Enhance emergency factor for new leads with significant closing speed
                    new_lead_boost = 1.0
                    if new_lead_detected and delta_v > 3.0:
                        # Progressive boost based on closing speed and TTC
                        ttc_urgency = clip(3.0 / (ttc + 0.2) - 0.5, 0.0, 1.0)
                        new_lead_boost = 1.0 + ttc_urgency * min(delta_v / 10.0, 0.8)

                    # Final factor with continuous blending and boost for new leads
                    emergency_factor = max(combined_factor, dist_factor * 0.9) * delta_v_activation * new_lead_boost
    except:
        emergency_factor = 0.0
        new_lead_detected = False

    return emergency_factor, new_lead_detected

  def calculate_limited_accel(self, accel, actuators, CS):
    if self.handle_cruise_cancel(CS):
        return accel

    self.make_jerk(CS, accel, actuators)
    accel_delta = accel - self.accel_last
    emergency_factor, new_lead_detected = self.calculate_emergency_factor(CS)

    # Add proactive braking based on closing dynamics
    if hasattr(CS.out, 'leadOne') and CS.out.leadOne.status and CS.out.vEgo > CS.out.leadOne.vLead:
        closing_speed = max(CS.out.vEgo - CS.out.leadOne.vLead, 0.1)
        ttc = CS.out.leadOne.dRel / closing_speed

        # More aggressive anticipation with continuous scaling
        ttc_urgency = clip(4.0 / (ttc + 0.3) - 0.7, 0.0, 1.0)
        speed_urgency = clip(closing_speed * 0.15, 0.0, 1.0)
        anticipation_factor = 1.0 + ttc_urgency * speed_urgency * 0.8

        if accel < 0:
            accel *= anticipation_factor
            accel_delta = accel - self.accel_last

    # Smooth transition between acceleration and braking regions
    brake_blend = 0.5 - 0.5 * accel / (abs(accel) + 0.2)

    # Enhanced transition from acceleration to braking for newly detected leads
    if accel < 0 and self.accel_last >= 0:
        # For new leads with high closing speed, start with higher brake application
        if new_lead_detected and emergency_factor > 0.3:
            # Scale initial braking based on emergency factor
            initial_brake_level = clip(emergency_factor * 0.7, 0.0, 0.7)
            self.accel_last = -initial_brake_level
            accel_delta = accel - self.accel_last
            # Jump-start brake ramp to avoid delay in braking
            self.brake_ramp = clip(emergency_factor * 0.8, 0.3, 0.8)

    # --- Enhanced Braking Logic ---
    brake_ratio = clip(abs(accel / CarControllerParams.ACCEL_MIN), 0.0, 1.0)
    brake_aggressiveness = brake_ratio ** 1.0  # Less progressive curve for faster response

    # Speed-dependent ramp rates with higher values for faster response
    low_speed_ramp = interp(brake_aggressiveness,
                          [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                          [0.7, 0.9, 1.1, 1.3, 1.6, 1.8])
    high_speed_ramp = interp(brake_aggressiveness,
                           [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                           [0.5, 0.65, 0.8, 1.0, 1.3, 1.6])

    # Smooth speed blending
    speed_blend = CS.out.vEgo * CS.out.vEgo / (CS.out.vEgo * CS.out.vEgo + 20.0)
    braking_ramp_rate = low_speed_ramp * (1.0 - speed_blend) + high_speed_ramp * speed_blend

    # More responsive emergency scaling
    emergency_scale = interp(emergency_factor,
                          [0.0, 0.3, 0.6, 1.0],
                          [1.0, 1.3, 1.7, 2.2])  # Higher multipliers for faster response
    braking_ramp_rate *= emergency_scale

    # Handle transition from acceleration to braking
    if self.accel_last >= 0 and not new_lead_detected:
        self.brake_ramp = 0.0
        transition_factor = interp(max(emergency_factor, brake_ratio),
                               [0.0, 0.3, 0.7, 1.0],
                               [0.7, 0.85, 1.0, 1.2])  # Higher baseline
        braking_ramp_rate *= transition_factor

    # Faster ramp-up for braking
    self.brake_ramp = min(1.0, self.brake_ramp + (braking_ramp_rate * self.DT_CTRL))

    # Reduced smoothing for faster response, especially in emergencies
    brake_smooth_factor = 0.85 - 0.45 * (abs(accel) / (abs(accel) + 0.4))
    emergency_response = 0.5 + 0.5 * emergency_factor  # Higher base value for faster response
    brake_smooth_factor *= (1.0 - 0.5 * emergency_response)

    # Apply almost no smoothing for new leads with high closing speeds
    if new_lead_detected and emergency_factor > 0.4:
        brake_smooth_factor *= 0.5  # Dramatically reduce smoothing

    brake_accel_delta = accel_delta * (brake_smooth_factor * self.brake_ramp)

    # --- Acceleration Logic (positive accel) ---
    base_ramp_rate = interp(CS.out.vEgo, [0.0, 1.0, 2.0, 4.0, 6.0], [2.0, 1.7, 1.5, 1.2, 1.0])
    start_boost = 0.7 * max(0.0, 1.0 - self.accel_last * 2.0)
    accel_boost = accel * accel * 0.15
    accel_ramp_rate = base_ramp_rate + start_boost + accel_boost
    accel_accel_delta = min(accel - self.accel_last, accel_ramp_rate * self.DT_CTRL)

    # --- Dynamic jerk limits with enhanced emergency response ---
    # Base jerk upper limit
    jerk_upper = self.jerk_upper_limit

    # For braking, increase jerk limit substantially in emergencies
    # Create a continuous scale based on emergency factor
    emergency_jerk_scale = 1.0 + emergency_factor * 1.2

    # Apply extra scaling for new leads with high closing speeds
    if new_lead_detected and emergency_factor > 0.3:
        emergency_jerk_scale += emergency_factor * 0.8

    jerk_lower = self.jerk_lower_limit * emergency_jerk_scale

    # Blend acceleration and braking deltas
    accel_delta = brake_blend * brake_accel_delta + (1.0 - brake_blend) * accel_accel_delta

    # Apply dynamic jerk limits
    accel_delta = clip(accel_delta, -jerk_lower * self.DT_CTRL, jerk_upper * self.DT_CTRL)

    accel = self.accel_last + accel_delta
    self.accel_last = accel
    return accel

  def calculate_accel(self, accel, actuators, CS, frogpilot_toggles):
    if self.handle_cruise_cancel(CS):
      return 0.0
    accel = self.calculate_limited_accel(accel, actuators, CS)
    return clip(accel, CarControllerParams.ACCEL_MIN, min(frogpilot_toggles.max_desired_acceleration, CarControllerParams.ACCEL_MAX))

  def apply_tune(self, CP: Any) -> None:
    CP.vEgoStopping = 0.2
    CP.vEgoStarting = 0.05
    CP.stoppingDecelRate = 0.01
    CP.startAccel = 3.5
    CP.startingState = True

  def get_jerk(self) -> JerkOutput:
    return JerkOutput(
      self.jerk_upper_limit,
      self.jerk_lower_limit,
      self.cb_upper,
      self.cb_lower,
    )

  def calculate_and_get_jerk(self, CS, accel, actuators):
    if self.hkg_tuning:
      self.make_jerk(CS, accel, actuators)
      return self.get_jerk()
    else:
      normal_jerk = self.calculate_normal_jerk(actuators.longControlState)
      return JerkOutput(normal_jerk, normal_jerk, 0.0, 0.0)

class HKGLongitudinalController:
  def __init__(self, CP):
    self.CP = CP
    self.tuning = HKGLongitudinalTuning(CP) if Params().get_bool("HKGtuning") else None
    self.jerk = None

  def apply_tune(self, CP):
    if self.tuning:
      self.tuning.apply_tune(CP)

  def calculate_normal_jerk(self, long_control_state):
    return 3.0 if long_control_state == LongCtrlState.pid else 1.0