#!/usr/bin/env python3
import os
import sys
import time
import math
import json
import cereal.messaging as messaging
from cereal import log
import traceback # For more detailed error printing

# --- BEGIN sys.path modification ---
# This is important if the script is not in the root of openpilot
# It tries to ensure that relative imports for mapd_py components work
# by adding the presumed 'selfdrive' directory to the path.
# Adjust if your script location or project structure is different.
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming script is in .../tools/map_processing, then openpilot_root is ../../
    openpilot_root = os.path.abspath(os.path.join(script_dir, "../../"))

    # A common structure is openpilot/selfdrive, so add openpilot_root
    if openpilot_root not in sys.path:
        print(f"mapd_rtm.py: Adding {openpilot_root} to sys.path for imports.")
        sys.path.insert(0, openpilot_root)
except Exception as e_path:
    print(f"mapd_rtm.py: Warning - Could not modify sys.path: {e_path}")
# --- END sys.path modification ---

# --- Add imports for mapd_py components ---
# Assuming this script is run from a location where these imports work,
# e.g., from openpilot root, or selfdrive/frogpilot/tools/
# Adjust sys.path if necessary, or ensure PYTHONPATH is set
try:
    from selfdrive.frogpilot.navigation.mapd_py.reader import MapReader, TILE_SIZE_DEG, get_tile_id, REGION_BOUNDS, TILE_DATA_BASE_DIR
    from selfdrive.frogpilot.navigation.mapd_py import matcher
    from selfdrive.frogpilot.navigation.mapd_py import geometry # For TO_RADIANS, bearing etc.
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import mapd_py components. Make sure script is run from openpilot root or PYTHONPATH is set.")
    print(f"Details: {e}")
    print("Example: python selfdrive/frogpilot/tools/map_processing/mapd_rtm.py") # Assuming mapd_rtm.py is in tools/map_processing
    exit(1)
# --- End mapd_py imports ---


# Global state for monitor's independent analysis
monitor_map_reader = None
monitor_last_pos = None
monitor_segment_data = None
monitor_on_way_result = None
monitor_next_ways_results = []
monitor_is_on_segment = False
monitor_current_segment_id = None

def initialize_monitor_map_logic():
    global monitor_map_reader
    print("Monitor: Initializing its own MapReader instance...")
    monitor_map_reader = MapReader(cache_size=50) # Smaller cache for monitor to be lighter
    print("Monitor: MapReader initialized.")

def process_location_for_monitor(llk_msg):
    global monitor_map_reader, monitor_last_pos, monitor_segment_data, monitor_on_way_result
    global monitor_next_ways_results, monitor_is_on_segment, monitor_current_segment_id

    if not monitor_map_reader:
        print("Monitor: MapReader not initialized yet. Skipping processing.")
        return

    if llk_msg.gpsOK and llk_msg.status == log.LiveLocationKalman.Status.valid and llk_msg.positionGeodetic.valid:
        # Use calibratedOrientationNED.value[2] for bearing as mapd_daemon does
        bearing_rad = llk_msg.calibratedOrientationNED.value[2]
        monitor_last_pos = matcher.Position(
            latitude=llk_msg.positionGeodetic.value[0],
            longitude=llk_msg.positionGeodetic.value[1],
            bearing_rad=bearing_rad
        )

        # Reset for this cycle
        monitor_is_on_segment = False
        monitor_current_segment_id = None
        monitor_segment_data = None
        monitor_on_way_result = None
        monitor_next_ways_results = []

        try:
            # 1. Get segment data using monitor's MapReader
            monitor_segment_data = monitor_map_reader.get_segment_data_at(
                monitor_last_pos.latitude,
                monitor_last_pos.longitude,
                monitor_last_pos.bearing_rad
            )

            if monitor_segment_data:
                segment_id = monitor_segment_data.get('id')
                if segment_id:
                    # 2. Perform on_way check
                    monitor_on_way_result = matcher.on_way(monitor_last_pos, segment_id, monitor_segment_data)
                    if monitor_on_way_result.on_way:
                        monitor_is_on_segment = True
                        monitor_current_segment_id = segment_id

                        # 3. Get next ways if on a segment
                        current_way_res_for_monitor = matcher.CurrentWayResult(
                            segment_id=monitor_current_segment_id,
                            on_way_result=monitor_on_way_result
                        )
                        monitor_next_ways_results = matcher.get_next_ways(monitor_last_pos, current_way_res_for_monitor, monitor_map_reader)
        except Exception as e:
            print(f"Monitor Logic Error: {e}")
            traceback.print_exc()
            monitor_is_on_segment = False # Ensure flags are reset on error
            monitor_current_segment_id = None
            monitor_segment_data = None
            monitor_on_way_result = None
            monitor_next_ways_results = []
    else:
        # GPS not valid, clear monitor state
        monitor_last_pos = None
        monitor_is_on_segment = False
        monitor_current_segment_id = None
        monitor_segment_data = None
        monitor_on_way_result = None
        monitor_next_ways_results = []


def print_map_data(sm):
    print("\033c", end="")

    llk = sm['liveLocationKalman']
    lmd = sm['liveMapData']

    # --- LiveLocationKalman (Input) ---
    llk_status_str = str(llk.status)
    llk_info = f"LLK: GPSOK:{int(llk.gpsOK)} Stat:{llk_status_str} "
    if llk.positionGeodetic.valid:
        llk_info += f"Lat:{llk.positionGeodetic.value[0]:.5f} Lon:{llk.positionGeodetic.value[1]:.5f} "
        llk_info += f"Spd:{llk.velocityDevice.value[0]:.1f}m/s "
        llk_info += f"LLK_Bear:{math.degrees(llk.calibratedOrientationNED.value[2]):.1f}° " # LLK's own bearing
    else:
        llk_info += "Pos:INVALID "
    llk_info += f"TS:{llk.unixTimestampMillis / 1000.0:.1f}"
    print(llk_info)

    print("--- MAPD DAEMON OUTPUT (liveMapData) ---")
    lmd_info = f" LMD_Fix:{int(lmd.lastGps.hasFix)} "
    if lmd.lastGps.hasFix:
        lmd_info += f"LMD_Lat:{lmd.lastGps.latitude:.5f} LMD_Lon:{lmd.lastGps.longitude:.5f} LMD_Spd:{lmd.lastGps.speed:.1f}m/s LMD_Bear:{lmd.lastGps.bearingDeg:.1f} "
    lmd_info += f'LMD_TS:{lmd.lastGps.unixTimestampMillis/1000.0:.1f} Road:\'{lmd.currentRoadName if lmd.currentRoadName else "--"}\''
    print(lmd_info)

    sl_info = f"  SL V:{int(lmd.speedLimitValid)} Lim:{lmd.speedLimit:.1f} ({(lmd.speedLimit * 2.23694):.0f}) | "
    sl_info += f"SLA V:{int(lmd.speedLimitAheadValid)} Lim:{lmd.speedLimitAhead:.1f} ({(lmd.speedLimitAhead * 2.23694):.0f}) D:{lmd.speedLimitAheadDistance:.0f}m"
    print(sl_info)

    cur_seg_id_str = str(lmd.currentSegment.segmentId) if lmd.currentSegment.segmentId != 0 else "N/A"
    cur_seg_info = f"  CurSeg: ID:{cur_seg_id_str} DAlong:{lmd.currentSegment.distanceAlongSegment:.1f}m | "
    cur_seg_info += f"CurvV:{int(lmd.curvatureDataValid)} #Pts:{len(lmd.currentSegment.curvatureDerivedSpeedsMps)}"
    print(cur_seg_info)

    next_seg_info = f"  NxtSegs ({len(lmd.nextSegments)}): "
    for i, next_seg in enumerate(lmd.nextSegments):
        if i >= 1: # Show only first next segment from LMD to save space
            next_seg_info += f"...+{len(lmd.nextSegments) - i} "
            break
        next_seg_info += f"ID:{next_seg.segmentId} DToS:{next_seg.distanceToStart:.0f} L:{next_seg.segmentLength:.0f} #S:{len(next_seg.curvatureDerivedSpeedsMps)} | "
    print(next_seg_info.strip().rstrip('|').strip())

    # --- MONITOR'S INDEPENDENT ANALYSIS ---
    print("--- MONITOR'S INDEPENDENT ANALYSIS (using own MapReader/Matcher) ---")
    if monitor_last_pos:
        mon_info = f" Mon_Pos: Lat:{monitor_last_pos.latitude:.5f} Lon:{monitor_last_pos.longitude:.5f} Bear:{math.degrees(monitor_last_pos.bearing_rad):.1f}°"
        print(mon_info)

        mon_match_info = f" Mon_Match: IsOnSeg:{int(monitor_is_on_segment)} "
        if monitor_is_on_segment and monitor_current_segment_id is not None:
            mon_match_info += f"ID:{monitor_current_segment_id} "
            if monitor_on_way_result:
                mon_match_info += f"Dist:{monitor_on_way_result.distance_m:.1f}m Fwd:{int(monitor_on_way_result.is_forward)} "
        else:
            mon_match_info += "ID:N/A "
            if monitor_segment_data: # Found data but not on_way
                 mon_match_info += f"(Found potential ID:{monitor_segment_data.get('id','?')}) "
            if monitor_on_way_result: # Has on_way_result but not on_way
                mon_match_info += f"DistToWay:{monitor_on_way_result.distance_m:.1f}m "


        print(mon_match_info)

        mon_next_info = f" Mon_NxtSegs ({len(monitor_next_ways_results)}): "
        for i, next_res in enumerate(monitor_next_ways_results):
            if i >= 2: # Show first 2 next segments from monitor
                mon_next_info += f"...+{len(monitor_next_ways_results) - i} "
                break
            # We need to fetch segment_data for the next_res.segment_id to get its length
            # This might be slow if tiles aren't loaded, but let's try for essential info
            next_seg_data_mon = monitor_map_reader.segments_data.get(next_res.segment_id) if monitor_map_reader else None
            length_str = f"L:{matcher.get_segment_length(next_seg_data_mon):.0f}" if next_seg_data_mon else "L:?"
            mon_next_info += f"ID:{next_res.segment_id} {length_str} Fwd:{int(next_res.is_forward)} | "
        print(mon_next_info.strip().rstrip('|').strip())

        # Hint for tiles based on monitor's MapReader
        if monitor_map_reader and monitor_map_reader.current_region:
            expected_tile_id = get_tile_id(monitor_last_pos.latitude, monitor_last_pos.longitude, TILE_SIZE_DEG)
            print(f" Mon_MapReader: Region:{monitor_map_reader.current_region} ExpectTile:{expected_tile_id} LoadedTiles:{len(monitor_map_reader.loaded_tiles)} CacheSz:{len(monitor_map_reader.segments_data)}")
        elif monitor_map_reader:
             print(f" Mon_MapReader: Region:Unknown LoadedTiles:{len(monitor_map_reader.loaded_tiles)} CacheSz:{len(monitor_map_reader.segments_data)}")


    else:
        print(" Monitor: No valid LLK position for analysis.")


    print(f"Updates: LLK:{int(sm.updated['liveLocationKalman'])} LMD_Daemon:{int(sm.updated['liveMapData'])}")


def main():
    print("--- RUNNING MODIFIED SCRIPT CHECKPOINT 1 ---", flush=True) # New print
    initialize_monitor_map_logic() # Initialize monitor's map tools

    sm = messaging.SubMaster(['liveMapData', 'liveLocationKalman'], poll='liveLocationKalman')

    print("Waiting for initial messages...")
    # Reduced timeout for faster startup if services are responsive
    start_time = time.monotonic()
    initial_wait_timeout = 10.0 # seconds

    print("--- RUNNING MODIFIED SCRIPT CHECKPOINT 2 ---", flush=True) # New print
    while not (sm.all_alive() and sm.all_valid()):
        sm.update(100) # Wait up to 100ms for messages

        llk_alive = sm.alive['liveLocationKalman']
        lmd_alive = sm.alive['liveMapData']
        llk_valid = sm.valid['liveLocationKalman']
        lmd_valid = sm.valid['liveMapData']

        status_msg = f"LLK: alive={llk_alive}, valid={llk_valid} | LMD: alive={lmd_alive}, valid={lmd_valid}"
        print(status_msg, end="\r", flush=True)

        if time.monotonic() - start_time > initial_wait_timeout:
            print(f"\nERROR: Timeout waiting for initial messages. Final status: {status_msg}", flush=True)
            print(f"sm.all_alive() = {sm.all_alive()}, sm.all_valid() = {sm.all_valid()}", flush=True)
            if not sm.all_alive():
                if not llk_alive:
                    print("liveLocationKalman is not alive.", flush=True)
                if not lmd_alive:
                    print("liveMapData is not alive.", flush=True)
            if not sm.all_valid():
                if not llk_valid:
                    print("liveLocationKalman is not valid.", flush=True)
                if not lmd_valid:
                    print("liveMapData is not valid.", flush=True)
            return
        time.sleep(0.1) # Slightly longer sleep to make messages readable if they change fast
    print(f"\nInitial messages received and valid. Final status: LLK alive={sm.alive['liveLocationKalman']}, valid={sm.valid['liveLocationKalman']} | LMD alive={sm.alive['liveMapData']}, valid={sm.valid['liveMapData']}. Starting monitor...")

    last_llk_update_time = 0
    monitor_processing_interval = 0.2 # Process LLK for monitor this often (e.g., 5Hz)

    try:
        while True:
            sm.update(0) # Non-blocking check for ZMQ messages

            current_time = time.monotonic()
            # Process LLK for monitor's internal logic at a defined interval
            if sm.updated['liveLocationKalman'] and (current_time - last_llk_update_time > monitor_processing_interval):
                process_location_for_monitor(sm['liveLocationKalman'])
                last_llk_update_time = current_time
                print_map_data(sm) # Update display when monitor logic runs
            elif sm.updated['liveMapData']: # Or update if actual LMD changes
                 print_map_data(sm)


            time.sleep(0.05) # Main loop sleep, keep it short for responsiveness
    except KeyboardInterrupt:
        print("\nExiting monitor.")
    except Exception as e:
        print(f"\nAn error occurred in monitor main loop: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # The sys.path modification logic has been moved to the top of the script.
    main()
