#!/usr/bin/env python3
"""
Unified Turn Speed Controller combining map and vision data.
This replaces the separate MTSC and VTSC controllers with a single unified approach.
"""

import time
import numpy as np
from typing import Optional, Tuple

import cereal.messaging as messaging
from cereal import log
from common.numpy_fast import clip
from common.realtime import DT_CTRL
from common.params import Params
from system.swaglog import cloudlog

from selfdrive.frogpilot.controls.lib.turn_speed_common import (
    curvature_to_safe_speed,
    calculate_curvature_from_points,
    blend_speed_profiles,
    TurnSpeedProfile,
    smooth_speed_profile,
    TARGET_LAT_ACCEL_BASE,
    MAX_SPEED
)

# Import existing controllers for gradual migration
from selfdrive.frogpilot.controls.lib.chauffeur_mtsc import ChauffeurMtsc
from selfdrive.frogpilot.controls.lib.chauffeur_vtsc import VisionTurnSpeedController


class UnifiedTurnController:
    """
    Unified controller that combines map and vision data for turn speed control.
    
    This controller can operate in multiple modes:
    - map_only: Use only map data (like MTSC)
    - vision_only: Use only vision data (like VTSC)
    - combined: Use both sources with intelligent blending
    - legacy: Use original MTSC/VTSC controllers (for testing)
    """
    
    def __init__(self, params: Optional[Params] = None):
        self.params = params or Params()
        
        # Operating mode
        self.mode = "combined"  # Default to combined mode
        self.blend_mode = "minimum"  # How to blend speeds
        
        # Sub-controllers for legacy mode and data acquisition
        self.mtsc = ChauffeurMtsc()
        self.vtsc = VisionTurnSpeedController()
        
        # State
        self.last_update_time = 0.0
        self.map_profile: Optional[TurnSpeedProfile] = None
        self.vision_profile: Optional[TurnSpeedProfile] = None
        self.combined_profile: Optional[TurnSpeedProfile] = None
        
        # Configuration
        self.lookahead_distance = 250.0  # meters
        self.smoothing_enabled = True
        self.smoothing_distance = 50.0
        self.smoothing_factor = 0.3
        
        # Logging
        self.log_data = {
            "mode": self.mode,
            "map_available": False,
            "vision_available": False,
            "min_speed_map": MAX_SPEED,
            "min_speed_vision": MAX_SPEED,
            "min_speed_combined": MAX_SPEED,
            "target_speed": MAX_SPEED
        }
    
    def set_mode(self, mode: str):
        """Set operating mode: map_only, vision_only, combined, or legacy."""
        valid_modes = ["map_only", "vision_only", "combined", "legacy"]
        if mode in valid_modes:
            self.mode = mode
            cloudlog.info(f"UnifiedTurnController mode set to: {mode}")
        else:
            cloudlog.warning(f"Invalid mode: {mode}, keeping current mode: {self.mode}")
    
    def set_blend_mode(self, blend_mode: str):
        """Set blending mode: minimum, weighted, or adaptive."""
        valid_modes = ["minimum", "weighted", "adaptive"]
        if blend_mode in valid_modes:
            self.blend_mode = blend_mode
            cloudlog.info(f"UnifiedTurnController blend mode set to: {blend_mode}")
    
    def update(
        self,
        v_ego: float,
        a_ego: float,
        v_cruise: float,
        modelData: Optional[log.ModelDataV2] = None,
        frogpilot_toggles: Optional[dict] = None
    ) -> Tuple[float, Optional[TurnSpeedProfile]]:
        """
        Main update function called every control cycle.
        
        Args:
            v_ego: Current vehicle speed (m/s)
            a_ego: Current vehicle acceleration (m/s²)
            v_cruise: Cruise control set speed (m/s)
            modelData: Vision model output (optional)
            frogpilot_toggles: Configuration toggles (optional)
        
        Returns:
            Tuple of (target_speed, speed_profile)
        """
        self.last_update_time = time.monotonic()
        
        # Extract aggressiveness from toggles
        aggressiveness = 1.0
        if frogpilot_toggles:
            aggressiveness = frogpilot_toggles.get('turn_aggressiveness', 1.0)
        
        # Legacy mode - use original controllers
        if self.mode == "legacy":
            return self._update_legacy(v_ego, a_ego, v_cruise, modelData, frogpilot_toggles)
        
        # Get data from both sources
        self._update_map_profile(v_ego, a_ego, v_cruise, aggressiveness, frogpilot_toggles)
        self._update_vision_profile(v_ego, modelData, aggressiveness)
        
        # Determine which sources are available
        map_available = self.map_profile is not None and len(self.map_profile.distances) > 0
        vision_available = self.vision_profile is not None and len(self.vision_profile.distances) > 0
        
        # Select profile based on mode and availability
        if self.mode == "map_only" and map_available:
            self.combined_profile = self.map_profile
        elif self.mode == "vision_only" and vision_available:
            self.combined_profile = self.vision_profile
        elif self.mode == "combined":
            self.combined_profile = self._combine_profiles(
                self.map_profile if map_available else None,
                self.vision_profile if vision_available else None,
                aggressiveness
            )
        else:
            # No data available
            self.combined_profile = None
        
        # Apply smoothing if enabled
        if self.combined_profile and self.smoothing_enabled:
            self.combined_profile = smooth_speed_profile(
                self.combined_profile,
                self.smoothing_distance,
                self.smoothing_factor
            )
        
        # Calculate target speed
        if self.combined_profile:
            min_speed, dist_to_min = self.combined_profile.get_min_speed_ahead(self.lookahead_distance)
            target_speed = min(min_speed, v_cruise)
        else:
            target_speed = v_cruise
        
        # Update logging data
        self.log_data.update({
            "mode": self.mode,
            "map_available": map_available,
            "vision_available": vision_available,
            "min_speed_map": self.map_profile.get_min_speed_ahead(self.lookahead_distance)[0] if map_available else MAX_SPEED,
            "min_speed_vision": self.vision_profile.get_min_speed_ahead(self.lookahead_distance)[0] if vision_available else MAX_SPEED,
            "min_speed_combined": min_speed if self.combined_profile else MAX_SPEED,
            "target_speed": target_speed
        })
        
        return target_speed, self.combined_profile
    
    def _update_legacy(
        self,
        v_ego: float,
        a_ego: float,
        v_cruise: float,
        modelData: Optional[log.ModelDataV2],
        frogpilot_toggles: Optional[dict]
    ) -> Tuple[float, Optional[TurnSpeedProfile]]:
        """Legacy mode using original MTSC and VTSC controllers."""
        # Get map profile from MTSC
        map_dist, map_speeds = self.mtsc.update(v_ego, a_ego, v_cruise, frogpilot_toggles or {})
        map_profile = None
        if map_dist is not None and map_speeds is not None:
            map_profile = (map_dist, map_speeds)
        
        # Get target from VTSC (which now incorporates map data)
        aggressiveness = 1.0
        if frogpilot_toggles:
            aggressiveness = frogpilot_toggles.get('turn_aggressiveness', 1.0)
        
        vtsc_target = self.vtsc.update(
            v_ego,
            v_cruise,
            map_speed_profile=map_profile,
            turn_aggressiveness=aggressiveness
        )
        
        # Convert to profile for consistency
        if map_profile:
            profile = TurnSpeedProfile(map_profile[0], map_profile[1], "legacy")
        else:
            # Create simple profile with just current target
            profile = TurnSpeedProfile(
                np.array([0.0, 100.0]),
                np.array([vtsc_target, vtsc_target]),
                "legacy"
            )
        
        return vtsc_target, profile
    
    def _update_map_profile(
        self,
        v_ego: float,
        a_ego: float,
        v_cruise: float,
        aggressiveness: float,
        frogpilot_toggles: Optional[dict]
    ):
        """Update map-based speed profile using MTSC data."""
        # Get raw profile from MTSC
        map_dist, map_speeds = self.mtsc.update(v_ego, a_ego, v_cruise, frogpilot_toggles or {})
        
        if map_dist is not None and map_speeds is not None and len(map_dist) > 0:
            # Apply aggressiveness scaling to speeds
            # Higher aggressiveness = higher speeds through turns
            adjusted_speeds = map_speeds * clip(aggressiveness, 0.5, 2.0)
            adjusted_speeds = np.clip(adjusted_speeds, 0, MAX_SPEED)
            
            self.map_profile = TurnSpeedProfile(map_dist, adjusted_speeds, "map")
        else:
            self.map_profile = None
    
    def _update_vision_profile(
        self,
        v_ego: float,
        modelData: Optional[log.ModelDataV2],
        aggressiveness: float
    ):
        """Update vision-based speed profile from model data."""
        if not modelData or not hasattr(modelData, 'orientationRate'):
            self.vision_profile = None
            return
        
        try:
            # Extract model predictions
            orientation_rate = modelData.orientationRate.z
            velocity_pred = modelData.velocity.x
            times = np.array(modelData.position.t)
            
            if len(orientation_rate) < 3 or len(velocity_pred) < 3:
                self.vision_profile = None
                return
            
            # Calculate distances from velocities and times
            dt_array = np.diff(times)
            distances = np.zeros(len(times))
            if len(times) > 1:
                distances[1:] = np.cumsum((velocity_pred[:-1] + velocity_pred[1:]) / 2.0 * dt_array)
            
            # Calculate curvatures
            eps = 1e-9
            curvatures = np.abs(orientation_rate) / np.maximum(velocity_pred, eps)
            
            # Convert curvatures to safe speeds
            safe_speeds = np.array([
                curvature_to_safe_speed(curv, aggressiveness)
                for curv in curvatures
            ])
            
            self.vision_profile = TurnSpeedProfile(distances, safe_speeds, "vision")
            
        except Exception as e:
            cloudlog.error(f"Error updating vision profile: {e}")
            self.vision_profile = None
    
    def _combine_profiles(
        self,
        map_profile: Optional[TurnSpeedProfile],
        vision_profile: Optional[TurnSpeedProfile],
        aggressiveness: float
    ) -> Optional[TurnSpeedProfile]:
        """Combine map and vision profiles intelligently."""
        # If only one source available, use it
        if not map_profile:
            return vision_profile
        if not vision_profile:
            return map_profile
        
        # Find common distance range
        max_dist = min(
            map_profile.distances[-1] if len(map_profile.distances) > 0 else 0,
            vision_profile.distances[-1] if len(vision_profile.distances) > 0 else 0
        )
        
        if max_dist <= 0:
            return None
        
        # Create unified distance grid
        num_points = 50
        distances = np.linspace(0, max_dist, num_points)
        
        # Interpolate both profiles to common grid
        map_speeds = np.array([
            map_profile.interpolate_speed_at_distance(d)
            for d in distances
        ])
        vision_speeds = np.array([
            vision_profile.interpolate_speed_at_distance(d)
            for d in distances
        ])
        
        # Calculate confidence based on data characteristics
        # Map confidence is higher for longer distances
        map_confidence = np.ones_like(distances)
        vision_confidence = np.exp(-distances / 100.0)  # Decays with distance
        
        # Blend speeds
        combined_speeds = np.zeros_like(distances)
        for i in range(len(distances)):
            combined_speeds[i] = blend_speed_profiles(
                vision_speeds[i],
                map_speeds[i],
                vision_confidence[i],
                map_confidence[i],
                self.blend_mode
            )
        
        return TurnSpeedProfile(distances, combined_speeds, "combined")
    
    def get_diagnostics(self) -> dict:
        """Get diagnostic information for debugging and UI display."""
        return self.log_data.copy()
    
    def shutdown(self):
        """Clean shutdown of sub-controllers."""
        self.mtsc.shutdown()
        # VTSC doesn't have explicit shutdown