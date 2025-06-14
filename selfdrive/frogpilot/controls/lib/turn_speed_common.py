#!/usr/bin/env python3
"""
Common turn speed control logic for unifying MTSC and VTSC.
This module contains shared functions and classes for computing turn speeds
from curvature data, regardless of whether the source is map or vision.
"""

import math
import numpy as np
from typing import Tuple, Optional

from openpilot.common.conversions import Conversions as CV
from openpilot.common.numpy_fast import clip


# Physics constants
TARGET_LAT_ACCEL_BASE = 2.0  # m/s² - base lateral acceleration for comfort
MIN_SPEED = 5.0  # m/s - minimum speed to consider
MAX_SPEED = 70.0  # m/s - maximum reasonable speed (~156 mph)

# Aggressiveness tuning
AGGR_MIN = 0.5  # Conservative driving
AGGR_MAX = 2.0  # Aggressive driving  
AGGR_DEFAULT = 1.0  # Normal driving


def curvature_to_safe_speed(curvature: float, aggressiveness: float = AGGR_DEFAULT) -> float:
    """
    Calculate safe speed for a given curvature using physics formula.
    
    Args:
        curvature: Road curvature in 1/meters (1/radius)
        aggressiveness: Factor to scale lateral acceleration (0.5-2.0)
    
    Returns:
        Safe speed in m/s
    """
    if abs(curvature) < 1e-7:  # Essentially straight
        return MAX_SPEED
    
    # Scale target lateral acceleration by aggressiveness
    target_lat_accel = TARGET_LAT_ACCEL_BASE * clip(aggressiveness, AGGR_MIN, AGGR_MAX)
    
    # Physics: v = sqrt(a_lat / curvature)
    # where a_lat is lateral acceleration and curvature = 1/radius
    try:
        safe_speed = math.sqrt(target_lat_accel / abs(curvature))
        return clip(safe_speed, MIN_SPEED, MAX_SPEED)
    except (ValueError, ZeroDivisionError):
        return MAX_SPEED


def calculate_curvature_from_points(
    lat1: float, lon1: float, 
    lat2: float, lon2: float,
    lat3: float, lon3: float
) -> float:
    """
    Calculate curvature from three GPS points using the three-point method.
    This matches the mapd algorithm for consistency.
    
    Args:
        lat1, lon1: First point (degrees)
        lat2, lon2: Second point (degrees)  
        lat3, lon3: Third point (degrees)
    
    Returns:
        Curvature in 1/meters
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    lat3_rad = math.radians(lat3)
    lon3_rad = math.radians(lon3)
    
    # Earth radius in meters
    R = 6371000.0
    
    # Calculate distances using haversine formula
    def haversine(lat_a, lon_a, lat_b, lon_b):
        dlat = lat_b - lat_a
        dlon = lon_b - lon_a
        a = math.sin(dlat/2)**2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    length_a = haversine(lat1_rad, lon1_rad, lat2_rad, lon2_rad)
    length_b = haversine(lat1_rad, lon1_rad, lat3_rad, lon3_rad)
    length_c = haversine(lat2_rad, lon2_rad, lat3_rad, lon3_rad)
    
    # Calculate area using Heron's formula
    sp = (length_a + length_b + length_c) / 2
    try:
        area = math.sqrt(sp * (sp - length_a) * (sp - length_b) * (sp - length_c))
    except ValueError:
        return 0.0  # Degenerate triangle
    
    # Calculate curvature
    if length_a * length_b * length_c == 0:
        return 0.0
    
    curvature = (4 * area) / (length_a * length_b * length_c)
    return curvature


def blend_speed_profiles(
    vision_speed: float,
    map_speed: float,
    vision_confidence: float = 1.0,
    map_confidence: float = 1.0,
    blend_mode: str = "minimum"
) -> float:
    """
    Blend speed recommendations from vision and map sources.
    
    Args:
        vision_speed: Speed recommendation from vision (m/s)
        map_speed: Speed recommendation from map (m/s)
        vision_confidence: Confidence in vision data (0-1)
        map_confidence: Confidence in map data (0-1)
        blend_mode: How to blend ("minimum", "weighted", "adaptive")
    
    Returns:
        Blended speed recommendation (m/s)
    """
    # Handle cases where one source is unavailable
    if vision_speed <= 0 or vision_confidence <= 0:
        return map_speed if map_speed > 0 else MAX_SPEED
    if map_speed <= 0 or map_confidence <= 0:
        return vision_speed if vision_speed > 0 else MAX_SPEED
    
    if blend_mode == "minimum":
        # Safety-first: use the lower of the two speeds
        return min(vision_speed, map_speed)
    
    elif blend_mode == "weighted":
        # Weighted average based on confidence
        total_confidence = vision_confidence + map_confidence
        if total_confidence > 0:
            weight_vision = vision_confidence / total_confidence
            weight_map = map_confidence / total_confidence
            return weight_vision * vision_speed + weight_map * map_speed
        else:
            return min(vision_speed, map_speed)
    
    elif blend_mode == "adaptive":
        # Adaptive blending based on which source sees a tighter curve
        # If one source sees a much tighter curve, trust it more
        speed_diff = abs(vision_speed - map_speed)
        if speed_diff < 5.0:  # Similar speeds, average them
            return (vision_speed + map_speed) / 2.0
        elif vision_speed < map_speed:
            # Vision sees tighter curve, weight it more
            return 0.7 * vision_speed + 0.3 * map_speed
        else:
            # Map sees tighter curve, weight it more
            return 0.3 * vision_speed + 0.7 * map_speed
    
    else:
        # Default to minimum for safety
        return min(vision_speed, map_speed)


class TurnSpeedProfile:
    """
    Container for a turn speed profile with distances and speeds.
    Used to pass data between controllers.
    """
    def __init__(self, distances: np.ndarray, speeds: np.ndarray, source: str = "unknown"):
        """
        Args:
            distances: Array of distances ahead (meters)
            speeds: Array of safe speeds at each distance (m/s)
            source: Source of the data ("map", "vision", "combined")
        """
        self.distances = distances
        self.speeds = speeds
        self.source = source
        
        # Validate arrays have same length
        if len(distances) != len(speeds):
            raise ValueError("Distance and speed arrays must have same length")
    
    def get_min_speed_ahead(self, lookahead_distance: float) -> Tuple[float, float]:
        """
        Get the minimum speed within a lookahead distance.
        
        Args:
            lookahead_distance: How far ahead to look (meters)
        
        Returns:
            Tuple of (min_speed, distance_to_min_speed)
        """
        if len(self.distances) == 0:
            return MAX_SPEED, 0.0
        
        # Find points within lookahead distance
        mask = self.distances <= lookahead_distance
        if not np.any(mask):
            # No points within lookahead, return first point
            return float(self.speeds[0]), float(self.distances[0])
        
        valid_speeds = self.speeds[mask]
        valid_distances = self.distances[mask]
        
        min_idx = np.argmin(valid_speeds)
        return float(valid_speeds[min_idx]), float(valid_distances[min_idx])
    
    def interpolate_speed_at_distance(self, distance: float) -> float:
        """
        Get interpolated speed at a specific distance.
        
        Args:
            distance: Distance ahead (meters)
        
        Returns:
            Interpolated speed (m/s)
        """
        if len(self.distances) == 0:
            return MAX_SPEED
        
        # Use numpy interpolation
        return float(np.interp(distance, self.distances, self.speeds))


def smooth_speed_profile(
    profile: TurnSpeedProfile,
    smoothing_distance: float = 50.0,
    smoothing_factor: float = 0.3
) -> TurnSpeedProfile:
    """
    Apply smoothing to a speed profile to avoid abrupt changes.
    
    Args:
        profile: Input speed profile
        smoothing_distance: Distance over which to smooth (meters)
        smoothing_factor: How much to smooth (0=none, 1=maximum)
    
    Returns:
        Smoothed speed profile
    """
    if len(profile.distances) < 2:
        return profile
    
    # Create copy of speeds to modify
    smoothed_speeds = profile.speeds.copy()
    
    # Apply exponential moving average
    for i in range(1, len(smoothed_speeds)):
        dist_diff = profile.distances[i] - profile.distances[i-1]
        if dist_diff > 0:
            # Calculate smoothing weight based on distance
            weight = math.exp(-dist_diff / smoothing_distance) * smoothing_factor
            smoothed_speeds[i] = weight * smoothed_speeds[i-1] + (1 - weight) * smoothed_speeds[i]
    
    return TurnSpeedProfile(profile.distances, smoothed_speeds, profile.source)


# Backward compatibility function for VTSC
def curvature_based_lat_accel(abs_curvature: float) -> float:
    """
    Legacy function for backward compatibility with existing VTSC code.
    Returns lateral acceleration for a given curvature.
    """
    # This maintains the sigmoid-based acceleration profile from MTSC
    high, low, span, center, k = 3.2, 1.5, 1.7, 0.018, 180.0
    reduction = span / (1.0 + math.exp(-k * (abs_curvature - center)))
    return clip(high - reduction, low, high)