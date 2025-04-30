#!/usr/bin/env python3
import math
import json
import numpy as np
from shapely.geometry import Point

import cereal.messaging as messaging
from cereal import log
from openpilot.common.realtime import Ratekeeper
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog

# mapd_py imports
from openpilot.selfdrive.frogpilot.navigation.mapd_py import reader
from openpilot.selfdrive.frogpilot.navigation.mapd_py import matcher
from openpilot.selfdrive.frogpilot.navigation.mapd_py import geometry # For TO_RADIANS
from openpilot.selfdrive.frogpilot.navigation.mapd_py.reader import TILE_SIZE_DEG, get_tile_id # For proactive loading
# --- Add matcher imports ---
from openpilot.selfdrive.frogpilot.navigation.mapd_py.matcher import (
    get_progress_along_way,
    get_segment_length,
    distance_from_start_to_node
)
# --------------------------

class MapdPyDaemon:
    def __init__(self):
        self.sm = messaging.SubMaster(['liveLocationKalman', 'carState'], poll='liveLocationKalman')
        self.pm = messaging.PubMaster(['liveMapData'])

        self.params = Params()
        self.params_memory = Params("/dev/shm/params") # For writing legacy params if needed

        self.map_reader = reader.MapReader()

        # State variables
        self.last_valid_pos = None      # matcher.Position: Last known valid position
        self.current_segment_id = None  # int: ID of the current segment
        self.current_segment_data = None# dict: Data for the current segment
        self.current_on_way_result = None # matcher.OnWayResult: Result of on_way check
        self.gps_ok = False
        self.last_v_ego = 0.0

    def update_location(self) -> bool:
        """
        Updates location information from liveLocationKalman.
        Returns True if the location is valid, False otherwise.
        """
        self.sm.update(0) # Ensure latest messages are available

        llk = self.sm['liveLocationKalman']
        self.gps_ok = llk.gpsOK and llk.status == log.LiveLocationKalman.Status.valid and llk.positionGeodetic.valid

        if self.gps_ok:
            # Construct matcher.Position object
            bearing_rad = llk.calibratedOrientationNED.value[2] # Use calibrated orientation yaw
            self.last_valid_pos = matcher.Position(
                latitude=llk.positionGeodetic.value[0],
                longitude=llk.positionGeodetic.value[1],
                bearing_rad=bearing_rad
            )
            # Write to LastGPSPosition param for compatibility with other modules (like chauffeur_mtsc)
            # Maybe consider removing this if chauffeur_mtsc is updated to use liveMapData directly
            try:
                pos_dict = {
                    'latitude': self.last_valid_pos.latitude,
                    'longitude': self.last_valid_pos.longitude,
                    'bearing': math.degrees(self.last_valid_pos.bearing_rad) # Convert back to degrees for param
                }
                self.params_memory.put("LastGPSPosition", json.dumps(pos_dict))
            except Exception as e:
                cloudlog.exception(f"MapdPyDaemon: Error writing LastGPSPosition param: {e}")

            return True
        else:
            # GPS lost or invalid
            self.last_valid_pos = None
            self.current_segment_id = None
            self.current_segment_data = None
            self.current_on_way_result = None
            # Clear legacy param on GPS loss
            self.params_memory.remove("LastGPSPosition")
            return False

    def update(self):
        """
        Main update loop: get location, find segment, calculate speed limits, publish liveMapData.
        """
        location_valid = self.update_location()

        if self.sm.updated['carState']:
          self.last_v_ego = self.sm['carState'].vEgo

        msg = messaging.new_message('liveMapData')
        is_on_segment = False # Assume not on segment initially
        next_ways_results = [] # Initialize next_ways_results

        # --- Initialize new fields ---
        msg.liveMapData.curvatureDataValid = False
        msg.liveMapData.turnSpeedLimit = 0.0
        msg.liveMapData.distToTurn = 0.0
        msg.liveMapData.currentSegment.segmentId = 0
        msg.liveMapData.currentSegment.distanceAlongSegment = 0.0
        msg.liveMapData.currentSegment.curvatureDerivedSpeedsMps = []
        msg.liveMapData.currentSegment.distancesForSpeeds = []
        msg.liveMapData.nextSegments = []
        # -----------------------------

        if location_valid and self.last_valid_pos is not None:
            # --- Find Current Segment ---
            try:
                # Ask MapReader for the closest segment (this queues required tile
                # loads *and* performs the spatial query in one place).  By relying
                # on the shared helper we avoid duplicating logic here and reduce
                # the chance of subtle inconsistencies.
                segment_data = self.map_reader.get_segment_data_at(
                    self.last_valid_pos.latitude,
                    self.last_valid_pos.longitude,
                    self.last_valid_pos.bearing_rad
                )

                # The rest of the logic remains the same, using the segment_data found (or None)
                if segment_data:
                    segment_id = segment_data.get('id')
                    if segment_id:
                        # Perform the detailed on_way check
                        on_way_result = matcher.on_way(self.last_valid_pos, segment_id, segment_data)
                        if on_way_result.on_way:
                            # Successfully found segment and we are on it
                            is_on_segment = True
                            self.current_segment_id = segment_id
                            self.current_segment_data = segment_data
                            self.current_on_way_result = on_way_result
                        else:
                            # Segment found, but on_way check failed
                            self.current_segment_id = None
                            self.current_segment_data = None
                            self.current_on_way_result = None
                    else: # No segment ID in data
                         self.current_segment_id = None
                         self.current_segment_data = None
                         self.current_on_way_result = None
                else: # No segment data found nearby
                     self.current_segment_id = None
                     self.current_segment_data = None
                     self.current_on_way_result = None

            except Exception as e:
                cloudlog.exception(f"MapdPyDaemon: Error finding current segment: {e}")
                is_on_segment = False
                self.current_segment_id = None
                self.current_segment_data = None
                self.current_on_way_result = None

        # --- Calculate Speed Limits ---
        current_limit_mps = 0.0
        next_limit_mps = 0.0
        next_limit_dist = 0.0

        if is_on_segment and self.current_segment_data is not None and self.current_on_way_result is not None:
            # Get current speed limit
            current_limit_mps = self.current_segment_data.get('speed_mps', 0.0)

            # --- Populate Current Segment Data for liveMapData ---
            msg.liveMapData.currentSegment.segmentId = self.current_segment_id
            current_curv_speeds = self.current_segment_data.get('curvature_derived_speeds_mps', [])
            current_coords = self.map_reader.get_segment_coords(self.current_segment_id)

            if current_curv_speeds and current_coords and len(current_coords) > 2:
                msg.liveMapData.curvatureDataValid = True # Mark as valid if speeds exist
                msg.liveMapData.currentSegment.curvatureDerivedSpeedsMps = current_curv_speeds
                # Calculate distances corresponding to each speed point
                # Speed[j] applies to curve ending at node j+1. Distance is to node j+1.
                current_distances_for_speeds = [0.0] * len(current_curv_speeds)
                cumulative_node_dist = 0.0
                if len(current_coords) > 1: # Distance to first node (index 1)
                    cumulative_node_dist = geometry.distance_linalg(current_coords[0], current_coords[1])

                for j in range(len(current_curv_speeds)):
                    target_node_index = j + 1
                    if target_node_index == 1: # Distance to node 1 already calculated
                        current_distances_for_speeds[j] = cumulative_node_dist
                    elif target_node_index < len(current_coords):
                        # Add length of segment from node j to j+1
                        cumulative_node_dist += geometry.distance_linalg(current_coords[j], current_coords[target_node_index])
                        current_distances_for_speeds[j] = cumulative_node_dist
                    else: # Should not happen if lists align, but handle gracefully
                        current_distances_for_speeds[j] = cumulative_node_dist # Use last known cumulative

                msg.liveMapData.currentSegment.distancesForSpeeds = current_distances_for_speeds

                # Calculate distance along current segment
                dist_covered_on_current = get_progress_along_way(
                    self.last_valid_pos, self.current_segment_data, self.current_on_way_result
                )
                msg.liveMapData.currentSegment.distanceAlongSegment = dist_covered_on_current
            else:
                msg.liveMapData.curvatureDataValid = False
            # -----------------------------------------------------

            # Find next speed limit change & next way segments
            try:
                current_way_res = matcher.CurrentWayResult(
                    segment_id=self.current_segment_id,
                    on_way_result=self.current_on_way_result
                )
                next_ways_results = matcher.get_next_ways(self.last_valid_pos, current_way_res, self.map_reader)

                # --- Proactive Tile Loading --- Added
                if next_ways_results:
                    future_tile_ids = set()
                    PROACTIVE_LOAD_DISTANCE_LIMIT = 1000.0 # meters
                    cumulative_proactive_dist = 0.0

                    # Get distance remaining on current segment to add to proactive distance
                    # Placeholder: Replace with accurate distance_to_end_of_way if available
                    dist_remaining_current_proactive = 0.0
                    coords_current = self.map_reader.get_segment_coords(self.current_segment_id)
                    if coords_current:
                        # Placeholder index
                        current_node_index_proactive = 0
                        if self.current_on_way_result and hasattr(self.current_on_way_result, 'segment_index'):
                           current_node_index_proactive = self.current_on_way_result.segment_index
                        for i in range(current_node_index_proactive, len(coords_current) - 1):
                             p1 = coords_current[i]
                             p2 = coords_current[i+1]
                             dist_remaining_current_proactive += geometry.distance_linalg(p1,p2)
                    cumulative_proactive_dist += dist_remaining_current_proactive
                    # --- End distance remaining calculation ---

                    for next_way in next_ways_results:
                        if cumulative_proactive_dist >= PROACTIVE_LOAD_DISTANCE_LIMIT:
                            # print(f"MapdDaemon: Reached proactive distance limit ({cumulative_proactive_dist:.0f}m). Stopping tile requests.")
                            break # Stop requesting tiles beyond the limit

                        # Get coordinates for the future segment to determine its tile
                        # Need segment coordinates (get_segment_coords handles locking)
                        coords = self.map_reader.get_segment_coords(next_way.segment_id)
                        if coords:
                            # Use first coordinate to determine tile ID
                            first_coord_lat, first_coord_lon = coords[0]
                            tile_id = get_tile_id(first_coord_lat, first_coord_lon, TILE_SIZE_DEG)
                            future_tile_ids.add(tile_id)

                        # Add segment length to cumulative distance for the *next* check
                        next_segment_data = self.map_reader.segments_data.get(next_way.segment_id)
                        if next_segment_data:
                            # --- Use imported function --- #
                            segment_len = get_segment_length(next_segment_data)
                            # --------------------------- #
                            cumulative_proactive_dist += segment_len
                        else:
                            # Cannot get length, break to be safe
                            print("MapdDaemon: Warning - Could not get next segment data for proactive length.")
                            break

                    if future_tile_ids:
                         # print(f"MapdDaemon: Proactively requesting {len(future_tile_ids)} future tiles.")
                         self.map_reader.request_tiles(future_tile_ids)
                # ------------------------------

                if next_ways_results:
                    dist_to_end_current = matcher.distance_to_end_of_way(
                        self.last_valid_pos, self.current_segment_data, self.current_on_way_result
                    )
                    cumulative_dist_to_next_start = dist_to_end_current

                    for next_way in next_ways_results:
                        next_segment_id = next_way.segment_id
                        next_segment_data = self.map_reader.segments_data.get(next_segment_id)
                        if not next_segment_data:
                            continue # Should not happen if reader works correctly

                        _next_limit_mps_segment = next_segment_data.get('speed_mps', 0.0)

                        # Check for change (allow for small float differences)
                        if abs(_next_limit_mps_segment - current_limit_mps) > 0.1:
                            next_limit_mps = _next_limit_mps_segment
                            next_limit_dist = cumulative_dist_to_next_start
                            break # Found first change

                        # If limit hasn't changed, add segment length to cumulative distance
                        # --- Use imported function --- #
                        segment_len = get_segment_length(next_segment_data)
                        # --------------------------- #
                        cumulative_dist_to_next_start += segment_len

                # --- Populate Next Segment Data for liveMapData ---
                if next_ways_results:
                    # Reuse the proactive loading limit for publishing to avoid excessive message size
                    PUBLISH_DISTANCE_LIMIT = PROACTIVE_LOAD_DISTANCE_LIMIT

                    # Recalculate dist_to_end_current and cumulative_dist_to_next_start for this block
                    dist_to_end_current = matcher.distance_to_end_of_way(
                        self.last_valid_pos, self.current_segment_data, self.current_on_way_result
                    )
                    cumulative_dist_next_start_for_pub = dist_to_end_current
                    next_segments_list = []

                    for next_way in next_ways_results:
                        # Stop adding segments if we exceed the publish distance limit
                        if cumulative_dist_next_start_for_pub >= PUBLISH_DISTANCE_LIMIT:
                            break

                        next_segment_id_pub = next_way.segment_id
                        next_segment_data_pub = self.map_reader.segments_data.get(next_segment_id_pub)
                        if not next_segment_data_pub: continue

                        # --- Use imported function --- #
                        seg_len_pub = get_segment_length(next_segment_data_pub)
                        # --------------------------- #
                        curv_speeds_pub = next_segment_data_pub.get('curvature_derived_speeds_mps', [])
                        coords_pub = self.map_reader.get_segment_coords(next_segment_id_pub)

                        distances_for_speeds_pub = []
                        if curv_speeds_pub and coords_pub and len(coords_pub) > 2:
                             # Calculate distances like for current segment
                             distances_for_speeds_pub = [0.0] * len(curv_speeds_pub)
                             cumulative_node_dist_pub = 0.0
                             if len(coords_pub) > 1:
                                  cumulative_node_dist_pub = geometry.distance_linalg(coords_pub[0], coords_pub[1])

                             for j in range(len(curv_speeds_pub)):
                                  target_node_index_pub = j + 1
                                  if target_node_index_pub == 1:
                                       distances_for_speeds_pub[j] = cumulative_node_dist_pub
                                  elif target_node_index_pub < len(coords_pub):
                                       cumulative_node_dist_pub += geometry.distance_linalg(coords_pub[j], coords_pub[target_node_index_pub])
                                       distances_for_speeds_pub[j] = cumulative_node_dist_pub
                                  else:
                                       distances_for_speeds_pub[j] = cumulative_node_dist_pub

                        next_seg_struct = log.LiveMapData.NextSegmentData.new_message(
                            segmentId=next_segment_id_pub,
                            distanceToStart=cumulative_dist_next_start_for_pub,
                            segmentLength=seg_len_pub,
                            curvatureDerivedSpeedsMps=curv_speeds_pub,
                            distancesForSpeeds=distances_for_speeds_pub
                        )
                        next_segments_list.append(next_seg_struct)
                        cumulative_dist_next_start_for_pub += seg_len_pub # Increment for the *next* segment

                    msg.liveMapData.nextSegments = next_segments_list
                # ------------------------------------------------

            except Exception as e:
                cloudlog.exception(f"MapdPyDaemon: Error finding next speed limit/ways: {e}")
                next_limit_mps = 0.0
                next_limit_dist = 0.0
                next_ways_results = [] # Clear on error

        else:
            # Not on a segment, clear limits (already handled by initialization)
            # Clear curvature limits as well - REMOVED, no longer needed here
            # turn_speed_mps = 0.0
            # dist_to_turn_m = 0.0
            # turn_speed_valid = False
            # Keep msg.liveMapData.curvatureDataValid as False (default)
            pass # Nothing specific needs clearing here anymore

        # --- Publish liveMapData ---
        # Populate the nested lastGps struct
        if self.gps_ok and self.last_valid_pos is not None:
            llk = self.sm['liveLocationKalman']
            msg.liveMapData.lastGps.latitude = self.last_valid_pos.latitude
            msg.liveMapData.lastGps.longitude = self.last_valid_pos.longitude
            msg.liveMapData.lastGps.altitude = llk.positionGeodetic.value[2]
            msg.liveMapData.lastGps.speed = llk.velocityDevice.value[0] # Assuming llk.velocityDevice[0] is speed
            msg.liveMapData.lastGps.bearingDeg = math.degrees(self.last_valid_pos.bearing_rad)
            msg.liveMapData.lastGps.horizontalAccuracy = llk.positionGeodetic.std[0] # Assuming std[0] is horizontal
            msg.liveMapData.lastGps.verticalAccuracy = llk.positionGeodetic.std[2] # Assuming std[2] is vertical
            msg.liveMapData.lastGps.unixTimestampMillis = llk.unixTimestampMillis
            msg.liveMapData.lastGps.source = 'ublox' # Or determine source more dynamically if needed
            msg.liveMapData.lastGps.vNED = list(llk.velocityNED.value)
            msg.liveMapData.lastGps.bearingAccuracyDeg = math.degrees(llk.calibratedOrientationNED.std[2]) # Assuming std[2] is yaw std
            msg.liveMapData.lastGps.speedAccuracy = llk.velocityDevice.std[0] # Assuming std[0] is speed std
            msg.liveMapData.lastGps.hasFix = True # Assuming gps_ok implies hasFix
        else:
            msg.liveMapData.lastGps.hasFix = False

        # Set other LiveMapData fields
        msg.liveMapData.speedLimitValid = is_on_segment and current_limit_mps > 0
        msg.liveMapData.speedLimit = float(current_limit_mps) # m/s

        msg.liveMapData.speedLimitAheadValid = is_on_segment and next_limit_mps > 0 and next_limit_dist > 0
        msg.liveMapData.speedLimitAhead = float(next_limit_mps) # m/s
        msg.liveMapData.speedLimitAheadDistance = float(next_limit_dist) # m

        # Add road name if available
        if is_on_segment and self.current_segment_data and 'name' in self.current_segment_data:
             msg.liveMapData.currentRoadName = str(self.current_segment_data['name'])
        else:
             msg.liveMapData.currentRoadName = ""

        # --- Publish curvature info --- (REMOVED - no longer calculated here)
        # msg.liveMapData.turnSpeedLimit = float(turn_speed_mps) if turn_speed_valid else 0.0
        # msg.liveMapData.distToTurn = float(dist_to_turn_m) if turn_speed_valid else 0.0
        # ---

        self.pm.send('liveMapData', msg)

        # --- Write legacy params (optional, for compatibility) ---
        # Maybe remove these if chauffeur_mtsc/vtsc are updated
        try:
            self.params_memory.put_float("MapSpeedLimit", float(current_limit_mps))
            next_limit_info = {}
            if msg.liveMapData.speedLimitAheadValid and self.last_valid_pos is not None:
                 # Need to find the coordinate of the start of the segment where the limit changes
                 # This requires more complex logic tracking the path geometry, skipping for now
                 # to keep the daemon simpler initially. chauffeur_mtsc has this logic.
                 pass # Placeholder - could add coordinate lookup later if needed for legacy param
            self.params_memory.put("NextMapSpeedLimit", json.dumps(next_limit_info))
        except Exception as e:
            cloudlog.exception(f"MapdPyDaemon: Error writing legacy params: {e}")


def main():
    daemon = MapdPyDaemon()
    rk = Ratekeeper(1.0) # Run at 1 Hz
    while True:
        daemon.update()
        rk.keep_time()

if __name__ == "__main__":
    main()