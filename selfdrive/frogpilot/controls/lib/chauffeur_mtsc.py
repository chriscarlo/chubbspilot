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

        # State variables for map matching
        self.current_way_result = None
        self.next_ways = []
        self.last_gps_pos = None

        # Cached speed profile
        self.distance_profile = np.array([], dtype=np.float64)
        self.speed_profile = np.array([], dtype=np.float64)

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

    def _update_map_path(self, pos: matcher.Position):
        """Loads map data, finds current way, and determines the path ahead."""
        # Load map data for current position
        offline_data = self.map_reader.load_map_data(pos.latitude, pos.longitude)
        if not offline_data:
            # print("MTSC: No map data loaded.")
            self.current_way_result = None
            self.next_ways = []
            return False

        # Find the current way
        # Pass previous results for continuity
        current_way_candidate = self.current_way_result.way if self.current_way_result else None
        self.current_way_result = matcher.get_current_way(
            current_way_candidate, self.next_ways, offline_data, pos
        )

        if not self.current_way_result:
            # print("MTSC: Could not find current way.")
            self.next_ways = []
            return False

        # Get the sequence of next ways
        self.next_ways = matcher.get_next_ways(pos, self.current_way_result, offline_data)
        # print(f"MTSC: Found {len(self.next_ways)} next ways.") # Debug
        return True

    def _calculate_path_profile(self, pos: matcher.Position, turn_aggressiveness: float):
        """
        Calculates curvature and speed profile along the determined path.
        Now accepts turn_aggressiveness to apply to the curvature-based lat accel.
        """
        if not self.current_way_result or not self.current_way_result.way:
            return np.array([]), np.array([])

        path_nodes_lat = []
        path_nodes_lon = []
        cumulative_distance = 0.0
        distances = [0.0]

        # Start from the projected position on the current way segment
        on_way_res = self.current_way_result.on_way_result
        if not on_way_res or not on_way_res.distance_result:
             return np.array([]), np.array([])

        line_start_node = on_way_res.distance_result.line_start_node
        line_end_node = on_way_res.distance_result.line_end_node
        is_fwd = on_way_res.is_forward

        proj_lat, proj_lon = geometry.point_on_line(
            line_start_node.latitude, line_start_node.longitude,
            line_end_node.latitude, line_end_node.longitude,
            pos.latitude, pos.longitude
        )
        path_nodes_lat.append(proj_lat)
        path_nodes_lon.append(proj_lon)
        last_lat_rad = proj_lat * geometry.TO_RADIANS
        last_lon_rad = proj_lon * geometry.TO_RADIANS

        # Add remaining nodes from the current way
        try:
            nodes, err = self.current_way_result.way.Nodes()
            if not err and nodes:
                start_idx = -1
                for i in range(nodes.Len()): # Find index of the segment's end node
                    node = nodes.At(i)
                    if abs(node.latitude - line_end_node.latitude) < 1e-9 and abs(node.longitude - line_end_node.longitude) < 1e-9:
                        start_idx = i
                        break

                if start_idx != -1:
                    node_indices = range(start_idx + 1, nodes.Len()) if is_fwd else range(start_idx - 1, -1, -1)
                    for i in node_indices:
                        node = nodes.At(i)
                        curr_lat_rad = node.latitude * geometry.TO_RADIANS
                        curr_lon_rad = node.longitude * geometry.TO_RADIANS
                        dist = geometry.distance_to_point(last_lat_rad, last_lon_rad, curr_lat_rad, curr_lon_rad)
                        cumulative_distance += dist
                        distances.append(cumulative_distance)
                        path_nodes_lat.append(node.latitude)
                        path_nodes_lon.append(node.longitude)
                        last_lat_rad, last_lon_rad = curr_lat_rad, curr_lon_rad
        except Exception as e:
            print(f"Error processing current way nodes: {e}")

        # Add nodes from next ways
        for next_way_res in self.next_ways:
            try:
                way = next_way_res.way
                is_fwd_next = next_way_res.is_forward
                nodes, err = way.Nodes()
                if not err and nodes:
                    node_indices = range(nodes.Len()) if is_fwd_next else range(nodes.Len() - 1, -1, -1)
                    for i in node_indices:
                        node = nodes.At(i)
                        curr_lat_rad = node.latitude * geometry.TO_RADIANS
                        curr_lon_rad = node.longitude * geometry.TO_RADIANS
                        dist = geometry.distance_to_point(last_lat_rad, last_lon_rad, curr_lat_rad, curr_lon_rad)
                        cumulative_distance += dist
                        distances.append(cumulative_distance)
                        path_nodes_lat.append(node.latitude)
                        path_nodes_lon.append(node.longitude)
                        last_lat_rad, last_lon_rad = curr_lat_rad, curr_lon_rad
            except Exception as e:
                 print(f"Error processing next way nodes: {e}")
                 break # Stop adding nodes if error occurs

        if len(path_nodes_lat) < 3:
            return np.array([]), np.array([])

        # Calculate curvatures along the path
        curvatures, _ = geometry.get_curvatures(path_nodes_lat, path_nodes_lon)

        # Calculate target speeds based on curvature using the new curvature-dependent lat accel function
        # Use VTSC's nonlinear_lat_accel for consistency - REMOVED
        # We need v_ego estimate for this... maybe use current v_ego? Or profile max? - REMOVED
        # Let's use a fixed estimate or make it adaptable later. - REMOVED
        # Assumed v_ego for lat_accel calculation (can be improved) - REMOVED
        # assumed_v_ego = 20.0 # m/s
        # turn_aggression = 1.0 # Get from params later if needed
        # max_lat_accel = nonlinear_lat_accel(assumed_v_ego, turn_aggression)

        target_speeds = []
        # Define a very small curvature threshold to treat as straight
        ZERO_CURVATURE_THRESHOLD = 1e-5
        # Define a maximum speed for effectively straight sections
        STRAIGHT_SPEED_LIMIT = 70.0 # m/s (~156 mph)

        for k in curvatures:
            abs_k = abs(k)
            if abs_k < ZERO_CURVATURE_THRESHOLD: # Treat near-zero curvature as straight
                target_speed = STRAIGHT_SPEED_LIMIT
            else:
                # Determine target lateral accel based purely on curvature
                target_lat_accel_base = curvature_based_lat_accel(abs_k)
                # Apply turn aggressiveness multiplier
                target_lat_accel = target_lat_accel_base * turn_aggressiveness
                # v = sqrt(a / k)
                # Ensure we don't divide by zero if abs_k is somehow exactly zero despite the check
                target_speed = math.sqrt(target_lat_accel / abs_k) if abs_k > 1e-9 else STRAIGHT_SPEED_LIMIT

            target_speeds.append(min(target_speed, STRAIGHT_SPEED_LIMIT)) # Cap speed

        # The curvature/speed applies starting from the *second* node of the triplet used.
        # Align speeds with distances: speed[i] corresponds to distance[i+1]
        if len(distances) > len(target_speeds):
             distance_points = np.array(distances[1:len(target_speeds)+1])
        else:
             # Handle edge case if distances is shorter than target_speeds
             distance_points = np.array(distances[1:])
             target_speeds = target_speeds[:len(distance_points)]

        speed_points = np.array(target_speeds)

        # print(f"MTSC: Calculated profile - {len(distance_points)} points.") # Debug
        return distance_points, speed_points

    def update(self, v_ego, a_ego, frogpilot_toggles, turn_aggressiveness=1.0) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
        """
        Main update loop for Chauffeur MTSC.
        Reads GPS, updates map path, calculates curvature/speed profile.
        Also extracts and publishes map speed limit data.
        Returns tuple: (distance_profile_m, speed_profile_mps)
                      or (None, None) if map data unavailable or path invalid.
        """
        # Get current GPS position
        pos = self._get_current_position()
        if pos is None:
            # If GPS is lost, clear published speed limits
            self.params_memory.put_float("MapSpeedLimit", 0.0)
            self.params_memory.put("NextMapSpeedLimit", "{}")
            self.current_way_result = None
            self.next_ways = []
            self.distance_profile = np.array([])
            self.speed_profile = np.array([])
            return None, None

        # Update the map path if needed
        path_updated = self._update_map_path(pos)

        # --- Speed Limit Extraction and Publishing ---
        current_limit_mps = 0.0
        next_limit_info = {}
        if self.current_way_result and self.current_way_result.way:
            try:
                # Access pre-parsed speed limit (assuming .maxSpeed attribute)
                # Use a default of 0.0 if attribute missing or parsing failed during generation
                current_limit_mps = getattr(self.current_way_result.way, 'maxSpeed', 0.0)

                # Iterate upcoming ways to find the next different speed limit
                for next_way_res in self.next_ways:
                    next_way = next_way_res.way
                    next_limit_mps_cand = getattr(next_way, 'maxSpeed', 0.0)

                    # Check if a valid limit was found and if it differs from the current
                    if next_limit_mps_cand > 0 and abs(next_limit_mps_cand - current_limit_mps) > 1e-3:
                        nodes, err = next_way.Nodes()
                        if not err and nodes and nodes.Len() > 0:
                            # Determine start node based on direction
                            start_node_index = 0 if next_way_res.is_forward else nodes.Len() - 1
                            start_node = nodes.At(start_node_index)
                            next_limit_info = {
                                'speedlimit': next_limit_mps_cand,
                                'latitude': start_node.latitude,
                                'longitude': start_node.longitude
                            }
                            break # Found the first change

            except AttributeError as e:
                print(f"MTSC: Error accessing Way attributes for speed limit: {e}")
                # Fallback: clear limits if attributes are missing
                current_limit_mps = 0.0
                next_limit_info = {}
            except Exception as e:
                print(f"MTSC: Unexpected error during speed limit extraction: {e}")
                current_limit_mps = 0.0
                next_limit_info = {}

        # Publish the found limits (or defaults)
        self.params_memory.put_float("MapSpeedLimit", float(current_limit_mps))
        self.params_memory.put("NextMapSpeedLimit", json.dumps(next_limit_info))
        # --- End Speed Limit Logic ---

        # Calculate the speed profile based on the path
        if path_updated or not self.speed_profile.any():
            self.distance_profile, self.speed_profile = self._calculate_path_profile(pos, turn_aggressiveness)

        # Return the calculated curvature/speed profiles
        if self.distance_profile.any() and self.speed_profile.any():
             return self.distance_profile, self.speed_profile
        else:
             # Even if profile calculation failed, speed limits might have been published
             # Return None, None for the profile tuple
             return None, None

# --- Old code removed ---
# TARGET_JERK, TARGET_ACCEL, TARGET_OFFSET
# calculate_velocity, calculate_distance
# Old target_speed method logic
