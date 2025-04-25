#!/usr/bin/env python3
import json
import math
import os
import threading

import requests

import cereal.messaging as messaging
from cereal import log
from openpilot.common.api import Api
from openpilot.common.numpy_fast import interp
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.selfdrive.navd.helpers import (Coordinate, coordinate_from_param,
                                    distance_along_geometry, maxspeed_to_ms,
                                    minimum_distance,
                                    parse_banner_instructions)
from openpilot.common.swaglog import cloudlog

from openpilot.selfdrive.frogpilot.frogpilot_variables import get_frogpilot_toggles, has_prime

REROUTE_DISTANCE = 25
MANEUVER_TRANSITION_THRESHOLD = 10
REROUTE_COUNTER_MIN = 3

# Mock Route Constants
MOCK_ROUTE_DISTANCE_KM = 1.5  # Distance ahead for mock route (km)
MOCK_ROUTE_RECALC_INTERVAL_SEC = 300 # How often to recalculate mock route (seconds)
EARTH_RADIUS_KM = 6371.0

MAPBOX_API_KEY_FILE = "/persist/mapbox/mapbox_api.txt"

class RouteEngine:
  def __init__(self, sm, pm):
    self.sm = sm
    self.pm = pm

    self.params = Params()
    print("navd.py: Params initialized.", flush=True)

    # == MOCK DATA FOR TESTING ==
    mock_lat = 37.7749 # San Francisco Civic Center approx lat
    mock_lon = -122.4194 # San Francisco Civic Center approx lon
    self.last_position = Coordinate(mock_lat, mock_lon)
    self.last_bearing = 0.0 # North
    self.gps_ok = True
    self.localizer_valid = True
    print(f"navd.py: Using MOCK Initial Data: pos={self.last_position}, bearing={self.last_bearing}, gps_ok={self.gps_ok}, localizer_valid={self.localizer_valid}", flush=True)
    # ===========================

    self.nav_destination = None
    self.step_idx = None
    self.route = None
    self.route_geometry = None

    self.recompute_backoff = 0
    self.recompute_countdown = 0

    self.ui_pid = None

    self.reroute_counter = 0


    self.api = None
    self.mapbox_token = None
    self.mapbox_public_token = None
    self.mapbox_host = None
    print(f"navd.py: Attempting to load keys from {MAPBOX_API_KEY_FILE}...", flush=True)
    key_loaded_from_file = False
    try:
      with open(MAPBOX_API_KEY_FILE, 'r') as f:
        print(f"navd.py: Opened {MAPBOX_API_KEY_FILE}", flush=True)
        keys = json.load(f)
        print(f"navd.py: Parsed JSON keys: {keys}", flush=True) # Be careful logging keys
        self.mapbox_token = keys.get('secret_key')
        self.mapbox_public_token = keys.get('public_key')
        if self.mapbox_token:
          print("navd.py: Found secret_key in file.", flush=True)
          self.mapbox_host = "https://api.mapbox.com"
          cloudlog.info("Using Mapbox keys from file.")
          print("navd.py: CLOUDLG - Using Mapbox keys from file.", flush=True)
          key_loaded_from_file = True
        else:
           print("navd.py: secret_key not found in file.", flush=True)
    except FileNotFoundError:
      print(f"navd.py: {MAPBOX_API_KEY_FILE} not found.", flush=True)
      cloudlog.warning(f"Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: FileNotFoundError.")
      print(f"navd.py: CLOUDLG - Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: FileNotFoundError.", flush=True)
    except json.JSONDecodeError as e:
      print(f"navd.py: Error decoding JSON from {MAPBOX_API_KEY_FILE}: {e}", flush=True)
      cloudlog.warning(f"Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: JSONDecodeError: {e}")
      print(f"navd.py: CLOUDLG - Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: JSONDecodeError: {e}", flush=True)
    except KeyError as e:
      print(f"navd.py: Key error parsing {MAPBOX_API_KEY_FILE}: {e}", flush=True)
      cloudlog.warning(f"Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: KeyError: {e}")
      print(f"navd.py: CLOUDLG - Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: KeyError: {e}", flush=True)
    except Exception as e: # Catch other potential errors
        print(f"navd.py: Unexpected error loading key file {MAPBOX_API_KEY_FILE}: {e}", flush=True)
        cloudlog.warning(f"Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: {e}. Falling back to other methods.")
        print(f"navd.py: CLOUDLG - Could not load Mapbox keys from {MAPBOX_API_KEY_FILE}: {e}. Falling back to other methods.", flush=True)

    # Fallback logic
    if not key_loaded_from_file:
      print("navd.py: Key file failed, entering fallback logic...", flush=True)
      # Fallback logic (existing code)
      if "MAPBOX_TOKEN" in os.environ:
        print("navd.py: Checking MAPBOX_TOKEN env var...", flush=True)
        self.mapbox_token = os.environ["MAPBOX_TOKEN"]
        self.mapbox_host = "https://api.mapbox.com"
        cloudlog.info("Using Mapbox token from environment variable.")
        print("navd.py: CLOUDLG - Using Mapbox token from environment variable.", flush=True)
      elif not has_prime():
        print("navd.py: Not prime user, checking MapboxSecretKey param...", flush=True)
        self.mapbox_token = self.params.get("MapboxSecretKey", encoding='utf8')
        if self.mapbox_token:
            print("navd.py: Using token from MapboxSecretKey param.", flush=True)
            cloudlog.info("Using Mapbox token from MapboxSecretKey param.")
            self.mapbox_host = "https://api.mapbox.com"
            print("navd.py: CLOUDLG - Using Mapbox token from MapboxSecretKey param.", flush=True)
        else:
            print("navd.py: MapboxSecretKey param not found.", flush=True)
            cloudlog.warning("No MapboxSecretKey param found.")
            print("navd.py: CLOUDLG - No MapboxSecretKey param found.", flush=True)
      else: # has_prime()
        print("navd.py: Prime user, using comma api proxy...", flush=True)
        self.api = Api(self.params.get("DongleId", encoding='utf8'))
        self.mapbox_host = "https://maps.comma.ai"
        cloudlog.info("Using comma.ai map proxy.")
        print("navd.py: CLOUDLG - Using comma.ai map proxy.", flush=True)

    # Ensure mapbox_host is set if token was found in file but not otherwise
    if self.mapbox_token and not self.mapbox_host:
        print("navd.py: Setting mapbox_host for file token.", flush=True)
        self.mapbox_host = "https://api.mapbox.com" # Default if token exists but host wasn't set

    # Final check
    if not self.mapbox_token and not self.api:
      print("navd.py: ERROR - No token/API configured.", flush=True)
      cloudlog.error("Mapbox token/API key not configured and not using comma proxy.")
      print("navd.py: CLOUDLG - Mapbox token/API key not configured and not using comma proxy.", flush=True)
    else:
       print(f"navd.py: API config final check OK. Host: {self.mapbox_host}, Token set: {self.mapbox_token is not None}, API set: {self.api is not None}", flush=True)

    # FrogPilot variables
    self.frogpilot_toggles = get_frogpilot_toggles()

    self.approaching_intersection = False
    self.approaching_turn = False

    self.nav_speed_limit = 0

    self.stop_coord = []
    self.stop_signal = []

    # Mock Route State
    self.mock_route_active = False
    self.mock_route_timer = 0 # Start timer at 0 to trigger initial calculation

    print("navd.py: RouteEngine __init__ finished.", flush=True)

  def update(self):
    print("\\n--- navd.py: update cycle start ---", flush=True) # ADDED
    self.sm.update(0)

    if self.sm.updated["managerState"]:
      ui_pid = [p.pid for p in self.sm["managerState"].processes if p.name == "ui" and p.running]
      if ui_pid:
        if self.ui_pid and self.ui_pid != ui_pid[0]:
          cloudlog.warning("UI restarting, sending route")
          print("navd.py: CLOUDLG - UI restarting, sending route", flush=True)
          threading.Timer(5.0, self.send_route).start()
        self.ui_pid = ui_pid[0]

    self.update_location()
    print(f"navd.py: update - after update_location: gps_ok={self.gps_ok}, localizer_valid={self.localizer_valid}, last_bearing={self.last_bearing}", flush=True) # ADDED
    try:
      print("navd.py: update - calling recompute_route...", flush=True) # ADDED
      self.recompute_route()
      print("navd.py: update - finished recompute_route, calling send_instruction...", flush=True) # ADDED
      self.send_instruction()
    except Exception:
      cloudlog.exception("navd.failed_to_compute")
      print("navd.py: CLOUDLG - navd.failed_to_compute", flush=True)

    # Update FrogPilot parameters
    if self.sm['frogpilotPlan'].togglesUpdated:
      self.frogpilot_toggles = get_frogpilot_toggles()

  def update_location(self):
    print("navd.py: update_location called...", flush=True) # ADDED
    location = self.sm['liveLocationKalman']
    # == TEMP MOD FOR TESTING: Prevent overwriting mock data ==
    # Normally, we'd update gps_ok, localizer_valid, last_bearing, and last_position here.
    # We are skipping this for now to force the use of initial mock data.
    # REMEMBER TO REVERT THIS!
    print("navd.py: update_location - TEMP: Skipping update from liveLocationKalman to preserve mock data.", flush=True)
    _gps_ok_real = location.gpsOK
    _localizer_valid_real = (location.status == log.LiveLocationKalman.Status.valid) and location.positionGeodetic.valid
    print(f"navd.py: update_location - TEMP: Real status is gps_ok={_gps_ok_real}, localizer_valid={_localizer_valid_real}", flush=True)
    # ========================================================

    # Decrement mock route timer (ensuring it doesn't go below zero)
    # Assumes update() is called roughly once per second by Ratekeeper
    self.mock_route_timer = max(0, self.mock_route_timer - 1)
    print(f"navd.py: update_location - Updated mock_route_timer: {self.mock_route_timer}", flush=True) # ADDED

  def recompute_route(self):
    print("navd.py: recompute_route called...", flush=True) # Existing trace, confirmed present
    if self.last_position is None:
      print("navd.py: recompute_route - last_position is None, returning.", flush=True)
      return

    # Don't recompute when GPS drifts in tunnels
    if not self.gps_ok and self.step_idx is not None:
      print("navd.py: recompute_route - GPS not OK but have route, returning.", flush=True)
      return

    new_destination = coordinate_from_param("NavDestination", self.params)
    print(f"navd.py: recompute_route - Read NavDestination: {new_destination}", flush=True)

    # --- Mock Route Logic ---
    if new_destination is None:
      print(f"navd.py: recompute_route - Entering mock route logic. Active: {self.mock_route_active}, Timer: {self.mock_route_timer}", flush=True)
      mock_conditions_met = (self.last_bearing is not None and self.gps_ok and self.localizer_valid)
      print(f"navd.py: recompute_route - Mock Activation Conditions: Bearing={self.last_bearing is not None}, GPS OK={self.gps_ok}, Localizer Valid={self.localizer_valid} -> Met={mock_conditions_met}", flush=True)
      if not self.mock_route_active and mock_conditions_met:
        # Start mock route if not active and conditions are met
        print("navd.py: recompute_route - Triggering mock route activation.", flush=True)
        self.mock_route_timer = 0 # Trigger immediate calculation
        self.mock_route_active = True
        cloudlog.info("No destination set, activating mock route.")
        print("navd.py: CLOUDLG - No destination set, activating mock route.", flush=True)

      if self.mock_route_active and self.mock_route_timer == 0:
        print("navd.py: recompute_route - Mock route active and timer is 0, attempting calculation.", flush=True)
        if self.last_bearing is None or not self.gps_ok or not self.localizer_valid:
          print("navd.py: recompute_route - Mock conditions lost before calculation.", flush=True)
          cloudlog.warning("Mock route conditions lost (bearing/gps/localizer), deactivating.")
          print("navd.py: CLOUDLG - Mock route conditions lost (bearing/gps/localizer), deactivating.", flush=True)
          self.clear_route() # This also sets mock_route_active to False and resets timer
          return

        mock_dest = self.calculate_coordinate_ahead(self.last_position.latitude,
                                                  self.last_position.longitude,
                                                  self.last_bearing,
                                                  MOCK_ROUTE_DISTANCE_KM)
        if mock_dest:
          print(f"navd.py: recompute_route - Calculated mock destination: {mock_dest}", flush=True)
          cloudlog.info(f"Calculating mock route to {mock_dest}")
          print(f"navd.py: CLOUDLG - Calculating mock route to {mock_dest}", flush=True)
          self.calculate_route(mock_dest)
          # Reset timer for next recalculation
          self.mock_route_timer = MOCK_ROUTE_RECALC_INTERVAL_SEC
        else:
          print("navd.py: recompute_route - Failed to calculate mock destination coordinate.", flush=True)
          cloudlog.error("Failed to calculate mock destination.")
          print("navd.py: CLOUDLG - Failed to calculate mock destination.", flush=True)
          # Don't retry immediately, wait for next timer cycle or location update
          self.mock_route_timer = MOCK_ROUTE_RECALC_INTERVAL_SEC // 10 # Retry sooner
      print("navd.py: recompute_route - Exiting after mock route logic.", flush=True)
      return # Don't proceed to regular route logic if handling mock route

    # --- Regular Route Logic ---
    print("navd.py: recompute_route - Entering regular route logic.", flush=True)
    # If a destination is set, ensure mock route is deactivated
    if self.mock_route_active:
        print("navd.py: recompute_route - Deactivating mock route due to set destination.", flush=True)
        cloudlog.info("Destination set, deactivating mock route.")
        print("navd.py: CLOUDLG - Destination set, deactivating mock route.", flush=True)
        self.clear_route() # Deactivates mock route and clears existing route data
        # Don't return here, let regular logic continue with the new destination

    # Existing logic for handling NavDestination changes and recomputing
    needs_route = self.should_recompute()
    print(f"navd.py: recompute_route - should_recompute() returned: {needs_route}", flush=True)
    destination_changed = (new_destination != self.nav_destination)
    print(f"navd.py: recompute_route - Destination changed: {destination_changed} (New: {new_destination}, Old: {self.nav_destination})", flush=True)

    should_recompute_final = needs_route or destination_changed
    print(f"navd.py: recompute_route - Final should_recompute check: {should_recompute_final}", flush=True)

    if new_destination != self.nav_destination: # Log only if changed
      cloudlog.warning(f"Got new destination from NavDestination param {new_destination}")
      print(f"navd.py: CLOUDLG - Got new destination from NavDestination param {new_destination}", flush=True)
      # should_recompute = True # Handled by should_recompute_final

    print(f"navd.py: recompute_route - Checking countdown ({self.recompute_countdown}) and should_recompute ({should_recompute_final})", flush=True)
    if self.recompute_countdown == 0 and should_recompute_final:
      print(f"navd.py: recompute_route - Conditions met, calling calculate_route. Backoff: {self.recompute_backoff}", flush=True)
      self.recompute_countdown = 2**self.recompute_backoff
      self.recompute_backoff = min(6, self.recompute_backoff + 1)
      self.calculate_route(new_destination)
      self.reroute_counter = 0
    else:
      print("navd.py: recompute_route - Conditions not met or countdown active, decrementing countdown.", flush=True)
      self.recompute_countdown = max(0, self.recompute_countdown - 1)
    print("navd.py: recompute_route finished.", flush=True)

  def calculate_route(self, destination):
    print(f"navd.py: calculate_route called for destination: {destination}", flush=True)
    cloudlog.warning(f"Calculating route {self.last_position} -> {destination}")
    print(f"navd.py: CLOUDLG - Calculating route {self.last_position} -> {destination}", flush=True)
    self.nav_destination = destination

    lang = self.params.get('LanguageSetting', encoding='utf8')
    if lang is not None:
      lang = lang.replace('main_', '')

    token = self.mapbox_token
    if token is None:
      token = self.api.get_token()

    if token is None:
      print("navd.py: calculate_route - No token available, exiting.", flush=True)
      cloudlog.error("No valid Mapbox token or API token available. Cannot fetch route.")
      print("navd.py: CLOUDLG - No valid Mapbox token or API token available. Cannot fetch route.", flush=True)
      self.clear_route()
      return

    params = {
      'access_token': token,
      'annotations': 'maxspeed',
      'geometries': 'geojson',
      'overview': 'full',
      'steps': 'true',
      'banner_instructions': 'true',
      'alternatives': 'false',
      'language': lang,
    }

    # TODO: move waypoints into NavDestination param?
    waypoints = self.params.get('NavDestinationWaypoints', encoding='utf8')
    waypoint_coords = []
    if waypoints is not None and len(waypoints) > 0:
      waypoint_coords = json.loads(waypoints)

    coords = [
      (self.last_position.longitude, self.last_position.latitude),
      *waypoint_coords,
      (destination.longitude, destination.latitude)
    ]
    params['waypoints'] = f'0;{len(coords)-1}'
    if self.last_bearing is not None:
      params['bearings'] = f"{(self.last_bearing + 360) % 360:.0f},90" + (';'*(len(coords)-1))

    coords_str = ';'.join([f'{lon},{lat}' for lon, lat in coords])
    url = self.mapbox_host + '/directions/v5/mapbox/driving-traffic/' + coords_str
    print(f"navd.py: calculate_route - Requesting URL: {url}", flush=True)
    print(f"navd.py: calculate_route - Params: {params}", flush=True)
    try:
      print("navd.py: calculate_route - Sending request...", flush=True)
      resp = requests.get(url, params=params, timeout=10)
      print(f"navd.py: calculate_route - Response Status Code: {resp.status_code}", flush=True)
      if resp.status_code != 200:
        print(f"navd.py: calculate_route - API Error Response Text: {resp.text}", flush=True)
        cloudlog.event("API request failed", status_code=resp.status_code, text=resp.text, error=True)
        print(f"navd.py: CLOUDLG - API request failed. status_code={resp.status_code}, text={resp.text}", flush=True)
      resp.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)

      print("navd.py: calculate_route - Request successful, parsing JSON...", flush=True)
      r = resp.json()
      r1 = resp.json()

      # Function to remove specified keys recursively unnessary for display
      def remove_keys(obj, keys_to_remove):
        if isinstance(obj, list):
          return [remove_keys(item, keys_to_remove) for item in obj]
        elif isinstance(obj, dict):
          return {key: remove_keys(value, keys_to_remove) for key, value in obj.items() if key not in keys_to_remove}
        else:
          return obj

      keys_to_remove = ['geometry', 'annotation', 'incidents', 'intersections', 'components', 'sub', 'waypoints']
      self.r2 = remove_keys(r1, keys_to_remove)
      self.r3 = {}

      # Add items for display under "routes"
      if 'routes' in self.r2 and len(self.r2['routes']) > 0:
        first_route = self.r2['routes'][0]
        nav_destination_json = self.params.get('NavDestination')

        # Only try to load destination info if it actually exists (not a mock route)
        if nav_destination_json is not None:
            try:
              nav_destination_data = json.loads(nav_destination_json)
              place_name = nav_destination_data.get('place_name', '[No Destination Set]') # Changed default
              first_route['Destination'] = place_name
            except json.JSONDecodeError as e:
              print(f"Error decoding NavDestination JSON: {e}")
              first_route['Destination'] = "[Destination Error]"
        else:
            first_route['Destination'] = "[Mock Route Active]" # Indicate mock route

        # These can be set regardless of destination existence
        first_route['Metric'] = self.params.get_bool("IsMetric")
        self.r3['CurrentStep'] = 0
        if 'uuid' in self.r2:
            self.r3['uuid'] = self.r2['uuid']
        else:
            print("Warning: No UUID found in Mapbox response")
            self.r3['uuid'] = "N/A"

      # Save slim json as file
      with open('navdirections.json', 'w') as json_file:
        json.dump(self.r2, json_file, indent=4)
      with open('CurrentStep.json', 'w') as json_file:
        json.dump(self.r3, json_file, indent=4)

      if len(r['routes']):
        print("navd.py: calculate_route - Route found, processing steps...", flush=True)
        self.route = r['routes'][0]['legs'][0]['steps']
        self.route_geometry = []

        # Iterate through the steps in self.route to find "stop_sign" and "traffic_light"
        if self.frogpilot_toggles.conditional_navigation_intersections:
          self.stop_signal = []
          self.stop_coord = []

          for step in self.route:
            for intersection in step["intersections"]:
              if "stop_sign" in intersection or "traffic_signal" in intersection:
                self.stop_signal.append(intersection["geometry_index"])
                self.stop_coord.append(Coordinate.from_mapbox_tuple(intersection["location"]))

        maxspeed_idx = 0
        maxspeeds = r['routes'][0]['legs'][0]['annotation']['maxspeed']

        # Convert coordinates
        for step in self.route:
          coords = []

          for c in step['geometry']['coordinates']:
            coord = Coordinate.from_mapbox_tuple(c)

            # Last step does not have maxspeed
            if (maxspeed_idx < len(maxspeeds)):
              maxspeed = maxspeeds[maxspeed_idx]
              if ('unknown' not in maxspeed) and ('none' not in maxspeed):
                coord.annotations['maxspeed'] = maxspeed_to_ms(maxspeed)

            coords.append(coord)
            maxspeed_idx += 1

          self.route_geometry.append(coords)
          maxspeed_idx -= 1  # Every segment ends with the same coordinate as the start of the next

        self.step_idx = 0
        print(f"navd.py: calculate_route - Successfully set step_idx to {self.step_idx}", flush=True)
      else:
        print("navd.py: calculate_route - Mapbox returned empty route list.", flush=True)
        cloudlog.warning("Got empty route response")
        print("navd.py: CLOUDLG - Got empty route response", flush=True)
        self.clear_route()

      # clear waypoints to avoid a re-route including past waypoints
      # TODO: only clear once we're past a waypoint
      self.params.remove('NavDestinationWaypoints')

    except requests.exceptions.Timeout:
        print("navd.py: calculate_route - Request timed out.", flush=True)
        cloudlog.exception("failed to get route - timeout")
        print("navd.py: CLOUDLG - failed to get route - timeout", flush=True)
        self.clear_route()
    except requests.exceptions.RequestException as e:
        print(f"navd.py: calculate_route - Request failed: {e}", flush=True)
        cloudlog.exception("failed to get route")
        print(f"navd.py: CLOUDLG - failed to get route: {e}", flush=True)
        self.clear_route()
    except Exception as e: # Catch other potential errors like JSON parsing
        print(f"navd.py: calculate_route - Unexpected error: {e}", flush=True)
        cloudlog.exception("navd.calculate_route unexpected error")
        print(f"navd.py: CLOUDLG - navd.calculate_route unexpected error: {e}", flush=True)
        self.clear_route()

    self.send_route()

  def send_instruction(self):
    print("navd.py: send_instruction called...", flush=True) # Added trace
    msg = messaging.new_message('navInstruction', valid=True)
    fp_msg = messaging.new_message('frogpilotNavigation', valid=True)

    if self.step_idx is None:
      print("navd.py: send_instruction - step_idx is None, invalidating.", flush=True)
      msg.valid = False
      self.pm.send('navInstruction', msg)

      fp_msg.frogpilotNavigation.navigationSpeedLimit = 0
      self.pm.send('frogpilotNavigation', fp_msg)
      return

    step = self.route[self.step_idx]
    geometry = self.route_geometry[self.step_idx]
    along_geometry = distance_along_geometry(geometry, self.last_position)
    distance_to_maneuver_along_geometry = step['distance'] - along_geometry

    # Banner instructions are for the following maneuver step, don't use empty last step
    banner_step = step
    if not len(banner_step['bannerInstructions']) and self.step_idx == len(self.route) - 1:
      banner_step = self.route[max(self.step_idx - 1, 0)]

    # Current instruction
    msg.navInstruction.maneuverDistance = distance_to_maneuver_along_geometry
    instruction = parse_banner_instructions(banner_step['bannerInstructions'], distance_to_maneuver_along_geometry)
    if instruction is not None:
      for k,v in instruction.items():
        setattr(msg.navInstruction, k, v)

    # All instructions
    maneuvers = []
    for i, step_i in enumerate(self.route):
      if i < self.step_idx:
        distance_to_maneuver = -sum(self.route[j]['distance'] for j in range(i+1, self.step_idx)) - along_geometry
      elif i == self.step_idx:
        distance_to_maneuver = distance_to_maneuver_along_geometry
      else:
        distance_to_maneuver = distance_to_maneuver_along_geometry + sum(self.route[j]['distance'] for j in range(self.step_idx+1, i+1))

      instruction = parse_banner_instructions(step_i['bannerInstructions'], distance_to_maneuver)
      if instruction is None:
        continue
      maneuver = {'distance': distance_to_maneuver}
      if 'maneuverType' in instruction:
        maneuver['type'] = instruction['maneuverType']
      if 'maneuverModifier' in instruction:
        maneuver['modifier'] = instruction['maneuverModifier']
      maneuvers.append(maneuver)

    msg.navInstruction.allManeuvers = maneuvers

    # Compute total remaining time and distance
    remaining = 1.0 - along_geometry / max(step['distance'], 1)
    total_distance = step['distance'] * remaining
    total_time = step['duration'] * remaining

    if step['duration_typical'] is None:
      total_time_typical = total_time
    else:
      total_time_typical = step['duration_typical'] * remaining

    # Add up totals for future steps
    for i in range(self.step_idx + 1, len(self.route)):
      total_distance += self.route[i]['distance']
      total_time += self.route[i]['duration']
      if self.route[i]['duration_typical'] is None:
        total_time_typical += self.route[i]['duration']
      else:
        total_time_typical += self.route[i]['duration_typical']

    msg.navInstruction.distanceRemaining = total_distance
    msg.navInstruction.timeRemaining = total_time
    msg.navInstruction.timeRemainingTypical = total_time_typical

    # Speed limit logic
    print("navd.py: send_instruction - Processing speed limit...", flush=True)
    current_nav_speed_limit = 0 # Local variable for this cycle
    speed_limit_found = False
    try:
        closest_idx, closest = min(enumerate(geometry), key=lambda p: p[1].distance_to(self.last_position))
        print(f"navd.py: send_instruction - Closest geometry index: {closest_idx}", flush=True)
        if closest_idx > 0:
            # If we are not past the closest point, show previous
            if along_geometry < distance_along_geometry(geometry, geometry[closest_idx]):
                print("navd.py: send_instruction - Using previous geometry point for speed limit.", flush=True)
                closest = geometry[closest_idx - 1]

        print(f"navd.py: send_instruction - Checking annotations for point: {closest}", flush=True)
        if 'maxspeed' in closest.annotations:
            speed_limit_found = True
            maxspeed_value = closest.annotations['maxspeed']
            print(f"navd.py: send_instruction - Found maxspeed annotation: {maxspeed_value}", flush=True)
            if self.localizer_valid:
                print("navd.py: send_instruction - Localizer valid, setting speed limit.", flush=True)
                msg.navInstruction.speedLimit = maxspeed_value
                current_nav_speed_limit = maxspeed_value
            else:
                print("navd.py: send_instruction - Localizer invalid, not setting speed limit in msg.", flush=True)
                current_nav_speed_limit = 0 # Set internal variable to 0 if localizer invalid
        else:
             print("navd.py: send_instruction - No maxspeed annotation found for closest point.", flush=True)

    except Exception as e:
        print(f"navd.py: send_instruction - Error during speed limit processing: {e}", flush=True)
        cloudlog.exception("navd.send_instruction speed limit error")
        print(f"navd.py: CLOUDLG - navd.send_instruction speed limit error: {e}", flush=True)

    # Update internal state AFTER processing
    self.nav_speed_limit = current_nav_speed_limit
    print(f"navd.py: send_instruction - Updated self.nav_speed_limit to: {self.nav_speed_limit}", flush=True)

    # Speed limit sign type
    if 'speedLimitSign' in step:
      if step['speedLimitSign'] == 'mutcd':
        msg.navInstruction.speedLimitSign = log.NavInstruction.SpeedLimitSign.mutcd
      elif step['speedLimitSign'] == 'vienna':
        msg.navInstruction.speedLimitSign = log.NavInstruction.SpeedLimitSign.vienna

    self.pm.send('navInstruction', msg)

    # Transition to next route segment
    if distance_to_maneuver_along_geometry < -MANEUVER_TRANSITION_THRESHOLD:
      if self.step_idx + 1 < len(self.route):
        self.step_idx += 1
        self.reset_recompute_limits()

        # Update the 'CurrentStep' value in the JSON
        if 'routes' in self.r2 and len(self.r2['routes']) > 0:
          self.r3['CurrentStep'] = self.step_idx
        # Write the modified JSON data back to the file
        with open('CurrentStep.json', 'w') as json_file:
          json.dump(self.r3, json_file, indent=4)
      else:
        cloudlog.warning("Destination reached")
        print("navd.py: CLOUDLG - Destination reached", flush=True)
        # Clear route if driving away from destination
        dist = self.nav_destination.distance_to(self.last_position)
        if dist > REROUTE_DISTANCE:
          self.params.remove("NavDestination")
          self.clear_route()

    if self.frogpilot_toggles.conditional_navigation:
      v_ego = self.sm['carState'].vEgo
      seconds_to_stop = interp(v_ego, [0, 22.5, 45], [5, 10, 10])

      closest_condition_indices = [idx for idx in self.stop_signal if idx >= closest_idx]
      if closest_condition_indices:
        closest_condition_index = min(closest_condition_indices, key=lambda idx: abs(closest_idx - idx))
        index = self.stop_signal.index(closest_condition_index)

        distance_to_condition = self.last_position.distance_to(self.stop_coord[index])
        self.approaching_intersection = self.frogpilot_toggles.conditional_navigation_intersections and distance_to_condition < max((seconds_to_stop * v_ego), 25)
      else:
        self.approaching_intersection = False

      self.approaching_turn = self.frogpilot_toggles.conditional_navigation_turns and distance_to_maneuver_along_geometry < max((seconds_to_stop * v_ego), 25)
    else:
      self.approaching_intersection = False
      self.approaching_turn = False

    fp_msg.frogpilotNavigation.approachingIntersection = self.approaching_intersection
    fp_msg.frogpilotNavigation.approachingTurn = self.approaching_turn
    fp_msg.frogpilotNavigation.navigationSpeedLimit = self.nav_speed_limit

    self.pm.send('frogpilotNavigation', fp_msg)
    print("navd.py: send_instruction finished.", flush=True) # Added trace

  def send_route(self):
    coords = []

    if self.route is not None:
      for path in self.route_geometry:
        coords += [c.as_dict() for c in path]

    msg = messaging.new_message('navRoute', valid=True)
    msg.navRoute.coordinates = coords
    self.pm.send('navRoute', msg)

  def clear_route(self):
    self.route = None
    self.route_geometry = None
    self.step_idx = None
    self.nav_destination = None
    self.mock_route_active = False # Ensure mock route is deactivated
    self.mock_route_timer = 0 # Reset timer

  def reset_recompute_limits(self):
    self.recompute_backoff = 0
    self.recompute_countdown = 0

  def should_recompute(self):
    if self.step_idx is None or self.route is None:
      return True

    # Don't recompute in last segment, assume destination is reached
    if self.step_idx == len(self.route) - 1:
      return False

    # Compute closest distance to all line segments in the current path
    min_d = REROUTE_DISTANCE + 1
    path = self.route_geometry[self.step_idx]
    for i in range(len(path) - 1):
      a = path[i]
      b = path[i + 1]

      if a.distance_to(b) < 1.0:
        continue

      min_d = min(min_d, minimum_distance(a, b, self.last_position))

    if min_d > REROUTE_DISTANCE:
      self.reroute_counter += 1
    else:
      self.reroute_counter = 0
    return self.reroute_counter > REROUTE_COUNTER_MIN
    # TODO: Check for going wrong way in segment

  def calculate_coordinate_ahead(self, lat_deg, lon_deg, bearing_deg, distance_km):
    try:
      lat_rad = math.radians(lat_deg)
      lon_rad = math.radians(lon_deg)
      bearing_rad = math.radians(bearing_deg)

      lat2_rad = math.asin(math.sin(lat_rad) * math.cos(distance_km / EARTH_RADIUS_KM) +
                           math.cos(lat_rad) * math.sin(distance_km / EARTH_RADIUS_KM) * math.cos(bearing_rad))
      lon2_rad = lon_rad + math.atan2(math.sin(bearing_rad) * math.sin(distance_km / EARTH_RADIUS_KM) * math.cos(lat_rad),
                                      math.cos(distance_km / EARTH_RADIUS_KM) - math.sin(lat_rad) * math.sin(lat2_rad))

      return Coordinate(math.degrees(lat2_rad), math.degrees(lon2_rad))
    except Exception as e:
      cloudlog.error(f"Error calculating coordinate ahead: {e}")
      print(f"navd.py: CLOUDLG - Error calculating coordinate ahead: {e}", flush=True)
      return None


def main():
  pm = messaging.PubMaster(['navInstruction', 'navRoute', 'frogpilotNavigation'])
  sm = messaging.SubMaster(['carState', 'liveLocationKalman', 'managerState', 'frogpilotPlan'])

  rk = Ratekeeper(1.0)
  route_engine = RouteEngine(sm, pm)
  while True:
    route_engine.update()
    rk.keep_time()


if __name__ == "__main__":
  main()
