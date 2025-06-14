# PFEIFER – MTSC – Modified by FrogAi for FrogPilot
# CHAUFFEUR MTSC – Uses liveMapData cereal messages for path and curvature data
#
# Version 2025-05-01a  (queue simplification, freshness fix, error logging)

from __future__ import annotations

import math
import time
import multiprocessing as mp
import queue
from typing import Tuple

import numpy as np
import cereal.messaging as messaging
from cereal import log

from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip
from openpilot.selfdrive.modeld.constants import ModelConstants

# ────────────────  CONSTANTS  ──────────────────────────────────────────────
LOOKAHEAD_DISTANCE = 500.0                    # reserved for future use
PROFILE_TIMES      = list(ModelConstants.T_IDXS[:33])
PROFILE_LENGTH     = len(PROFILE_TIMES)

PROFILE_RATE_HZ    = 2.0                      # worker frequency (Hz)
STRATEGIC_DECEL    = 1.2                      # (m/s²) backward pass
FALLBACK_SPEED     = 50.0                     # (m/s) if cruise unset

# back-compat symbols expected by external code
MS_TO_MPH        = CV.MS_TO_MPH
CURV_CORR        = MS_TO_MPH ** 2
MIN_ENABLE_KAPPA = 8e-4

DEFAULT_CRUISE_MS = 50.0

# ───────────────  HELPER – SIGMOID (kept for API compat)  ────────────────
def curvature_based_lat_accel(abs_curvature: float) -> float:
    """Lat-accel lookup preserved for callers outside this module."""
    high, low, span, center, k = 3.2, 1.5, 1.7, 0.018, 180.0
    reduction = span / (1.0 + math.exp(-k * (abs_curvature - center)))
    return clip(high - reduction, low, high)

# ───────────────  CORE – BUILD PROFILE  ──────────────────────────────────
def build_speed_profile_from_mapdata(
    map_data: log.LiveMapData,
    v_clamp_ms: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert curvature→speed maps into (distance, speed) NumPy arrays.
    Pure function – safe to run in worker process.
    """
    if not map_data.curvatureDataValid:
        return np.array([]), np.array([])

    dists, speeds = [], []

    cur = map_data.currentSegment
    nxts = map_data.nextSegments

    # current segment
    if cur.segmentId and cur.curvatureDerivedSpeedsMps:
        rel_d = np.array(cur.distancesForSpeeds) - cur.distanceAlongSegment
        mask  = rel_d >= -1e-3
        if np.any(mask):
            dists.extend(rel_d[mask])
            speeds.extend(np.array(cur.curvatureDerivedSpeedsMps)[mask])

    # next segments
    for nxt in nxts:
        if nxt.segmentId and nxt.curvatureDerivedSpeedsMps:
            dists.extend(np.array(nxt.distancesForSpeeds) + nxt.distanceToStart)
            speeds.extend(np.array(nxt.curvatureDerivedSpeedsMps))

    if not dists:
        return np.array([]), np.array([])

    dist = np.array(dists, dtype=float)
    spd  = np.array(speeds, dtype=float)

    # sort & deduplicate
    if dist.size > 1:
        idx   = np.argsort(dist)
        dist, spd = dist[idx], spd[idx]
        dist, uidx = np.unique(dist, return_index=True)
        spd  = spd[uidx]

    # backward pass for smooth strategic decel
    for i in range(spd.size - 2, -1, -1):
        d = dist[i + 1] - dist[i]
        if d < 1e-3:
            spd[i] = min(spd[i], spd[i + 1])
            continue
        max_sq = spd[i + 1] ** 2 + 2 * STRATEGIC_DECEL * d
        spd[i] = min(spd[i], math.sqrt(max_sq))

    # clamp to cruise target
    spd = np.minimum(spd, v_clamp_ms)
    return dist, spd

# ───────────────  WORKER PROCESS  ─────────────────────────────────────────
def _worker_main(out_q: mp.Queue, cruise_clamp: mp.Value):
    sm = messaging.SubMaster(['liveMapData', 'carState'])
    while True:
        start = time.monotonic()

        try:
            sm.update(0)

            if sm.updated['liveMapData'] and sm.valid['liveMapData']:
                with cruise_clamp.get_lock():
                    clamp_ms = cruise_clamp.value

                if clamp_ms <= 0.0:
                    clamp_ms = float(sm['carState'].vEgo) if sm.valid['carState'] else FALLBACK_SPEED

                dist, spd = build_speed_profile_from_mapdata(sm['liveMapData'], clamp_ms)

                if dist.size:
                    try:
                        out_q.put_nowait((dist, spd))
                    except queue.Full:
                        # overwrite the single slot with latest data
                        out_q.get_nowait()
                        out_q.put_nowait((dist, spd))

        except Exception as e:
            print(f"ChauffeurMtsc worker exception: {e}")

        # maintain ≈2 Hz cadence
        sleep = 1.0 / PROFILE_RATE_HZ - (time.monotonic() - start)
        if sleep > 0.0:
            time.sleep(sleep)

# ───────────────  PUBLIC CLASS  ───────────────────────────────────────────
class ChauffeurMtsc:
    """
    Multiprocess map-based speed profile generator.
    Public API is identical to the previous threaded version.
    """
    def __init__(self):
        self._cruise = mp.Value('d', DEFAULT_CRUISE_MS)
        self._queue  = mp.Queue(maxsize=1)         # only latest profile
        self._proc   = mp.Process(
            target=_worker_main,
            args=(self._queue, self._cruise),
            daemon=True
        )
        self._proc.start()
        self._latest: Tuple[np.ndarray, np.ndarray] = (None, None)

    # ––– internal ---------------------------------------------------------
    def _drain(self) -> Tuple[np.ndarray, np.ndarray]:
        """Pull newest item if available; otherwise keep previous."""
        try:
            while True:                 # empty queue to get very latest
                self._latest = self._queue.get_nowait()
        except queue.Empty:
            pass
        return self._latest

    # ––– called once per 20 Hz control cycle -----------------------------
    def update(self, v_ego, a_ego, v_cruise_cluster, frogpilot_toggles):
        if v_cruise_cluster and v_cruise_cluster > 0.0:
            with self._cruise.get_lock():
                self._cruise.value = float(v_cruise_cluster)
        return self._drain()

    # ––– called by planners/UI any time -----------------------------------
    def get_latest_profile(self):
        return self._drain()

    # ––– graceful teardown -------------------------------------------------
    def shutdown(self):
        if self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(timeout=1.0)

    def __del__(self):
        self.shutdown()
