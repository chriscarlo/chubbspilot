import math
from collections import namedtuple
from rtree import index as rtree_index

# Local imports (assuming reader.py and geometry.py are in the same directory)
from . import geometry
from . import reader # Although MapReader might be instantiated elsewhere

# REMOVE Placeholder Classes and offline_capnp stub
# class ProtoCoordinates: ...
# class ProtoWay: ...
# class ProtoOffline: ...
# offline_capnp = type(...)

# --- Data Structures ---

Position = namedtuple('Position', ['latitude', 'longitude', 'bearing_rad'])

# NEW: Represent a way segment using its ID and data dictionary from reader.segments_data
SegmentData = dict # Type alias for clarity

# NEW: Define Coordinates simply as a tuple for internal use when needed
CoordinatesTuple = tuple[float, float] # (latitude, longitude)

# Results now refer to segment IDs or data, not Way objects
DistanceResult = namedtuple('DistanceResult', [
    'segment_id',       # ID of the segment the closest point lies on
    'line_start_coord', # CoordinatesTuple of the start of the relevant line sub-segment
    'line_end_coord',   # CoordinatesTuple of the end of the relevant line sub-segment
    'distance_m'        # Distance from pos to the closest point on the segment
])
OnWayResult = namedtuple('OnWayResult', [
    'on_way',           # bool: Is the position likely on *any* segment?
    'segment_id',       # int | None: OSM Way ID of the matched segment
    'distance_m',       # float: Distance to the matched segment
    'is_forward',       # bool: Is the travel direction aligned with the segment's node order?
    'line_start_coord', # CoordinatesTuple | None: Start node coord of the matched sub-segment
    'line_end_coord'    # CoordinatesTuple | None: End node coord of the matched sub-segment
])

CurrentWayResult = namedtuple('CurrentWayResult', [
    'segment_id',       # int: OSM Way ID of the current segment
    'on_way_result'     # OnWayResult: Detailed result from on_way check
])

NextWayResult = namedtuple('NextWayResult', [
    'segment_id',       # int: OSM Way ID of the next segment
    'is_forward'        # bool: Direction of travel on the next segment
])

# --- Constants ---
LANE_WIDTH = 3.7  # meters
# PADDING_DEG no longer needed directly here, reader/rtree handles spatial query extent

# --- Helper Functions ---
def _get_coords_from_segment(segment_data: SegmentData) -> list[CoordinatesTuple]:
    """Extracts node coordinates as (lat, lon) tuples from segment geom."""
    if not segment_data or 'geom' not in segment_data:
        return []
    # Ensure geom is LineString and coords are accessible
    geom = segment_data['geom']
    if not hasattr(geom, 'coords'):
        return []
    # Convert (lon, lat) from LineString to (lat, lon)
    return [(coord[1], coord[0]) for coord in geom.coords]

# --- Core Matching Functions ---
# Functions below will be modified to accept segment_data dicts or segment_ids
# and use the all_segments dict and rtree_idx instead of Offline object.

def distance_to_way(pos: Position, segment_id: int, segment_data: SegmentData) -> DistanceResult | None:
    """
    Calculates the minimum distance from a Position to a Way segment.
    Returns a DistanceResult namedtuple or None if segment data is invalid.
    """
    min_distance_m = float('inf')
    min_node_start_coord = None
    min_node_end_coord = None

    coords = _get_coords_from_segment(segment_data)
    if len(coords) < 2:
        return None

    pos_lat_rad = pos.latitude * geometry.TO_RADIANS
    pos_lon_rad = pos.longitude * geometry.TO_RADIANS

    for i in range(len(coords) - 1):
        node_start_lat, node_start_lon = coords[i]
        node_end_lat, node_end_lon = coords[i+1]

        # Use Euclidean approximation for closest point on line
        line_lat_deg, line_lon_deg = geometry.point_on_line(
            node_start_lat, node_start_lon,
            node_end_lat, node_end_lon,
            pos.latitude, pos.longitude
        )

        # Calculate distance using Haversine
        distance_m = geometry.distance_to_point(
            pos_lat_rad, pos_lon_rad,
            line_lat_deg * geometry.TO_RADIANS,
            line_lon_deg * geometry.TO_RADIANS
        )

        if distance_m < min_distance_m:
            min_distance_m = distance_m
            min_node_start_coord = (node_start_lat, node_start_lon)
            min_node_end_coord = (node_end_lat, node_end_lon)

    if min_node_start_coord is None:
         return None # Should not happen if len(coords) >= 2

    return DistanceResult(
        segment_id=segment_id,
        line_start_coord=min_node_start_coord,
        line_end_coord=min_node_end_coord,
        distance_m=min_distance_m
    )

def is_forward(line_start_coord: CoordinatesTuple, line_end_coord: CoordinatesTuple, bearing_rad: float):
    """
    Determines if the bearing aligns with the direction of the line segment.
    Bearing must be in radians. Coordinates are (lat, lon).
    """
    start_lat, start_lon = line_start_coord
    end_lat, end_lon = line_end_coord

    way_bearing_rad = geometry.bearing(start_lat, start_lon, end_lat, end_lon)
    bearing_delta_rad = abs(bearing_rad - way_bearing_rad)

    # Normalize delta to (-pi, pi]
    while bearing_delta_rad <= -math.pi:
        bearing_delta_rad += 2 * math.pi
    while bearing_delta_rad > math.pi:
        bearing_delta_rad -= 2 * math.pi

    return math.cos(bearing_delta_rad) >= 0

def on_way(pos: Position, segment_id: int, segment_data: SegmentData):
    """
    Checks if the position is likely on the given way segment.
    Returns an OnWayResult namedtuple.
    """
    geom = segment_data.get('geom')
    if not geom or not hasattr(geom, 'bounds'):
        return OnWayResult(False, None, float('inf'), False, None, None)

    # Basic bounding box check using Shapely bounds (minx, miny, maxx, maxy) -> (minlon, minlat, maxlon, maxlat)
    min_lon, min_lat, max_lon, max_lat = geom.bounds
    # Use a small degree padding for the check
    padding = 0.0001 # Roughly 11 meters padding
    if not (min_lat - padding <= pos.latitude <= max_lat + padding and
            min_lon - padding <= pos.longitude <= max_lon + padding):
        return OnWayResult(False, None, float('inf'), False, None, None)

    dist_result = distance_to_way(pos, segment_id, segment_data)
    if dist_result is None or dist_result.distance_m == float('inf'):
        return OnWayResult(False, segment_id, float('inf'), False, None, None)

    lanes = segment_data.get('lanes', 2) # Default to 2 lanes if not specified
    if lanes == 0:
        lanes = 2

    road_width_estimate = float(lanes) * LANE_WIDTH
    max_dist_threshold = 5.0 + road_width_estimate

    if dist_result.distance_m < max_dist_threshold:
        is_fwd = is_forward(dist_result.line_start_coord, dist_result.line_end_coord, pos.bearing_rad)
        # Assume 'oneway' field: 0=No, 1=Yes (forward), -1=Yes (backward) - NEEDS CONFIRMATION from reader/processor
        # Let's assume 0=No, >0 = Yes (forward) for now based on typical OSM usage
        oneway_val = segment_data.get('oneway', 0) # Default to not oneway
        is_way_oneway = oneway_val != 0 # Simplified check

        if not is_fwd and is_way_oneway:
            # Going wrong way on a oneway street
            return OnWayResult(False, segment_id, dist_result.distance_m, is_fwd, dist_result.line_start_coord, dist_result.line_end_coord)
        else:
            # On way or going correct direction on oneway
            return OnWayResult(True, segment_id, dist_result.distance_m, is_fwd, dist_result.line_start_coord, dist_result.line_end_coord)
    else:
        # Too far from the way
        return OnWayResult(False, segment_id, dist_result.distance_m, False, None, None)

def get_way_start_end(segment_data: SegmentData, is_fwd: bool) -> tuple[CoordinatesTuple | None, CoordinatesTuple | None]:
    """
    Gets the first and last coordinate nodes (lat, lon) of a way based on travel direction.
    Returns (None, None) if segment data is invalid or has < 1 node.
    """
    coords = _get_coords_from_segment(segment_data)
    num_nodes = len(coords)

    if num_nodes == 0:
        return None, None
    if num_nodes == 1:
        return coords[0], coords[0]

    if is_fwd:
        return coords[0], coords[num_nodes - 1]
    else:
        return coords[num_nodes - 1], coords[0]

def get_current_way(
    current_segment_id_candidate: int | None, # OSM Way ID from previous cycle
    next_segment_results: list[NextWayResult], # List of NextWayResult from previous cycle
    map_reader: reader.MapReader,            # MapReader instance containing segments_data and rtree_idx
    pos: Position
) -> CurrentWayResult | None:
    """
    Finds the most likely current way segment the vehicle is on.
    Uses MapReader's rtree for spatial querying and segments_data for details.
    Searches in order: current candidate -> predicted next ways -> nearby ways via R-tree.
    Returns a CurrentWayResult namedtuple, or None if no way is found.
    """
    all_segments = map_reader.segments_data
    rtree = map_reader.rtree_idx

    # 1. Check the candidate from the previous cycle
    if current_segment_id_candidate is not None and current_segment_id_candidate in all_segments:
        candidate_data = all_segments[current_segment_id_candidate]
        on_way_result = on_way(pos, current_segment_id_candidate, candidate_data)
        if on_way_result.on_way:
            return CurrentWayResult(segment_id=current_segment_id_candidate, on_way_result=on_way_result)

    # 2. Check the predicted next ways from the previous cycle
    if next_segment_results:
        for next_res in next_segment_results:
            segment_id = next_res.segment_id
            if segment_id in all_segments:
                 segment_data = all_segments[segment_id]
                 on_way_result = on_way(pos, segment_id, segment_data)
                 if on_way_result.on_way:
                    return CurrentWayResult(segment_id=segment_id, on_way_result=on_way_result)

    # 3. Search nearby ways using R-tree
    # Use the reader's method which already incorporates R-tree search
    # Note: get_segment_data_at updates loaded tiles and queries rtree
    closest_segment_info = map_reader.get_segment_data_at(pos.latitude, pos.longitude)

    if closest_segment_info:
        segment_id = closest_segment_info.get('id')
        # Verify the found segment is suitable using on_way check (includes distance threshold)
        on_way_result = on_way(pos, segment_id, closest_segment_info)
        if on_way_result.on_way:
            return CurrentWayResult(segment_id=segment_id, on_way_result=on_way_result)
        # else: Fall through if closest R-tree match fails detailed on_way check

    return None # No matching way found

# Helper - Checks coordinate equality with tolerance
def _coords_equal(coord1: CoordinatesTuple | None, coord2: CoordinatesTuple | None, tol=1e-9) -> bool:
    if coord1 is None or coord2 is None:
        return False
    return abs(coord1[0] - coord2[0]) < tol and abs(coord1[1] - coord2[1]) < tol

# Modified: Uses MapReader's data/index instead of Offline object
def matching_ways(
    current_segment_id: int,
    all_segments: dict[int, SegmentData],
    rtree: rtree_index.Index,
    match_coord: CoordinatesTuple # (lat, lon) of the node to connect TO
) -> list[int]: # Returns list of matching segment IDs
    """
    Finds segments spatially near the match_coord whose start or end node matches it.
    Excludes the current_segment_id itself.
    Uses R-tree for spatial pre-filtering.
    """
    matching_segment_ids = []
    if not match_coord:
        return []

    match_lat, match_lon = match_coord
    # Query R-tree for ways intersecting a small box around the match_coord
    search_bounds = (match_lon - 1e-5, match_lat - 1e-5, match_lon + 1e-5, match_lat + 1e-5) # lon,lat,...
    try:
        candidate_items = list(rtree.intersection(search_bounds, objects="raw")) # Get stored IDs
    except Exception as e:
        print(f"R-tree intersection error in matching_ways: {e}")
        return []

    candidate_ids = set(item for item in candidate_items if isinstance(item, int)) # Ensure IDs are ints

    for segment_id in candidate_ids:
        if segment_id == current_segment_id:
            continue # Don't match with self

        if segment_id not in all_segments:
            # print(f"Warning: R-tree candidate {segment_id} not in loaded segments_data.")
            continue

        segment_data = all_segments[segment_id]
        coords = _get_coords_from_segment(segment_data)
        if len(coords) < 1:
            continue

        first_node_matches = _coords_equal(coords[0], match_coord)
        last_node_matches = _coords_equal(coords[-1], match_coord)

        if first_node_matches or last_node_matches:
            matching_segment_ids.append(segment_id)

    return matching_segment_ids

# Modified: Accepts segment_data dictionary and match coordinate tuple
def next_is_forward(next_segment_data: SegmentData, match_coord: CoordinatesTuple):
    """
    Determines if travel on the next_segment will be in its forward node order,
    given that it connects at match_coord (lat, lon).
    Returns True if forward, False otherwise.
    """
    coords = _get_coords_from_segment(next_segment_data)
    if len(coords) < 1:
        return True # Default assumption?

    # Check if the first node of the next_way is the connection node.
    if _coords_equal(coords[0], match_coord):
        return True # Entering at the start, travel is forward
    else:
        # Assume connection is at the end node if not the start.
        return False

# Modified: Accepts segment_data dictionary and match coordinate tuple
def _get_candidate_bearing_node(segment_data: SegmentData, is_fwd: bool, match_coord: CoordinatesTuple) -> CoordinatesTuple | None:
    """ Helper to get the coordinate (lat, lon) used for curvature calculation. """
    coords = _get_coords_from_segment(segment_data)
    num_nodes = len(coords)
    if num_nodes < 2:
        return None

    if is_fwd: # Entering at node 0 (match_coord), need node 1
        return coords[1]
    else:      # Entering at node N-1 (match_coord), need node N-2
        return coords[num_nodes - 2]

# Heavily Modified: Uses MapReader's data/index instead of Offline object
def next_way(
    current_segment_id: int,
    all_segments: dict[int, SegmentData],
    rtree: rtree_index.Index,
    is_currently_forward: bool
) -> NextWayResult | None:
    """
    Finds the most likely next way segment connecting to the end of the current segment.
    Returns a NextWayResult or None.
    """
    if current_segment_id not in all_segments:
        return None
    current_segment_data = all_segments[current_segment_id]
    current_coords = _get_coords_from_segment(current_segment_data)
    num_nodes = len(current_coords)

    if num_nodes < 2:
        return None

    # Determine the node where connections should occur (match_coord)
    # and the node just before it for curvature calculation (match_bearing_coord)
    if is_currently_forward:
        match_coord = current_coords[num_nodes - 1]
        match_bearing_coord = current_coords[num_nodes - 2]
    else:
        match_coord = current_coords[0]
        match_bearing_coord = current_coords[1]

    # Find all ways physically connecting to the match_coord
    connecting_segment_ids = matching_ways(current_segment_id, all_segments, rtree, match_coord)
    if not connecting_segment_ids:
        return None

    # --- Selection Logic ---
    candidates = []
    for seg_id in connecting_segment_ids:
        if seg_id not in all_segments: continue # Should not happen if matching_ways checks
        m_segment_data = all_segments[seg_id]

        is_fwd_next = next_is_forward(m_segment_data, match_coord)

        # Skip if it's a one-way street and we're going the wrong way
        oneway_val = m_segment_data.get('oneway', 0)
        is_way_oneway = oneway_val != 0
        if not is_fwd_next and is_way_oneway:
            continue

        # Calculate curvature between current segment end and next segment start
        bearing_node_next_coord = _get_candidate_bearing_node(m_segment_data, is_fwd_next, match_coord)
        if bearing_node_next_coord is None:
            continue # Cannot calculate curvature if only one node in next segment

        curv, _, _ = geometry.get_curvature(
            match_bearing_coord[0], match_bearing_coord[1], # lat, lon
            match_coord[0], match_coord[1],                 # lat, lon
            bearing_node_next_coord[0], bearing_node_next_coord[1] # lat, lon
        )

        candidates.append({
            'segment_id': seg_id,
            'is_forward': is_fwd_next,
            'curvature': abs(curv),
            'name': m_segment_data.get('name', ''),
            'ref': m_segment_data.get('ref', '')
        })

    if not candidates:
        return None

    # Get current way name and ref
    current_name = current_segment_data.get('name', '')
    current_ref = current_segment_data.get('ref', '')
    current_refs = set(r.strip() for r in current_ref.split(';') if r.strip())

    # 1. Check for same name and low curvature
    if current_name:
        same_name_candidates = [c for c in candidates if c['name'] == current_name and c['curvature'] < 0.1]
        if same_name_candidates:
            best_candidate = min(same_name_candidates, key=lambda x: x['curvature'])
            return NextWayResult(segment_id=best_candidate['segment_id'], is_forward=best_candidate['is_forward'])

    # 2. Check for same ref and low curvature
    if current_ref:
        same_ref_candidates = [c for c in candidates if c['ref'] == current_ref and c['curvature'] < 0.1]
        if same_ref_candidates:
            best_candidate = min(same_ref_candidates, key=lambda x: x['curvature'])
            return NextWayResult(segment_id=best_candidate['segment_id'], is_forward=best_candidate['is_forward'])

    # 3. Check for *any* matching ref (split by ;) and low curvature, return lowest curvature match
    if current_refs:
        matching_ref_candidates = []
        for c in candidates:
            c_refs = set(r.strip() for r in c['ref'].split(';') if r.strip())
            if current_refs.intersection(c_refs) and c['curvature'] < 0.1:
                 matching_ref_candidates.append(c)
        if matching_ref_candidates:
             best_candidate = min(matching_ref_candidates, key=lambda x: x['curvature'])
             return NextWayResult(segment_id=best_candidate['segment_id'], is_forward=best_candidate['is_forward'])

    # 4. Final fallback: return the candidate with the minimum curvature
    best_candidate = min(candidates, key=lambda x: x['curvature'])
    return NextWayResult(segment_id=best_candidate['segment_id'], is_forward=best_candidate['is_forward'])

# Modified: Accepts segment_data and OnWayResult containing coordinates
def distance_to_end_of_way(pos: Position, segment_data: SegmentData, on_way_result: OnWayResult):
    """
    Calculates the distance from the vehicle's projected point on the way segment
    to the end of that segment, following the direction of travel.
    Returns distance in meters.
    """
    if not on_way_result or not on_way_result.on_way or not on_way_result.line_end_coord or not on_way_result.line_start_coord:
        return 0.0

    is_fwd = on_way_result.is_forward
    line_start_coord = on_way_result.line_start_coord
    line_end_coord = on_way_result.line_end_coord

    # Get the vehicle's projected point on the current line segment (in degrees)
    projected_lat_deg, projected_lon_deg = geometry.point_on_line(
        line_start_coord[0], line_start_coord[1], # lat, lon
        line_end_coord[0], line_end_coord[1],     # lat, lon
        pos.latitude, pos.longitude
    )
    projected_lat_rad = projected_lat_deg * geometry.TO_RADIANS
    projected_lon_rad = projected_lon_deg * geometry.TO_RADIANS

    # Calculate distance from projected point to the end node of the *current segment*
    end_node_lat_rad = line_end_coord[0] * geometry.TO_RADIANS
    end_node_lon_rad = line_end_coord[1] * geometry.TO_RADIANS
    dist_to_segment_end = geometry.distance_to_point(projected_lat_rad, projected_lon_rad, end_node_lat_rad, end_node_lon_rad)

    total_dist = dist_to_segment_end
    last_node_lat_rad = end_node_lat_rad
    last_node_lon_rad = end_node_lon_rad

    coords = _get_coords_from_segment(segment_data)
    num_nodes = len(coords)
    start_index = -1
    # Find the index of the end node of the current segment
    for i in range(num_nodes):
        if _coords_equal(coords[i], line_end_coord):
            start_index = i
            break

    if start_index == -1:
         return total_dist # Should not happen

    # Iterate through remaining nodes in the correct direction
    if is_fwd:
        node_indices = range(start_index + 1, num_nodes)
    else:
        node_indices = range(start_index - 1, -1, -1)

    for i in node_indices:
        node_lat, node_lon = coords[i]
        node_lat_rad = node_lat * geometry.TO_RADIANS
        node_lon_rad = node_lon * geometry.TO_RADIANS

        total_dist += geometry.distance_to_point(last_node_lat_rad, last_node_lon_rad, node_lat_rad, node_lon_rad)
        last_node_lat_rad = node_lat_rad
        last_node_lon_rad = node_lon_rad

    return total_dist

# <<< NEW HELPER FUNCTIONS START >>>

def distance_from_start_to_node(coords: list[CoordinatesTuple], node_index: int) -> float:
    """Calculates distance along geometry from start (index 0) to node_index."""
    distance = 0.0
    if not coords or node_index >= len(coords) or node_index < 0:
        return 0.0

    # Sum distances between consecutive nodes up to the target index
    last_lat_rad = coords[0][0] * geometry.TO_RADIANS
    last_lon_rad = coords[0][1] * geometry.TO_RADIANS
    for i in range(1, node_index + 1):
        if i >= len(coords): break # Should not happen with initial check, but safety
        curr_lat, curr_lon = coords[i]
        curr_lat_rad = curr_lat * geometry.TO_RADIANS
        curr_lon_rad = curr_lon * geometry.TO_RADIANS
        distance += geometry.distance_to_point(last_lat_rad, last_lon_rad, curr_lat_rad, curr_lon_rad)
        last_lat_rad = curr_lat_rad
        last_lon_rad = curr_lon_rad
    return distance

def get_progress_along_way(pos: Position, segment_data: SegmentData, on_way_result: OnWayResult) -> float:
    """
    Calculates the distance traveled along the segment geometry from its start
    to the projected point of the current position.
    Returns distance in meters.
    """
    if not on_way_result or not on_way_result.on_way or \
       not on_way_result.line_start_coord or not on_way_result.line_end_coord:
        return 0.0

    coords = _get_coords_from_segment(segment_data)
    if len(coords) < 2:
        return 0.0

    is_fwd = on_way_result.is_forward
    line_start_coord = on_way_result.line_start_coord
    line_end_coord = on_way_result.line_end_coord

    # Find the index of the *start* node of the line segment we are currently projected onto
    segment_start_node_index = -1
    for i in range(len(coords)):
        if _coords_equal(coords[i], line_start_coord):
            segment_start_node_index = i
            break

    if segment_start_node_index == -1:
        # Fallback: try finding the end node index if start wasn't found (shouldn't happen)
        for i in range(len(coords)):
           if _coords_equal(coords[i], line_end_coord):
                segment_start_node_index = i - 1 # Use the node before the end node
                break
    if segment_start_node_index == -1 or segment_start_node_index < 0:
         print("Matcher Warning: Could not find segment start node index in get_progress_along_way")
         return 0.0 # Cannot determine progress

    # Calculate distance from the way's start to the start node of our current line segment
    dist_to_segment_start_node = distance_from_start_to_node(coords, segment_start_node_index)

    # Calculate the vehicle's projected point on the current line segment (in degrees)
    projected_lat_deg, projected_lon_deg = geometry.point_on_line(
        line_start_coord[0], line_start_coord[1], # lat, lon
        line_end_coord[0], line_end_coord[1],     # lat, lon
        pos.latitude, pos.longitude
    )

    # Calculate distance from the segment_start_node to the projected point
    dist_along_segment = geometry.distance_to_point(
        line_start_coord[0] * geometry.TO_RADIANS, line_start_coord[1] * geometry.TO_RADIANS,
        projected_lat_deg * geometry.TO_RADIANS, projected_lon_deg * geometry.TO_RADIANS
    )

    # Total progress is distance to segment start + distance along segment
    # Handle directionality - this assumes nodes are ordered 0 to N
    # If driving backwards (is_fwd=False), progress is total_length - calculated_forward_progress
    # For now, we assume the calling function (mapd_daemon) handles directionality based on is_fwd
    # This function returns progress assuming forward traversal (0 -> N)
    total_progress = dist_to_segment_start_node + dist_along_segment

    # TODO(?): If !is_fwd, should we return total_length - total_progress?
    # Let's return forward progress for now and let caller adjust.
    return total_progress

# <<< NEW HELPER FUNCTIONS END >>>

MIN_WAY_DIST_M = 500.0 # Lookahead distance

# Modified: Uses MapReader instance and returns list of NextWayResult
def get_next_ways(
    pos: Position,
    current_way_result: CurrentWayResult,
    map_reader: reader.MapReader
) -> list[NextWayResult]:
    """
    Finds a sequence of upcoming way segments based on the current position and map data.
    Returns a list of NextWayResult objects.
    """
    if not current_way_result or current_way_result.segment_id not in map_reader.segments_data:
        return []

    all_segments = map_reader.segments_data
    rtree = map_reader.rtree_idx

    next_ways_list = []
    total_distance_m = 0.0
    current_segment_id = current_way_result.segment_id
    current_on_way_result = current_way_result.on_way_result
    is_currently_forward = current_on_way_result.is_forward

    # Loop until we have enough lookahead distance or cannot find more ways
    while total_distance_m < MIN_WAY_DIST_M:
        current_segment_data = all_segments.get(current_segment_id)
        if not current_segment_data: break # Should not happen if ID is valid

        # Calculate distance remaining on the *current* way being processed in the loop
        if not next_ways_list: # Only calculate this for the first way
             dist_remaining_on_current = distance_to_end_of_way(pos, current_segment_data, current_on_way_result)
             if dist_remaining_on_current <= 0:
                 # If distance is zero, try finding the next way anyway before breaking
                 nw_result = next_way(current_segment_id, all_segments, rtree, is_currently_forward)
                 if nw_result:
                    next_ways_list.append(nw_result)
                    current_segment_id = nw_result.segment_id
                    is_currently_forward = nw_result.is_forward
                    current_segment_data = all_segments.get(current_segment_id) # Update data for length calc
                    if not current_segment_data: break
                 else:
                    break # Cannot proceed if stuck or error and no next way

             else:
                  total_distance_m += dist_remaining_on_current

        # Find the single next way connected to the current_way
        # If we already added one due to zero distance, skip finding another in this iteration
        if next_ways_list and next_ways_list[-1].segment_id == current_segment_id:
             pass # Already advanced due to zero distance calculation
        else:
            nw_result = next_way(current_segment_id, all_segments, rtree, is_currently_forward)
            if nw_result is None:
                break # Stop if no further way is found

            next_ways_list.append(nw_result)
            # Update state for the next iteration
            current_segment_id = nw_result.segment_id
            is_currently_forward = nw_result.is_forward
            current_segment_data = all_segments.get(current_segment_id) # Update data for length calc
            if not current_segment_data: break


        # Estimate distance of this newly added way segment
        start_coord, end_coord = get_way_start_end(current_segment_data, is_currently_forward)
        if start_coord and end_coord:
            way_length = 0
            coords = _get_coords_from_segment(current_segment_data)
            num_nodes = len(coords)

            if num_nodes >= 2:
                 # Use the correct start/end based on direction
                 iter_start_coord = start_coord if is_currently_forward else end_coord
                 last_lat_rad = iter_start_coord[0] * geometry.TO_RADIANS
                 last_lon_rad = iter_start_coord[1] * geometry.TO_RADIANS

                 node_indices = range(1, num_nodes) if is_currently_forward else range(num_nodes - 2, -1, -1)
                 for i in node_indices:
                     curr_lat, curr_lon = coords[i]
                     curr_lat_rad = curr_lat * geometry.TO_RADIANS
                     curr_lon_rad = curr_lon * geometry.TO_RADIANS
                     way_length += geometry.distance_to_point(last_lat_rad, last_lon_rad, curr_lat_rad, curr_lon_rad)
                     last_lat_rad = curr_lat_rad
                     last_lon_rad = curr_lon_rad
            else: # Single node segment? Use 0 length.
                way_length = 0.0

            total_distance_m += way_length
        else:
            break # Cannot calculate length, stop lookahead


    # Ensure at least one next way is returned if possible (even if dist < MIN_WAY_DIST_M)
    if not next_ways_list:
        initial_segment_id = current_way_result.segment_id
        initial_is_fwd = current_way_result.on_way_result.is_forward
        nw_result = next_way(initial_segment_id, all_segments, rtree, initial_is_fwd)
        if nw_result:
            next_ways_list.append(nw_result)

    return next_ways_list


# --- Example Usage ---
if __name__ == '__main__':
    print("Matcher module - contains functions for map matching.")
    # Example: Test is_forward (remains the same logic)
    node_a = (0.0, 0.0) # lat, lon
    node_b = (0.0, 1.0) # lat, lon
    bearing_east_rad = math.pi / 2
    print(f"Test is_forward (East bearing vs East way): {is_forward(node_a, node_b, bearing_east_rad)}")
    bearing_west_rad = -math.pi / 2
    print(f"Test is_forward (West bearing vs East way): {is_forward(node_a, node_b, bearing_west_rad)}")

    # Need more comprehensive tests involving a MapReader instance with loaded data.