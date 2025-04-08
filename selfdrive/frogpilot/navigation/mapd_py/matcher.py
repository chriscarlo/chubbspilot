import math
from collections import namedtuple

# Local imports (assuming reader.py and geometry.py are in the same directory)
from . import geometry
from . import reader # Although MapReader might be instantiated elsewhere

# Attempt to import the generated capnp schema
try:
    from . import offline_capnp
except ImportError:
    print("Warning: matcher.py - offline_capnp Python schema not found.")
    # Define dummy structures if import fails
    class DummyCoordinates:
        latitude = 0.0
        longitude = 0.0
        def __init__(self, lat=0.0, lon=0.0):
            self.latitude = lat
            self.longitude = lon
    class DummyWay:
        nodes = []
        minLat = 0.0
        minLon = 0.0
        maxLat = 0.0
        maxLon = 0.0
        lanes = 2
        oneWay = False
        name = ""
        ref = ""
        def Name(self): return self.name, None
        def Ref(self): return self.ref, None
        def Nodes(self): return self, None # Fake list access
        def Len(self): return len(self.nodes)
        def At(self, i): return self.nodes[i]
        def Lanes(self): return self.lanes
        def OneWay(self): return self.oneWay
        def HasNodes(self): return bool(self.nodes)
        def MinLat(self): return self.minLat
        def MinLon(self): return self.minLon
        def MaxLat(self): return self.maxLat
        def MaxLon(self): return self.maxLon

    class DummyOffline:
        ways = []
        minLat = 0.0
        minLon = 0.0
        maxLat = 0.0
        maxLon = 0.0
        overlap = 0.0
        def Ways(self): return self, None # Fake list access
        def Len(self): return len(self.ways)
        def At(self, i): return self.ways[i]
        def MinLat(self): return self.minLat
        def MinLon(self): return self.minLon
        def MaxLat(self): return self.maxLat
        def MaxLon(self): return self.maxLon
        def Overlap(self): return self.overlap

    # Replace capnp classes with dummies
    offline_capnp = type('obj', (object,), {
        'Coordinates': DummyCoordinates,
        'Way': DummyWay,
        'Offline': DummyOffline
    })()

# --- Data Structures (using namedtuples for simplicity) ---
# Consider using dataclasses in Python 3.7+

Position = namedtuple('Position', ['latitude', 'longitude', 'bearing_rad'])
# Note: Changed bearing to bearing_rad to be explicit about units

Coordinates = offline_capnp.Coordinates # Use generated or dummy Coordinates
Way = offline_capnp.Way             # Use generated or dummy Way
Offline = offline_capnp.Offline     # Use generated or dummy Offline

DistanceResult = namedtuple('DistanceResult', ['line_start_node', 'line_end_node', 'distance_m'])
OnWayResult = namedtuple('OnWayResult', ['on_way', 'distance_result', 'is_forward'])

# Define structure for the result of finding the current way
CurrentWayResult = namedtuple('CurrentWayResult', ['way', 'on_way_result'])
# We omit start/end position from here, calculate it when needed maybe?
# Or add it: CurrentWayResult = namedtuple('CurrentWayResult', ['way', 'on_way_result', 'start_pos', 'end_pos'])

# Define structure for finding the next way
NextWayResult = namedtuple('NextWayResult', ['way', 'is_forward'])
# Go version includes Start/EndPosition, add if needed:
# NextWayResult = namedtuple('NextWayResult', ['way', 'is_forward', 'start_pos', 'end_pos'])

# --- Constants --- Based on way.go and math.go
LANE_WIDTH = 3.7  # meters
PADDING_DEG = geometry.PADDING # 10 meters in degrees, from math.go (via geometry.py)

# --- Core Matching Functions ---

def distance_to_way(pos: Position, way: Way):
    """
    Calculates the minimum distance from a Position to a Way.
    Equivalent to DistanceToWay in way.go.
    Returns a DistanceResult namedtuple.
    Handles potential errors during node access.
    """
    min_distance_m = float('inf')
    min_node_start = None
    min_node_end = None

    try:
        nodes, err_nodes = way.Nodes()
        if err_nodes or not nodes or nodes.Len() < 2:
            # print(f"Warning: Could not get nodes for way or not enough nodes ({err_nodes})")
            return DistanceResult(None, None, float('inf'))

        pos_lat_rad = pos.latitude * geometry.TO_RADIANS
        pos_lon_rad = pos.longitude * geometry.TO_RADIANS

        for i in range(nodes.Len() - 1):
            node_start = nodes.At(i)
            node_end = nodes.At(i + 1)

            # Use Euclidean approximation for closest point on line (like Go code)
            line_lat_deg, line_lon_deg = geometry.point_on_line(
                node_start.latitude, node_start.longitude,
                node_end.latitude, node_end.longitude,
                pos.latitude, pos.longitude
            )

            # Calculate distance using Haversine (more accurate than Euclidean)
            distance_m = geometry.distance_to_point(
                pos_lat_rad, pos_lon_rad,
                line_lat_deg * geometry.TO_RADIANS,
                line_lon_deg * geometry.TO_RADIANS
            )

            if distance_m < min_distance_m:
                min_distance_m = distance_m
                min_node_start = node_start
                min_node_end = node_end

        if min_node_start is None:
             # This shouldn't happen if nodes.Len() >= 2
             return DistanceResult(None, None, float('inf'))

        return DistanceResult(min_node_start, min_node_end, min_distance_m)

    except Exception as e:
        print(f"Error in distance_to_way: {e}")
        return DistanceResult(None, None, float('inf'))

def is_forward(line_start_node: Coordinates, line_end_node: Coordinates, bearing_rad: float):
    """
    Determines if the bearing aligns with the direction of the line segment.
    Equivalent to IsForward in way.go.
    Bearing must be in radians.
    """
    way_bearing_rad = geometry.bearing(
        line_start_node.latitude, line_start_node.longitude,
        line_end_node.latitude, line_end_node.longitude
    )

    bearing_delta_rad = abs(bearing_rad - way_bearing_rad)

    # Normalize delta to (-pi, pi]
    while bearing_delta_rad <= -math.pi:
        bearing_delta_rad += 2 * math.pi
    while bearing_delta_rad > math.pi:
        bearing_delta_rad -= 2 * math.pi

    # Check if the absolute difference is within +/- 90 degrees (pi/2 radians)
    # math.cos(delta) >= 0 means delta is within [-pi/2, pi/2]
    return math.cos(bearing_delta_rad) >= 0

def on_way(way: Way, pos: Position):
    """
    Checks if the position is likely on the given way.
    Equivalent to OnWay in way.go.
    Returns an OnWayResult namedtuple.
    """
    # Basic bounding box check with padding
    if not (way.HasNodes() and
            pos.latitude < way.MaxLat() + PADDING_DEG and
            pos.latitude > way.MinLat() - PADDING_DEG and
            pos.longitude < way.MaxLon() + PADDING_DEG and
            pos.longitude > way.MinLon() - PADDING_DEG):
        return OnWayResult(False, None, False)

    dist_result = distance_to_way(pos, way)
    if dist_result.distance_m == float('inf') or dist_result.line_start_node is None:
        return OnWayResult(False, dist_result, False)

    try:
        lanes = way.Lanes()
        if lanes == 0:
            lanes = 2 # Default assumption like in Go code
    except Exception:
        lanes = 2 # Default on error accessing Lanes

    road_width_estimate = float(lanes) * LANE_WIDTH
    max_dist_threshold = 5.0 + road_width_estimate # Threshold from Go code

    if dist_result.distance_m < max_dist_threshold:
        is_fwd = is_forward(dist_result.line_start_node, dist_result.line_end_node, pos.bearing_rad)
        # If it's a one-way street and we are going the wrong way, it's not a match
        if not is_fwd and way.OneWay():
            return OnWayResult(False, dist_result, is_fwd)
        else:
            return OnWayResult(True, dist_result, is_fwd)
    else:
        return OnWayResult(False, dist_result, False)

def get_way_start_end(way: Way, is_fwd: bool):
    """
    Gets the first and last coordinate nodes of a way based on travel direction.
    Equivalent to GetWayStartEnd in way.go.
    Returns tuple: (start_coordinate, end_coordinate)
    Returns (None, None) if nodes cannot be accessed or way has < 1 node.
    """
    try:
        nodes, err_nodes = way.Nodes()
        if err_nodes or not nodes:
            # print(f"Warning: Cannot get start/end, no nodes for way: {err_nodes}")
            return None, None

        num_nodes = nodes.Len()
        if num_nodes == 0:
            return None, None
        if num_nodes == 1:
            return nodes.At(0), nodes.At(0)

        if is_fwd:
            return nodes.At(0), nodes.At(num_nodes - 1)
        else:
            return nodes.At(num_nodes - 1), nodes.At(0)
    except Exception as e:
        print(f"Error in get_way_start_end: {e}")
        return None, None

def get_current_way(current_way_candidate: Way, # Way object from previous cycle, can be None
                    next_way_results: list,      # List of NextWayResult from previous cycle
                    offline_data: Offline,       # Loaded map data for the area
                    pos: Position) -> CurrentWayResult | None:
    """
    Finds the most likely current way the vehicle is on.
    Equivalent logic to GetCurrentWay in way.go.
    Searches in order: current candidate -> predicted next ways -> all ways in data.
    Returns a CurrentWayResult namedtuple, or None if no way is found.
    """

    # 1. Check the candidate from the previous cycle
    if current_way_candidate and current_way_candidate.HasNodes():
        on_way_result = on_way(current_way_candidate, pos)
        if on_way_result.on_way:
            # print("Current way candidate is valid.") # Debug
            return CurrentWayResult(way=current_way_candidate, on_way_result=on_way_result)

    # 2. Check the predicted next ways from the previous cycle
    # Assumes next_way_results is a list of objects each having a 'way' attribute
    if next_way_results:
        for next_way_res in next_way_results:
            if hasattr(next_way_res, 'way') and next_way_res.way and next_way_res.way.HasNodes():
                on_way_result = on_way(next_way_res.way, pos)
                if on_way_result.on_way:
                    # print(f"Found match in predicted next ways.") # Debug
                    return CurrentWayResult(way=next_way_res.way, on_way_result=on_way_result)

    # 3. Search all ways in the loaded offline data chunk
    # print(f"Searching all {offline_data.Ways().Len()} ways in loaded data...") # Debug
    try:
        all_ways, err_ways = offline_data.Ways()
        if err_ways:
            print(f"Error accessing ways from offline data: {err_ways}")
            return None

        for i in range(all_ways.Len()):
            way = all_ways.At(i)
            # Check if it's the same way object as the candidate to avoid re-check (might be tricky)
            # Simple check: skip if no nodes
            if not way.HasNodes():
                continue

            # Optimization: Skip if BBox doesn't match pos at all (already done in on_way)
            # on_way first checks bounding box
            on_way_result = on_way(way, pos)
            if on_way_result.on_way:
                # print(f"Found match by searching all ways.") # Debug
                return CurrentWayResult(way=way, on_way_result=on_way_result)

    except Exception as e:
        print(f"Error searching all ways in offline data: {e}")
        return None

    # print("Could not find any matching way.") # Debug
    return None # No matching way found

def point_in_box(lat, lon, min_lat, min_lon, max_lat, max_lon):
    """Checks if a point is within a bounding box."""
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

def matching_ways(current_way: Way, offline_data: Offline, match_node: Coordinates):
    """
    Finds ways in the offline data that connect to the match_node, excluding the current_way itself.
    Equivalent to MatchingWays in way.go.
    Returns a list of matching Way objects.
    """
    matching_ways_list = []
    try:
        all_ways, err_ways = offline_data.Ways()
        if err_ways:
            print(f"Error accessing ways in matching_ways: {err_ways}")
            return []

        num_all_ways = all_ways.Len()
        # print(f"Checking {num_all_ways} ways for matches with node {match_node.latitude}, {match_node.longitude}") # Debug

        # Get properties of current_way once to compare
        # Comparing capnp objects directly might be possible but potentially slow?
        # Let's compare based on basic properties like bounds for now.
        # A more robust way might involve a unique ID if available.
        curr_min_lat, curr_min_lon = current_way.MinLat(), current_way.MinLon()
        curr_max_lat, curr_max_lon = current_way.MaxLat(), current_way.MaxLon()

        for i in range(num_all_ways):
            w = all_ways.At(i)
            if not w.HasNodes():
                continue

            # Skip if it's the same way as current_way (basic check)
            if (w.MinLat() == curr_min_lat and w.MaxLat() == curr_max_lat and
                w.MinLon() == curr_min_lon and w.MaxLon() == curr_max_lon):
                continue

            w_nodes, err_w_nodes = w.Nodes()
            if err_w_nodes or w_nodes.Len() < 1: # Need at least one node to match
                continue

            num_w_nodes = w_nodes.Len()
            f_node = w_nodes.At(0)
            l_node = w_nodes.At(num_w_nodes - 1)

            # Check if first or last node matches the connection point
            # Use a small tolerance for float comparison?
            TOL = 1e-9 # Or maybe check object identity if possible?
            match_lat, match_lon = match_node.latitude, match_node.longitude

            first_node_matches = (abs(f_node.latitude - match_lat) < TOL and
                                abs(f_node.longitude - match_lon) < TOL)
            last_node_matches = (abs(l_node.latitude - match_lat) < TOL and
                               abs(l_node.longitude - match_lon) < TOL)

            if first_node_matches or last_node_matches:
                # print(f"  Found matching way index {i}") # Debug
                matching_ways_list.append(w)

    except Exception as e:
        print(f"Error in matching_ways: {e}")
        return []

    return matching_ways_list

def next_is_forward(next_way: Way, match_node: Coordinates):
    """
    Determines if travel on the next_way will be in its forward node order,
    given that it connects at match_node.
    Equivalent to NextIsForward in way.go.
    Returns True if forward, False otherwise.
    """
    try:
        nodes, err_nodes = next_way.Nodes()
        if err_nodes or not nodes or nodes.Len() < 1:
            # print(f"Warning: Cannot determine next_is_forward, no nodes: {err_nodes}")
            return True # Default assumption?

        # Check if the first node of the next_way is the connection node.
        # If yes, we are entering at the start, so travel is forward.
        f_node = nodes.At(0)
        TOL = 1e-9
        if (abs(f_node.latitude - match_node.latitude) < TOL and
            abs(f_node.longitude - match_node.longitude) < TOL):
            return True
        else:
            # If the last node matches, we are entering at the end, so travel is backward.
            # Any other case (match_node isn't first or last) shouldn't happen if matching_ways worked.
            return False
    except Exception as e:
        print(f"Error in next_is_forward: {e}")
        return True # Default assumption on error?

def _get_candidate_bearing_node(way: Way, is_fwd: bool, match_node: Coordinates):
    """ Helper to get the node used for curvature calculation on a candidate way. """
    nodes, err = way.Nodes()
    if err or nodes.Len() < 2:
        return None

    # If our entry (match_node) is the first node, the bearing node is the second (index 1).
    # If our entry (match_node) is the last node, the bearing node is the second-to-last.
    if is_fwd: # We are entering at node 0
        return nodes.At(1)
    else:      # We are entering at node Len-1
        return nodes.At(nodes.Len() - 2)

def next_way(way: Way, offline_data: Offline, is_currently_forward: bool):
    """
    Finds the most likely next way segment connecting to the end of the current way.
    Equivalent logic to NextWay in way.go.
    Handles connection logic based on name, ref, and curvature.
    Returns a NextWayResult or None.
    """
    try:
        nodes, err_nodes = way.Nodes()
        if err_nodes or not nodes or nodes.Len() < 2:
            # print("Cannot find next way, current way has < 2 nodes.")
            return None

        # Determine the node where connections should occur (match_node)
        # and the node just before it for curvature calculation (match_bearing_node)
        num_nodes = nodes.Len()
        if is_currently_forward:
            match_node = nodes.At(num_nodes - 1)
            match_bearing_node = nodes.At(num_nodes - 2)
        else:
            match_node = nodes.At(0)
            match_bearing_node = nodes.At(1)

        # Check if the match_node is within the loaded map bounds (including overlap)
        overlap_deg = offline_data.Overlap()
        if not point_in_box(match_node.latitude, match_node.longitude,
                          offline_data.MinLat() - overlap_deg, offline_data.MinLon() - overlap_deg,
                          offline_data.MaxLat() + overlap_deg, offline_data.MaxLon() + overlap_deg):
            # print("Match node is outside loaded map bounds.")
            return None # Connection point is outside the loaded data area

        # Find all ways physically connecting to the match_node
        connecting_ways = matching_ways(way, offline_data, match_node)
        if not connecting_ways:
            # print("No ways connect to the match node.")
            return None

        # --- Selection Logic ---
        # This closely follows the Go implementation's priority.

        candidates = []
        for m_way in connecting_ways:
            # Determine direction on the matched way
            is_fwd_next = next_is_forward(m_way, match_node)

            # Skip if it's a one-way street and we're going the wrong way
            if not is_fwd_next and m_way.OneWay():
                continue

            # Calculate curvature between current segment end and next segment start
            bearing_node_next = _get_candidate_bearing_node(m_way, is_fwd_next, match_node)
            if bearing_node_next is None:
                continue # Cannot calculate curvature if only one node

            curv, _, _ = geometry.get_curvature(
                match_bearing_node.latitude, match_bearing_node.longitude,
                match_node.latitude, match_node.longitude,
                bearing_node_next.latitude, bearing_node_next.longitude
            )

            # Get name and ref (handle potential errors)
            try:
                m_name, _ = m_way.Name()
            except Exception: m_name = ""
            try:
                m_ref, _ = m_way.Ref()
            except Exception: m_ref = ""

            candidates.append({
                'way': m_way,
                'is_forward': is_fwd_next,
                'curvature': abs(curv),
                'name': m_name,
                'ref': m_ref
            })

        if not candidates:
            # print("No valid candidates after filtering one-way/curvature calc.")
            return None

        # Get current way name and ref
        try:
            current_name, _ = way.Name()
        except Exception: current_name = ""
        try:
            current_ref, _ = way.Ref()
        except Exception: current_ref = ""
        current_refs = set(r.strip() for r in current_ref.split(';') if r.strip())

        # 1. Check for same name and low curvature
        if current_name:
            same_name_candidates = [c for c in candidates if c['name'] == current_name and c['curvature'] < 0.1]
            if same_name_candidates:
                best_candidate = min(same_name_candidates, key=lambda x: x['curvature']) # Lowest curvature wins tie
                return NextWayResult(way=best_candidate['way'], is_forward=best_candidate['is_forward'])

        # 2. Check for same ref and low curvature
        if current_ref:
            same_ref_candidates = [c for c in candidates if c['ref'] == current_ref and c['curvature'] < 0.1]
            if same_ref_candidates:
                best_candidate = min(same_ref_candidates, key=lambda x: x['curvature'])
                return NextWayResult(way=best_candidate['way'], is_forward=best_candidate['is_forward'])

        # 3. Check for *any* matching ref (split by ;) and low curvature, return lowest curvature match
        if current_refs:
            matching_ref_candidates = []
            for c in candidates:
                c_refs = set(r.strip() for r in c['ref'].split(';') if r.strip())
                if current_refs.intersection(c_refs) and c['curvature'] < 0.1:
                     matching_ref_candidates.append(c)
            if matching_ref_candidates:
                 best_candidate = min(matching_ref_candidates, key=lambda x: x['curvature'])
                 return NextWayResult(way=best_candidate['way'], is_forward=best_candidate['is_forward'])

        # 4. Final fallback: return the candidate with the minimum curvature
        best_candidate = min(candidates, key=lambda x: x['curvature'])
        return NextWayResult(way=best_candidate['way'], is_forward=best_candidate['is_forward'])

    except Exception as e:
        print(f"Error in next_way: {e}")
        return None

def distance_to_end_of_way(pos: Position, way: Way, on_way_result: OnWayResult):
    """
    Calculates the distance from the vehicle's projected point on the way
    to the end of that way segment, following the direction of travel.
    Equivalent to DistanceToEndOfWay in way.go.
    Requires the OnWayResult to know the relevant line segment and travel direction.
    Returns distance in meters.
    """
    if not on_way_result or not on_way_result.distance_result or not on_way_result.distance_result.line_end_node:
        return 0.0 # Cannot calculate without valid on_way result

    is_fwd = on_way_result.is_forward
    line_end_node = on_way_result.distance_result.line_end_node
    # The Go code seems to use the END node of the matched line segment as the starting point for summation.
    # Let's find the closest point on the line segment to the actual position first.

    line_start_node = on_way_result.distance_result.line_start_node

    # Get the vehicle's projected point on the current line segment (in degrees)
    projected_lat_deg, projected_lon_deg = geometry.point_on_line(
        line_start_node.latitude, line_start_node.longitude,
        line_end_node.latitude, line_end_node.longitude,
        pos.latitude, pos.longitude
    )
    projected_lat_rad = projected_lat_deg * geometry.TO_RADIANS
    projected_lon_rad = projected_lon_deg * geometry.TO_RADIANS

    # Calculate distance from projected point to the end node of the *current segment*
    end_node_lat_rad = line_end_node.latitude * geometry.TO_RADIANS
    end_node_lon_rad = line_end_node.longitude * geometry.TO_RADIANS
    dist_to_segment_end = geometry.distance_to_point(projected_lat_rad, projected_lon_rad, end_node_lat_rad, end_node_lon_rad)

    total_dist = dist_to_segment_end
    last_node_lat_rad = end_node_lat_rad
    last_node_lon_rad = end_node_lon_rad

    try:
        nodes, err_nodes = way.Nodes()
        if err_nodes or not nodes:
            return total_dist # Return distance just to end of segment if nodes error

        num_nodes = nodes.Len()
        start_index = -1
        # Find the index of the end node of the current segment
        for i in range(num_nodes):
            node = nodes.At(i)
            if (abs(node.latitude - line_end_node.latitude) < 1e-9 and
                abs(node.longitude - line_end_node.longitude) < 1e-9):
                start_index = i
                break

        if start_index == -1:
             return total_dist # Should not happen if line_end_node is from this way

        # Iterate through remaining nodes in the correct direction
        if is_fwd:
            # Iterate from start_index + 1 to the end
            node_indices = range(start_index + 1, num_nodes)
        else:
            # Iterate from start_index - 1 down to 0
            node_indices = range(start_index - 1, -1, -1)

        for i in node_indices:
            node = nodes.At(i)
            node_lat_rad = node.latitude * geometry.TO_RADIANS
            node_lon_rad = node.longitude * geometry.TO_RADIANS

            total_dist += geometry.distance_to_point(last_node_lat_rad, last_node_lon_rad, node_lat_rad, node_lon_rad)
            last_node_lat_rad = node_lat_rad
            last_node_lon_rad = node_lon_rad

        return total_dist

    except Exception as e:
        print(f"Error in distance_to_end_of_way: {e}")
        return dist_to_segment_end # Fallback to distance just to segment end


MIN_WAY_DIST_M = 500.0 # Lookahead distance from way.go

def get_next_ways(pos: Position, current_way_result: CurrentWayResult, offline_data: Offline):
    """
    Finds a sequence of upcoming ways based on the current position and map data.
    Equivalent to NextWays in way.go.
    Returns a list of NextWayResult objects.
    """
    if not current_way_result or not current_way_result.way or not current_way_result.on_way_result:
        return []

    next_ways_list = []
    total_distance_m = 0.0
    current_way = current_way_result.way
    is_currently_forward = current_way_result.on_way_result.is_forward
    start_pos_for_dist_calc = pos # Use actual position for first segment distance

    # Loop until we have enough lookahead distance or cannot find more ways
    while total_distance_m < MIN_WAY_DIST_M:
        # Calculate distance remaining on the *current* way being processed in the loop
        # Need OnWayResult relative to the start_pos_for_dist_calc and current_way
        # This is getting complicated. Let's simplify based on Go code's apparent logic:
        # It seems to calculate distance from a *position* to the *end* of a way segment.

        # Recalculate OnWayResult for the start_pos relative to the current_way in the loop
        # This might be slow. Let's approximate based on the initial logic.
        # The Go code calls DistanceToEndOfWay using the *start position* for the *first* iteration.
        # For subsequent iterations, it uses the *start node* of the *next way* as the start pos.

        # Simplified approach: Sum distances of subsequent ways until target distance is met.
        # Start by calculating distance left on the initial current_way
        if not next_ways_list: # Only calculate this for the first way
             dist_remaining_on_current = distance_to_end_of_way(pos, current_way, current_way_result.on_way_result)
             if dist_remaining_on_current <= 0:
                 break # Cannot proceed if stuck or error
             total_distance_m += dist_remaining_on_current

        # Find the single next way connected to the current_way
        nw_result = next_way(current_way, offline_data, is_currently_forward)

        if nw_result is None or nw_result.way is None:
            # print("Could not find next way, stopping path generation.")
            break # Stop if no further way is found

        next_ways_list.append(nw_result)

        # Update state for the next iteration
        current_way = nw_result.way
        is_currently_forward = nw_result.is_forward

        # Estimate distance of this newly added way segment
        # We need its start and end nodes
        start_node, end_node = get_way_start_end(current_way, is_currently_forward)
        if start_node and end_node:
            way_length = 0
            try:
                nodes, _ = current_way.Nodes()
                last_lat_rad = start_node.latitude * geometry.TO_RADIANS
                last_lon_rad = start_node.longitude * geometry.TO_RADIANS
                # Sum distances between consecutive nodes
                node_indices = range(1, nodes.Len()) if is_currently_forward else range(nodes.Len() - 2, -1, -1)
                for i in node_indices:
                    curr_node = nodes.At(i)
                    curr_lat_rad = curr_node.latitude * geometry.TO_RADIANS
                    curr_lon_rad = curr_node.longitude * geometry.TO_RADIANS
                    way_length += geometry.distance_to_point(last_lat_rad, last_lon_rad, curr_lat_rad, curr_lon_rad)
                    last_lat_rad = curr_lat_rad
                    last_lon_rad = curr_lon_rad

            except Exception as e:
                print(f"Error calculating way length: {e}")
                way_length = geometry.distance_to_point(
                    start_node.latitude * geometry.TO_RADIANS, start_node.longitude * geometry.TO_RADIANS,
                    end_node.latitude * geometry.TO_RADIANS, end_node.longitude * geometry.TO_RADIANS
                ) # Fallback: straight line distance

            total_distance_m += way_length
        else:
            # Cannot calculate length, stop lookahead
            break

    # Go code ensures at least one next way is returned if possible
    if not next_ways_list:
        nw_result = next_way(current_way_result.way, offline_data, current_way_result.on_way_result.is_forward)
        if nw_result:
            next_ways_list.append(nw_result)

    return next_ways_list


# --- Example Usage ---
if __name__ == '__main__':
    # This requires map data to be loaded and a Position object
    print("Matcher module - contains functions for map matching.")
    # Add test cases here later, likely requiring a dummy Offline object
    # or loading real data with the reader.

    # Example: Create a dummy position and way for testing is_forward
    # Point A: Equator, 0 Longitude
    # Point B: Equator, 1 Degree East Longitude
    node_a = offline_capnp.Coordinates(latitude=0.0, longitude=0.0)
    node_b = offline_capnp.Coordinates(latitude=0.0, longitude=1.0)

    # Bearing: East (pi/2 radians or 90 degrees)
    bearing_east_rad = math.pi / 2
    print(f"Test is_forward (East bearing vs East way): {is_forward(node_a, node_b, bearing_east_rad)}") # Expect True

    # Bearing: West (-pi/2 radians or 270 degrees)
    bearing_west_rad = -math.pi / 2
    print(f"Test is_forward (West bearing vs East way): {is_forward(node_a, node_b, bearing_west_rad)}") # Expect False

    # Bearing: North (0 radians or 0 degrees)
    bearing_north_rad = 0
    print(f"Test is_forward (North bearing vs East way): {is_forward(node_a, node_b, bearing_north_rad)}") # Expect True (within 90 deg)

    # Bearing: South (pi radians or 180 degrees)
    bearing_south_rad = math.pi
    print(f"Test is_forward (South bearing vs East way): {is_forward(node_a, node_b, bearing_south_rad)}") # Expect False (outside 90 deg)

    # Need more comprehensive tests involving dummy map data...

    print("\n---")
    print("get_current_way requires loaded Offline data and Position.")
    # Add tests for get_current_way later with mock data.

    print("\n---")
    print("next_way requires loaded Offline data and a current Way.")
    # Add tests for next_way later with mock data.