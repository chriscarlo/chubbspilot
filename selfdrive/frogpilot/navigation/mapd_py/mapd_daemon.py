#!/usr/bin/env python3
import math
import json
import numpy as np
from shapely.geometry import Point
# import datetime # No longer needed here directly if log_event handles it

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
from openpilot.selfdrive.frogpilot.navigation.mapd_py.logging_utils import log_event # Centralized logger
# --- Add matcher imports ---
from openpilot.selfdrive.frogpilot.navigation.mapd_py.matcher import (
    get_progress_along_way,
    get_segment_length,
    distance_from_start_to_node
)
# --------------------------

# --- DEDUP + RESAMPLE FUNCTION ---
def _compact(dist: list[float], speed: list[float], target=80) -> tuple[list[float], list[float]]:
  if not dist or not speed or len(dist) <= target:
    return dist, speed
  # Ensure lists are numpy arrays for efficient indexing
  dist_np = np.array(dist)
  speed_np = np.array(speed)
  idx = np.linspace(0, len(dist_np)-1, target, dtype=int)
  # Use array indexing and convert back to list
  return dist_np[idx].tolist(), speed_np[idx].tolist()
# --- END DEDUP + RESAMPLE FUNCTION ---

# Local logger definition REMOVED

class MapdPyDaemon:
    def __init__(self):
        log_event("DAEMON", "INFO", "INIT_START")
        self.sm = messaging.SubMaster(['liveLocationKalman', 'carState'], poll='liveLocationKalman')
        self.pm = messaging.PubMaster(['liveMapData'])

        self.params = Params()
        self.params_memory = Params("/dev/shm/params") # For writing legacy params if needed

        # Initialise the MapReader with the tile-loader worker pinned to CPU 3 to
        # keep heavy protobuf unpacking off the daemon's main core.
        log_event("DAEMON", "INFO", "INIT_MAP_READER", worker_cpu=3)
        self.map_reader = reader.MapReader(worker_cpu=3)

        # State variables
        self.last_valid_pos = None      # matcher.Position: Last known valid position
        self.current_segment_id = None  # int: ID of the current segment
        self.current_segment_data = None# dict: Data for the current segment
        self.current_on_way_result = None # matcher.OnWayResult: Result of on_way check
        self.gps_ok = False
        self.last_v_ego = 0.0
        log_event("DAEMON", "INFO", "INIT_COMPLETE")

    def update_location(self) -> bool:
        """
        Updates location information from liveLocationKalman.
        Returns True if the location is valid, False otherwise.
        """
        self.sm.update(0) # Ensure latest messages are available
        log_event("DAEMON", "DEBUG", "UPDATE_LOCATION_START")

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
            log_event("DAEMON", "INFO", "GPS_UPDATE_SUCCESS",
                      latitude=self.last_valid_pos.latitude,
                      longitude=self.last_valid_pos.longitude,
                      bearing_rad=self.last_valid_pos.bearing_rad,
                      gps_ok=self.gps_ok,
                      llk_status=llk.status.raw,
                      pos_geodetic_valid=llk.positionGeodetic.valid)
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
                log_event("DAEMON", "ERROR", "PARAM_WRITE_FAIL", param_name="LastGPSPosition", error=str(e))

            return True
        else:
            log_event("DAEMON", "WARN", "GPS_UPDATE_FAIL",
                      gps_ok_llk=llk.gpsOK,
                      llk_status=llk.status.raw,
                      pos_geodetic_valid=llk.positionGeodetic.valid,
                      current_gps_ok_state=self.gps_ok)
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
        log_event("DAEMON", "DEBUG", "UPDATE_CYCLE_START", location_valid=location_valid, v_ego=self.last_v_ego)

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
                log_event("DAEMON", "DEBUG", "READER_CALL_GET_SEGMENT_DATA_AT_START",
                          latitude=self.last_valid_pos.latitude,
                          longitude=self.last_valid_pos.longitude,
                          bearing_rad=self.last_valid_pos.bearing_rad if self.last_valid_pos.bearing_rad is not None else -1.0)
                # Ask MapReader for the closest segment (this queues required tile
                # loads *and* performs the spatial query in one place).  By relying
                # on the shared helper we avoid duplicating logic here and reduce
                # the chance of subtle inconsistencies.
                segment_data = self.map_reader.get_segment_data_at(
                    self.last_valid_pos.latitude,
                    self.last_valid_pos.longitude,
                    self.last_valid_pos.bearing_rad
                )
                log_event("DAEMON", "DEBUG", "READER_CALL_GET_SEGMENT_DATA_AT_END",
                          segment_data_found=(segment_data is not None),
                          segment_id=segment_data.get('id') if segment_data else "None")

                # The rest of the logic remains the same, using the segment_data found (or None)
                if segment_data:
                    segment_id_candidate = segment_data.get('id')
                    if segment_id_candidate:
                        log_event("DAEMON", "DEBUG", "MATCHER_CALL_ON_WAY_START",
                                  segment_id=segment_id_candidate,
                                  pos_lat=self.last_valid_pos.latitude,
                                  pos_lon=self.last_valid_pos.longitude)
                        # Perform the detailed on_way check
                        on_way_result = matcher.on_way(self.last_valid_pos, segment_id_candidate, segment_data)
                        log_event("DAEMON", "DEBUG", "MATCHER_CALL_ON_WAY_END",
                                  segment_id=segment_id_candidate,
                                  on_way=on_way_result.on_way,
                                  distance_m=on_way_result.distance_m,
                                  is_forward=on_way_result.is_forward)
                        if on_way_result.on_way:
                            # Successfully found segment and we are on it
                            is_on_segment = True
                            self.current_segment_id = segment_id_candidate
                            self.current_segment_data = segment_data
                            self.current_on_way_result = on_way_result
                            log_event("DAEMON", "INFO", "CURRENT_SEGMENT_MATCH_SUCCESS",
                                      segment_id=self.current_segment_id,
                                      distance_m=on_way_result.distance_m,
                                      is_forward=on_way_result.is_forward)
                        else:
                            # Segment found, but on_way check failed
                            log_event("DAEMON", "INFO", "CURRENT_SEGMENT_MATCH_FAIL_ONWAY_CHECK",
                                      candidate_segment_id=segment_id_candidate,
                                      reason="on_way returned false",
                                      on_way_dist_m=on_way_result.distance_m,
                                      on_way_is_fwd=on_way_result.is_forward)
                            self.current_segment_id = None
                            self.current_segment_data = None
                            self.current_on_way_result = None
                    else: # No segment ID in data
                         log_event("DAEMON", "WARN", "CURRENT_SEGMENT_MATCH_FAIL_NO_ID",
                                   segment_data_keys=list(segment_data.keys()) if segment_data else "None")
                         self.current_segment_id = None
                         self.current_segment_data = None
                         self.current_on_way_result = None
                else: # No segment data found nearby
                     log_event("DAEMON", "INFO", "CURRENT_SEGMENT_MATCH_FAIL_NO_DATA",
                               reason="get_segment_data_at returned None")
                     self.current_segment_id = None
                     self.current_segment_data = None
                     self.current_on_way_result = None

            except Exception as e:
                cloudlog.exception(f"MapdPyDaemon: Error finding current segment: {e}")
                log_event("DAEMON", "ERROR", "CURRENT_SEGMENT_FIND_EXCEPTION", error=str(e))
                is_on_segment = False
                self.current_segment_id = None
                self.current_segment_data = None
                self.current_on_way_result = None

            # Calculate distance along current segment
            if is_on_segment and self.current_segment_data and self.current_on_way_result and self.last_valid_pos:
                log_event("DAEMON", "DEBUG", "MATCHER_CALL_GET_PROGRESS_ALONG_WAY_START",
                          segment_id=self.current_segment_id,
                          pos_lat=self.last_valid_pos.latitude)
                dist_covered_on_current = get_progress_along_way(
                    self.last_valid_pos, self.current_segment_data, self.current_on_way_result
                )
                log_event("DAEMON", "DEBUG", "MATCHER_CALL_GET_PROGRESS_ALONG_WAY_END",
                          segment_id=self.current_segment_id,
                          progress_m=dist_covered_on_current)
            else:
                dist_covered_on_current = 0.0
                if location_valid : # Only log if we expected to calculate it
                    log_event("DAEMON", "DEBUG", "PROGRESS_ALONG_WAY_SKIP",
                              is_on_segment=is_on_segment,
                              has_segment_data=(self.current_segment_data is not None),
                              has_on_way_result=(self.current_on_way_result is not None),
                              has_pos=(self.last_valid_pos is not None))

            # Defines the distance from the OSM way's start node (node 0)
            # to the vehicle's current projected point along the way's geometry.
            msg.liveMapData.currentSegment.distanceAlongSegment = dist_covered_on_current
        else:
            log_event("DAEMON", "INFO", "UPDATE_SKIP_NO_VALID_LOCATION", gps_ok=self.gps_ok)
            # Not on a segment, clear limits (already handled by initialization)
            # Clear curvature limits as well - REMOVED, no longer needed here
            # turn_speed_mps = 0.0
            pass # Nothing specific needs clearing here anymore

        # --- Calculate Speed Limits ---
        current_limit_mps = 0.0
        next_limit_mps = 0.0
        next_limit_dist = 0.0

        if is_on_segment and self.current_segment_data is not None and self.current_on_way_result is not None:
            # Get current speed limit
            current_limit_mps = self.current_segment_data.get('speed_mps', 0.0)
            log_event("DAEMON", "DEBUG", "CURRENT_SPEED_LIMIT",
                      limit_mps=current_limit_mps,
                      segment_id=self.current_segment_id)

            # --- Populate Current Segment Data for liveMapData ---
            msg.liveMapData.currentSegment.segmentId = self.current_segment_id
            current_curv_speeds = self.current_segment_data.get('curvature_derived_speeds_mps', [])
            log_event("DAEMON", "DEBUG", "READER_CALL_GET_SEGMENT_COORDS_START", segment_id=self.current_segment_id if self.current_segment_id is not None else 0)
            current_coords = self.map_reader.get_segment_coords(self.current_segment_id if self.current_segment_id is not None else 0)
            log_event("DAEMON", "DEBUG", "READER_CALL_GET_SEGMENT_COORDS_END",
                      segment_id=self.current_segment_id if self.current_segment_id is not None else 0,
                      coords_found=(current_coords is not None),
                      num_coords=len(current_coords) if current_coords else 0)

            if current_curv_speeds and current_coords and len(current_coords) > 2:
                msg.liveMapData.curvatureDataValid = True # Mark as valid if speeds exist
                # Calculate distances corresponding to each speed point
                # Speed[j] applies to curve ending at node j+1. Distance is to node j+1.
                current_distances_for_speeds_raw = [0.0] * len(current_curv_speeds)
                cumulative_node_dist = 0.0
                if len(current_coords) > 1: # Distance to first node (index 1)
                    # --- Use distance_to_point with radians ---
                    lat1, lon1 = current_coords[0]
                    lat2, lon2 = current_coords[1]
                    cumulative_node_dist = geometry.distance_to_point(
                        lat1 * geometry.TO_RADIANS, lon1 * geometry.TO_RADIANS,
                        lat2 * geometry.TO_RADIANS, lon2 * geometry.TO_RADIANS
                    )
                    # ------------------------------------------

                for j in range(len(current_curv_speeds)):
                    target_node_index = j + 1
                    if target_node_index == 1: # Distance to node 1 already calculated
                        current_distances_for_speeds_raw[j] = cumulative_node_dist
                    elif target_node_index < len(current_coords):
                        # Add length of segment from node j to j+1
                        # --- Use distance_to_point with radians ---
                        lat1_curr, lon1_curr = current_coords[j]
                        lat2_curr, lon2_curr = current_coords[target_node_index]
                        segment_dist = geometry.distance_to_point(
                            lat1_curr * geometry.TO_RADIANS, lon1_curr * geometry.TO_RADIANS,
                            lat2_curr * geometry.TO_RADIANS, lon2_curr * geometry.TO_RADIANS
                        )
                        cumulative_node_dist += segment_dist
                        # ------------------------------------------
                        current_distances_for_speeds_raw[j] = cumulative_node_dist
                    else: # Should not happen if lists align, but handle gracefully
                        current_distances_for_speeds_raw[j] = cumulative_node_dist # Use last known cumulative

                # --- COMPACT BEFORE ASSIGNING ---
                compact_distances, compact_speeds = _compact(
                    current_distances_for_speeds_raw, current_curv_speeds)
                msg.liveMapData.currentSegment.distancesForSpeeds = compact_distances
                msg.liveMapData.currentSegment.curvatureDerivedSpeedsMps = compact_speeds
                log_event("DAEMON", "DEBUG", "CURRENT_SEGMENT_CURVATURE_DATA_POPULATED",
                          segment_id=self.current_segment_id,
                          raw_distances_count=len(current_distances_for_speeds_raw),
                          raw_speeds_count=len(current_curv_speeds),
                          compact_distances_count=len(compact_distances),
                          compact_speeds_count=len(compact_speeds))
                # --- END COMPACT --- #

            else:
                msg.liveMapData.curvatureDataValid = False
                log_event("DAEMON", "DEBUG", "CURRENT_SEGMENT_CURVATURE_DATA_INVALID_OR_INSUFFICIENT",
                  segment_id=self.current_segment_id if self.current_segment_id is not None else "None",
                  has_curv_speeds=(current_curv_speeds is not None and len(current_curv_speeds) > 0),
                  has_coords=(current_coords is not None),
                  num_coords=len(current_coords) if current_coords else 0)
            # -----------------------------------------------------

            # Find next speed limit change & next way segments
            try:
                current_way_res = matcher.CurrentWayResult(
                    segment_id=self.current_segment_id,
                    on_way_result=self.current_on_way_result
                )
                next_ways_results = matcher.get_next_ways(self.last_valid_pos, current_way_res, self.map_reader)
                log_event("DAEMON", "DEBUG", "MATCHER_CALL_FIND_NEXT_WAYS_START",
                          segment_id=self.current_segment_id,
                          on_way_result=self.current_on_way_result,
                          current_way_res=current_way_res,
                          pos=self.last_valid_pos,
                          map_reader=self.map_reader)

                # Initialize variables for calculating next speed limit ahead
                calculated_next_speed_limit_mps = 0.0
                calculated_distance_to_speed_limit_change = 0.0
                found_next_limit = False

                current_segment_remaining_dist_val = 0.0
                if is_on_segment and self.current_segment_data and self.current_on_way_result and self.last_valid_pos:
                    current_segment_remaining_dist_val = matcher.distance_to_end_of_way(
                        self.last_valid_pos,
                        self.current_segment_data,
                        self.current_on_way_result
                    )

                if next_ways_results and is_on_segment and self.current_segment_data:
                    current_speed_for_comparison = self.current_segment_data.get('speed_mps', 0.0)
                    cumulative_dist_to_next_segment = current_segment_remaining_dist_val

                    for next_way_item_calc in next_ways_results:
                        next_segment_id_calc = next_way_item_calc.segment_id
                        next_segment_data_calc = self.map_reader.segments_data.get(next_segment_id_calc)

                        if not next_segment_data_calc:
                            log_event("DAEMON", "WARN", "NEXT_SPEED_LIMIT_CALC_SKIP_NO_DATA", segment_id=next_segment_id_calc)
                            break # Cannot proceed without segment data

                        next_segment_actual_speed_mps = next_segment_data_calc.get('speed_mps', 0.0)

                        if next_segment_actual_speed_mps > 0 and abs(next_segment_actual_speed_mps - current_speed_for_comparison) > 1e-3:
                            calculated_next_speed_limit_mps = next_segment_actual_speed_mps
                            calculated_distance_to_speed_limit_change = cumulative_dist_to_next_segment
                            found_next_limit = True
                            log_event("DAEMON", "DEBUG", "NEXT_SPEED_LIMIT_FOUND",
                                      next_limit_mps=calculated_next_speed_limit_mps,
                                      dist_to_change_m=calculated_distance_to_speed_limit_change,
                                      on_segment_id=next_segment_id_calc)
                            break # Found the first change

                        segment_len_calc = get_segment_length(next_segment_data_calc)
                        cumulative_dist_to_next_segment += segment_len_calc

                log_event("DAEMON", "DEBUG", "MATCHER_CALL_FIND_NEXT_WAYS_END",
                          num_next_ways=len(next_ways_results),
                          next_limit_mps=calculated_next_speed_limit_mps, # Use calculated value
                          next_limit_dist_m=calculated_distance_to_speed_limit_change) # Use calculated value

                next_limit_mps = calculated_next_speed_limit_mps # Assign from calculated value
                next_limit_dist = calculated_distance_to_speed_limit_change # Assign from calculated value

                # --- Proactive Tile Loading for Next Segments ---
                PROACTIVE_LOAD_DISTANCE_LIMIT = 2000 # meters (2km)
                cumulative_proactive_dist = 0.0
                future_tile_ids = set()

                if next_ways_results:
                    log_event("DAEMON", "DEBUG", "PROACTIVE_TILE_LOADING_START", num_next_ways=len(next_ways_results), limit_m=PROACTIVE_LOAD_DISTANCE_LIMIT)

                    for next_way in next_ways_results:
                        if cumulative_proactive_dist >= PROACTIVE_LOAD_DISTANCE_LIMIT:
                            log_event("DAEMON", "DEBUG", "PROACTIVE_TILE_LOADING_LIMIT_REACHED",
                                      cumulative_dist_m=cumulative_proactive_dist,
                                      limit_m=PROACTIVE_LOAD_DISTANCE_LIMIT)
                            break # Stop requesting tiles beyond the limit

                        # Get coordinates for the future segment to determine its tile
                        # Need segment coordinates (get_segment_coords handles locking)
                        log_event("DAEMON", "DEBUG", "READER_CALL_GET_SEGMENT_COORDS_PROACTIVE_START", segment_id=next_way.segment_id)
                        coords = self.map_reader.get_segment_coords(next_way.segment_id)
                        log_event("DAEMON", "DEBUG", "READER_CALL_GET_SEGMENT_COORDS_PROACTIVE_END",
                                  segment_id=next_way.segment_id,
                                  coords_found=(coords is not None))
                        if coords:
                            # Use first coordinate to determine tile ID
                            first_coord_lat, first_coord_lon = coords[0]
                            tile_id = get_tile_id(first_coord_lat, first_coord_lon, TILE_SIZE_DEG)
                            future_tile_ids.add(tile_id)
                            log_event("DAEMON", "TRACE", "PROACTIVE_TILE_CALCULATED", segment_id=next_way.segment_id, tile_id=tile_id)


                        # Add segment length to cumulative distance for the *next* check
                        log_event("DAEMON", "DEBUG", "READER_ACCESS_SEGMENT_DATA_PROACTIVE_START", segment_id=next_way.segment_id)
                        # Access segments_data directly as it should be loaded by reader if coords were found
                        # This avoids re-locking if get_segment_data_at was used.
                        # Ensure the lock in map_reader protects segments_data for this read if needed,
                        # or ensure data is copied if accessed outside a lock.
                        # For now, assuming direct access is okay post get_segment_coords.
                        next_segment_data = self.map_reader.segments_data.get(next_way.segment_id) # Direct access
                        log_event("DAEMON", "DEBUG", "READER_ACCESS_SEGMENT_DATA_PROACTIVE_END",
                                  segment_id=next_way.segment_id,
                                  data_found=(next_segment_data is not None))

                        if next_segment_data:
                            # --- Use imported function --- #
                            segment_len = get_segment_length(next_segment_data)
                            log_event("DAEMON", "TRACE", "PROACTIVE_SEGMENT_LENGTH", segment_id=next_way.segment_id, length_m=segment_len)
                            # --------------------------- #
                            cumulative_proactive_dist += segment_len
                        else:
                            # Cannot get length, break to be safe
                            # print("MapdDaemon: Warning - Could not get next segment data for proactive length.")
                            log_event("DAEMON", "WARN", "PROACTIVE_TILE_LOADING_FAIL_NO_SEG_DATA", segment_id=next_way.segment_id)
                            break

                    if future_tile_ids:
                         log_event("DAEMON", "INFO", "READER_CALL_REQUEST_TILES_START", num_tiles=len(future_tile_ids), tile_ids=list(future_tile_ids))
                         self.map_reader.request_tiles(future_tile_ids)
                         log_event("DAEMON", "INFO", "READER_CALL_REQUEST_TILES_END", num_tiles=len(future_tile_ids))
                    else:
                         log_event("DAEMON", "DEBUG", "PROACTIVE_TILE_LOADING_NO_NEW_TILES")
                else:
                    log_event("DAEMON", "DEBUG", "PROACTIVE_TILE_LOADING_SKIP_NO_NEXT_WAYS")

                # --- Populate Next Segments Data for liveMapData ---
                next_segments_list = []
                cumulative_dist_next_start_for_pub = next_limit_dist # Start with dist to first speed change / way end
                current_segment_remaining_dist = 0.0

                if self.current_segment_data and self.current_on_way_result and self.last_valid_pos:
                    log_event("DAEMON", "DEBUG", "MATCHER_CALL_DISTANCE_TO_END_OF_WAY_START", segment_id=self.current_segment_id)
                    current_segment_remaining_dist = matcher.distance_to_end_of_way(
                        self.last_valid_pos,
                        self.current_segment_data,
                        self.current_on_way_result
                    )
                    log_event("DAEMON", "DEBUG", "MATCHER_CALL_DISTANCE_TO_END_OF_WAY_END",
                              segment_id=self.current_segment_id,
                              remaining_dist_m=current_segment_remaining_dist)

                # Adjust cumulative_dist_next_start_for_pub:
                # If next_limit_dist refers to a point on the *current* segment,
                # it's an absolute distance from the *start* of the current segment.
                # We need to convert it to distance from *current vehicle position*.
                # However, find_next_ways_and_speed_limit_change already returns dist_to_slc FROM VEHICLE.
                # So, next_limit_dist is already correct.

                # The first "next" segment for publishing purposes starts *after* the current one.
                # The distance to its start is current_segment_remaining_dist.
                # If a speed limit change occurs *on the current segment*,
                #   next_limit_dist will be < current_segment_remaining_dist.
                # If it occurs *on a future segment*,
                #   next_limit_dist will be current_segment_remaining_dist + dist_on_future_segments.

                # For msg.liveMapData.nextSegments, distanceToStart is from vehicle to START of that segment.
                # Initial distance is to the start of the *first actual next* segment.
                cumulative_dist_to_start_of_next_segment_for_msg = current_segment_remaining_dist
                log_event("DAEMON", "DEBUG", "NEXT_SEGMENTS_POPULATION_START",
                          num_next_ways_results=len(next_ways_results),
                          initial_cumulative_dist_m=cumulative_dist_to_start_of_next_segment_for_msg)

                for i, next_way_item in enumerate(next_ways_results):
                    next_segment_id_pub = next_way_item.segment_id
                    log_event("DAEMON", "DEBUG", "READER_ACCESS_SEGMENT_DATA_NEXT_SEG_START", segment_id=next_segment_id_pub)
                    next_segment_data_pub = self.map_reader.segments_data.get(next_segment_id_pub)
                    log_event("DAEMON", "DEBUG", "READER_ACCESS_SEGMENT_DATA_NEXT_SEG_END",
                              segment_id=next_segment_id_pub,
                              data_found=(next_segment_data_pub is not None))

                    if not next_segment_data_pub:
                        log_event("DAEMON", "WARN", "NEXT_SEGMENTS_POPULATION_FAIL_NO_SEG_DATA", segment_id=next_segment_id_pub)
                        continue # Skip if data not available (should be rare if proactive loading works)

                    seg_len_pub = get_segment_length(next_segment_data_pub)
                    curv_speeds_next_raw = next_segment_data_pub.get('curvature_derived_speeds_mps', [])
                    coords_next_raw = self.map_reader.get_segment_coords(next_segment_id_pub)
                    distances_next_raw = []

                    if curv_speeds_next_raw and coords_next_raw and len(coords_next_raw) > 2:
                        cumulative_node_dist_next = 0.0
                        if len(coords_next_raw) > 1:
                            lat1_n, lon1_n = coords_next_raw[0]
                            lat2_n, lon2_n = coords_next_raw[1]
                            cumulative_node_dist_next = geometry.distance_to_point(
                                lat1_n * geometry.TO_RADIANS, lon1_n * geometry.TO_RADIANS,
                                lat2_n * geometry.TO_RADIANS, lon2_n * geometry.TO_RADIANS
                            )
                        for j_next in range(len(curv_speeds_next_raw)):
                            target_node_idx_next = j_next + 1
                            if target_node_idx_next == 1:
                                distances_next_raw.append(cumulative_node_dist_next)
                            elif target_node_idx_next < len(coords_next_raw):
                                lat1_curr_n, lon1_curr_n = coords_next_raw[j_next]
                                lat2_curr_n, lon2_curr_n = coords_next_raw[target_node_idx_next]
                                segment_dist_n = geometry.distance_to_point(
                                    lat1_curr_n * geometry.TO_RADIANS, lon1_curr_n * geometry.TO_RADIANS,
                                    lat2_curr_n * geometry.TO_RADIANS, lon2_curr_n * geometry.TO_RADIANS
                                )
                                cumulative_node_dist_next += segment_dist_n
                                distances_next_raw.append(cumulative_node_dist_next)
                            else:
                                distances_next_raw.append(cumulative_node_dist_next)

                    # --- COMPACT BEFORE ASSIGNING --- #
                    compact_distances_next, compact_speeds_next = _compact(distances_next_raw, curv_speeds_next_raw)
                    log_event("DAEMON", "TRACE", "NEXT_SEGMENT_CURVATURE_COMPACTED",
                              segment_id=next_segment_id_pub,
                              raw_dist_count=len(distances_next_raw),
                              raw_speed_count=len(curv_speeds_next_raw),
                              compact_dist_count=len(compact_distances_next),
                              compact_speed_count=len(compact_speeds_next))
                    # --- END COMPACT --- #

                    next_seg_struct = log.LiveMapData.NextSegmentData.new_message(
                        segmentId=next_segment_id_pub,
                        distanceToStart=cumulative_dist_to_start_of_next_segment_for_msg, # This is distance from VEHICLE to START of this specific next_segment
                        segmentLength=seg_len_pub,
                        curvatureDerivedSpeedsMps=compact_speeds_next, # Use compacted data
                        distancesForSpeeds=compact_distances_next  # Use compacted data
                    )
                    next_segments_list.append(next_seg_struct)
                    # For the *following* segment in the list, its distanceToStart will be incremented by current one's length
                    cumulative_dist_to_start_of_next_segment_for_msg += seg_len_pub
                    log_event("DAEMON", "TRACE", "NEXT_SEGMENT_ADDED_TO_MSG",
                              segment_id=next_segment_id_pub,
                              dist_to_start_m=next_seg_struct.distanceToStart,
                              length_m=seg_len_pub,
                              next_cumulative_dist_m=cumulative_dist_to_start_of_next_segment_for_msg)

                    msg.liveMapData.nextSegments = next_segments_list
                log_event("DAEMON", "DEBUG", "NEXT_SEGMENTS_POPULATION_COMPLETE", num_populated=len(next_segments_list))
                # ------------------------------------------------

            except Exception as e:
                cloudlog.exception(f"MapdPyDaemon: Error finding next speed limit/ways: {e}")
                log_event("DAEMON", "ERROR", "NEXT_WAYS_SPEED_LIMIT_EXCEPTION", error=str(e))
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

        msg.liveMapData.speedLimitAheadValid = is_on_segment and found_next_limit and next_limit_mps > 0 and next_limit_dist >= 0
        msg.liveMapData.speedLimitAhead = float(next_limit_mps) # m/s
        msg.liveMapData.speedLimitAheadDistance = float(next_limit_dist) # m

        # Add road name if available
        if is_on_segment and self.current_segment_data: # Check if current_segment_data is not None
             msg.liveMapData.currentRoadName = str(self.current_segment_data.get('name', "")) # Use .get for safety
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
                 # For now, just populate with what we have for the param.
                 next_limit_info = {
                     'speed': next_limit_mps, # m/s
                     'distance': next_limit_dist, # m
                     # 'latitude': None, # To be added if needed
                     # 'longitude': None # To be added if needed
                 }
            self.params_memory.put("NextMapSpeedLimit", json.dumps(next_limit_info))
            log_event("DAEMON", "DEBUG", "LEGACY_PARAMS_WRITE_SUCCESS",
                      map_speed_limit=current_limit_mps,
                      next_map_speed_limit_info=next_limit_info)
        except Exception as e:
            cloudlog.exception(f"MapdPyDaemon: Error writing legacy params: {e}")
            log_event("DAEMON", "ERROR", "LEGACY_PARAMS_WRITE_FAIL", error=str(e))


def main():
    # Run this Python process with low scheduling priority on core 2 so it
    # can do heavy shapely/math work without contending with openpilot's
    # real-time control loops (controlsd/core-0, locationd/core-1 etc.).
    try:
        from openpilot.common.realtime import config_realtime_process, Priority
        # Allow the process to run on cores 2 *and* 3 so that the dedicated tile
        # loader thread can be exclusively pinned to core 3 while the rest of the
        # daemon continues on core 2.  See reader.MapReader initialisation above.
        config_realtime_process([2, 3], Priority.CTRL_LOW)
        log_event("DAEMON", "INFO", "REALTIME_PRIORITY_CONFIG_SUCCESS", cores=[2,3], priority="CTRL_LOW")
    except Exception as e:
        # Don't crash if called outside full openpilot environment
        # print(f"mapd_daemon: unable to set realtime priority ({e})")
        log_event("DAEMON", "WARN", "REALTIME_PRIORITY_CONFIG_FAIL", error=str(e))

    daemon = MapdPyDaemon()
    rk = Ratekeeper(1.0) # Run at 1 Hz
    log_event("DAEMON", "INFO", "MAIN_LOOP_STARTING", rate_hz=1.0)
    while True:
        daemon.update()
        rk.keep_time()

if __name__ == "__main__":
    main()