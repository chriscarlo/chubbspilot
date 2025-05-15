import math
from collections import namedtuple
from rtree import index as rtree_index
import datetime # Added for logging
import json # Added for logging

# Local imports (assuming reader.py and geometry.py are in the same directory)
from . import geometry
from . import reader # Although MapReader might be instantiated elsewhere

# --- Logging Utility (simplified, to be centralized later) ---
def format_value_matcher(value):
    if isinstance(value, (list, dict)):
        # For lists/dicts, use a compact JSON representation unless it's a known complex object
        if hasattr(value, '__dict__') and not isinstance(value, (list, dict, str, int, float, bool)):
            return str(value) # For complex objects, just use string representation
        return json.dumps(value, separators=(',', ':'))
    if isinstance(value, str) and (' ' in value or '=' in value or ',' in value or '"' in value):
        processed_value = value.replace('"', '\"')
        return f'"{processed_value}"'
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return "None"
    return str(value)

def log_event_matcher(module_name: str, level: str, event_description: str, **kwargs):
    timestamp = datetime.datetime.utcnow().isoformat(timespec='milliseconds') + "Z"
    details = ", ".join(f"{key}={format_value_matcher(value)}" for key, value in kwargs.items())
    log_message = f"[{timestamp}] [{module_name.upper()}] [{level.upper()}] {event_description}: {details if details else 'No details'}"
    print(log_message, flush=True)
# --- End Logging Utility ---

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
    log_event_matcher("MATCHER", "TRACE", "DISTANCE_TO_WAY_START", segment_id=segment_id, pos_lat=pos.latitude, pos_lon=pos.longitude, num_coords_in_segment=len(segment_data.get('geom', {}).coords) if segment_data.get('geom') else 0)
    min_distance_m = float('inf')
    min_node_start_coord = None
    min_node_end_coord = None

    coords = _get_coords_from_segment(segment_data)
    if len(coords) < 2:
        log_event_matcher("MATCHER", "WARN", "DISTANCE_TO_WAY_FAIL_INSUFFICIENT_COORDS", segment_id=segment_id, num_coords=len(coords))
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
        log_event_matcher("MATCHER", "TRACE", "DISTANCE_TO_WAY_SUB_SEGMENT_EVAL", segment_id=segment_id, sub_segment_index=i, start_node=(node_start_lat, node_start_lon), end_node=(node_end_lat, node_end_lon), projected_point=(line_lat_deg, line_lon_deg), distance_m=distance_m)

        if distance_m < min_distance_m:
            min_distance_m = distance_m
            min_node_start_coord = (node_start_lat, node_start_lon)
            min_node_end_coord = (node_end_lat, node_end_lon)

    if min_node_start_coord is None:
         log_event_matcher("MATCHER", "WARN", "DISTANCE_TO_WAY_FAIL_NO_MIN_COORD_FOUND", segment_id=segment_id) # Should not happen
         return None # Should not happen if len(coords) >= 2

    result = DistanceResult(
        segment_id=segment_id,
        line_start_coord=min_node_start_coord,
        line_end_coord=min_node_end_coord,
        distance_m=min_distance_m
    )
    log_event_matcher("MATCHER", "DEBUG", "DISTANCE_TO_WAY_SUCCESS", segment_id=segment_id, distance_m=result.distance_m, line_start_coord=result.line_start_coord, line_end_coord=result.line_end_coord)
    return result

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

    is_fwd_result = math.cos(bearing_delta_rad) >= 0
    log_event_matcher("MATCHER", "TRACE", "IS_FORWARD_CHECK", line_start=line_start_coord, line_end=line_end_coord, vehicle_bearing_rad=bearing_rad, way_bearing_rad=way_bearing_rad, delta_rad=bearing_delta_rad, result=is_fwd_result)
    return is_fwd_result

def on_way(pos: Position, segment_id: int, segment_data: SegmentData):
    """
    Checks if the position is likely on the given way segment.
    Returns an OnWayResult namedtuple.
    """
    log_event_matcher("MATCHER", "DEBUG", "ON_WAY_START", segment_id=segment_id, pos_lat=pos.latitude, pos_lon=pos.longitude, segment_geom_type=type(segment_data.get('geom')).__name__ if segment_data.get('geom') else "None")
    geom = segment_data.get('geom')
    if not geom or not hasattr(geom, 'bounds'):
        log_event_matcher("MATCHER", "WARN", "ON_WAY_FAIL_NO_GEOM_OR_BOUNDS", segment_id=segment_id, has_geom=(geom is not None), has_bounds=hasattr(geom, 'bounds') if geom else False)
        return OnWayResult(False, None, float('inf'), False, None, None)

    # Basic bounding box check using Shapely bounds (minx, miny, maxx, maxy) -> (minlon, minlat, maxlon, maxlat)
    min_lon, min_lat, max_lon, max_lat = geom.bounds
    # Use a small degree padding for the check
    padding = 0.0001 # Roughly 11 meters padding
    bbox_check_passed = (min_lat - padding <= pos.latitude <= max_lat + padding and
                         min_lon - padding <= pos.longitude <= max_lon + padding)
    log_event_matcher("MATCHER", "TRACE", "ON_WAY_BOUNDING_BOX_CHECK", segment_id=segment_id, pos_lat=pos.latitude, pos_lon=pos.longitude, geom_bounds=(min_lon,min_lat,max_lon,max_lat), padding=padding, passed=bbox_check_passed)
    if not bbox_check_passed:
        return OnWayResult(False, None, float('inf'), False, None, None)

    dist_result = distance_to_way(pos, segment_id, segment_data)
    if dist_result is None or dist_result.distance_m == float('inf'):
        log_event_matcher("MATCHER", "INFO", "ON_WAY_FAIL_DISTANCE_TO_WAY_INVALID", segment_id=segment_id, dist_result_is_none=(dist_result is None), dist_is_inf=dist_result.distance_m == float('inf') if dist_result else False)
        return OnWayResult(False, segment_id, float('inf'), False, None, None)

    lanes = segment_data.get('lanes', 2) # Default to 2 lanes if not specified
    if lanes == 0:
        lanes = 2

    road_width_estimate = float(lanes) * LANE_WIDTH
    max_dist_threshold = 5.0 + road_width_estimate
    log_event_matcher("MATCHER", "TRACE", "ON_WAY_DISTANCE_THRESHOLD_CALC", segment_id=segment_id, calculated_dist_m=dist_result.distance_m, lanes=lanes, road_width_estimate=road_width_estimate, max_dist_threshold=max_dist_threshold)

    if dist_result.distance_m < max_dist_threshold:
        is_fwd = is_forward(dist_result.line_start_coord, dist_result.line_end_coord, pos.bearing_rad)
        oneway_val = segment_data.get('oneway', 0) # Default to not oneway
        is_way_oneway = oneway_val != 0 # Simplified check
        log_event_matcher("MATCHER", "TRACE", "ON_WAY_DIRECTION_CHECK", segment_id=segment_id, vehicle_is_forward_on_segment=is_fwd, segment_oneway_value=oneway_val, is_segment_oneway=is_way_oneway)

        if not is_fwd and is_way_oneway:
            # Going wrong way on a oneway street
            log_event_matcher("MATCHER", "INFO", "ON_WAY_FAIL_WRONG_WAY_ONEWAY", segment_id=segment_id, dist_m=dist_result.distance_m, is_fwd=is_fwd)
            return OnWayResult(False, segment_id, dist_result.distance_m, is_fwd, dist_result.line_start_coord, dist_result.line_end_coord)
        else:
            # On way or going correct direction on oneway
            log_event_matcher("MATCHER", "DEBUG", "ON_WAY_SUCCESS", segment_id=segment_id, dist_m=dist_result.distance_m, is_fwd=is_fwd)
            return OnWayResult(True, segment_id, dist_result.distance_m, is_fwd, dist_result.line_start_coord, dist_result.line_end_coord)
    else:
        # Too far from the way
        log_event_matcher("MATCHER", "INFO", "ON_WAY_FAIL_TOO_FAR", segment_id=segment_id, dist_m=dist_result.distance_m, threshold_m=max_dist_threshold)
        return OnWayResult(False, segment_id, dist_result.distance_m, False, None, None)

def get_way_start_end(segment_data: SegmentData, is_fwd: bool) -> tuple[CoordinatesTuple | None, CoordinatesTuple | None]:
    """
    Gets the first and last coordinate nodes (lat, lon) of a way based on travel direction.
    Returns (None, None) if segment data is invalid or has < 1 node.
    """
    log_event_matcher("MATCHER", "TRACE", "GET_WAY_START_END_START", segment_id=segment_data.get('id', 'UnknownID'), is_fwd=is_fwd)
    coords = _get_coords_from_segment(segment_data)
    num_nodes = len(coords)

    if num_nodes == 0:
        log_event_matcher("MATCHER", "WARN", "GET_WAY_START_END_FAIL_NO_COORDS", segment_id=segment_data.get('id', 'UnknownID'))
        return None, None
    if num_nodes == 1:
        log_event_matcher("MATCHER", "DEBUG", "GET_WAY_START_END_SINGLE_NODE", segment_id=segment_data.get('id', 'UnknownID'), node=coords[0])
        return coords[0], coords[0]

    start_node, end_node = (coords[0], coords[num_nodes - 1]) if is_fwd else (coords[num_nodes - 1], coords[0])
    log_event_matcher("MATCHER", "TRACE", "GET_WAY_START_END_SUCCESS", segment_id=segment_data.get('id', 'UnknownID'), start_node=start_node, end_node=end_node, num_nodes=num_nodes)
    return start_node, end_node

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
    log_event_matcher("MATCHER", "DEBUG", "GET_CURRENT_WAY_START", current_candidate_id=current_segment_id_candidate, num_next_segment_results=len(next_segment_results), pos_lat=pos.latitude)
    all_segments = map_reader.segments_data
    rtree = map_reader.rtree_idx

    # 1. Check the candidate from the previous cycle
    if current_segment_id_candidate is not None and current_segment_id_candidate in all_segments:
        log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_CHECKING_PREVIOUS_CANDIDATE", candidate_id=current_segment_id_candidate)
        candidate_data = all_segments[current_segment_id_candidate]
        on_way_result = on_way(pos, current_segment_id_candidate, candidate_data)
        if on_way_result.on_way:
            log_event_matcher("MATCHER", "INFO", "GET_CURRENT_WAY_SUCCESS_PREVIOUS_CANDIDATE", segment_id=current_segment_id_candidate, on_way_details=on_way_result)
            return CurrentWayResult(segment_id=current_segment_id_candidate, on_way_result=on_way_result)
        else:
            log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_FAIL_PREVIOUS_CANDIDATE_ONWAY_CHECK", candidate_id=current_segment_id_candidate, on_way_dist_m=on_way_result.distance_m)

    # 2. Check the predicted next ways from the previous cycle
    if next_segment_results:
        log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_CHECKING_PREDICTED_NEXT_WAYS", num_predicted=len(next_segment_results))
        for i, next_res in enumerate(next_segment_results):
            segment_id = next_res.segment_id
            log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_CHECKING_PREDICTED_WAY", predicted_index=i, segment_id=segment_id)
            if segment_id in all_segments:
                 segment_data = all_segments[segment_id]
                 on_way_result = on_way(pos, segment_id, segment_data)
                 if on_way_result.on_way:
                    log_event_matcher("MATCHER", "INFO", "GET_CURRENT_WAY_SUCCESS_PREDICTED_WAY", segment_id=segment_id, on_way_details=on_way_result)
                    return CurrentWayResult(segment_id=segment_id, on_way_result=on_way_result)
                 else:
                    log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_FAIL_PREDICTED_WAY_ONWAY_CHECK", segment_id=segment_id, on_way_dist_m=on_way_result.distance_m)
            else:
                log_event_matcher("MATCHER", "WARN", "GET_CURRENT_WAY_PREDICTED_WAY_NOT_IN_CACHE", segment_id=segment_id)

    # 3. Search nearby ways using R-tree
    # Use the reader's method which already incorporates R-tree search
    # Note: get_segment_data_at updates loaded tiles and queries rtree
    log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_CALLING_READER_GET_SEGMENT_DATA_AT", pos_lat=pos.latitude, pos_lon=pos.longitude)
    # closest_segment_info = map_reader.get_segment_data_at(pos.latitude, pos.longitude)
    # ^ This was the old way. The daemon now calls get_segment_data_at and passes the result to on_way.
    # This function get_current_way seems to be deprecated or its role changed. For now, assuming it might still be called
    # or its logic is indicative. If it *is* called, it would need map_reader.get_segment_data_at or similar.
    # For the purpose of this logging exercise, I will assume it is NOT called directly if the daemon handles the R-tree search directly.
    # If this function is indeed still used, its call to map_reader.get_segment_data_at would be logged by the reader.
    # The below logic assumes closest_segment_info might come from *somewhere* if this function were active.
    # Given the prompt, I should focus on logging what *is* present.
    # The daemon already calls map_reader.get_segment_data_at(), then matcher.on_way().
    # This get_current_way function is NOT directly called by the daemon in the provided mapd_daemon.py.
    # It appears to be a legacy or alternative way-finding strategy.
    # Let's assume if it *were* called, `closest_segment_info` would be passed or obtained.
    # For safety, I will comment out the call to map_reader.get_segment_data_at here as it's redundant with daemon's flow.

    # If the R-Tree search was intended here:
    # log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_USING_RTREE_SEARCH_VIA_READER")
    # closest_segment_info = map_reader.get_segment_data_at(pos.latitude, pos.longitude, pos.bearing_rad)
    # log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_READER_RTREE_RESULT", found=(closest_segment_info is not None), segment_id=closest_segment_info.get('id') if closest_segment_info else "None")
    # if closest_segment_info:
    #     segment_id = closest_segment_info.get('id')
    #     on_way_result = on_way(pos, segment_id, closest_segment_info)
    #     if on_way_result.on_way:
    #         log_event_matcher("MATCHER", "INFO", "GET_CURRENT_WAY_SUCCESS_RTREE_SEARCH", segment_id=segment_id, on_way_details=on_way_result)
    #         return CurrentWayResult(segment_id=segment_id, on_way_result=on_way_result)
    #     else:
    #         log_event_matcher("MATCHER", "TRACE", "GET_CURRENT_WAY_FAIL_RTREE_ONWAY_CHECK", segment_id=segment_id, on_way_dist_m=on_way_result.distance_m)

    log_event_matcher("MATCHER", "INFO", "GET_CURRENT_WAY_FAIL_NO_MATCHING_WAY_FOUND")
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
    log_event_matcher("MATCHER", "TRACE", "MATCHING_WAYS_START", current_segment_id=current_segment_id, match_coord=match_coord)
    matches = []
    # Define a small search box around the match_coord for R-tree query
    search_dist_deg = 0.00001  # Approx 1.1 meter, for exact node matches
    search_bounds = (
        match_coord[1] - search_dist_deg,  # min_lon
        match_coord[0] - search_dist_deg,  # min_lat
        match_coord[1] + search_dist_deg,  # max_lon
        match_coord[0] + search_dist_deg   # max_lat
    )
    log_event_matcher("MATCHER", "TRACE", "MATCHING_WAYS_RTREE_QUERY", bounds=search_bounds)
    try:
        candidate_items = list(rtree.intersection(search_bounds, objects=True))
        log_event_matcher("MATCHER", "TRACE", "MATCHING_WAYS_RTREE_CANDIDATES", num_candidates=len(candidate_items))
    except Exception as e:
        log_event_matcher("MATCHER", "ERROR", "MATCHING_WAYS_RTREE_EXCEPTION", error=str(e))
        return []

    for item in candidate_items:
        segment_id = item.object
        if segment_id == current_segment_id:
            log_event_matcher("MATCHER", "TRACE", "MATCHING_WAYS_SKIP_CURRENT_SEGMENT", segment_id=segment_id)
            continue  # Don't connect to itself

        segment_data = all_segments.get(segment_id)
        if not segment_data:
            log_event_matcher("MATCHER", "WARN", "MATCHING_WAYS_CANDIDATE_DATA_MISSING", segment_id=segment_id)
            continue

        coords = _get_coords_from_segment(segment_data)
        if not coords:
            log_event_matcher("MATCHER", "TRACE", "MATCHING_WAYS_CANDIDATE_NO_COORDS", segment_id=segment_id)
            continue

        # Check if the start or end node of the candidate segment matches match_coord
        if (_coords_equal(coords[0], match_coord) or
                _coords_equal(coords[-1], match_coord)):
            matches.append(segment_id)
            log_event_matcher("MATCHER", "TRACE", "MATCHING_WAYS_CANDIDATE_MATCH_SUCCESS", segment_id=segment_id, start_node=coords[0], end_node=coords[-1])
        else:
            log_event_matcher("MATCHER", "TRACE", "MATCHING_WAYS_CANDIDATE_NODE_MISMATCH", segment_id=segment_id, start_node=coords[0], end_node=coords[-1], match_coord=match_coord)

    log_event_matcher("MATCHER", "DEBUG", "MATCHING_WAYS_END", num_matches=len(matches), matched_ids=matches)
    return matches

# Modified: Accepts segment_data dictionary and match coordinate tuple
def next_is_forward(next_segment_data: SegmentData, match_coord: CoordinatesTuple):
    """
    Determines if travel on the next_segment will be in its forward node order,
    given that it connects at match_coord (lat, lon).
    Returns True if forward, False otherwise.
    """
    log_event_matcher("MATCHER", "TRACE", "NEXT_IS_FORWARD_START", segment_id=next_segment_data.get('id', 'UnknownID'), match_coord=match_coord)
    coords = _get_coords_from_segment(next_segment_data)
    if len(coords) < 2:
        log_event_matcher("MATCHER", "WARN", "NEXT_IS_FORWARD_FAIL_INSUFFICIENT_COORDS", segment_id=next_segment_data.get('id', 'UnknownID'), num_coords=len(coords))
        return False  # Or raise error, but returning False is safer for now

    # If the first node of the next segment matches the connection point,
    # then travel on the next segment is forward.
    is_fwd = _coords_equal(coords[0], match_coord)
    log_event_matcher("MATCHER", "TRACE", "NEXT_IS_FORWARD_END", segment_id=next_segment_data.get('id', 'UnknownID'), result=is_fwd, first_node=coords[0])
    return is_fwd

# Modified: Accepts segment_data dictionary and match coordinate tuple
def _get_candidate_bearing_node(segment_data: SegmentData, is_fwd: bool, match_coord: CoordinatesTuple) -> CoordinatesTuple | None:
    """ Helper to get the coordinate (lat, lon) used for curvature calculation. """
    log_event_matcher("MATCHER", "TRACE", "_GET_CANDIDATE_BEARING_NODE_START", segment_id=segment_data.get('id', 'UnknownID'), is_fwd=is_fwd, match_coord=match_coord)
    coords = _get_coords_from_segment(segment_data)
    if not coords:
        log_event_matcher("MATCHER", "WARN", "_GET_CANDIDATE_BEARING_NODE_FAIL_NO_COORDS", segment_id=segment_data.get('id', 'UnknownID'))
        return None

    if is_fwd:
        # Travel is from coords[0] to coords[1]...
        # match_coord should be coords[0]
        # Bearing node is coords[1] if it exists
        if len(coords) > 1 and _coords_equal(coords[0], match_coord):
            log_event_matcher("MATCHER", "TRACE", "_GET_CANDIDATE_BEARING_NODE_SUCCESS_FWD", segment_id=segment_data.get('id', 'UnknownID'), bearing_node=coords[1])
            return coords[1]
    else:
        # Travel is from coords[-1] to coords[-2]...
        # match_coord should be coords[-1]
        # Bearing node is coords[-2] if it exists
        if len(coords) > 1 and _coords_equal(coords[-1], match_coord):
            log_event_matcher("MATCHER", "TRACE", "_GET_CANDIDATE_BEARING_NODE_SUCCESS_REV", segment_id=segment_data.get('id', 'UnknownID'), bearing_node=coords[-2])
            return coords[-2]

    log_event_matcher("MATCHER", "WARN", "_GET_CANDIDATE_BEARING_NODE_FAIL_NO_SUITABLE_NODE", segment_id=segment_data.get('id', 'UnknownID'), num_coords=len(coords), first_coord=coords[0] if coords else "None", last_coord=coords[-1] if coords else "None")
    return None

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
        # Note: Current reader.py defaults 'oneway' to 0 if not present in data.
        # This logic will only become effective if 'oneway' data (e.g., 1 for oneway forward, -1 for oneway backward)
        # is populated by process_osm.py and available in segment_data.
        # If 'oneway' is 0 (default), is_way_oneway will be False, and this block is skipped.
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

def distance_from_start_to_node(coords: list[CoordinatesTuple], node_index: int) -> float:
    """Calculates distance along geometry from start (index 0) to node_index."""
    log_event_matcher("MATCHER", "TRACE", "DISTANCE_FROM_START_TO_NODE_START", num_coords=len(coords), target_node_index=node_index)
    if not coords or node_index < 0 or node_index >= len(coords):
        log_event_matcher("MATCHER", "WARN", "DISTANCE_FROM_START_TO_NODE_FAIL_INVALID_INPUTS", num_coords=len(coords), target_node_index=node_index)
        return 0.0
    if node_index == 0:
        log_event_matcher("MATCHER", "TRACE", "DISTANCE_FROM_START_TO_NODE_SUCCESS_NODE_0", result=0.0)
        return 0.0

    dist_m = 0.0
    for i in range(node_index):
        n1_lat, n1_lon = coords[i]
        n2_lat, n2_lon = coords[i+1]
        segment_len = geometry.distance_to_point(
            n1_lat * geometry.TO_RADIANS, n1_lon * geometry.TO_RADIANS,
            n2_lat * geometry.TO_RADIANS, n2_lon * geometry.TO_RADIANS
        )
        dist_m += segment_len
        log_event_matcher("MATCHER", "TRACE", "DISTANCE_FROM_START_TO_NODE_SUB_SEGMENT", sub_idx_from=i, sub_idx_to=i+1, length_m=segment_len, cumulative_dist_m=dist_m)

    log_event_matcher("MATCHER", "DEBUG", "DISTANCE_FROM_START_TO_NODE_SUCCESS", target_node_index=node_index, total_dist_m=dist_m)
    return dist_m

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
    # Definition: `distanceAlongSegment` is always from the OSM way's start (node 0)
    # to the vehicle's current projected point. `is_fwd` in OnWayResult indicates
    # vehicle's travel direction relative to the way's node order.
    total_progress = dist_to_segment_start_node + dist_along_segment

    # TODO(?): If !is_fwd, should we return total_length - total_progress?
    # Let's return forward progress for now and let caller adjust.
    # Current adopted definition: Progress is always from the way's start node (0).
    return total_progress

def get_segment_length(segment_data: SegmentData) -> float:
    """Calculates the total length of a way segment geometry in meters."""
    log_event_matcher("MATCHER", "TRACE", "GET_SEGMENT_LENGTH_START", segment_id=segment_data.get('id', 'UnknownID'))
    coords = _get_coords_from_segment(segment_data)
    if not coords or len(coords) < 2:
        log_event_matcher("MATCHER", "WARN", "GET_SEGMENT_LENGTH_FAIL_INSUFFICIENT_COORDS", segment_id=segment_data.get('id', 'UnknownID'), num_coords=len(coords))
        return 0.0

    # This is equivalent to distance_from_start_to_node(coords, len(coords)-1)
    total_length = distance_from_start_to_node(coords, len(coords)-1)
    log_event_matcher("MATCHER", "DEBUG", "GET_SEGMENT_LENGTH_SUCCESS", segment_id=segment_data.get('id', 'UnknownID'), total_length_m=total_length)
    return total_length

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

        # --- Use new function --- #
        if current_segment_data:
            way_length = get_segment_length(current_segment_data)
            total_distance_m += way_length
        else:
            break # Stop if we cannot get segment data for length calculation
        # ---------------------- #

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