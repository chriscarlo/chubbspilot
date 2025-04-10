# PFEIFER - MTSC - Modified by FrogAi for FrogPilot
# CHAUFFEUR MTSC - Refactored to use mapd_py for path and curvature data

import json
import math
import numpy as np

from openpilot.common.conversions import Conversions as CV
from openpilot.common.params import Params
from openpilot.common.numpy_fast import clip, interp

# Import new mapd_py components
from openpilot.selfdrive.frogpilot.navigation.mapd_py import reader
from openpilot.selfdrive.frogpilot.navigation.mapd_py import geometry
from openpilot.selfdrive.frogpilot.navigation.mapd_py import matcher

# Import VTSC's lat accel function for consistency
# (Alternatively, define it in a shared location)
try:
    from openpilot.selfdrive.frogpilot.controls.lib.chauffeur_vtsc import nonlinear_lat_accel
except ImportError:
    # Fallback or define locally if VTSC isn't available/refactored yet
    print("Warning: Could not import nonlinear_lat_accel from chauffeur_vtsc. Using local definition.")
    def nonlinear_lat_accel(v_ego_ms: float, turn_aggressiveness: float = 1.0) -> float:
        v_ego_mph = v_ego_ms * CV.MS_TO_MPH
        base = 2.0
        span = 1.8
        center = 20.0
        k = 0.15
        lat_acc = base + span / (1 + math.exp(-k * (v_ego_mph - center)))
        lat_acc = min(lat_acc, 3.2)
        return lat_acc * turn_aggressiveness

# Define lookahead distance (can be tuned)
LOOKAHEAD_DISTANCE = 500.0 # Meters, similar to MIN_WAY_DIST_M

# Define desired output profile length or resolution
# This should align with what VTSC expects
# Example: Match VTSC's 33 points over ModelConstants.T_IDXS
from openpilot.selfdrive.modeld.constants import ModelConstants
PROFILE_TIMES = list(ModelConstants.T_IDXS[:33])
PROFILE_LENGTH = len(PROFILE_TIMES)

# --- New Function: Target Lateral Accel based on Curvature ---
def curvature_based_lat_accel(abs_curvature: float) -> float:
    """
    Determines the target lateral acceleration based on curvature.
    Targets 3.02 m/s^2 for very gentle curves, ramping up to 3.1 m/s^2 for sharper curves.
    """
    K_MIN = 0.001  # Curvature threshold for gentle curves (Radius = 1000m)
    A_MIN = 3.02   # Target lat accel for gentle curves

    K_MAX = 0.02   # Curvature threshold for sharp curves (Radius = 50m)
    A_MAX = 3.1    # Target lat accel for sharp curves

    if abs_curvature <= K_MIN:
        # For very gentle curves (>= 1000m radius), use the lower limit
        return A_MIN
    elif abs_curvature >= K_MAX:
        # For sharper curves (<= 50m radius), use the upper limit
        return A_MAX
    else:
        # Linearly interpolate between the min and max thresholds
        ratio = (abs_curvature - K_MIN) / (K_MAX - K_MIN)
        return A_MIN + ratio * (A_MAX - A_MIN)
# --- End New Function ---

class ChauffeurMtsc:
    def __init__(self):
        self.map_reader = reader.MapReader()
        self.params = Params()
        self.params_memory = Params("/dev/shm/params")

        # State variables - Simplified, as path is now just the current segment
        self.current_segment_data = None # Store dict from MapReader
        # self.current_way_result = None # Old
        # self.next_ways = [] # Old
        self.last_gps_pos = None

        # Cached speed profile
        self.distance_profile = np.array([], dtype=np.float64)
        self.speed_profile = np.array([], dtype=np.float64)
        self.curvature_valid = False # Flag if curvature data is usable

    def _get_current_position(self):
        """Safely reads the last GPS position from params_memory."""
        try:
            pos_json = self.params_memory.get("LastGPSPosition", block=False)
            if pos_json:
                pos_data = json.loads(pos_json)
                # Assuming bearing is provided in degrees, convert to radians for internal use
                bearing_deg = pos_data.get('bearing')
                bearing_rad = math.radians(bearing_deg) if bearing_deg is not None else 0.0
                self.last_gps_pos = matcher.Position(
                    latitude=pos_data['latitude'],
                    longitude=pos_data['longitude'],
                    bearing_rad=bearing_rad
                )
                return self.last_gps_pos
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"Error reading or parsing LastGPSPosition: {e}")
        return None

    def _update_current_segment(self, pos: matcher.Position):
        """
        Gets the current road segment data using the new MapReader.
        Updates self.current_segment_data and self.curvature_valid (placeholder).
        Returns True if segment data was found, False otherwise.
        """
        try:
            segment_data = self.map_reader.get_segment_data_at(pos.latitude, pos.longitude)
            if segment_data:
                self.current_segment_data = segment_data
                # print(f"MTSC: Updated current segment ID {segment_data.get('id', 'N/A')}") # Debug
                # TODO: Check if curvature data exists in segment_data once added
                # self.curvature_valid = 'curvatures' in segment_data and len(segment_data['curvatures']) > 0
                self.curvature_valid = False # Placeholder until curvatures are added
                return True
            else:
                self.current_segment_data = None
                self.curvature_valid = False
                return False
        except Exception as e:
            print(f"MTSC: Error getting segment data: {e}")
            self.current_segment_data = None
            self.curvature_valid = False
            return False

    def _calculate_speed_profile_from_segment(self, pos: matcher.Position, v_ego: float, turn_aggressiveness: float):
        """
        Calculates a speed profile based on the geometry (and later, curvature)
        of the current road segment.
        """
        if not self.current_segment_data or 'geom' not in self.current_segment_data:
            return np.array([]), np.array([])

        segment_geom = self.current_segment_data['geom'] # Shapely LineString
        if not isinstance(segment_geom, LineString) or len(segment_geom.coords) < 3:
            return np.array([]), np.array([]) # Need at least 3 points for curvature

        # Extract coordinates in degrees (Shapely coords are lon, lat)
        coords_lon_lat = list(segment_geom.coords)
        path_nodes_lon = [c[0] for c in coords_lon_lat]
        path_nodes_lat = [c[1] for c in coords_lon_lat]

        # Calculate curvatures along the *entire* segment's geometry
        # We will later figure out where the car is along this path
        # TODO: Use pre-calculated curvatures when available in self.current_segment_data
        curvatures = self.current_segment_data.get('curvatures', [])

        if not curvatures:
            self.curvature_valid = False
            return np.array([]), np.array([])

        # Calculate distances along the segment corresponding to curvature points
        # Curvature[i] corresponds to the curve defined by nodes i, i+1, i+2
        # We need cumulative distance up to the *start* of the curve (point i+1).
        # Let's recalculate the segment lengths needed for distances, as arc_lengths isn't stored.
        cumulative_distances = [0.0] * len(curvatures)
        current_dist = 0.0
        # Calculate distance to the start of the first curve (point 1)
        if len(path_nodes_lat) > 1:
             dist_to_pt1 = geometry.distance_to_point(path_nodes_lat[0] * geometry.TO_RADIANS,
                                                      path_nodes_lon[0] * geometry.TO_RADIANS,
                                                      path_nodes_lat[1] * geometry.TO_RADIANS,
                                                      path_nodes_lon[1] * geometry.TO_RADIANS)
             current_dist = dist_to_pt1

        for i in range(len(curvatures)):
             cumulative_distances[i] = current_dist
             # Add length of segment i+1 -> i+2 for next curvature point
             if (i + 2) < len(path_nodes_lat): # Check index exists for point i+2
                  segment_len = geometry.distance_to_point(path_nodes_lat[i+1] * geometry.TO_RADIANS,
                                                          path_nodes_lon[i+1] * geometry.TO_RADIANS,
                                                          path_nodes_lat[i+2] * geometry.TO_RADIANS,
                                                          path_nodes_lon[i+2] * geometry.TO_RADIANS)
                  current_dist += segment_len
             # else: We are at the last curvature point, no more segments to add length from

        # Calculate target speeds based on curvature
        target_speeds = []
        ZERO_CURVATURE_THRESHOLD = 1e-5
        STRAIGHT_SPEED_LIMIT = 70.0 # m/s

        for k in curvatures:
            abs_k = abs(k)
            if abs_k < ZERO_CURVATURE_THRESHOLD:
                target_speed = STRAIGHT_SPEED_LIMIT
            else:
                # Use the original MTSC curvature-based lateral accel logic
                target_lat_accel_base = curvature_based_lat_accel(abs_k)
                target_lat_accel = target_lat_accel_base * turn_aggressiveness
                target_speed = math.sqrt(target_lat_accel / abs_k) if abs_k > 1e-9 else STRAIGHT_SPEED_LIMIT
            target_speeds.append(min(target_speed, STRAIGHT_SPEED_LIMIT))

        distance_points = np.array(cumulative_distances)
        speed_points = np.array(target_speeds)
        self.curvature_valid = True # Mark as valid since we calculated curvatures

        # Now, find where the car is along this segment's profile
        current_point = Point(pos.longitude, pos.latitude)
        # Project the car's position onto the segment geometry
        car_dist_along_segment = segment_geom.project(current_point)

        # Shift the distance profile so that the car's position is at distance 0
        distance_profile_shifted = distance_points - car_dist_along_segment

        # --- Generate profile matching VTSC/Planner output format ---
        # Target distances ahead based on current speed and profile times
        lookahead_distances = np.array(PROFILE_TIMES) * v_ego

        # Ensure distance_profile_shifted covers the range needed for interpolation
        # We need points both before and after the lookahead_distances
        # Add a point at the start (car's projected position) if needed
        interp_distances = distance_profile_shifted
        interp_speeds = speed_points

        if len(interp_distances) == 0:
            # If no curvature points (straight road), return empty profile?
            # Or return profile with high speed? Let's return empty for now.
            self.curvature_valid = False
            return np.array([]), np.array([])

        # Ensure distance_profile_shifted is monotonically increasing for interp
        sort_indices = np.argsort(interp_distances)
        distance_profile_sorted = interp_distances[sort_indices]
        speed_points_sorted = interp_speeds[sort_indices]

        # Remove duplicate distances which can break interpolation
        unique_distances, unique_indices = np.unique(distance_profile_sorted, return_index=True)
        speed_points_unique = speed_points_sorted[unique_indices]

        if len(unique_distances) < 1:
            self.curvature_valid = False
            return np.array([]), np.array([])
        elif len(unique_distances) < 2:
            # Only one point, use constant speed
            final_speeds = np.full(PROFILE_LENGTH, speed_points_unique[0])
        else:
            # Interpolate speeds at the desired lookahead distances
            # Use bounds_error=False and fill_value=(first_speed, last_speed) for extrapolation
            first_speed = speed_points_unique[0]
            last_speed = speed_points_unique[-1]
            final_speeds = np.interp(lookahead_distances, unique_distances, speed_points_unique,
                                     left=first_speed, right=last_speed)

        # Final distance profile corresponds to PROFILE_TIMES * v_ego
        final_distances = lookahead_distances

        # print(f"MTSC: Generated profile: {len(final_distances)} dist, {len(final_speeds)} speed") # Debug
        return final_distances, final_speeds

    def update(self, v_ego, a_ego, frogpilot_toggles, turn_aggressiveness=1.0) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
        """
        Main update loop for Chauffeur MTSC.
        Reads GPS, finds current road segment, calculates curvature-based speed profile,
        and publishes the tagged speed limit.
        """
        # Get current GPS position
        pos = self._get_current_position()
        if pos is None:
            # If GPS is lost, clear published speed limits
            self.params_memory.put_float("MapSpeedLimit", 0.0)
            self.params_memory.put("NextMapSpeedLimit", "{}")
            # Clear internal state as well
            self.current_segment_data = None
            self.curvature_valid = False # Ensure flag is cleared
            self.distance_profile = np.array([])
            self.speed_profile = np.array([])
            return None, None

        # Find the current road segment
        segment_updated = self._update_current_segment(pos)

        # --- Speed Limit Publishing (Using segment data) ---
        current_limit_mps = 0.0
        next_limit_info = {} # Still not implemented

        # TODO: Reimplement logic to find the *next* speed limit change downstream.
        #       The old version iterated through `self.next_ways` (if available)
        #       to find the first way with a different speed limit and its start point.
        #       This will require adapting the logic to work with the current MapReader
        #       approach, potentially involving querying segments further along the path
        #       or enhancing MapReader to provide lookahead data.

        if self.current_segment_data:
            try:
                # Get speed limit from the current segment data
                current_limit_mps = self.current_segment_data.get('speed_mps', 0.0)
                # TODO: Add logic for next speed limit if we enhance the reader later
            except Exception as e:
                print(f"MTSC: Error reading speed limit from segment data: {e}")
                current_limit_mps = 0.0
        else:
             # If no segment found, ensure limit is 0
             current_limit_mps = 0.0

        # Publish the found limits (or defaults)
        # print(f"MTSC: Publishing MapSpeedLimit = {current_limit_mps:.2f}") # Debug
        self.params_memory.put_float("MapSpeedLimit", float(current_limit_mps))
        self.params_memory.put("NextMapSpeedLimit", json.dumps(next_limit_info))
        # --- End Speed Limit Publishing ---

        # --- Curvature-Based Speed Profile Calculation ---
        if self.current_segment_data:
            # Calculate profile based on current segment's geometry
            # Pass v_ego which is needed for the final profile generation
            self.distance_profile, self.speed_profile = self._calculate_speed_profile_from_segment(
                pos, v_ego, turn_aggressiveness
            )
            # self.curvature_valid is set within _calculate_speed_profile_from_segment
        else:
            # No segment, clear profile
            self.distance_profile = np.array([])
            self.speed_profile = np.array([])
            self.curvature_valid = False

        # Return the calculated profiles (or empty if invalid)
        return self.distance_profile, self.speed_profile

# --- Old code removed ---
# TARGET_JERK, TARGET_ACCEL, TARGET_OFFSET
