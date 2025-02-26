#!/usr/bin/env python3
# desire_helper.py

from cereal import log
from openpilot.common.conversions import Conversions as CV
from openpilot.common.realtime import DT_MDL
from cereal.messaging import SubMaster
from openpilot.selfdrive.car.hyundai.hyundaicanfd import create_spas_messages
import math

LaneChangeState = log.LaneChangeState
LaneChangeDirection = log.LaneChangeDirection
TurnDirection = log.Desire

LANE_CHANGE_SPEED_MIN = 20 * CV.MPH_TO_MS
LANE_CHANGE_TIME_MAX = 10.

# Pre-signal duration for auto-passing (in seconds)
AUTO_PASS_PRE_SIGNAL_TIME = 2.0

# Minimum speed for auto-passing feature (55 mph)
AUTO_PASS_SPEED_MIN = 40.0 * CV.MPH_TO_MS

DESIRES = {
  LaneChangeDirection.none: {
    LaneChangeState.off: log.Desire.none,
    LaneChangeState.preLaneChange: log.Desire.none,
    LaneChangeState.laneChangeStarting: log.Desire.none,
    LaneChangeState.laneChangeFinishing: log.Desire.none,
  },
  LaneChangeDirection.left: {
    LaneChangeState.off: log.Desire.none,
    LaneChangeState.preLaneChange: log.Desire.none,
    LaneChangeState.laneChangeStarting: log.Desire.laneChangeLeft,
    LaneChangeState.laneChangeFinishing: log.Desire.laneChangeLeft,
  },
  LaneChangeDirection.right: {
    LaneChangeState.off: log.Desire.none,
    LaneChangeState.preLaneChange: log.Desire.none,
    LaneChangeState.laneChangeStarting: log.Desire.laneChangeRight,
    LaneChangeState.laneChangeFinishing: log.Desire.laneChangeRight,
  },
}

TURN_DESIRES = {
  TurnDirection.none: log.Desire.none,
  TurnDirection.turnLeft: log.Desire.turnLeft,
  TurnDirection.turnRight: log.Desire.turnRight,
}


def detect_adjacent_vehicle_from_radar(direction, radar_tracks, frogpilotPlan, lane_detection_width, v_ego, lead_id=-1):
  """
  Check radar tracks for vehicles in adjacent lanes using TTC-based safety assessment.
  """
  if not radar_tracks:
    return False

  # Lane width determination
  if direction == LaneChangeDirection.left:
    use_measured_width = hasattr(frogpilotPlan, 'laneWidthLeft') and frogpilotPlan.laneWidthLeft > 0
    lane_width = frogpilotPlan.laneWidthLeft if use_measured_width else (lane_detection_width if lane_detection_width > 0 else 3.7)
    lateral_min = -lane_width - 0.2  # Added small safety margin
    lateral_max = 0.0
  else:  # right
    use_measured_width = hasattr(frogpilotPlan, 'laneWidthRight') and frogpilotPlan.laneWidthRight > 0
    lane_width = frogpilotPlan.laneWidthRight if use_measured_width else (lane_detection_width if lane_detection_width > 0 else 3.7)
    lateral_min = 0.0
    lateral_max = lane_width + 0.2  # Added small safety margin

  # Fixed TTC threshold
  min_ttc = 2.5  # Static 2.5s TTC threshold for all speeds

  # Scale minimum distance with speed to avoid being rude
  # Base distance + roughly 1 car length per 10 mph
  min_distance = 7.0 + (v_ego * 0.3)  # Base distance + scaled factor

  # Check if any radar track is in the adjacent lane with unsafe TTC
  for track in radar_tracks:
    # Skip lead vehicle in our lane
    if track.trackId == lead_id:
      continue

    if lateral_min < track.yRel < lateral_max:
      # First check: minimum distance
      if abs(track.dRel) < min_distance:
        return True

      # Calculate TTC only for vehicles that are approaching or moving away slowly
      if track.vRel < 1.0:
        closing_speed = max(-track.vRel, 0.1)
        ttc = abs(track.dRel) / closing_speed
        if ttc < min_ttc:
          return True

      # Simple blind-spot check for vehicles at similar speed
      if abs(track.dRel) < 10.0 and abs(track.yRel) < (lane_width / 2):
        return True

  return False


class DesireHelper:
  def __init__(self):
    self.lane_change_state = LaneChangeState.off
    self.lane_change_direction = LaneChangeDirection.none
    self.lane_change_timer = 0.0
    self.lane_change_ll_prob = 1.0
    self.keep_pulse_timer = 0.0
    self.prev_one_blinker = False
    self.desire = log.Desire.none

    # FrogPilot variables
    self.lane_change_completed = False
    self.lane_change_wait_timer = 0
    self.turn_direction = TurnDirection.none

    # Initialize SubMaster for live tracks, radar state, and car control
    self.sm = SubMaster(['liveTracks', 'radarState', 'carControl', 'carState'])

    # Vehicle speed variables
    self.v_lead = 0.0
    self.v_cruise_cluster = 0.0  # changed from v_cruise to v_cruise_cluster

    # Auto-passing variables
    self.lead_follow_timer = 0.0
    self.auto_passing_active = False
    self.auto_passing_direction = LaneChangeDirection.none
    self.lane_change_cooldown = 0.0
    self.pre_signal_timer = 0.0
    self.pre_signaling = False

  def check_adjacent_lead_speed(self, direction, radar_tracks, frogpilotPlan, lane_detection_width, v_ego, current_lead_speed, lead_id=-1):
    """
    Determines if changing to the specified lane would be advantageous based on lead vehicle speeds.
    Returns True if the lane is clear or has a faster lead vehicle than our current lane.
    """
    if not radar_tracks:
      return True

    if direction == LaneChangeDirection.left:
      use_measured_width = hasattr(frogpilotPlan, 'laneWidthLeft') and frogpilotPlan.laneWidthLeft > 0
      lane_width = frogpilotPlan.laneWidthLeft if use_measured_width else (lane_detection_width if lane_detection_width > 0 else 3.7)
      lateral_min = -lane_width - 0.2
      lateral_max = 0.0
    else:  # right
      use_measured_width = hasattr(frogpilotPlan, 'laneWidthRight') and frogpilotPlan.laneWidthRight > 0
      lane_width = frogpilotPlan.laneWidthRight if use_measured_width else (lane_detection_width if lane_detection_width > 0 else 3.7)
      lateral_min = 0.0
      lateral_max = lane_width + 0.2

    lead_found = False
    lead_speed = 0
    min_distance = float('inf')

    for track in radar_tracks:
      if track.trackId == lead_id:
        continue

      if lateral_min < track.yRel < lateral_max and track.dRel > 0:
        if track.dRel < min_distance:
          min_distance = track.dRel
          lead_speed = v_ego + track.vRel
          lead_found = True

    return not lead_found or lead_speed > current_lead_speed

  def update(self, carstate, lateral_active, lane_change_prob, frogpilotPlan, frogpilot_toggles):
    """
    carstate here is assumed to be the *cereal* CarState message
    (so it has vEgo, leftBlinker, rightBlinker, etc.).
    """
    # Pull new data from SubMaster
    self.sm.update(0)

    # Radar / lead info
    lead_one = self.sm['radarState'].leadOne if self.sm.valid['radarState'] else None
    has_lead = lead_one.status if lead_one is not None else False
    lead_rel_speed = lead_one.vRel if has_lead else 0
    lead_id = lead_one.radarTrackId if has_lead else -1

    # Calculate absolute lead vehicle speed
    # Handle both direct and nested structure
    v_ego = getattr(carstate, 'vEgo', 0.0) if not hasattr(carstate, 'out') else getattr(carstate.out, 'vEgo', 0.0)
    self.v_lead = v_ego + lead_rel_speed if has_lead else 0.0

    # If we have a valid carState from SubMaster, get cluster speed
    if self.sm.valid['carState']:
      # Using a custom 'speedCluster' if your fork populates it
      self.v_cruise_cluster = self.sm['carState'].cruiseState.speedCluster

    # Check auto-passing logic
    self.check_auto_passing(carstate, lateral_active, v_ego, frogpilotPlan, frogpilot_toggles, lead_id)

    # Create effective blinker states (using auto-passing if active)
    if (self.auto_passing_active or self.pre_signaling) and not (self._get_attr(carstate, 'leftBlinker', False) or self._get_attr(carstate, 'rightBlinker', False)):
      effective_left_blinker = self.auto_passing_direction == LaneChangeDirection.left
      effective_right_blinker = self.auto_passing_direction == LaneChangeDirection.right
      one_blinker = True
    else:
      effective_left_blinker = self._get_attr(carstate, 'leftBlinker', False)
      effective_right_blinker = self._get_attr(carstate, 'rightBlinker', False)
      one_blinker = effective_left_blinker != effective_right_blinker

    # Cancel auto-passing if driver manually activates blinkers
    if one_blinker:
      self.auto_passing_active = False
      self.pre_signaling = False
      self.auto_passing_direction = LaneChangeDirection.none

    below_lane_change_speed = v_ego < frogpilot_toggles.minimum_lane_change_speed

    # Lane detection check
    if not (frogpilot_toggles.lane_detection and one_blinker) or below_lane_change_speed:
      lane_available = True
    else:
      desired_lane_width = frogpilotPlan.laneWidthLeft if effective_left_blinker else frogpilotPlan.laneWidthRight
      lane_available = desired_lane_width >= frogpilot_toggles.lane_detection_width

    # Lane change logic
    if not lateral_active or self.lane_change_timer > LANE_CHANGE_TIME_MAX:
      self.lane_change_state = LaneChangeState.off
      self.lane_change_direction = LaneChangeDirection.none
      self.turn_direction = TurnDirection.none
      self.auto_passing_active = False
      self.pre_signaling = False
    elif one_blinker and below_lane_change_speed and not self._get_attr(carstate, 'standstill', False) and frogpilot_toggles.use_turn_desires:
      self.lane_change_state = LaneChangeState.off
      self.lane_change_direction = LaneChangeDirection.none
      self.turn_direction = TurnDirection.turnLeft if effective_left_blinker else TurnDirection.turnRight
    else:
      self.turn_direction = TurnDirection.none

      # Handle pre-signaling for auto-passing
      if self.pre_signaling:
        self.pre_signal_timer += DT_MDL
        if self.pre_signal_timer >= AUTO_PASS_PRE_SIGNAL_TIME:
          self.pre_signaling = False
          self.auto_passing_active = True
          self.pre_signal_timer = 0.0

      # LaneChangeState.off
      if self.lane_change_state == LaneChangeState.off and one_blinker and not self.prev_one_blinker and not below_lane_change_speed:
        self.lane_change_state = LaneChangeState.preLaneChange
        self.lane_change_ll_prob = 1.0
        self.lane_change_wait_timer = 0.0

      # LaneChangeState.preLaneChange
      elif self.lane_change_state == LaneChangeState.preLaneChange:
        self.lane_change_wait_timer += DT_MDL
        self.lane_change_direction = LaneChangeDirection.left if effective_left_blinker else LaneChangeDirection.right

        torque_applied = self._get_attr(carstate, 'steeringPressed', False) and (
                          (self._get_attr(carstate, 'steeringTorque', 0) > 0 and self.lane_change_direction == LaneChangeDirection.left) or
                          (self._get_attr(carstate, 'steeringTorque', 0) < 0 and self.lane_change_direction == LaneChangeDirection.right))

        # Reset wait timer if driver nudges steering
        if torque_applied:
          self.lane_change_wait_timer = frogpilot_toggles.lane_change_delay

        # Nudgeless or auto-pass override
        auto_pass_nudgeless = self.auto_passing_active and not self.pre_signaling
        torque_applied |= frogpilot_toggles.nudgeless or auto_pass_nudgeless

        # Check car's built-in blind spot detection
        blindspot_detected = ((self._get_attr(carstate, 'leftBlindspot', False) and self.lane_change_direction == LaneChangeDirection.left) or
                              (self._get_attr(carstate, 'rightBlindspot', False) and self.lane_change_direction == LaneChangeDirection.right))

        # Use radar tracks for blind spot as well
        if self.sm.valid['liveTracks']:
          radar_blindspot = detect_adjacent_vehicle_from_radar(
            self.lane_change_direction,
            self.sm['liveTracks'],
            frogpilotPlan,
            frogpilot_toggles.lane_detection_width,
            v_ego,
            lead_id
          )
          blindspot_detected |= radar_blindspot

          # Check if lane change is advantageous if we have a lead
          if has_lead:
            current_lead_speed = v_ego + lead_rel_speed
            advantageous = self.check_adjacent_lead_speed(
              self.lane_change_direction,
              self.sm['liveTracks'],
              frogpilotPlan,
              frogpilot_toggles.lane_detection_width,
              v_ego,
              current_lead_speed,
              lead_id
            )
            if not advantageous:
              blindspot_detected = True

        # Cancel conditions
        if not one_blinker or below_lane_change_speed or self.lane_change_completed:
          self.lane_change_state = LaneChangeState.off
          self.lane_change_direction = LaneChangeDirection.none
          self.auto_passing_active = False
          self.pre_signaling = False

        elif torque_applied and not blindspot_detected and lane_available and \
             self.lane_change_wait_timer >= frogpilot_toggles.lane_change_delay:
          self.lane_change_state = LaneChangeState.laneChangeStarting
          self.lane_change_completed = frogpilot_toggles.one_lane_change
          self.lane_change_wait_timer = 0.0

      # LaneChangeState.laneChangeStarting
      elif self.lane_change_state == LaneChangeState.laneChangeStarting:
        # fade out over .5s
        self.lane_change_ll_prob = max(self.lane_change_ll_prob - 2 * DT_MDL, 0.0)

        # once laneChangeProb < 0.02
        if lane_change_prob < 0.02 and self.lane_change_ll_prob < 0.01:
          self.lane_change_state = LaneChangeState.laneChangeFinishing

      # LaneChangeState.laneChangeFinishing
      elif self.lane_change_state == LaneChangeState.laneChangeFinishing:
        # fade in laneline over 1s
        self.lane_change_ll_prob = min(self.lane_change_ll_prob + DT_MDL, 1.0)

        if self.lane_change_ll_prob > 0.99:
          self.lane_change_direction = LaneChangeDirection.none
          self.auto_passing_active = False
          self.pre_signaling = False
          self.lane_change_cooldown = 5.0
          if one_blinker:
            self.lane_change_state = LaneChangeState.preLaneChange
          else:
            self.lane_change_state = LaneChangeState.off

    # Timer updates
    if self.lane_change_state in (LaneChangeState.off, LaneChangeState.preLaneChange):
      self.lane_change_timer = 0.0
    else:
      self.lane_change_timer += DT_MDL

    if self.lane_change_cooldown > 0.0:
      self.lane_change_cooldown -= DT_MDL

    self.lane_change_completed &= one_blinker
    self.prev_one_blinker = one_blinker

    # Set final desire
    if self.turn_direction != TurnDirection.none:
      self.desire = TURN_DESIRES[self.turn_direction]
    else:
      self.desire = DESIRES[self.lane_change_direction][self.lane_change_state]

    # Send keep pulse once per second in preLaneChange
    if self.lane_change_state in (LaneChangeState.off, LaneChangeState.laneChangeStarting):
      self.keep_pulse_timer = 0.0
    elif self.lane_change_state == LaneChangeState.preLaneChange:
      self.keep_pulse_timer += DT_MDL
      if self.keep_pulse_timer > 1.0:
        self.keep_pulse_timer = 0.0
      elif self.desire in (log.Desire.keepLeft, log.Desire.keepRight):
        self.desire = log.Desire.none

  def check_auto_passing(self, carstate, lateral_active, v_ego, frogpilotPlan, frogpilot_toggles, lead_id=-1):
    """
    Check if conditions are met for automatic passing and update auto-passing state
    """
    MIN_FOLLOW_TIME = 3.0
    SPEED_DIFF_THRESHOLD = 2.0 * CV.MPH_TO_MS
    below_lane_change_speed = v_ego < frogpilot_toggles.minimum_lane_change_speed
    below_auto_pass_speed = v_ego < AUTO_PASS_SPEED_MIN

    lead_one = self.sm['radarState'].leadOne if self.sm.valid['radarState'] else None
    has_lead = lead_one.status if lead_one is not None else False

    # Track lead follow time
    if has_lead:
      lead_is_slower = (
        self.v_cruise_cluster > 0 and
        (self.v_lead < (self.v_cruise_cluster - SPEED_DIFF_THRESHOLD))
      )
      if lead_is_slower:
        self.lead_follow_timer += DT_MDL
      else:
        self.lead_follow_timer = 0.0
    else:
      self.lead_follow_timer = 0.0
      self.auto_passing_active = False
      self.pre_signaling = False
      self.auto_passing_direction = LaneChangeDirection.none
      return

    # No manual blinkers and not currently changing lanes
    no_manual_blinker = not self._get_attr(carstate, 'leftBlinker', False) and not self._get_attr(carstate, 'rightBlinker', False)
    not_changing_lanes = self.lane_change_state == LaneChangeState.off

    # Auto-passing feature enabled in settings
    auto_passing_enabled = frogpilot_toggles.auto_passing

    # Cancel if we detect blindspot or speed drops
    if (self.auto_passing_active or self.pre_signaling) and (
        (self._get_attr(carstate, 'leftBlindspot', False) and self.auto_passing_direction == LaneChangeDirection.left) or
        (self._get_attr(carstate, 'rightBlindspot', False) and self.auto_passing_direction == LaneChangeDirection.right) or
        below_auto_pass_speed  # Cancel if speed drops below threshold
    ):
      self.auto_passing_active = False
      self.pre_signaling = False
      self.auto_passing_direction = LaneChangeDirection.none
      return

    auto_passing_ready = (auto_passing_enabled and
                          lateral_active and
                          self.lead_follow_timer >= MIN_FOLLOW_TIME and
                          not below_lane_change_speed and
                          not below_auto_pass_speed and
                          no_manual_blinker and
                          not_changing_lanes and
                          self.lane_change_cooldown <= 0.0 and
                          not self.pre_signaling)

    if auto_passing_ready and not self.auto_passing_active:
      # Determine best passing lane (prefer left, fall back to right)
      left_clear = not self._get_attr(carstate, 'leftBlindspot', False)
      right_clear = not self._get_attr(carstate, 'rightBlinker', False)
      if has_lead:
        current_lead_speed = v_ego + lead_one.vRel
        left_clear = left_clear and self.check_adjacent_lead_speed(
          LaneChangeDirection.left,
          self.sm['liveTracks'],
          frogpilotPlan,
          frogpilot_toggles.lane_detection_width,
          v_ego,
          current_lead_speed,
          lead_id
        )
        right_clear = right_clear and self.check_adjacent_lead_speed(
          LaneChangeDirection.right,
          self.sm['liveTracks'],
          frogpilotPlan,
          frogpilot_toggles.lane_detection_width,
          v_ego,
          current_lead_speed,
          lead_id
        )

      if frogpilot_toggles.lane_detection:
        left_clear = left_clear and frogpilotPlan.laneWidthLeft >= frogpilot_toggles.lane_detection_width
        right_clear = right_clear and frogpilotPlan.laneWidthRight >= frogpilot_toggles.lane_detection_width

      # Start pre-signaling in the best direction (prefer left)
      if left_clear:
        self.pre_signaling = True
        self.pre_signal_timer = 0.0
        self.auto_passing_direction = LaneChangeDirection.left
      elif right_clear:
        self.pre_signaling = True
        self.pre_signal_timer = 0.0
        self.auto_passing_direction = LaneChangeDirection.right
    # Reset if conditions no longer met
    elif (self.auto_passing_active or self.pre_signaling) and (
        not lateral_active or
        below_lane_change_speed or
        below_auto_pass_speed or
        not auto_passing_enabled
    ):
      self.auto_passing_active = False
      self.pre_signaling = False
      self.auto_passing_direction = LaneChangeDirection.none

  def get_spas_blinker_messages(self, packer, CAN, frame, carstate):
    """
    Returns SPAS blinker control messages for Hyundai CAN-FD vehicles
    with auto-passing blinker activation.
    """
    # Override blinker states when auto-passing is active or pre-signaling
    if (self.auto_passing_active or self.pre_signaling) and not (self._get_attr(carstate, 'leftBlinker', False) or self._get_attr(carstate, 'rightBlinker', False)):
      left_blinker = self.auto_passing_direction == LaneChangeDirection.left
      right_blinker = self.auto_passing_direction == LaneChangeDirection.right
    else:
      left_blinker = self._get_attr(carstate, 'leftBlinker', False)
      right_blinker = self._get_attr(carstate, 'rightBlinker', False)

    return create_spas_messages(packer, CAN, frame, left_blinker, right_blinker)

  # Add a helper method to handle attribute access
  def _get_attr(self, obj, attr, default=None):
    """Helper to get attribute from an object with fallback to 'out' property"""
    value = getattr(obj, attr, None)
    if value is None and hasattr(obj, 'out'):
        value = getattr(obj.out, attr, default)
    return value if value is not None else default