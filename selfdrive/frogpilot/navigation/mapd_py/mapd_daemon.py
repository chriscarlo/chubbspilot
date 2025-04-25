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

        if location_valid and self.last_valid_pos is not None:
            # --- Find Current Segment ---
            try:
                # Ensure tiles around the current location are loaded into the cache
                self.map_reader._update_loaded_tiles(self.last_valid_pos.latitude, self.last_valid_pos.longitude)

                # Query the R-tree index (which reflects the cache) for nearby segments
                search_bounds = (self.last_valid_pos.longitude - 1e-4,
                                 self.last_valid_pos.latitude - 1e-4,
                                 self.last_valid_pos.longitude + 1e-4,
                                 self.last_valid_pos.latitude + 1e-4)
                nearest_candidates = list(self.map_reader.rtree_idx.intersection(search_bounds, objects=True))

                segment_data = None # Initialize segment_data to None
                if nearest_candidates:
                    closest_segment_info = None
                    min_dist = float('inf')
                    current_point = Point(self.last_valid_pos.longitude, self.last_valid_pos.latitude)

                    # Find the segment whose geometry is actually closest among candidates
                    for item in nearest_candidates:
                        segment_id = item.object
                        segment_info = self.map_reader.segments_data.get(segment_id)
                        if segment_info:
                            self.map_reader.segments_data.move_to_end(segment_id) # Mark as recently used
                            distance = segment_info['geom'].distance(current_point)
                            MAX_RELEVANT_DISTANCE_DEGREES = 0.0015
                            if distance < min_dist and distance < MAX_RELEVANT_DISTANCE_DEGREES:
                                min_dist = distance
                                closest_segment_info = segment_info

                    segment_data = closest_segment_info # Assign the closest found segment

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

            # Find next speed limit change
            try:
                current_way_res = matcher.CurrentWayResult(
                    segment_id=self.current_segment_id,
                    on_way_result=self.current_on_way_result
                )
                next_ways_results = matcher.get_next_ways(self.last_valid_pos, current_way_res, self.map_reader)

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
                        segment_len = matcher.get_segment_length(next_segment_data) # Use simplified length getter
                        cumulative_dist_to_next_start += segment_len

            except Exception as e:
                cloudlog.exception(f"MapdPyDaemon: Error finding next speed limit: {e}")
                next_limit_mps = 0.0
                next_limit_dist = 0.0
        else:
            # Not on a segment, clear limits
            current_limit_mps = 0.0
            next_limit_mps = 0.0
            next_limit_dist = 0.0

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

        # Add curvature info (placeholder for now, could be calculated here or read if precalculated)
        # msg.liveMapData.curvatureValid = False
        # msg.liveMapData.distToTurn = 0.0
        # msg.liveMapData.turnSpeedLimit = 0.0

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