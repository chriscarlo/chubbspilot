#!/usr/bin/env python3
"""
Python wrapper for the mapd Go binary.
This module manages the mapd process lifecycle and provides a bridge
between mapd's param-based output and openpilot's cereal messaging.
"""

import os
import subprocess
import time
import signal
import json
import math
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

import cereal.messaging as messaging
from cereal import log
from openpilot.common.params import Params
from openpilot.common.realtime import DT_CTRL, Ratekeeper
from openpilot.system.swaglog import cloudlog


MAPD_PATH = Path(__file__).parent / "mapd"
MAPD_PROCESS = None


def get_mapd_binary_path():
    """Get the path to the mapd binary."""
    return str(MAPD_PATH)


def ensure_mapd_binary():
    """Ensure the mapd binary exists and is executable."""
    binary_path = get_mapd_binary_path()
    
    if not os.path.exists(binary_path):
        cloudlog.warning("mapd binary not found at " + binary_path)
        
        # Try to download the binary
        download_script = Path(__file__).parent / "download_mapd.sh"
        if download_script.exists():
            cloudlog.info("Attempting to download mapd binary...")
            try:
                result = subprocess.run([str(download_script)], capture_output=True, text=True)
                if result.returncode == 0:
                    cloudlog.info("Successfully downloaded mapd binary")
                else:
                    cloudlog.error(f"Failed to download mapd binary: {result.stderr}")
                    return False
            except Exception as e:
                cloudlog.error(f"Error running download script: {e}")
                return False
        else:
            cloudlog.error("Download script not found and binary not present")
            return False
    
    # Ensure the binary is executable
    if not os.access(binary_path, os.X_OK):
        try:
            os.chmod(binary_path, 0o755)
            cloudlog.info("Made mapd binary executable")
        except Exception as e:
            cloudlog.error(f"Failed to make mapd binary executable: {e}")
            return False
    
    return True


def start_mapd():
    """Start the mapd daemon process."""
    global MAPD_PROCESS
    
    if MAPD_PROCESS is not None and MAPD_PROCESS.poll() is None:
        cloudlog.info("mapd already running")
        return True
    
    binary_path = get_mapd_binary_path()
    
    try:
        # Start mapd as a subprocess
        MAPD_PROCESS = subprocess.Popen(
            [binary_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN)
        )
        cloudlog.info(f"Started mapd with PID {MAPD_PROCESS.pid}")
        return True
    except Exception as e:
        cloudlog.error(f"Failed to start mapd: {e}")
        return False


def stop_mapd():
    """Stop the mapd daemon process."""
    global MAPD_PROCESS
    
    if MAPD_PROCESS is None:
        return
    
    if MAPD_PROCESS.poll() is None:
        try:
            MAPD_PROCESS.terminate()
            MAPD_PROCESS.wait(timeout=5)
            cloudlog.info("mapd terminated gracefully")
        except subprocess.TimeoutExpired:
            MAPD_PROCESS.kill()
            MAPD_PROCESS.wait()
            cloudlog.warning("mapd killed forcefully")
    
    MAPD_PROCESS = None


def monitor_mapd():
    """Monitor mapd process and restart if needed."""
    if MAPD_PROCESS is None or MAPD_PROCESS.poll() is not None:
        cloudlog.warning("mapd not running, attempting restart")
        if ensure_mapd_binary():
            start_mapd()


def parse_mapd_params(params_mem: Params) -> Dict[str, Any]:
    """Parse mapd param outputs into structured data."""
    data = {}
    
    # Road name
    road_name = params_mem.get("RoadName")
    data["road_name"] = road_name.decode() if road_name else ""
    
    # Speed limit
    speed_limit = params_mem.get("MapSpeedLimit") 
    try:
        data["speed_limit"] = float(speed_limit) if speed_limit else 0.0
        data["speed_limit_valid"] = speed_limit is not None and float(speed_limit) > 0
    except (ValueError, TypeError):
        data["speed_limit"] = 0.0
        data["speed_limit_valid"] = False
    
    # Map curvatures (list of {latitude, longitude, curvature})
    curvatures = params_mem.get("MapCurvatures")
    try:
        data["curvatures"] = json.loads(curvatures) if curvatures else []
    except json.JSONDecodeError:
        data["curvatures"] = []
    
    # Map target velocities (list of {latitude, longitude, velocity})
    velocities = params_mem.get("MapTargetVelocities")
    try:
        data["velocities"] = json.loads(velocities) if velocities else []
    except json.JSONDecodeError:
        data["velocities"] = []
    
    # Next speed limit
    next_speed_limit = params_mem.get("NextMapSpeedLimit")
    try:
        data["next_speed_limit"] = json.loads(next_speed_limit) if next_speed_limit else None
    except json.JSONDecodeError:
        data["next_speed_limit"] = None
    
    # GPS position 
    gps_pos = params_mem.get("LastGPSPosition")
    try:
        data["gps_position"] = json.loads(gps_pos) if gps_pos else None
    except json.JSONDecodeError:
        data["gps_position"] = None
    
    return data


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on earth in meters."""
    R = 6371000  # Earth's radius in meters
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = lat2_rad - lat1_rad
    dlon = math.radians(lon2 - lon1)
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def velocities_to_segments(velocities: List[Dict], gps_position: Optional[Dict]) -> tuple:
    """Convert mapd velocities to MTSC-compatible segment data."""
    if not velocities or not gps_position:
        return None, []
    
    # Filter out zero velocities (straight sections with no curvature)
    filtered_velocities = [v for v in velocities if v.get("velocity", 0) > 0]
    
    if not filtered_velocities:
        return None, []
    
    # Create current segment with all velocity points
    current_segment = {
        "segment_id": 1,  # Use a consistent ID for the current road segment
        "distance_along_segment": 0.0,  # Distance from start of segment to current position
        "curvature_derived_speeds_mps": [],
        "distances_for_speeds": []  # Distances from current position
    }
    
    # Find the closest point to current GPS position
    min_dist = float('inf')
    closest_idx = 0
    curr_lat = gps_position.get("latitude", 0)
    curr_lon = gps_position.get("longitude", 0)
    
    for i, vel in enumerate(filtered_velocities):
        dist = haversine_distance(curr_lat, curr_lon, vel["latitude"], vel["longitude"])
        if dist < min_dist:
            min_dist = dist
            closest_idx = i
    
    # Build arrays starting from closest point
    cumulative_dist = 0.0
    last_lat = curr_lat
    last_lon = curr_lon
    
    # Add points ahead of current position
    for i in range(closest_idx, len(filtered_velocities)):
        vel = filtered_velocities[i]
        
        # Calculate distance from last point
        if i == closest_idx:
            # First point - use distance from current position
            dist = haversine_distance(curr_lat, curr_lon, vel["latitude"], vel["longitude"])
        else:
            # Subsequent points - use distance between consecutive points
            dist = haversine_distance(last_lat, last_lon, vel["latitude"], vel["longitude"])
        
        cumulative_dist += dist
        current_segment["distances_for_speeds"].append(cumulative_dist)
        current_segment["curvature_derived_speeds_mps"].append(vel["velocity"])
        
        last_lat = vel["latitude"]
        last_lon = vel["longitude"]
    
    # For now, no next segments - all data goes into current segment
    next_segments = []
    
    return current_segment, next_segments


def publish_live_map_data(pm: messaging.PubMaster, params_mem: Params):
    """Read mapd params and publish as liveMapData."""
    data = parse_mapd_params(params_mem)
    
    msg = messaging.new_message('liveMapData')
    dat = msg.liveMapData
    
    # Basic fields
    dat.speedLimitValid = data["speed_limit_valid"]
    dat.speedLimit = data["speed_limit"]
    dat.currentRoadName = data["road_name"]
    dat.mapValid = len(data["velocities"]) > 0
    
    # GPS data
    if data["gps_position"]:
        dat.lastGps.latitude = data["gps_position"]["latitude"]
        dat.lastGps.longitude = data["gps_position"]["longitude"] 
        dat.lastGps.bearing = data["gps_position"]["bearing"]
        dat.lastGps.hasFix = True
    
    # Next speed limit
    if data["next_speed_limit"]:
        dat.speedLimitAheadValid = True
        dat.speedLimitAhead = data["next_speed_limit"]["speedlimit"]
        # Calculate distance (placeholder - would need proper calculation)
        dat.speedLimitAheadDistance = 100.0  
    
    # Convert velocities to segment data for MTSC
    current_seg, next_segs = velocities_to_segments(data["velocities"], data["gps_position"])
    
    if current_seg:
        dat.curvatureDataValid = True
        dat.currentSegment.segmentId = current_seg["segment_id"]
        dat.currentSegment.distanceAlongSegment = current_seg["distance_along_segment"]
        dat.currentSegment.curvatureDerivedSpeedsMps = current_seg["curvature_derived_speeds_mps"]
        dat.currentSegment.distancesForSpeeds = current_seg["distances_for_speeds"]
    
    # For now, no next segments
    dat.nextSegments = []
    
    pm.send('liveMapData', msg)


def mapd_bridge_thread(stop_event: threading.Event):
    """Thread that bridges mapd params to liveMapData messages."""
    cloudlog.info("Starting mapd bridge thread")
    
    params_mem = Params("/dev/shm/params")
    pm = messaging.PubMaster(['liveMapData'])
    rk = Ratekeeper(1.0)  # 1 Hz as per service definition
    
    while not stop_event.is_set():
        try:
            publish_live_map_data(pm, params_mem)
        except Exception as e:
            cloudlog.error(f"Error in mapd bridge: {e}")
        
        rk.keep_time()
    
    cloudlog.info("mapd bridge thread stopped")


def main():
    """Main entry point for the mapd Python wrapper."""
    cloudlog.info("mapd wrapper starting")
    
    # Ensure params directories exist
    params_mem = Params("/dev/shm/params")
    params_persist = Params()
    
    # Reset map parameters on startup
    params_mem.put("RoadName", b"")
    params_mem.put("MapSpeedLimit", b"0")
    params_mem.put("MapCurvatures", b"[]")
    params_mem.put("MapTargetVelocities", b"[]")
    
    # Ensure mapd binary exists
    if not ensure_mapd_binary():
        cloudlog.error("mapd binary not available, exiting")
        return
    
    # Start mapd
    if not start_mapd():
        cloudlog.error("Failed to start mapd, exiting")
        return
    
    # Start bridge thread
    stop_event = threading.Event()
    bridge_thread = threading.Thread(target=mapd_bridge_thread, args=(stop_event,))
    bridge_thread.start()
    
    try:
        # Monitor loop
        while True:
            monitor_mapd()
            time.sleep(5.0)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        cloudlog.info("mapd wrapper shutting down")
    finally:
        stop_event.set()
        bridge_thread.join(timeout=2.0)
        stop_mapd()


if __name__ == "__main__":
    main()