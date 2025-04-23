#!/usr/bin/env python3
import importlib
import math
from collections import deque
from types import SimpleNamespace
from typing import Any

import capnp
from cereal import messaging, log, car
from openpilot.common.numpy_fast import interp
from openpilot.common.params import Params
from openpilot.common.realtime import DT_CTRL, Ratekeeper, Priority, config_realtime_process
from openpilot.common.swaglog import cloudlog

# Removed openpilot.common.simple_kalman import, since we'll define our own 2D filter here

from openpilot.selfdrive.frogpilot.frogpilot_variables import get_frogpilot_toggles

# ---------------------------------------------------------------------------------------
# 2D Kalman filter: state = [ dRel, vRel ]
# ---------------------------------------------------------------------------------------
import numpy as np

class KF2D:
  """
  Minimal 2D Kalman filter for tracking [dRel, vRel].
  The state transition assumes constant velocity (zero accel).
  You can expand to 3D if you want explicit acceleration in the state.
  """

  def __init__(self, dt: float):
    self.dt = dt

    # State x = [ dRel, vRel ]^T
    self.x = np.zeros((2, 1))
    # Covariance P
    self.P = np.eye(2) * 1e3  # large initial uncertainty

    # Constant-velocity state transition:
    #   dRel_{k+1} = dRel_k + dt*vRel_k
    #   vRel_{k+1} = vRel_k
    self.A = np.array([
      [1.0, dt],
      [0.0, 1.0],
    ])

    # We measure [dRel, vRel] directly
    self.C = np.eye(2)

    # Process noise Q (tune these).
    # Larger Q -> trust the model less, respond faster to measurements
    self.Q = np.array([
      [0.3*dt, 0.0 ],
      [0.0,    0.3*dt],
    ])**2

    # Measurement noise R (tune these).
    # If radar distance is accurate, keep R(dRel) small; if vRel is noisy, keep R(vRel) bigger, etc.
    self.R = np.diag([1.0, 2.0])

  def predict(self):
    # Predict next (x, P)
    self.x = self.A @ self.x
    self.P = self.A @ self.P @ self.A.T + self.Q

  def update(self, z: np.ndarray):
    """
    z is [dRel_meas, vRel_meas].
    We'll do the standard linear Kalman update.
    """
    z = z.reshape((2, 1))
    y = z - (self.C @ self.x)                      # residual
    S = self.C @ self.P @ self.C.T + self.R        # residual covariance
    K = self.P @ self.C.T @ np.linalg.inv(S)       # Kalman gain
    self.x = self.x + K @ y
    I = np.eye(2)
    self.P = (I - K @ self.C) @ self.P

# ---------------------------------------------------------------------------------------
# Original constants, plus we keep _LEAD_ACCEL_TAU if you like
# ---------------------------------------------------------------------------------------
_LEAD_ACCEL_TAU = 0.6

# For track association
V_EGO_STATIONARY = 4.0
RADAR_TO_CAMERA = 1.52

class Track:
  def __init__(self, identifier: int, d_rel_init: float, v_rel_init: float, dt: float, is_hyundai_interface: bool):
    self.identifier = identifier
    self.cnt = 0
    # We'll keep aLeadTau logic if desired
    self.aLeadTau = _LEAD_ACCEL_TAU
    self.is_hyundai_interface = is_hyundai_interface

    # New 2D KF for [dRel, vRel]
    self.kf = KF2D(dt)
    self.kf.x[0, 0] = d_rel_init
    self.kf.x[1, 0] = v_rel_init
    # e.g. smaller initial cov if we trust the first measurement
    self.kf.P = np.diag([10.0, 10.0])

    # For computing approximate acceleration
    self.prev_vRel_K = v_rel_init
    self.aLeadK = 0.0

    # For calculating vRel from dRel derivative (Hyundai interface only)
    self.prev_dRel_K = d_rel_init
    self.calculated_vRel = v_rel_init

    # store raw measured values
    self.dRel = d_rel_init
    self.yRel = 0.0
    self.vRel = v_rel_init
    self.vLead = 0.0
    self.measured = False

    # Store filtered states from KF and vLeadK
    self.dRel_K = d_rel_init
    self.vRel_K = v_rel_init
    self.vLeadK = v_rel_init

  def update(self, d_rel: float, y_rel: float, v_rel: float, v_lead: float, measured: bool, v_ego: float):
    """
    d_rel: measured distance
    y_rel: measured lateral offset
    v_rel: measured relative speed
    v_lead: measured absolute lead speed (v_rel + v_ego)
    measured: bool
    v_ego: our own speed
    """
    # store raw
    self.dRel = d_rel
    self.yRel = y_rel
    self.vRel = v_rel
    self.vLead = v_lead
    self.measured = measured

    # 1) Predict
    self.kf.predict()

    # 2) Update with measurement = [d_rel, v_rel]
    z = np.array([d_rel, v_rel], dtype=float)
    self.kf.update(z)

    # Get filtered states from KF
    dRel_K = float(self.kf.x[0, 0])
    vRel_K = float(self.kf.x[1, 0])

    # --- Conditional vRel Calculation ---
    if self.is_hyundai_interface:
        current_dRel_K = dRel_K
        dt = self.kf.dt
        if self.cnt > 0 and dt > 1e-5:
            self.calculated_vRel = (current_dRel_K - self.prev_dRel_K) / dt
        self.prev_dRel_K = current_dRel_K
    else:
        self.calculated_vRel = vRel_K
    # --- End Conditional Calculation ---

    # approximate lead acceleration (always using KF's vRel_K for stability/consistency for now)
    if self.cnt > 0:
      dt = self.kf.dt
      if dt > 1e-5:
          self.aLeadK = (vRel_K - self.prev_vRel_K) / dt
    self.prev_vRel_K = vRel_K

    # If you want to keep some "aLeadTau" adaptation logic:
    if abs(self.aLeadK) < 0.5:
      self.aLeadTau = min(max(self.aLeadTau, 1e-2) * 1.1, _LEAD_ACCEL_TAU)
    else:
      self.aLeadTau *= 0.9

    self.cnt += 1

    # Store KF states and KF-derived vLeadK
    self.dRel_K = dRel_K
    self.vRel_K = vRel_K
    self.vLeadK = vRel_K + v_ego

  def get_key_for_cluster(self):
    # Weigh y higher since radar is inaccurate in that dimension
    return [self.dRel, self.yRel*2, self.vRel]

  def reset_a_lead(self, aLeadK: float, aLeadTau: float):
    # If you ever want to forcibly reset the filter's acceleration estimate
    self.aLeadK = aLeadK
    self.aLeadTau = aLeadTau
    # Optionally reinit the KF with new states
    self.kf.x[1, 0] = self.vRel

  def is_potential_fcw(self, model_prob: float):
    return model_prob > 0.9

  def get_RadarState(self, model_prob: float = 0.0):
    """
    Return a dictionary for radarState.leadOne / leadTwo, with *filtered* velocity.
    We'll store `vLead` and `vRel` as the filtered versions so the planner uses them.
    Calculates TTC based on filtered dRel_K and vRel_K.
    """
    # Calculate TTC using filtered dRel_K and the calculated vRel (either derived or KF's)
    ttc = safe_ttc(self.dRel_K, self.calculated_vRel)

    # Recover the v_ego used during the last update to calculate the vLead based on calculated_vRel
    # vLeadK = vRel_K + v_ego  => v_ego = vLeadK - vRel_K
    # Note: This assumes v_ego didn't change significantly between the update and this call
    v_ego_est = self.vLeadK - self.vRel_K

    return {
      "dRel": float(self.dRel_K),   # use filtered distance
      "yRel": float(self.yRel),     # lateral remains unfiltered
      "vRel": float(self.calculated_vRel),   # Use calculated (derived or KF) relative speed
      "vLead": float(self.calculated_vRel + v_ego_est),  # Use calculated (derived or KF) absolute speed
      "vLeadK": float(self.vLeadK), # keep original KF-based vLeadK for debugging/comparison
      "aLeadK": float(self.aLeadK),
      "aLeadTau": float(self.aLeadTau),
      "ttc": float(ttc),            # TTC uses calculated vRel
      "status": True,
      "fcw": self.is_potential_fcw(model_prob),
      "modelProb": model_prob,
      "radar": True,
      "radarTrackId": self.identifier,
    }

  def potential_adjacent_lead(self, far: bool, left: bool, model_data: capnp._DynamicStructReader, standstill: bool):
    # unchanged from your original
    if standstill or self.vLeadK < 1:
      return False

    near_lane_index = 1 if left else 2
    far_lane_index = 0 if left else 3

    if far:
      lane_position = interp(self.dRel, model_data.laneLines[far_lane_index].x, model_data.laneLines[far_lane_index].y)
      return self.yRel < lane_position if left else lane_position < self.yRel
    else:
      near_lane = interp(self.dRel, model_data.laneLines[near_lane_index].x, model_data.laneLines[near_lane_index].y)
      far_lane = interp(self.dRel, model_data.laneLines[far_lane_index].x, model_data.laneLines[far_lane_index].y)
      return min(near_lane, far_lane) < self.yRel < max(near_lane, far_lane)

  def potential_far_lead(self, model_data: capnp._DynamicStructReader):
    if self.vLeadK < 1:
      return False

    left_lane = interp(self.dRel, model_data.laneLines[1].x, model_data.laneLines[1].y)
    right_lane = interp(self.dRel, model_data.laneLines[2].x, model_data.laneLines[2].y)

    return left_lane < self.yRel < right_lane

  def potential_low_speed_lead(self, v_ego: float):
    # unchanged from your original
    return abs(self.yRel) < 1.0 and (v_ego < V_EGO_STATIONARY) and (0.75 < self.dRel < 25)

  def __str__(self):
    ret = f"x: {self.dRel:4.1f}  y: {self.yRel:4.1f}  v: {self.vRel:4.1f}  a: {self.aLeadK:4.1f}"
    return ret


def laplacian_pdf(x: float, mu: float, b: float):
  b = max(b, 1e-4)
  return math.exp(-abs(x - mu)/b)


def match_vision_to_track(v_ego: float, lead: capnp._DynamicStructReader, tracks: dict[int, Track]):
  offset_vision_dist = lead.x[0] - RADAR_TO_CAMERA

  def prob(c: Track):
    # We'll compare to the raw states, or the filtered states?  Typically filtered is safer.
    # But your original code used c.dRel, c.vRel...
    prob_d = laplacian_pdf(c.dRel, offset_vision_dist, lead.xStd[0])
    prob_y = laplacian_pdf(c.yRel, -lead.y[0], lead.yStd[0])
    prob_v = laplacian_pdf(c.vRel + v_ego, lead.v[0], lead.vStd[0])
    return prob_d * prob_y * prob_v

  track = max(tracks.values(), key=prob)

  dist_sane = abs(track.dRel - offset_vision_dist) < max(offset_vision_dist * 0.25, 5.0)
  vel_sane = (abs(track.vRel + v_ego - lead.v[0]) < 10) or (v_ego + track.vRel > 3)
  if dist_sane and vel_sane:
    return track
  else:
    return None


def get_RadarState_from_vision(lead_msg: capnp._DynamicStructReader, v_ego: float, model_v_ego: float):
  lead_v_rel_pred = lead_msg.v[0] - model_v_ego
  d_rel_vision = float(lead_msg.x[0] - RADAR_TO_CAMERA)

  # Calculate TTC using vision relative values
  ttc = safe_ttc(d_rel_vision, lead_v_rel_pred)

  return {
    "dRel": d_rel_vision,
    "yRel": float(-lead_msg.y[0]),
    "vRel": float(lead_v_rel_pred),
    "vLead": float(v_ego + lead_v_rel_pred),
    "vLeadK": float(v_ego + lead_v_rel_pred),
    "aLeadK": float(lead_msg.a[0]),
    "aLeadTau": 0.3,
    "ttc": float(ttc),
    "fcw": False,
    "modelProb": float(lead_msg.prob),
    "status": True,
    "radar": False,
    "radarTrackId": -1,
  }


def get_lead(v_ego: float, ready: bool, tracks: dict[int, Track], lead_msg: capnp._DynamicStructReader,
             model_v_ego: float, model_data: capnp._DynamicStructReader,
             frogpilot_toggles: SimpleNamespace, frogpilotCarState: capnp._DynamicStructReader,
             low_speed_override: bool = True) -> dict[str, Any]:
  if len(tracks) > 0 and ready and lead_msg.prob > frogpilot_toggles.lead_detection_probability:
    track = match_vision_to_track(v_ego, lead_msg, tracks)
  else:
    track = None

  lead_dict = {'status': False}
  if track is not None:
    lead_dict = track.get_RadarState(lead_msg.prob)
  elif (track is None) and ready and (lead_msg.prob > frogpilot_toggles.lead_detection_probability):
    lead_dict = get_RadarState_from_vision(lead_msg, v_ego, model_v_ego)

  if low_speed_override:
    low_speed_tracks = [c for c in tracks.values() if c.potential_low_speed_lead(v_ego)]
    if len(low_speed_tracks) > 0:
      closest_track = min(low_speed_tracks, key=lambda c: c.dRel)
      if (not lead_dict['status']) or (closest_track.dRel < lead_dict['dRel']):
        lead_dict = closest_track.get_RadarState()

    if not lead_dict['status'] and frogpilot_toggles.allow_far_lead_tracking:
      far_lead_tracks = [c for c in tracks.values() if c.potential_far_lead(model_data)]
      if len(far_lead_tracks) > 0:
        closest_track = min(far_lead_tracks, key=lambda c: c.dRel)
        lead_dict = closest_track.get_RadarState()
        lead_dict['vLead'] = lead_dict['vLeadK']

  if 'dRel' in lead_dict:
    lead_dict['dRel'] -= frogpilot_toggles.increased_stopped_distance if not frogpilotCarState.trafficModeActive else 0

  return lead_dict


def get_adjacent_lead(tracks: dict[int, Track], model_data: capnp._DynamicStructReader, standstill: bool, left: bool = True, far: bool = False) -> dict[str, Any]:
  lead_dict = {'status': False}

  adjacent_tracks = [c for c in tracks.values() if c.potential_adjacent_lead(far, left, model_data, standstill)]
  if len(adjacent_tracks) > 0:
    closest_track = min(adjacent_tracks, key=lambda c: c.dRel)
    lead_dict = closest_track.get_RadarState()

  return lead_dict


def get_forward_blindspot(tracks: dict[int, Track], left: bool = True) -> bool:
  """
  Detect vehicles in forward blindspots (adjacent lane but forward).
  We'll keep your original logic, just referencing track data.
  """
  y_min = -4.0 if left else 0.5
  y_max = -0.5 if left else 4.0
  d_min = 3.0
  d_max = 20.0

  front_left_ids = range(3000, 4000)
  front_right_ids = range(4000, 5000)

  relevant_ids = front_left_ids if left else front_right_ids
  for track_id, track in tracks.items():
    if (track_id in relevant_ids) or (track_id < 1000 and y_min < track.yRel < y_max and d_min < track.dRel < d_max):
      if track_id in relevant_ids:
        return True
      elif track.measured and track.vLeadK > 0:
        return True
  return False


class RadarD:
  def __init__(self, frogpilot_toggles, radar_ts: float, delay: int = 0, is_hyundai_interface: bool = False):
    self.points: dict[int, tuple[float, float, float]] = {}
    self.current_time = 0.0

    self.tracks: dict[int, Track] = {}
    self.radar_state: capnp._DynamicStructBuilder | None = None

    self.v_ego = 0.0
    self.v_ego_hist = deque([0.0], maxlen=delay+1)
    self.last_v_ego_frame = -1

    self.radar_state_valid = False
    self.radar_tracks_valid = False
    self.ready = False

    self.left_forward_blindspot = False
    self.right_forward_blindspot = False

    self.frogpilot_toggles = frogpilot_toggles
    self.classic_model = self.frogpilot_toggles.classic_model
    self.radar_ts = radar_ts
    self.is_hyundai_interface = is_hyundai_interface

  def update(self, sm: messaging.SubMaster, rr):
    self.ready = sm.seen['modelV2']
    self.current_time = 1e-9*max(sm.logMonoTime.values())

    radar_points = []
    radar_errors = []
    if rr is not None:
      radar_points = rr.points
      radar_errors = rr.errors

    if sm.recv_frame['carState'] != self.last_v_ego_frame:
      self.v_ego = sm['carState'].vEgo
      self.v_ego_hist.append(self.v_ego)
      self.last_v_ego_frame = sm.recv_frame['carState']

    ar_pts = {}
    for pt in radar_points:
      ar_pts[pt.trackId] = [pt.dRel, pt.yRel, pt.vRel, pt.measured]

    # Remove missing points
    for ids in list(self.tracks.keys()):
      if ids not in ar_pts:
        self.tracks.pop(ids, None)

    # Update or create tracks
    for ids in ar_pts:
      d_rel, y_rel, v_rel, measured = ar_pts[ids]
      # align v_ego by a fixed time
      v_lead = v_rel + self.v_ego_hist[0]

      if ids not in self.tracks:
        # create new track with initial distance, relative speed
        self.tracks[ids] = Track(ids, d_rel, v_rel, self.radar_ts, self.is_hyundai_interface)

      self.tracks[ids].update(d_rel, y_rel, v_rel, v_lead, measured, self.v_ego_hist[0])

    # publish radarState
    self.radar_state_valid = sm.all_checks() and len(radar_errors) == 0
    self.radar_state = log.RadarState.new_message()
    self.radar_state.mdMonoTime = sm.logMonoTime['modelV2']
    self.radar_state.radarErrors = list(radar_errors)
    self.radar_state.carStateMonoTime = sm.logMonoTime['carState']

    if self.classic_model and len(sm['modelV2'].temporalPose.trans):
      model_v_ego = sm['modelV2'].temporalPose.trans[0]
    elif len(sm['modelV2'].velocity.x):
      model_v_ego = sm['modelV2'].velocity.x[0]
    else:
      model_v_ego = self.v_ego

    leads_v3 = sm['modelV2'].leadsV3
    if len(leads_v3) > 1:
      # filter out corner radar points for lead detection
      forward_radar_tracks = {k: v for k, v in self.tracks.items() if k < 1000}
      self.radar_state.leadOne = get_lead(self.v_ego, self.ready, forward_radar_tracks,
                                          leads_v3[0], model_v_ego, sm['modelV2'],
                                          self.frogpilot_toggles, sm['frogpilotCarState'],
                                          low_speed_override=True)
      self.radar_state.leadTwo = get_lead(self.v_ego, self.ready, forward_radar_tracks,
                                          leads_v3[1], model_v_ego, sm['modelV2'],
                                          self.frogpilot_toggles, sm['frogpilotCarState'],
                                          low_speed_override=False)

    if self.frogpilot_toggles.adjacent_lead_tracking and self.ready:
      self.radar_state.leadLeft = get_adjacent_lead(self.tracks, sm['modelV2'],
                                                    sm['carState'].standstill, left=True)
      self.radar_state.leadLeftFar = get_adjacent_lead(self.tracks, sm['modelV2'],
                                                       sm['carState'].standstill, left=True, far=True)
      self.radar_state.leadRight = get_adjacent_lead(self.tracks, sm['modelV2'],
                                                     sm['carState'].standstill, left=False)
      self.radar_state.leadRightFar = get_adjacent_lead(self.tracks, sm['modelV2'],
                                                        sm['carState'].standstill, left=False, far=True)

    # Check forward blindspots
    self.left_forward_blindspot = get_forward_blindspot(self.tracks, left=True)
    self.right_forward_blindspot = get_forward_blindspot(self.tracks, left=False)

    if sm['frogpilotPlan'].togglesUpdated:
      self.frogpilot_toggles = get_frogpilot_toggles()

  def publish(self, pm: messaging.PubMaster, lag_ms: float):
    assert self.radar_state is not None

    radar_msg = messaging.new_message("radarState")
    radar_msg.valid = self.radar_state_valid
    radar_msg.radarState = self.radar_state
    radar_msg.radarState.cumLagMs = lag_ms
    radar_msg.radarState.leftForwardBlindspot = self.left_forward_blindspot
    radar_msg.radarState.rightForwardBlindspot = self.right_forward_blindspot

    pm.send("radarState", radar_msg)

    # publish tracks for UI debugging
    tracks_msg = messaging.new_message('liveTracks', len(self.tracks))
    tracks_msg.valid = self.radar_state_valid
    for index, tid in enumerate(sorted(self.tracks.keys())):
      radar_type = "main"
      if tid >= 1000:
        if tid < 2000:
          radar_type = "rear_left"
        elif tid < 3000:
          radar_type = "rear_right"
        elif tid < 4000:
          radar_type = "front_left"
        else:
          radar_type = "front_right"

      t = self.tracks[tid]
      tracks_msg.liveTracks[index] = {
        "trackId": tid,
        "dRel": float(t.dRel_K),   # filtered
        "yRel": float(t.yRel),
        "vRel": float(t.calculated_vRel),   # Use calculated (derived or KF) relative speed
        "aRel": float(t.aLeadK),
        "measured": bool(t.measured),
        "isCornerRadar": tid >= 1000,
        "radarType": radar_type,
      }
    pm.send('liveTracks', tracks_msg)

  def update_radardless(self, rr):
    # unchanged
    radar_points = []
    radar_errors = []
    if rr is not None:
      radar_points = rr.points
      radar_errors = rr.errors

    self.radar_tracks_valid = len(radar_errors) == 0
    self.points = {}
    for pt in radar_points:
      self.points[pt.trackId] = (pt.dRel, pt.yRel, pt.vRel)

  def publish_radardless(self):
    # unchanged
    tracks_msg = messaging.new_message('liveTracks', len(self.points))
    tracks_msg.valid = self.radar_tracks_valid
    for index, tid in enumerate(sorted(self.points.keys())):
      tracks_msg.liveTracks[index] = {
        "trackId": tid,
        "dRel": float(self.points[tid][0]) + RADAR_TO_CAMERA,
        "yRel": -float(self.points[tid][1]),
        "vRel": float(self.points[tid][2]),
      }
    return tracks_msg

# ---------------------------------------------------------------------------
# TTC helper
# ---------------------------------------------------------------------------


def safe_ttc(d_rel: float, v_rel: float, ttc_max: float = 30.0) -> float:
  """Return a finite, clipped Time‑To‑Collision.

  If the relative speed is not closing (v_rel >= -0.1 m/s) or inputs are not
  finite, returns ``float('inf')``.  Otherwise ``d_rel / -v_rel`` is computed
  and clipped to ``[0, ttc_max]`` seconds to avoid pathological large values.
  """

  if not (math.isfinite(d_rel) and math.isfinite(v_rel)):
    return float('inf')

  # Only consider closing targets
  if v_rel >= -0.1:  # not closing or moving away
    return float('inf')

  ttc = d_rel / -v_rel
  return float(min(max(ttc, 0.0), ttc_max))

def main():
  config_realtime_process(5, Priority.CTRL_LOW)
  cloudlog.info("radard is waiting for CarParams")
  with car.CarParams.from_bytes(Params().get("CarParams", block=True)) as msg:
    CP = msg
  cloudlog.info("radard got CarParams")

  cloudlog.info("radard is importing %s", CP.carName)
  RadarInterface = importlib.import_module(f'selfdrive.car.{CP.carName}.radar_interface').RadarInterface
  # Check if the imported interface is the specific Hyundai one
  is_hyundai_interface = RadarInterface.__module__ == 'selfdrive.car.hyundai.radar_interface'
  cloudlog.info(f"radard: Using Hyundai interface specific logic: {is_hyundai_interface}")

  can_sock = messaging.sub_sock('can')
  RI = RadarInterface(CP)
  rk = Ratekeeper(1.0 / CP.radarTimeStep, print_delay_threshold=0.1)

  frogpilot_toggles = get_frogpilot_toggles()
  # Pass the flag to the RadarD constructor
  RD = RadarD(frogpilot_toggles, CP.radarTimeStep, RI.delay, is_hyundai_interface)

  if not frogpilot_toggles.radarless_model:
    sm = messaging.SubMaster(['modelV2', 'carState', 'frogpilotCarState', 'frogpilotPlan'],
                             frequency=int(1./DT_CTRL))
    pm = messaging.PubMaster(['radarState', 'liveTracks'])
    while True:
      can_strings = messaging.drain_sock_raw(can_sock, wait_for_one=True)
      rr = RI.update(can_strings)
      sm.update(0)
      if rr is None:
        continue
      RD.update(sm, rr)
      RD.publish(pm, -rk.remaining*1000.0)
      rk.monitor_time()
  else:
    pub_sock = messaging.pub_sock('liveTracks')
    while True:
      can_strings = messaging.drain_sock_raw(can_sock, wait_for_one=True)
      rr = RI.update(can_strings)
      if rr is None:
        continue
      RD.update_radardless(rr)
      msg = RD.publish_radardless()
      pub_sock.send(msg.to_bytes())
      rk.monitor_time()

if __name__ == "__main__":
  main()
