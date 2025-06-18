#!/usr/bin/env python3
"""
Migration helper for transitioning from separate MTSC/VTSC to unified controller.
This provides a compatibility layer and migration path.
"""

from typing import Optional, Tuple
import numpy as np

from common.params import Params
from system.swaglog import cloudlog
from selfdrive.frogpilot.controls.lib.unified_turn_controller import UnifiedTurnController
from selfdrive.frogpilot.controls.lib.turn_speed_common import TurnSpeedProfile


class MigrationController:
    """
    Drop-in replacement for FrogPilotVCruise's use of MTSC and VTSC.
    Provides backward-compatible interface while using unified controller internally.
    """
    
    def __init__(self):
        # Create unified controller
        self.unified = UnifiedTurnController()
        
        # Migration settings
        self.params = Params()
        self.migration_mode = self._get_migration_mode()
        
        # State for compatibility
        self.map_speed_profile = None
        self.vtsc_target = 0.0
        self.vtsc = self  # Self-reference for compatibility
        
        cloudlog.info(f"MigrationController initialized in mode: {self.migration_mode}")
    
    def _get_migration_mode(self) -> str:
        """Determine migration mode from params."""
        # Check for migration parameter
        mode = self.params.get("TurnControllerMode", encoding='utf8')
        
        if mode in ["unified", "combined"]:
            return "unified"
        elif mode == "legacy":
            return "legacy"
        else:
            # Default based on existing toggles
            mtsc_enabled = self.params.get_bool("MapTurnSpeedController")
            vtsc_enabled = self.params.get_bool("VisionTurnSpeedController")
            
            if mtsc_enabled and vtsc_enabled:
                return "unified"  # Both enabled, use unified
            elif mtsc_enabled:
                return "map_only"
            elif vtsc_enabled:
                return "vision_only"
            else:
                return "legacy"  # Neither enabled, use legacy mode
    
    def update_mtsc(
        self,
        v_ego: float,
        a_ego: float,
        v_cruise: float,
        frogpilot_toggles: dict
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        MTSC-compatible update method.
        Returns (distances, speeds) tuple like original MTSC.
        """
        if self.migration_mode == "legacy":
            # Use legacy MTSC directly
            return self.unified.mtsc.update(v_ego, a_ego, v_cruise, frogpilot_toggles)
        
        # In unified mode, we'll get the profile after VTSC update
        # For now, return None to indicate no separate MTSC data
        return None, None
    
    def update_vtsc(
        self,
        v_ego: float,
        v_cruise: float,
        map_speed_profile: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        turn_aggressiveness: float = 1.0,
        modelData = None,
        a_ego: float = 0.0,
        frogpilot_toggles: Optional[dict] = None
    ) -> float:
        """
        VTSC-compatible update method.
        Returns target speed like original VTSC.
        """
        if self.migration_mode == "legacy":
            # Use legacy mode
            self.unified.set_mode("legacy")
        else:
            # Set unified controller mode based on migration mode
            if self.migration_mode == "map_only":
                self.unified.set_mode("map_only")
            elif self.migration_mode == "vision_only":
                self.unified.set_mode("vision_only")
            else:
                self.unified.set_mode("combined")
        
        # Create toggles dict if needed
        if frogpilot_toggles is None:
            frogpilot_toggles = {}
        frogpilot_toggles['turn_aggressiveness'] = turn_aggressiveness
        
        # Call unified update
        target_speed, profile = self.unified.update(
            v_ego, a_ego, v_cruise, modelData, frogpilot_toggles
        )
        
        # Store results for compatibility
        self.vtsc_target = target_speed
        if profile and len(profile.distances) > 0:
            self.map_speed_profile = (profile.distances, profile.speeds)
        else:
            self.map_speed_profile = None
        
        return target_speed
    
    def reset(self, v_ego: float):
        """VTSC-compatible reset method."""
        # Unified controller doesn't need explicit reset
        # but we'll clear state for compatibility
        self.vtsc_target = v_ego
        self.map_speed_profile = None
    
    def shutdown(self):
        """Shutdown method for compatibility."""
        self.unified.shutdown()
    
    # Compatibility properties/methods for FrogPilotVCruise
    @property
    def mtsc(self):
        """Return self as MTSC for compatibility."""
        return self
    
    def update(self, *args, **kwargs):
        """
        Unified update method that routes to appropriate sub-method.
        This allows using the same object for both MTSC and VTSC updates.
        """
        # Detect which controller is being called based on arguments
        if len(args) >= 4 or 'frogpilot_toggles' in kwargs:
            # MTSC-style call (has 4 args including frogpilot_toggles)
            return self.update_mtsc(*args, **kwargs)
        else:
            # VTSC-style call
            return self.update_vtsc(*args, **kwargs)


def create_migration_params():
    """Create default parameters for migration."""
    params = Params()
    
    # Set default migration mode
    current_mode = params.get("TurnControllerMode", encoding='utf8')
    if not current_mode:
        params.put("TurnControllerMode", "legacy")  # Start with legacy mode
        cloudlog.info("Set default TurnControllerMode to legacy")
    
    # Create aggressiveness mapping
    # Map old separate aggressiveness values to unified one
    mtsc_aggr = params.get_float("MTSCAggressiveness", 1.0)
    vtsc_aggr = params.get_float("VTSCAggressiveness", 1.0)
    unified_aggr = (mtsc_aggr + vtsc_aggr) / 2.0  # Average them
    
    params.put_float("TurnAggressiveness", unified_aggr)
    cloudlog.info(f"Set unified TurnAggressiveness to {unified_aggr}")


def print_migration_guide():
    """Print migration guide for users."""
    guide = """
    === Unified Turn Controller Migration Guide ===
    
    The separate MTSC and VTSC controllers have been unified into a single controller.
    
    Migration Steps:
    1. The system will start in "legacy" mode using the original controllers
    2. Test that everything works as before
    3. Switch to "unified" mode to use the new controller
    4. Adjust settings as needed
    
    Available Modes (set via TurnControllerMode param):
    - "legacy": Use original MTSC/VTSC controllers
    - "map_only": Use only map data (like MTSC alone)  
    - "vision_only": Use only vision data (like VTSC alone)
    - "unified": Use combined map and vision data (recommended)
    
    Settings:
    - TurnAggressiveness: Replaces separate MTSC/VTSC aggressiveness (0.5-2.0)
    - TurnControllerBlendMode: How to combine map/vision ("minimum", "weighted", "adaptive")
    
    To switch modes:
    echo "unified" > /data/params/d/TurnControllerMode
    
    To adjust aggressiveness:
    echo "1.2" > /data/params/d/TurnAggressiveness
    """
    print(guide)


if __name__ == "__main__":
    # Run this script to set up migration parameters
    create_migration_params()
    print_migration_guide()