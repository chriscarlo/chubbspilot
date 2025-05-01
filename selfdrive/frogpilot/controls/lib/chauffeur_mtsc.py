# PFEIFER - MTSC - Modified by FrogAi for FrogPilot
# CHAUFFEUR MTSC - Refactored to use mapd_py for path and curvature data

# import json # Removed
import math
import numpy as np
# from shapely.geometry import LineString, Point # Removed
import threading, time
from collections import deque

# --- Add cereal message import ---
import cereal.messaging as messaging
from cereal import log
# ---------------------------------

from openpilot.common.conversions import Conversions as CV
from openpilot.common.params import Params
from openpilot.common.numpy_fast import clip, interp

# Import new mapd_py components - REMOVED
# from openpilot.selfdrive.frogpilot.navigation.mapd_py import reader
# from openpilot.selfdrive.frogpilot.navigation.mapd_py import geometry
# from openpilot.selfdrive.frogpilot.navigation.mapd_py import matcher

# Define lookahead distance (can be tuned)
LOOKAHEAD_DISTANCE = 500.0 # Meters, similar to MIN_WAY_DIST_M

# Define desired output profile length or resolution
# This should align with what VTSC expects
# Example: Match VTSC's 33 points over ModelConstants.T_IDXS
from openpilot.selfdrive.modeld.constants import ModelConstants
PROFILE_TIMES = list(ModelConstants.T_IDXS[:33])
PROFILE_LENGTH = len(PROFILE_TIMES)

# --- New Constants for Threading ---
PROFILE_RATE_HZ = 2.0          # worker frequency – >500 m still fine
CACHE_LEN        = 2           # keep last 2 profiles
# --- End New Constants ---

# --- New Constant for Curvature Unit Correction ---
MS_TO_MPH = CV.MS_TO_MPH
CURV_CORR = MS_TO_MPH ** 2 # Correction factor (MPH^2 / MS^2) ≈ 5.0
# --- End New Constant ---

# --- New Constant for MTSC Activation Threshold ---
MIN_ENABLE_KAPPA = 8e-4 # Minimum curvature (1/radius) to enable MTSC profile (1/1250 m)
# --- End New Constant ---

# --- New Function: Target Lateral Accel based on Curvature (Decreasing Sigmoid) ---
def curvature_based_lat_accel(abs_curvature: float) -> float:
    """
    Determines target lateral acceleration based on curvature using a tuned decreasing sigmoid.
    Targets high acceleration (3.2 m/s^2) for gentle curves (low curvature / high speed).
    Smoothly decreases towards a lower acceleration (1.5 m/s^2) for very sharp curves
    (high curvature / low speed), approximating low-speed torque/comfort limits.
    """
    # Target lateral acceleration range
    high_accel = 3.2  # Target accel for gentle/moderate curves (kappa -> 0)
    low_accel = 1.5   # Target accel limit for very sharp curves (kappa -> high)
    span = high_accel - low_accel # The range of reduction (1.7 m/s^2)

    # Sigmoid parameters tuned to approximate:
    # - lat_accel ~ 3.1-3.2 for kappa ~ 0
    # - lat_accel ~ 2.0 for kappa ~ 0.02 (equiv. ~10 m/s)
    # - lat_accel ~ 1.5 for kappa ~ 0.06 (equiv. ~5 m/s)
    center_curvature = 0.018 # Center the transition slightly below kappa=0.02
    k = 180                  # Gain to control the transition sharpness

    # Calculate the decreasing sigmoid value:
    reduction = span / (1.0 + math.exp(-k * (abs_curvature - center_curvature)))
    lat_acc = high_accel - reduction

    # Ensure the value stays within the intended bounds [low_accel, high_accel]
    return clip(lat_acc, low_accel, high_accel)
# --- End New Function ---

class ChauffeurMtsc:
    def __init__(self):
        # self.map_reader = reader.MapReader() # Removed
        self.params = Params()
        # self.params_memory = Params("/dev/shm/params") # Removed - mapd handles legacy params
        self.sm = messaging.SubMaster(['liveMapData', 'carState']) # Added liveMapData

        # State variables - REMOVED
        # self.current_segment_id = None     # int: ID of the current segment
        # self.current_segment_data = None   # dict: Data for the current segment
        # self.current_on_way_result = None  # matcher.OnWayResult: Result of on_way check
        # self.last_gps_pos = None

        # Cached speed profile
        # self.distance_profile = np.array([], dtype=np.float64) # Replaced by queue
        # self.speed_profile = np.array([], dtype=np.float64)   # Replaced by queue
        # self.curvature_valid = False # Flag if curvature data is usable # Now handled implicitly by queue state

        # --- Threading components ---
        self.profile_lock = threading.Lock()
        self.profile_queue: deque[tuple[np.ndarray, np.ndarray]] = deque(maxlen=CACHE_LEN)
        self.last_worker_ts = 0.0
        self.worker_running = True
        # Shared variable for latest cruise speed (m/s) provided by FrogPilotVCruise
        self._latest_v_cruise_cluster = 50.0  # default fallback
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()
        # --- End Threading components ---

    # --- REMOVED HELPER FUNCTIONS --- #
    # def _get_current_position(self): ...
    # def _update_current_segment(self, pos: matcher.Position): ...
    # def _calculate_segment_length(self, segment_data: dict, is_fwd: bool) -> float: ...
    # def _project_along_segment_m(self, pos: matcher.Position) -> float: ...
    # --- END REMOVED HELPER FUNCTIONS --- #

    # Renamed and Refactored function to use LiveMapData
    def _build_speed_profile_from_mapdata(self, map_data: log.LiveMapData, v_cruise_cluster: float):
        """
        Calculates a speed profile based on the curvature data provided in LiveMapData.
        Clamps speeds to v_cruise_cluster.
        THIS IS THE HEAVY WORK DONE BY THE WORKER THREAD.
        """
        # self.curvature_valid = False # Assume invalid initially # No longer needed here

        if not map_data.curvatureDataValid:
            return np.array([]), np.array([])

        # Extract data from current and next segments
        current_segment = map_data.currentSegment
        next_segments = map_data.nextSegments

        all_distances = []
        all_speeds = []

        # --- Process Current Segment --- #
        if current_segment.segmentId != 0 and current_segment.curvatureDerivedSpeedsMps:
            # Adjust distances relative to the car's current position
            current_distances = np.array(current_segment.distancesForSpeeds)
            relative_distances = current_distances - current_segment.distanceAlongSegment
            current_speeds = np.array(current_segment.curvatureDerivedSpeedsMps)

            # Only keep points ahead of the car
            valid_idx = relative_distances >= -1e-3 # Allow for small negative due to float precision
            if np.any(valid_idx):
                 all_distances.extend(relative_distances[valid_idx])
                 all_speeds.extend(current_speeds[valid_idx])

        # --- Process Next Segments --- #
        for next_seg in next_segments:
             if next_seg.segmentId != 0 and next_seg.curvatureDerivedSpeedsMps:
                  # Distances are relative to the start of the *next* segment.
                  # Add the distance *to* the start of this next segment.
                  next_distances = np.array(next_seg.distancesForSpeeds)
                  relative_distances = next_distances + next_seg.distanceToStart
                  next_speeds = np.array(next_seg.curvatureDerivedSpeedsMps)

                  all_distances.extend(relative_distances)
                  all_speeds.extend(next_speeds)

        if not all_distances:
            return np.array([]), np.array([]) # No valid points found

        distance_points = np.array(all_distances)
        speed_points = np.array(all_speeds)

        # --- Sort by distance (ensure monotonicity) --- #
        # This is crucial as segments might be processed slightly out of order
        # or points might overlap at segment boundaries.
        if len(distance_points) > 1:
            sort_indices = np.argsort(distance_points)
            distance_points = distance_points[sort_indices]
            speed_points = speed_points[sort_indices]

            # Remove duplicate distances which can break interpolation
            unique_distances, unique_indices = np.unique(distance_points, return_index=True)
            # Keep only unique points based on distance, select corresponding speeds
            if len(unique_distances) < len(distance_points):
                distance_points = unique_distances
                speed_points = speed_points[unique_indices]

        if len(distance_points) == 0:
            return np.array([]), np.array([])

        # --- Add Strategic Deceleration Backward Pass (remains the same) ---
        if len(speed_points) > 1:
            STRATEGIC_DECEL = 1.2  # m/s^2, comfortable early deceleration rate (was 1.5)
            for i in range(len(speed_points) - 2, -1, -1):
                dist = distance_points[i+1] - distance_points[i]
                if dist < 1e-3: # Avoid issues with zero/tiny distance
                    # If distance is negligible, speed should ideally be the same or lower
                    speed_points[i] = min(speed_points[i], speed_points[i+1])
                    continue

                # Calculate max feasible speed at i to reach speed_points[i+1] decelerating at STRATEGIC_DECEL
                # v_i = sqrt(v_{i+1}^2 + 2 * a * d)
                try:
                    required_speed_sq = speed_points[i+1]**2 + 2 * STRATEGIC_DECEL * dist
                    # Ensure we don't take sqrt of negative if speed_points[i+1] somehow became negative (shouldn't happen)
                    if required_speed_sq < 0: required_speed_sq = 0
                    max_feasible_speed = math.sqrt(required_speed_sq)
                    speed_points[i] = min(speed_points[i], max_feasible_speed)
                except ValueError: # Catch potential math domain errors, though unlikely
                    # If error, default to the more conservative speed (the next point's speed)
                    speed_points[i] = min(speed_points[i], speed_points[i+1])
        # --- End Strategic Deceleration Backward Pass ---

        # --- Clamp speed profile to v_cruise_cluster ---
        speed_points = np.minimum(speed_points, v_cruise_cluster)
        # --- End Clamping ---

        # Mark as valid since we successfully processed map data
        # self.curvature_valid = True # No longer needed here

        # Return the raw distance/speed profile for VTSC to interpolate
        # Note: distance_points are already relative to the car's position
        return distance_points, speed_points

    # --- NEW WORKER THREAD LOGIC ---
    def _worker_loop(self):
      """Background thread: builds speed profiles at PROFILE_RATE_HZ."""
      while self.worker_running:
        start = time.monotonic()
        self.sm.update(0)                       # non-blocking
        if self.sm.updated['liveMapData'] and self.sm.valid['liveMapData']:
          # Heavy lifting **once**, outside controls thread
          # Use the latest cruise speed passed in from the controls thread whenever available,
          # otherwise fall back to the instantaneous ego speed so we still have *some* clamp.
          fallback_speed = float(self.sm['carState'].vEgo) if self.sm.valid['carState'] else 50.0
          v_cruise_for_clamp = self._latest_v_cruise_cluster if self._latest_v_cruise_cluster > 0 else fallback_speed

          dist, spd = self._build_speed_profile_from_mapdata(
                        self.sm['liveMapData'],
                        v_cruise_cluster = v_cruise_for_clamp)
          with self.profile_lock:
            self.profile_queue.append((dist, spd))
        # sleep until next tick
        dt = 1/PROFILE_RATE_HZ - (time.monotonic() - start)
        if dt > 0:
          time.sleep(dt)
    # --- END NEW WORKER THREAD LOGIC ---

    # --- NEW PROFILE GETTER ---
    def get_latest_profile(self):
      with self.profile_lock:
        return self.profile_queue[-1] if self.profile_queue else (None, None)
    # --- END NEW PROFILE GETTER ---

    # --- REPLACED UPDATE METHOD ---
    def update(self, v_ego, a_ego, v_cruise_cluster, frogpilot_toggles):
      """
      Lightweight wrapper called from FrogPilotVCruise at 20 Hz.
      It never does heavy work: just delivers the newest profile.
      """
      # Cache the latest cruise speed so the worker thread can clamp its profile correctly.
      if v_cruise_cluster is not None and v_cruise_cluster > 0:
          self._latest_v_cruise_cluster = float(v_cruise_cluster)

      return self.get_latest_profile()
    # --- END REPLACED UPDATE METHOD ---

    # --- NEW SHUTDOWN METHOD ---
    def shutdown(self):
      self.worker_running = False
      # Optional: join the thread if immediate cleanup is critical
      # self.worker.join()
    # --- END NEW SHUTDOWN METHOD ---

    # --- NEW DESTRUCTOR ---
    def __del__(self):
      self.shutdown()
    # --- END NEW DESTRUCTOR ---

