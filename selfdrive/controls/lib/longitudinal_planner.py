#!/usr/bin/env python3
import math
import numpy as np
from openpilot.common.numpy_fast import clip, interp

import cereal.messaging as messaging
from openpilot.common.conversions import Conversions as CV
from openpilot.common.filter_simple import FirstOrderFilter
from openpilot.common.simple_kalman import KF1D
from openpilot.common.realtime import DT_MDL
from openpilot.selfdrive.modeld.constants import ModelConstants
from openpilot.selfdrive.car.interfaces import ACCEL_MIN, ACCEL_MAX
from openpilot.selfdrive.controls.lib.longcontrol import LongCtrlState
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import LongitudinalMpc
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import T_IDXS as T_IDXS_MPC, LEAD_ACCEL_TAU
from openpilot.selfdrive.controls.lib.drive_helpers import V_CRUISE_MAX, V_CRUISE_UNSET, CONTROL_N, get_speed_error
from openpilot.common.swaglog import cloudlog

LON_MPC_STEP = 0.2
A_CRUISE_MIN = -6.0
A_CRUISE_MAX_VALS = [4.2, 3.0, 1.8, 1.0]
A_CRUISE_MAX_BP = [0., 10.0, 25., 40.]
CONTROL_N_T_IDX = ModelConstants.T_IDXS[:CONTROL_N]
ALLOW_THROTTLE_THRESHOLD = 0.3
MIN_ALLOW_THROTTLE_SPEED = 1.0

_A_TOTAL_MAX_V = [1.7, 3.2]
_A_TOTAL_MAX_BP = [20., 40.]

def get_max_accel(v_ego):
  return interp(v_ego, A_CRUISE_MAX_BP, A_CRUISE_MAX_VALS)

def get_coast_accel(pitch):
  return np.sin(pitch) * -5.65 - 0.3

def limit_accel_in_turns(v_ego, angle_steers, a_target, CP):
  a_total_max = interp(v_ego, _A_TOTAL_MAX_BP, _A_TOTAL_MAX_V)
  a_y = v_ego ** 2 * angle_steers * CV.DEG_TO_RAD / (CP.steerRatio * CP.wheelbase)
  a_x_allowed = math.sqrt(max(a_total_max ** 2 - a_y ** 2, 0.))
  return [a_target[0], min(a_target[1], a_x_allowed)]

def get_accel_from_plan_classic(CP, speeds, accels, vEgoStopping):
  if len(speeds) == CONTROL_N:
    from openpilot.common.numpy_fast import interp
    v_target_now = interp(DT_MDL, CONTROL_N_T_IDX, speeds)
    a_target_now = interp(DT_MDL, CONTROL_N_T_IDX, accels)
    v_target = interp(CP.longitudinalActuatorDelay + DT_MDL, CONTROL_N_T_IDX, speeds)
    if v_target != v_target_now:
      a_target = 2 * (v_target - v_target_now) / CP.longitudinalActuatorDelay - a_target_now
    else:
      a_target = a_target_now
    v_target_1sec = interp(CP.longitudinalActuatorDelay + DT_MDL + 1.0, CONTROL_N_T_IDX, speeds)
  else:
    v_target = 0.0
    v_target_1sec = 0.0
    a_target = 0.0
  should_stop = (v_target < vEgoStopping and v_target_1sec < vEgoStopping)
  return a_target, should_stop

def get_accel_from_plan(speeds, accels, action_t=DT_MDL, vEgoStopping=0.05):
  if len(speeds) == CONTROL_N:
    v_now = speeds[0]
    a_now = accels[0]
    v_target = interp(action_t, CONTROL_N_T_IDX, speeds)
    a_target = 2 * (v_target - v_now) / action_t - a_now
    v_target_1sec = interp(action_t + 1.0, CONTROL_N_T_IDX, speeds)
  else:
    v_target = 0.0
    v_target_1sec = 0.0
    a_target = 0.0
  should_stop = (v_target < vEgoStopping and v_target_1sec < vEgoStopping)
  return a_target, should_stop

# If you're using "radarless_model", you have a 'Lead' class with a simple Kalman
# Otherwise, in normal radar usage, we get a capnp struct from radarState.
LEAD_KALMAN_SPEED, LEAD_KALMAN_ACCEL = 0, 1

def lead_kf(v_lead: float, dt: float = 0.05):
  # Old 1D code for the "classic" lead if you want it
  from openpilot.common.simple_kalman import KF1D
  assert dt > .01 and dt < .2
  A = [[1.0, dt],[0.0, 1.0]]
  C = [1.0, 0.0]
  dts = [dt * 0.01 for dt in range(1, 21)]
  K0 = [0.12287673, 0.14556536, 0.16522756, 0.18281627, 0.1988689,  0.21372394,
        0.22761098, 0.24069424, 0.253096,   0.26491023, 0.27621103, 0.28705801,
        0.29750003, 0.30757767, 0.31732515, 0.32677158, 0.33594201, 0.34485814,
        0.35353899, 0.36200124]
  K1 = [0.29666309, 0.29330885, 0.29042818, 0.28787125, 0.28555364, 0.28342219,
        0.28144091, 0.27958406, 0.27783249, 0.27617149, 0.27458948, 0.27307714,
        0.27162685, 0.27023228, 0.26888809, 0.26758976, 0.26633338, 0.26511557,
        0.26393339, 0.26278425]
  from openpilot.common.numpy_fast import interp
  K = [[interp(dt, dts, K0)], [interp(dt, dts, K1)]]
  kf = KF1D([[v_lead],[0.0]], A, C, K)
  return kf

class Lead:
  def __init__(self):
    self.dRel = 0.0
    self.yRel = 0.0
    self.vLead = 0.0
    self.aLead = 0.0
    self.vLeadK = 0.0
    self.aLeadK = 0.0
    self.aLeadTau = LEAD_ACCEL_TAU
    self.prob = 0.0
    self.status = False
    self.kf: KF1D | None = None

  def reset(self):
    self.status = False
    self.kf = None
    self.aLeadTau = LEAD_ACCEL_TAU

  def update(self, dRel: float, yRel: float, vLead: float, aLead: float, prob: float):
    self.dRel = dRel
    self.yRel = yRel
    self.vLead = vLead
    self.aLead = aLead
    self.prob = prob
    self.status = True
    if self.kf is None:
      self.kf = lead_kf(self.vLead)
    else:
      self.kf.update(self.vLead)
    self.vLeadK = float(self.kf.x[LEAD_KALMAN_SPEED][0])
    self.aLeadK = float(self.kf.x[LEAD_KALMAN_ACCEL][0])
    if abs(self.aLeadK) < 0.5:
      self.aLeadTau = LEAD_ACCEL_TAU
    else:
      self.aLeadTau *= 0.9

#
# A dynamic time-to-collision threshold function
#
def emergency_brake_threshold(v_ego: float) -> float:
  t_stop = v_ego / 6.0
  return t_stop + 0.5

#
# Helper to unify how we get lead fields in "classic_model" (dictionary style) vs. normal capnp struct
#
def get_drel(lead, classic_model):
  """
  Return the lead's distance, either from a dictionary or from a capnp struct
  """
  if classic_model:
    # old "Lead" object with .dRel
    return lead.dRel
  else:
    # radarState lead is a capnp struct with .dRel
    return lead.dRel

def get_vlead(lead, classic_model):
  """
  Return the lead's speed, either from a dictionary or from a capnp struct
  """
  if classic_model:
    # old "Lead" object with .vLead
    return lead.vLead
  else:
    # radarState lead is a capnp struct with .vLead
    return lead.vLead

def get_status(lead, classic_model):
  """
  Return the lead's status (True/False).
  """
  if classic_model:
    return lead.status
  else:
    return lead.status

class LongitudinalPlanner:
  def __init__(self, CP, init_v=0.0, init_a=0.0, dt=DT_MDL):
    self.CP = CP
    self.mpc = LongitudinalMpc(dt=dt)
    self.fcw = False
    self.dt = dt
    self.allow_throttle = True

    self.a_desired = init_a
    self.v_desired_filter = FirstOrderFilter(init_v, 2.0, self.dt)
    self.v_model_error = 0.0

    # For "classic_model" usage
    self.lead_one = Lead()
    self.lead_two = Lead()

    self.v_desired_trajectory = np.zeros(CONTROL_N)
    self.a_desired_trajectory = np.zeros(CONTROL_N)
    self.j_desired_trajectory = np.zeros(CONTROL_N)
    self.solverExecutionTime = 0.0

  @staticmethod
  def parse_model(model_msg, model_error, v_ego, taco_tune):
    if (len(model_msg.position.x) == ModelConstants.IDX_N and
        len(model_msg.velocity.x) == ModelConstants.IDX_N and
        len(model_msg.acceleration.x) == ModelConstants.IDX_N):
      from openpilot.common.numpy_fast import interp
      x = np.interp(T_IDXS_MPC, ModelConstants.T_IDXS, model_msg.position.x) - model_error * T_IDXS_MPC
      v = np.interp(T_IDXS_MPC, ModelConstants.T_IDXS, model_msg.velocity.x) - model_error
      a = np.interp(T_IDXS_MPC, ModelConstants.T_IDXS, model_msg.acceleration.x)
      j = np.zeros(len(T_IDXS_MPC))
    else:
      x = np.zeros(len(T_IDXS_MPC))
      v = np.zeros(len(T_IDXS_MPC))
      a = np.zeros(len(T_IDXS_MPC))
      j = np.zeros(len(T_IDXS_MPC))

    if taco_tune:
      lat_accel_bp = [0.0, 5.0, 10.0, 15.0, 20.0, 30.0]
      lat_accel_v = [1.3, 1.5, 2.0, 2.5, 3.0, 3.5]
      max_lat_accel = interp(v_ego, lat_accel_bp, lat_accel_v)
      v_for_curvature = np.maximum(v, 0.3)
      curvatures = np.interp(T_IDXS_MPC, ModelConstants.T_IDXS, model_msg.orientationRate.z) / v_for_curvature
      curve_factor = np.clip(np.abs(curvatures) * 10.0, 0.5, 3.0)
      safety_margin = 1.0 + 1.0 * (curve_factor - 0.5) / 2.5
      max_v = np.sqrt(max_lat_accel / (np.abs(curvatures) + 1e-3)) / safety_margin
      v = np.minimum(max_v, v)

    if len(model_msg.meta.disengagePredictions.gasPressProbs) > 1:
      throttle_prob = model_msg.meta.disengagePredictions.gasPressProbs[1]
    else:
      throttle_prob = 1.0
    return x, v, a, j, throttle_prob

  def update(self, radarless_model, sm, frogpilot_toggles):
    self.mpc.mode = 'blended' if sm['controlsState'].experimentalMode else 'acc'

    if len(sm['carControl'].orientationNED) == 3:
      accel_coast = get_coast_accel(sm['carControl'].orientationNED[1])
    else:
      accel_coast = ACCEL_MAX

    v_ego = sm['carState'].vEgo
    v_cruise_kph = min(sm['controlsState'].vCruise, V_CRUISE_MAX)
    v_cruise = v_cruise_kph * CV.KPH_TO_MS
    v_cruise_initialized = sm['controlsState'].vCruise != V_CRUISE_UNSET

    long_control_off = (sm['controlsState'].longControlState == LongCtrlState.off)
    force_slow_decel = sm['controlsState'].forceDecel
    reset_state = (long_control_off if self.CP.openpilotLongitudinalControl else not sm['controlsState'].enabled)
    reset_state = reset_state or not v_cruise_initialized
    prev_accel_constraint = not (reset_state or sm['carState'].standstill)

    if self.mpc.mode == 'acc':
      accel_limits = [sm['frogpilotPlan'].minAcceleration, sm['frogpilotPlan'].maxAcceleration]
      accel_limits_turns = accel_limits
    else:
      accel_limits = [ACCEL_MIN, ACCEL_MAX]
      accel_limits_turns = [ACCEL_MIN, ACCEL_MAX]

    if reset_state:
      self.v_desired_filter.x = v_ego
      self.a_desired = clip(sm['carState'].aEgo, accel_limits[0], accel_limits[1])

    self.v_desired_filter.x = max(0.0, self.v_desired_filter.update(v_ego))
    self.v_model_error = get_speed_error(sm['modelV2'], v_ego)
    x, v, a, j, throttle_prob = self.parse_model(sm['modelV2'], self.v_model_error, v_ego, frogpilot_toggles.taco_tune)

    throttle_weight = np.clip((throttle_prob - (ALLOW_THROTTLE_THRESHOLD - 0.1)) / 0.2, 0.0, 1.0)
    speed_weight = np.clip((MIN_ALLOW_THROTTLE_SPEED + 1.0 - v_ego) / 1.0, 0.0, 1.0)
    allow_factor = np.clip(throttle_weight + speed_weight, 0.0, 1.0)
    self.allow_throttle = allow_factor > 0.1

    if allow_factor < 0.99:
      clipped_accel_coast = max(accel_coast, accel_limits_turns[0])
      speed_blend = np.clip((v_ego - MIN_ALLOW_THROTTLE_SPEED) / (MIN_ALLOW_THROTTLE_SPEED * 2 - MIN_ALLOW_THROTTLE_SPEED), 0.0, 1.0)
      coast_limit = speed_blend * clipped_accel_coast + (1.0 - speed_blend) * accel_limits_turns[1]
      accel_limits_turns[1] = allow_factor * accel_limits_turns[1] + (1.0 - allow_factor) * coast_limit

    if force_slow_decel:
      v_cruise = 0.0
    accel_limits_turns[0] = min(accel_limits_turns[0], self.a_desired + 0.05)
    accel_limits_turns[1] = max(accel_limits_turns[1], self.a_desired - 0.05)

    # Construct leads from either radarless model or from radarState
    if radarless_model:
      # In "classic model" mode, we fill self.lead_one/lead_two with the old style
      model_leads = list(sm['modelV2'].leadsV3)
      lead_states = [self.lead_one, self.lead_two]
      for index in range(len(lead_states)):
        if len(model_leads) > index:
          model_lead = model_leads[index]
          lead_speed = model_lead.v[0]
          stop_factor = 1.0/(1.0 + np.exp((lead_speed - 0.5)/0.1))
          closing_speed = max(v_ego - lead_speed, 0.1)
          ttc = model_lead.x[0]/closing_speed
          ttc_factor = 6.0/(1.0 + np.exp((ttc - 2.5)/0.4))
          speed_factor = 0.8 + 1.5/(1.0 + np.exp(-(v_ego - 7.0)/2.5))
          early_brake_factor = 1.0 + 0.3*(1.0 - np.exp(-v_ego/12.0))
          closing_speed_factor = min(2.0, closing_speed/5.0)
          ttc_urgency = np.clip(4.0/(ttc + 0.1) - 0.5, 0.0, 1.0)
          dynamic_offset = frogpilot_toggles.increased_stopped_distance * 0.5 * closing_speed_factor * ttc_urgency
          traffic_offset = 0.0
          if sm['frogpilotCarState'].trafficModeActive:
            traffic_offset = max(0.0, 12.0 - v_ego) * 0.6
          stopped_offset = frogpilot_toggles.increased_stopped_distance * stop_factor * ttc_factor * speed_factor * early_brake_factor
          moving_offset = frogpilot_toggles.increased_stopped_distance + traffic_offset
          distance_offset = stop_factor*stopped_offset + (1.0 - stop_factor)*moving_offset + dynamic_offset
          lead_states[index].update(model_lead.x[0] - distance_offset,
                                    model_lead.y[0],
                                    model_lead.v[0],
                                    model_lead.a[0],
                                    model_lead.prob)
        else:
          lead_states[index].reset()
    else:
      # If not radarless, we get a capnp struct from radarState
      self.lead_one = sm['radarState'].leadOne
      self.lead_two = sm['radarState'].leadTwo

    self.mpc.set_weights(sm['frogpilotPlan'].accelerationJerk,
                         sm['frogpilotPlan'].dangerJerk,
                         sm['frogpilotPlan'].speedJerk,
                         prev_accel_constraint,
                         personality=sm['controlsState'].personality)
    self.mpc.set_accel_limits(accel_limits_turns[0], accel_limits_turns[1])
    self.mpc.set_cur_state(self.v_desired_filter.x, self.a_desired)
    self.mpc.update(self.lead_one, self.lead_two, sm['frogpilotPlan'].vCruise,
                    x, v, a, j, radarless_model,
                    sm['frogpilotPlan'].tFollow,
                    sm['frogpilotCarState'].trafficModeActive,
                    personality=sm['controlsState'].personality)

    self.a_desired_trajectory_full = np.interp(CONTROL_N_T_IDX, T_IDXS_MPC, self.mpc.a_solution)
    self.v_desired_trajectory = np.interp(CONTROL_N_T_IDX, T_IDXS_MPC, self.mpc.v_solution)
    self.a_desired_trajectory = np.interp(CONTROL_N_T_IDX, T_IDXS_MPC, self.mpc.a_solution)
    self.j_desired_trajectory = np.interp(CONTROL_N_T_IDX[:-1], T_IDXS_MPC[:-1], self.mpc.j_solution)

    self.fcw = self.mpc.crash_cnt > 2 and not sm['carState'].standstill
    if self.fcw:
      cloudlog.info("FCW triggered")

    a_prev = self.a_desired
    self.a_desired = float(np.interp(self.dt, CONTROL_N_T_IDX, self.a_desired_trajectory))
    self.v_desired_filter.x = self.v_desired_filter.x + self.dt * (self.a_desired + a_prev) / 2.0

  def publish(self, classic_model, sm, pm, frogpilot_toggles):
    plan_send = messaging.new_message('longitudinalPlan')
    plan_send.valid = sm.all_checks(service_list=['carState', 'controlsState'])
    longitudinalPlan = plan_send.longitudinalPlan
    longitudinalPlan.modelMonoTime = sm.logMonoTime['modelV2']
    longitudinalPlan.processingDelay = (plan_send.logMonoTime / 1e9) - sm.logMonoTime['modelV2']
    longitudinalPlan.solverExecutionTime = self.mpc.solve_time

    longitudinalPlan.speeds = self.v_desired_trajectory.tolist()
    longitudinalPlan.accels = self.a_desired_trajectory.tolist()
    longitudinalPlan.jerks = self.j_desired_trajectory.tolist()

    # We'll unify the hasLead logic. If in "classic_model", self.lead_one is a Lead object
    # otherwise it's a capnp struct from radarState.
    if classic_model:
      longitudinalPlan.hasLead = self.lead_one.status
    else:
      longitudinalPlan.hasLead = self.lead_one.status

    longitudinalPlan.longitudinalPlanSource = self.mpc.source
    longitudinalPlan.fcw = self.fcw

    # Compute final a_target, should_stop
    if classic_model:
      a_target, should_stop = get_accel_from_plan_classic(self.CP,
                                                          longitudinalPlan.speeds,
                                                          longitudinalPlan.accels,
                                                          vEgoStopping=frogpilot_toggles.vEgoStopping)
    else:
      action_t = self.CP.longitudinalActuatorDelay + DT_MDL
      a_target, should_stop = get_accel_from_plan(longitudinalPlan.speeds,
                                                  longitudinalPlan.accels,
                                                  action_t=action_t,
                                                  vEgoStopping=frogpilot_toggles.vEgoStopping)

    #
    # Emergency braking override
    #
    # We'll do the same approach for lead_one, lead_two, calling our get_drel / get_vlead helpers
    # so it doesn't matter if we have a dictionary or a capnp struct
    #
    for lead_obj in [self.lead_one, self.lead_two]:
      if get_status(lead_obj, classic_model):
        d_rel = get_drel(lead_obj, classic_model)
        v_lead = get_vlead(lead_obj, classic_model)
        closing_speed = max(sm['carState'].vEgo - v_lead, 0.1)
        ttc_lead = d_rel / closing_speed
        ttc_threshold = emergency_brake_threshold(sm['carState'].vEgo)
        if ttc_lead < ttc_threshold:
          should_stop = True
          cloudlog.info(
            f"Emergency braking override: lead dRel={d_rel:.1f}, "
            f"closing_speed={closing_speed:.1f}, ttc={ttc_lead:.2f}, "
            f"threshold={ttc_threshold:.2f}"
          )
          break

    longitudinalPlan.aTarget = a_target
    longitudinalPlan.shouldStop = should_stop
    longitudinalPlan.allowBrake = True
    longitudinalPlan.allowThrottle = bool(self.allow_throttle)

    pm.send('longitudinalPlan', plan_send)