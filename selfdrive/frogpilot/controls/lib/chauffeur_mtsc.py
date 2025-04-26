# PFEIFER - MTSC - Modified by FrogAi for FrogPilot
# CHAUFFEUR MTSC - Refactored to use mapd_py for path and curvature data

import json
import math
import numpy as np
from shapely.geometry import LineString, Point

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
        self.map_reader = reader.MapReader()
        self.params = Params()
        self.params_memory = Params("/dev/shm/params")

        # State variables
        self.current_segment_id = None     # int: ID of the current segment
        self.current_segment_data = None   # dict: Data for the current segment
        self.current_on_way_result = None  # matcher.OnWayResult: Result of on_way check
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
        # Clear state if GPS is invalid
        self.last_gps_pos = None
        self.current_segment_id = None
        self.current_segment_data = None
        self.current_on_way_result = None
        self.curvature_valid = False
        return None

    def _update_current_segment(self, pos: matcher.Position):
        """
        Gets the current road segment data using the MapReader and performs on_way check.
        Updates self.current_segment_id, self.current_segment_data, self.current_on_way_result.
        Returns True if a valid segment is found and the vehicle is considered on it, False otherwise.
        """
        try:
            # Use MapReader to find the closest segment data first
            segment_data = self.map_reader.get_segment_data_at(pos.latitude, pos.longitude)

            if not segment_data:
                # No segment found nearby by the reader
                self.current_segment_id = None
                self.current_segment_data = None
                self.current_on_way_result = None
                self.curvature_valid = False
                return False

            segment_id = segment_data.get('id')
            if not segment_id:
                # Should not happen if reader returns valid data, but check anyway
                self.current_segment_id = None
                self.current_segment_data = None
                self.current_on_way_result = None
                self.curvature_valid = False
                return False

            # Now perform the detailed on_way check using the matcher
            on_way_result = matcher.on_way(pos, segment_id, segment_data)

            if on_way_result.on_way:
                # Successfully found segment and we are on it
                self.current_segment_id = segment_id
                self.current_segment_data = segment_data
                self.current_on_way_result = on_way_result
                # Curvature validity will be checked later in profile calculation
                return True
            else:
                # Segment found, but on_way check failed (e.g., too far, wrong direction on oneway)
                self.current_segment_id = None # Treat as not being on a valid segment
                self.current_segment_data = None
                self.current_on_way_result = None
                self.curvature_valid = False
                return False

        except Exception as e:
            print(f"MTSC: Error getting/checking segment data: {e}")
            self.current_segment_id = None
            self.current_segment_data = None
            self.current_on_way_result = None
            self.curvature_valid = False
            return False

    # Helper function to calculate segment length (extracted and simplified from matcher)
    def _calculate_segment_length(self, segment_data: dict, is_fwd: bool) -> float:
        """ Calculates the approximate length of a map segment in meters. """
        coords = matcher._get_coords_from_segment(segment_data)
        num_nodes = len(coords)
        if num_nodes < 2:
            return 0.0

        total_length = 0.0
        # Iterate through node pairs to sum segment lengths
        # No need to consider is_fwd here, length is the same
        last_lat_rad = coords[0][0] * geometry.TO_RADIANS
        last_lon_rad = coords[0][1] * geometry.TO_RADIANS
        for i in range(1, num_nodes):
             curr_lat, curr_lon = coords[i]
             curr_lat_rad = curr_lat * geometry.TO_RADIANS
             curr_lon_rad = curr_lon * geometry.TO_RADIANS
             total_length += geometry.distance_to_point(last_lat_rad, last_lon_rad, curr_lat_rad, curr_lon_rad)
             last_lat_rad = curr_lat_rad
             last_lon_rad = curr_lon_rad
        return total_length

    # --- meters-true projection ----------------------------------------------
    def _project_along_segment_m(self, pos: matcher.Position) -> float:
        """
        Return distance [m] from segment start to the orthogonal projection of 'pos'.
        Requires self.current_segment_data to be valid.
        """
        if not self.current_segment_data or 'geom' not in self.current_segment_data:
            return 0.0
        coords = list(self.current_segment_data['geom'].coords)
        if len(coords) < 2:
            return 0.0

        # Find the node pair that straddles the projected point
        min_dist_sq = float('inf') # Use squared distance for comparison efficiency
        best_i = 0
        pos_lat_rad = pos.latitude * geometry.TO_RADIANS
        pos_lon_rad = pos.longitude * geometry.TO_RADIANS

        for i in range(len(coords) - 1):
            p0_lon, p0_lat = coords[i]
            p1_lon, p1_lat = coords[i + 1]
            p0_lat_rad, p0_lon_rad = p0_lat * geometry.TO_RADIANS, p0_lon * geometry.TO_RADIANS
            p1_lat_rad, p1_lon_rad = p1_lat * geometry.TO_RADIANS, p1_lon * geometry.TO_RADIANS

            # Quick check: Check if longitude is within bounds (approximate)
            # Adding a small buffer for floating point comparisons
            lon_buffer = 1e-6
            if not (min(p0_lon, p1_lon) - lon_buffer <= pos.longitude <= max(p0_lon, p1_lon) + lon_buffer):
                continue
            # Quick check: Check if latitude is within bounds (approximate)
            lat_buffer = 1e-6
            if not (min(p0_lat, p1_lat) - lat_buffer <= pos.latitude <= max(p0_lat, p1_lat) + lat_buffer):
                 continue

            # Calculate cross-track error (distance from point to line segment)
            # Use squared distance to avoid sqrt for comparison
            dist_sq = geometry.cross_track_error_squared(
                p0_lat_rad, p0_lon_rad,
                p1_lat_rad, p1_lon_rad,
                pos_lat_rad, pos_lon_rad)

            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                best_i = i

        # Sum metres up to best_i
        meters = 0.0
        for j in range(best_i):
            p_j0_lon, p_j0_lat = coords[j]
            p_j1_lon, p_j1_lat = coords[j + 1]
            meters += geometry.distance_to_point(
                p_j0_lat * geometry.TO_RADIANS, p_j0_lon * geometry.TO_RADIANS,
                p_j1_lat * geometry.TO_RADIANS, p_j1_lon * geometry.TO_RADIANS)

        # Add fractional distance along the best segment (best_i to best_i+1)
        p0_lon, p0_lat = coords[best_i]
        p1_lon, p1_lat = coords[best_i + 1]
        seg_len = geometry.distance_to_point(
            p0_lat * geometry.TO_RADIANS, p0_lon * geometry.TO_RADIANS,
            p1_lat * geometry.TO_RADIANS, p1_lon * geometry.TO_RADIANS)

        if seg_len > 1e-3: # Avoid division by zero/tiny segments
            frac = geometry.fraction_along_segment(
                p0_lat, p0_lon, p1_lat, p1_lon, pos.latitude, pos.longitude)
            # Clamp frac to [0, 1] as projection might slightly exceed segment bounds
            frac = clip(frac, 0.0, 1.0)
            meters += frac * seg_len
        # else: segment is too short, don't add fractional component

        return meters
    # --- end meters-true projection ------------------------------------------

    def _calculate_speed_profile_from_segment(self, pos: matcher.Position, v_ego: float, turn_aggressiveness: float):
        """
        Calculates a speed profile based on the geometry (and later, curvature)
        of the current road segment.
        """
        # Requires valid current_segment_data and current_on_way_result from _update_current_segment
        if not self.current_segment_data or not self.current_on_way_result or 'geom' not in self.current_segment_data:
            self.curvature_valid = False # Ensure flag is cleared
            return np.array([]), np.array([])

        segment_geom = self.current_segment_data['geom'] # Shapely LineString
        if not isinstance(segment_geom, LineString) or len(segment_geom.coords) < 3:
            self.curvature_valid = False
            return np.array([]), np.array([]) # Need at least 3 points for curvature

        # Extract coordinates in degrees (Shapely coords are lon, lat)
        coords_lon_lat = list(segment_geom.coords)
        path_nodes_lon = [c[0] for c in coords_lon_lat]
        path_nodes_lat = [c[1] for c in coords_lon_lat]

        # Use pre-calculated curvatures if available
        curvatures = self.current_segment_data.get('curvatures', [])

        if not curvatures:
            self.curvature_valid = False
            return np.array([]), np.array([])

        # Calculate distances along the segment corresponding to curvature points
        # Curvature[i] corresponds to the curve defined by nodes i, i+1, i+2
        # We need cumulative distance up to the *start* of the curve (point i+1).
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

        # --- Add Strategic Deceleration Backward Pass ---
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

        self.curvature_valid = True # Mark as valid since we processed curvatures

        # Now, find where the car is along this segment's profile using metres
        # current_point = Point(pos.longitude, pos.latitude) # No longer needed
        # car_dist_along_segment = segment_geom.project(current_point) # WRONG UNITS!
        car_dist_along_segment = self._project_along_segment_m(pos) # Correct units

        # Shift the distance profile so that the car's position is at distance 0
        distance_profile_shifted = distance_points - car_dist_along_segment

        # --- Generate profile matching VTSC/Planner output format --- # REMOVED v_ego based interpolation
        # Target distances ahead based on current speed and profile times
        # lookahead_distances = np.array(PROFILE_TIMES) * v_ego # REMOVED - VTSC uses its own kinematic projection

        # Ensure distance_profile_shifted covers the range needed for interpolation
        interp_distances = distance_profile_shifted
        interp_speeds = speed_points

        if len(interp_distances) == 0:
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
        # elif len(unique_distances) < 2: # Let VTSC handle interpolation even with 1 point
        #     # Only one point, use constant speed
        #     final_speeds = np.full(PROFILE_LENGTH, speed_points_unique[0])
        # else:
        #     # Interpolate speeds at the desired lookahead distances
        #     # Use bounds_error=False and fill_value=(first_speed, last_speed) for extrapolation
        #     first_speed = speed_points_unique[0]
        #     last_speed = speed_points_unique[-1]
        #     final_speeds = np.interp(lookahead_distances, unique_distances, speed_points_unique,
        #                              left=first_speed, right=last_speed)

        # Final distance profile corresponds to PROFILE_TIMES * v_ego # REMOVED
        # final_distances = lookahead_distances # REMOVED

        # Return the raw distance/speed profile for VTSC to interpolate
        # print(f"MTSC: Generated raw profile: {len(unique_distances)} dist, {len(speed_points_unique)} speed") # Debug
        return unique_distances, speed_points_unique
        # --- End REMOVED v_ego interpolation ---

    def update(self, v_ego, a_ego, frogpilot_toggles, turn_aggressiveness=1.0) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
        """
        Main update loop for Chauffeur MTSC.
        Reads GPS, finds current road segment, calculates curvature-based speed profile,
        determines upcoming speed limit, and publishes the tagged speed limits.
        """
        # Get current GPS position
        pos = self._get_current_position()
        if pos is None:
            # If GPS is lost, clear published speed limits and internal state
            self.params_memory.put_float("MapSpeedLimit", 0.0)
            self.params_memory.put("NextMapSpeedLimit", "{}")
            # Reset profiles
            self.distance_profile = np.array([])
            self.speed_profile = np.array([])
            return None, None # Return None to indicate invalid state

        # Find the current road segment and check if we are on it
        is_on_segment = self._update_current_segment(pos)

        # Initialize limits
        current_limit_mps = 0.0
        next_limit_info = {} # Default to empty dict

        if is_on_segment:
            # --- Current Speed Limit ---
            try:
                current_limit_mps = self.current_segment_data.get('speed_mps', 0.0)
            except Exception as e:
                print(f"MTSC: Error reading speed limit from current segment data: {e}")
                current_limit_mps = 0.0

            # --- Next Speed Limit Logic ---
            try:
                # Construct CurrentWayResult needed by get_next_ways
                current_way_res = matcher.CurrentWayResult(
                    segment_id=self.current_segment_id,
                    on_way_result=self.current_on_way_result
                )

                # Get sequence of next way segments
                next_ways_results = matcher.get_next_ways(pos, current_way_res, self.map_reader)

                if next_ways_results:
                    # Calculate distance remaining on the current segment first
                    dist_to_end_current = matcher.distance_to_end_of_way(
                        pos, self.current_segment_data, self.current_on_way_result
                    )
                    cumulative_dist_to_next_start = dist_to_end_current

                    # Iterate through the predicted next segments
                    for i, next_way in enumerate(next_ways_results):
                        next_segment_id = next_way.segment_id
                        next_is_fwd = next_way.is_forward

                        # Fetch data for this next segment
                        next_segment_data = self.map_reader.segments_data.get(next_segment_id)
                        if not next_segment_data:
                            # print(f"Warning: Data for next segment {next_segment_id} not found.")
                            continue # Skip if data isn't loaded for some reason

                        next_limit_mps = next_segment_data.get('speed_mps', 0.0)

                        # Check for speed limit change (allow for small float differences)
                        if abs(next_limit_mps - current_limit_mps) > 0.1:
                            # Found the segment where the speed limit changes
                            # Get coordinates of the start of this segment
                            start_coord, _ = matcher.get_way_start_end(next_segment_data, next_is_fwd)

                            if start_coord:
                                next_limit_info = {
                                    'speedlimit': float(next_limit_mps),
                                    'latitude': float(start_coord[0]),
                                    'longitude': float(start_coord[1]),
                                    'distance': float(cumulative_dist_to_next_start)
                                }
                            break # Stop searching once the first change is found

                        # If limit hasn't changed, add the length of this segment to the cumulative distance
                        # This segment's length will contribute to the distance *to the start* of the *following* segment
                        segment_len = self._calculate_segment_length(next_segment_data, next_is_fwd)
                        cumulative_dist_to_next_start += segment_len

            except Exception as e:
                print(f"MTSC: Error calculating next speed limit: {e}")
                next_limit_info = {} # Reset on error

        else:
            # Not on a segment, ensure current limit is 0
            current_limit_mps = 0.0
            next_limit_info = {}


        # Publish the found limits (or defaults)
        # print(f"MTSC: Publishing MapSpeedLimit = {current_limit_mps:.2f}, Next: {next_limit_info}") # Debug
        self.params_memory.put_float("MapSpeedLimit", float(current_limit_mps))
        self.params_memory.put("NextMapSpeedLimit", json.dumps(next_limit_info))
        # --- End Speed Limit Publishing ---

        # --- Curvature-Based Speed Profile Calculation ---
        if is_on_segment:
            # Calculate profile based on current segment's geometry
            self.distance_profile, self.speed_profile = self._calculate_speed_profile_from_segment(
                pos, v_ego, turn_aggressiveness
            )
            # self.curvature_valid is set within _calculate_speed_profile_from_segment
        else:
            # No segment or not on segment, clear profile
            self.distance_profile = np.array([])
            self.speed_profile = np.array([])
            self.curvature_valid = False

        # Return the calculated profiles (or empty if invalid/not on segment)
        if is_on_segment and self.curvature_valid:
            return self.distance_profile, self.speed_profile
        else:
            # Return None, None if we aren't on a segment or curvature is invalid
            # This signals to VTSC or other consumers that the profile is not usable
            return None, None

# --- Old code removed ---
# TARGET_JERK, TARGET_ACCEL, TARGET_OFFSET
