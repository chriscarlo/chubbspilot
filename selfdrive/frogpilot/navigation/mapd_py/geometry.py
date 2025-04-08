import math
import numpy as np

# Constants based on mapd_source/math.go
R = 6373000.0             # Approximate radius of Earth in meters
TO_RADIANS = math.pi / 180.0
TO_DEGREES = 180.0 / math.pi

# Earth radius in meters (using WGS84 value)
EARTH_RADIUS_M = 6378137.0

# Padding constant, approximately 10 meters in degrees latitude
# Used for bounding box expansion, etc. (Referenced by matcher.py)
PADDING = 10.0 / EARTH_RADIUS_M * TO_DEGREES # Approx 0.00009 degrees

# Consider adding other potentially useful constants from math.go if needed later
# LANE_WIDTH = 3.7
# QUERY_RADIUS = 3000.0
# TARGET_LAT_ACCEL = 2.0 # This will likely be handled by VTSC/MTSC logic


def distance_to_point(lat_a_rad, lon_a_rad, lat_b_rad, lon_b_rad):
    """
    Calculates the Haversine distance between two points given in radians.
    Equivalent to DistanceToPoint in math.go.
    """
    # Check for identical points to avoid domain errors in sqrt
    if lat_a_rad == lat_b_rad and lon_a_rad == lon_b_rad:
        return 0.0

    a = (math.sin((lat_b_rad - lat_a_rad) / 2) ** 2 +
         math.cos(lat_a_rad) * math.cos(lat_b_rad) *
         math.sin((lon_b_rad - lon_a_rad) / 2) ** 2)

    # Handle potential floating point inaccuracies leading to a > 1
    a = min(a, 1.0)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c  # Distance in meters

def vector(lat_a_rad, lon_a_rad, lat_b_rad, lon_b_rad):
    """
    Calculates the vector components for bearing calculation.
    Equivalent to Vector in math.go.
    Input angles must be in radians.
    """
    dlon = lon_b_rad - lon_a_rad
    x = math.sin(dlon) * math.cos(lat_b_rad)
    y = (math.cos(lat_a_rad) * math.sin(lat_b_rad) -
         (math.sin(lat_a_rad) * math.cos(lat_b_rad) * math.cos(dlon)))
    return x, y

def bearing(lat_a_deg, lon_a_deg, lat_b_deg, lon_b_deg):
    """
    Calculates the initial bearing (azimuth) from point A to point B.
    Equivalent to Bearing in math.go.
    Input angles are in degrees, converts them to radians internally.
    Returns bearing in radians (from -pi to pi).
    """
    lat_a_rad = lat_a_deg * TO_RADIANS
    lon_a_rad = lon_a_deg * TO_RADIANS
    lat_b_rad = lat_b_deg * TO_RADIANS
    lon_b_rad = lon_b_deg * TO_RADIANS

    x, y = vector(lat_a_rad, lon_a_rad, lat_b_rad, lon_b_rad)
    # atan2(y, x) gives bearing East of North in Nav standard, Go used atan2(x, y)
    # We replicate the Go code's atan2(x, y) which gives bearing East of North
    # Note: Standard geographic bearing often uses atan2(y, x)
    return math.atan2(x, y)

def dot(ax, ay, bx, by):
    """
    Calculates the dot product of two 2D vectors.
    Equivalent to Dot in math.go.
    """
    return (ax * bx) + (ay * by)

def point_on_line(start_lat_deg, start_lon_deg, end_lat_deg, end_lon_deg, point_lat_deg, point_lon_deg):
    """
    Finds the closest point on a line segment (defined by start and end) to a given point.
    Equivalent to PointOnLine in math.go.
    Inputs are in degrees.
    Returns the coordinates (latitude, longitude) of the closest point in degrees.
    Uses simple Euclidean approximation, assuming small distances where Mercator distortion is negligible.
    Note: For high accuracy over long distances, spherical geometry should be used.
    """
    ap_lat = point_lat_deg - start_lat_deg
    ap_lon = point_lon_deg - start_lon_deg

    ab_lat = end_lat_deg - start_lat_deg
    ab_lon = end_lon_deg - start_lon_deg

    ab_mag_sq = dot(ab_lat, ab_lon, ab_lat, ab_lon)

    # Handle zero-length line segment
    if ab_mag_sq == 0:
        return start_lat_deg, start_lon_deg

    t = dot(ap_lat, ap_lon, ab_lat, ab_lon) / ab_mag_sq

    # Clamp t to the range [0, 1] to stay within the line segment
    t = max(0.0, min(1.0, t))

    closest_lat = start_lat_deg + t * ab_lat
    closest_lon = start_lon_deg + t * ab_lon

    return closest_lat, closest_lon

def get_curvature(lat_a_deg, lon_a_deg, lat_b_deg, lon_b_deg, lat_c_deg, lon_c_deg):
    """
    Calculates the curvature defined by three points (A, B, C).
    Equivalent to GetCurvature in math.go.
    Inputs are in degrees.
    Returns curvature (1/radius) in 1/meters, arc length (meters) of segment AB, and angle (radians).
    Returns (0, 0, 0) if points are collinear or form a zero-area triangle.
    """
    lat_a_rad = lat_a_deg * TO_RADIANS
    lon_a_rad = lon_a_deg * TO_RADIANS
    lat_b_rad = lat_b_deg * TO_RADIANS
    lon_b_rad = lon_b_deg * TO_RADIANS
    lat_c_rad = lat_c_deg * TO_RADIANS
    lon_c_rad = lon_c_deg * TO_RADIANS

    # Calculate side lengths using Haversine distance
    length_a = distance_to_point(lat_a_rad, lon_a_rad, lat_b_rad, lon_b_rad) # Side c in standard triangle notation (opposite C)
    length_b = distance_to_point(lat_a_rad, lon_a_rad, lat_c_rad, lon_c_rad) # Side b (opposite B)
    length_c = distance_to_point(lat_b_rad, lon_b_rad, lat_c_rad, lon_c_rad) # Side a (opposite A)

    # Check for degenerate triangle (collinear points or zero length sides)
    if length_a * length_b * length_c == 0:
        return 0.0, 0.0, 0.0

    # Calculate the semi-perimeter
    sp = (length_a + length_b + length_c) / 2.0

    # Calculate area using Heron's formula
    # Handle potential floating point issues where sp < side_length slightly
    area_sq_arg = sp * max(0.0, sp - length_a) * max(0.0, sp - length_b) * max(0.0, sp - length_c)
    if area_sq_arg <= 0:
        # Collinear points
        return 0.0, length_a, 0.0 # Return 0 curvature, length of first segment, 0 angle

    area = math.sqrt(area_sq_arg)

    # Calculate curvature (K = 4 * Area / (abc))
    # This is derived from the circumradius R = abc / (4 * Area) and K = 1/R
    curvature = (4.0 * area) / (length_a * length_b * length_c)

    # Avoid division by zero if curvature is effectively zero
    if curvature < 1e-9: # Use a small epsilon
       # For near-straight lines, the angle is small, arc length approx equals chord length
       return 0.0, length_a, 0.0

    radius = 1.0 / curvature

    # Calculate the angle subtended by the chord length_b at the center of the circumcircle
    # Using Law of Cosines on the isosceles triangle formed by two radii and length_b:
    # length_b^2 = radius^2 + radius^2 - 2 * radius * radius * cos(angle)
    # length_b^2 = 2 * radius^2 * (1 - cos(angle))
    # cos(angle) = 1 - (length_b^2 / (2 * radius^2))
    # Handle potential floating point issues where the argument might be slightly outside [-1, 1]
    cos_angle_arg = (2.0 * radius**2 - length_b**2) / (2.0 * radius**2)
    cos_angle_arg = max(-1.0, min(1.0, cos_angle_arg))
    angle = math.acos(cos_angle_arg)

    # Arc length is radius * angle (where angle is in radians)
    # The Go code seems to return length_a here, let's verify which arc length is intended.
    # Based on the usage in GetCurvatures, it seems to be the arc length corresponding to the middle point (B).
    # However, the Go implementation calculates angle based on length_b but returns length_a... odd.
    # Let's stick to what the Go code calculates for now, which seems to be angle related to length_b,
    # but the arc length returned is just length_a (the chord length AB).
    # Revisit if MTSC requires the actual arc length of the curve segment.
    arc_length = length_a # Replicating Go code's apparent return value for arc_length

    # Let's calculate the *actual* arc length related to the angle we found for completeness, though unused for now:
    # actual_arc_length = radius * angle

    # Determine the sign of the curvature (left or right turn)
    # Check orientation using the cross-product of vectors AB and BC in the tangent plane
    # Simplified approach: compare bearings
    bearing_ab = bearing(lat_a_deg, lon_a_deg, lat_b_deg, lon_b_deg)
    bearing_bc = bearing(lat_b_deg, lon_b_deg, lat_c_deg, lon_c_deg)
    bearing_diff = bearing_bc - bearing_ab

    # Normalize bearing difference to (-pi, pi]
    while bearing_diff <= -math.pi:
        bearing_diff += 2 * math.pi
    while bearing_diff > math.pi:
        bearing_diff -= 2 * math.pi

    # Positive difference usually means left turn, negative means right turn
    if bearing_diff < 0:
        curvature *= -1.0

    return curvature, arc_length, angle


# --- Functions below might be needed for path finding / matching ---

def get_curvatures(lat_points_deg, lon_points_deg):
    """
    Calculates curvatures for a series of points.
    Equivalent to GetCurvatures in math.go.
    Inputs are lists/arrays of latitudes and longitudes in degrees.
    Returns tuple: (list of curvatures, list of arc lengths)
    """
    if len(lat_points_deg) < 3:
        # raise ValueError("Need at least 3 points to calculate curvatures")
        return [], [] # Return empty lists, similar to Go error handling

    num_curvatures = len(lat_points_deg) - 2
    curvatures = [0.0] * num_curvatures
    arc_lengths = [0.0] * num_curvatures # Corresponds to length_a in get_curvature

    for i in range(num_curvatures):
        curv, arc_len, _ = get_curvature(
            lat_points_deg[i], lon_points_deg[i],
            lat_points_deg[i+1], lon_points_deg[i+1],
            lat_points_deg[i+2], lon_points_deg[i+2]
        )
        curvatures[i] = curv
        arc_lengths[i] = arc_len

    return curvatures, arc_lengths


# Note: GetAverageCurvatures, GetStateCurvatures, GetTargetVelocities from math.go
# depend on the 'State' and Capnp structures, so they would likely belong in
# the MTSC or a dedicated path processing module rather than pure geometry.