#!/usr/bin/env python3
# desire_helper.py

from cereal import log
from openpilot.common.conversions import Conversions as CV
from openpilot.common.realtime import DT_MDL
from cereal.messaging import SubMaster

LaneChangeState = log.LaneChangeState
LaneChangeDirection = log.LaneChangeDirection
TurnDirection = log.Desire

LANE_CHANGE_TIME_MAX = 10.0

# Speed thresholds
LANE_CHANGE_SPEED_MIN = 35.0 * CV.MPH_TO_MS   # For manual or auto-lane-change
AUTO_PASS_SPEED_MIN   = 40.0 * CV.MPH_TO_MS   # For auto‑passing

# Advantage threshold: if the lead in the adjacent lane is not at least 2 mph faster,
# no point in changing lanes (to avoid worthless merges).
SPEED_DIFF_THRESHOLD = 2.0 * CV.MPH_TO_MS

# Desire mappings
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
  TurnDirection.none:      log.Desire.none,
  TurnDirection.turnLeft:  log.Desire.turnLeft,
  TurnDirection.turnRight: log.Desire.turnRight,
}


def check_adjacent_lead_speed(direction, radar_tracks, frogpilotPlan, lane_detection_width,
                              v_ego, current_lead_speed, lead_id=-1):
  """
  Return True if the adjacent lane is clear or has a faster lead (by > SPEED_DIFF_THRESHOLD).
  If there's a lead but it's not strictly faster, no advantage => return False.
  """
  if not radar_tracks:
    # No radar info => assume it's okay
    return True

  # Determine lateral range for left vs. right lane
  if direction == LaneChangeDirection.left:
    lane_width = getattr(frogpilotPlan, 'laneWidthLeft', 0.0) or lane_detection_width or 3.7
    lateral_min, lateral_max = -lane_width - 0.2, 0.0
  else:
    lane_width = getattr(frogpilotPlan, 'laneWidthRight', 0.0) or lane_detection_width or 3.7
    lateral_min, lateral_max = 0.0, lane_width + 0.2

  found_adj_lead = False
  best_lead_speed = 0.0
  min_d_rel = float('inf')

  for track in radar_tracks:
    if track.trackId == lead_id:
      continue

    if lateral_min < track.yRel < lateral_max and track.dRel > 0:
      # Found a car in that lane
      if track.dRel < min_d_rel:
        min_d_rel = track.dRel
        best_lead_speed = v_ego + track.vRel
        found_adj_lead = True

  # If we found a lead in that lane, proceed only if it's at least SPEED_DIFF_THRESHOLD faster
  # than our current lead => a real advantage. If no lead, then it's clear => True.
  if found_adj_lead:
    return best_lead_speed > (current_lead_speed + SPEED_DIFF_THRESHOLD)
  else:
    return True


class DesireHelper:
  def __init__(self):
    self.lane_change_state = LaneChangeState.off
    self.lane_change_direction = LaneChangeDirection.none
    self.lane_change_timer = 0.0
    self.lane_change_ll_prob = 1.0
    self.turn_direction = TurnDirection.none
    self.desire = log.Desire.none

    # For "one lane change per blinker" logic
    self.lane_change_completed = False

    # Radar / speed
    self.v_lead = 0.0
    self.v_cruise_cluster = 0.0

    # Auto-passing
    self.auto_passing_active = False
    self.auto_passing_direction = LaneChangeDirection.none
    self.is_auto_pass = False   # Flag to distinguish auto pass vs. manual

    # Lane change cooldown to prevent spam
    self.lane_change_cooldown = 0.0

    # Bookkeeping
    self.prev_one_blinker = False

    # SubMaster for radar / carState
    self.sm = SubMaster(['liveTracks', 'radarState', 'carControl', 'carState'])

  def update(self, carstate, lateral_active, lane_change_prob, frogpilotPlan, frogpilot_toggles):
    """Main loop logic. Called periodically."""

    self.sm.update(0)

    # --- Gather speed / lead info ---
    v_ego = getattr(carstate, 'vEgo', 0.0)
    if self.sm.valid['carState']:
      self.v_cruise_cluster = self.sm['carState'].cruiseState.speedCluster

    lead_one = self.sm['radarState'].leadOne if self.sm.valid['radarState'] else None
    has_lead = bool(lead_one and lead_one.status)
    lead_rel_speed = lead_one.vRel if has_lead else 0.0
    lead_id = lead_one.radarTrackId if has_lead else -1
    self.v_lead = v_ego + lead_rel_speed if has_lead else 0.0

    # --- Check auto pass logic (will set self.auto_passing_active, direction, etc.) ---
    self.check_auto_passing(carstate, lateral_active, v_ego, frogpilotPlan, frogpilot_toggles, lead_id)

    # Figure out effective blinkers (spoof internally if auto pass is active).
    physical_left = getattr(carstate, 'leftBlinker', False)
    physical_right = getattr(carstate, 'rightBlinker', False)

    if self.auto_passing_active and not (physical_left or physical_right):
      # Spoof the blinker internally (no actual external blinkers)
      effective_left_blinker = (self.auto_passing_direction == LaneChangeDirection.left)
      effective_right_blinker = (self.auto_passing_direction == LaneChangeDirection.right)
      one_blinker = True
    else:
      # If not auto passing, use real signals
      effective_left_blinker = physical_left
      effective_right_blinker = physical_right
      one_blinker = (effective_left_blinker != effective_right_blinker)

    # If driver physically activates a turn signal while auto passing, cancel the auto pass
    if (physical_left or physical_right) and self.auto_passing_active:
      self.auto_passing_active = False
      self.auto_passing_direction = LaneChangeDirection.none
      self.is_auto_pass = False

    # --- Cancel auto-passing on driver steering nudge ---
    steering_pressed = getattr(carstate, 'steeringPressed', False)
    if self.auto_passing_active and steering_pressed:
      self.auto_passing_active = False
      self.auto_passing_direction = LaneChangeDirection.none
      self.is_auto_pass = False
      self._reset_lane_change()
      return  # Immediately exit, skip the rest of the update

    # If we’re below lane change speed, we can’t do a lane change
    below_lane_change_speed = (v_ego < frogpilot_toggles.minimum_lane_change_speed)

    # Check if we should revert to off if lateral is off or time exceeded
    if (not lateral_active) or (self.lane_change_timer > LANE_CHANGE_TIME_MAX):
      self._reset_lane_change()
    else:
      # Possibly handle turn desire if below lane-change speed
      if one_blinker and below_lane_change_speed and frogpilot_toggles.use_turn_desires:
        self.lane_change_state = LaneChangeState.off
        self.lane_change_direction = LaneChangeDirection.none
        self.turn_direction = (TurnDirection.turnLeft if effective_left_blinker else TurnDirection.turnRight)
      else:
        self.turn_direction = TurnDirection.none

        # --- Lane change state machine ---
        if self.lane_change_state == LaneChangeState.off:
          # No more 'not self.prev_one_blinker' so auto-passing can trigger
          if one_blinker and not below_lane_change_speed:
            self.lane_change_state = LaneChangeState.preLaneChange
            self.lane_change_direction = (
              LaneChangeDirection.left if effective_left_blinker else LaneChangeDirection.right
            )
            self.lane_change_ll_prob = 1.0
            self.lane_change_completed = False  # reset each time we go from off->pre

        elif self.lane_change_state == LaneChangeState.preLaneChange:
          # Check for blindspot or advantage
          blindspot_detected = (
            (effective_left_blinker and getattr(carstate, 'leftBlindspot', False)) or
            (effective_right_blinker and getattr(carstate, 'rightBlindspot', False))
          )

          # Also check advantage via radar
          if self.sm.valid['liveTracks'] and has_lead:
            current_lead_speed = self.v_lead
            adv_ok = check_adjacent_lead_speed(
              self.lane_change_direction,
              self.sm['liveTracks'],
              frogpilotPlan,
              frogpilot_toggles.lane_detection_width,
              v_ego,
              current_lead_speed,
              lead_id
            )
            if not adv_ok:
              blindspot_detected = True

          # If manual “one lane change per blinker” is active, see if we already used it
          # to prevent multiple merges off the same physical blink
          manual_blink = (physical_left or physical_right)
          if frogpilot_toggles.one_lane_change and manual_blink and self.lane_change_completed:
            # Already used up
            blindspot_detected = True

          # Possibly also check lane detection if toggles.lane_detection
          lane_available = True
          if frogpilot_toggles.lane_detection and one_blinker:
            if effective_left_blinker:
              lane_width = getattr(frogpilotPlan, 'laneWidthLeft', 0.0)
            else:
              lane_width = getattr(frogpilotPlan, 'laneWidthRight', 0.0)
            lane_available = (lane_width >= frogpilot_toggles.lane_detection_width)

          # Cancel conditions
          if (not one_blinker) or below_lane_change_speed or blindspot_detected or (not lane_available):
            self._reset_lane_change()
          else:
            # Enough conditions satisfied => start
            self.lane_change_state = LaneChangeState.laneChangeStarting

            # If it was a manual blink and toggles.one_lane_change = True,
            # we mark "used up" so we don't do multiple merges with the same blink
            if manual_blink and frogpilot_toggles.one_lane_change and (not self.is_auto_pass):
              self.lane_change_completed = True

        elif self.lane_change_state == LaneChangeState.laneChangeStarting:
          # fade out over .5s
          self.lane_change_ll_prob = max(self.lane_change_ll_prob - 2 * DT_MDL, 0.0)
          # transition to finishing
          if lane_change_prob < 0.02 and self.lane_change_ll_prob < 0.01:
            self.lane_change_state = LaneChangeState.laneChangeFinishing

        elif self.lane_change_state == LaneChangeState.laneChangeFinishing:
          # fade in lane line
          self.lane_change_ll_prob = min(self.lane_change_ll_prob + DT_MDL, 1.0)
          if self.lane_change_ll_prob > 0.99:
            self.lane_change_direction = LaneChangeDirection.none
            self.auto_passing_active = False
            self.is_auto_pass = False
            self.lane_change_cooldown = 5.0
            if one_blinker:
              self.lane_change_state = LaneChangeState.preLaneChange
            else:
              self.lane_change_state = LaneChangeState.off

    # Update timers
    if self.lane_change_state in (LaneChangeState.off, LaneChangeState.preLaneChange):
      self.lane_change_timer = 0.0
    else:
      self.lane_change_timer += DT_MDL

    if self.lane_change_cooldown > 0.0:
      self.lane_change_cooldown -= DT_MDL

    self.prev_one_blinker = one_blinker

    # Final desire
    if self.turn_direction != TurnDirection.none:
      self.desire = TURN_DESIRES[self.turn_direction]
    else:
      self.desire = DESIRES[self.lane_change_direction][self.lane_change_state]


  def check_auto_passing(self, carstate, lateral_active, v_ego, frogpilotPlan, frogpilot_toggles, lead_id=-1):
    """
    Minimal auto-passing logic:
      - Must have a slower lead (by >2mph)
      - Must be above AUTO_PASS_SPEED_MIN
      - Not already changing lanes or blinking
      - Check the adjacent lanes for advantage
      - If left is good, pick left; else if right is good, pick right
    """
    if not (frogpilot_toggles.auto_passing and lateral_active):
      return

    # If we’re already in or just finished a lane change, wait for cooldown
    if (self.lane_change_state != LaneChangeState.off) or (self.lane_change_cooldown > 0.0):
      return

    # Must be above auto pass speed
    if v_ego < AUTO_PASS_SPEED_MIN:
      return

    # Must not have user blinkers on
    if getattr(carstate, 'leftBlinker', False) or getattr(carstate, 'rightBlinker', False):
      return

    # Must have a valid lead that is slower by at least 2 mph
    if self.v_lead <= 0.0 or (self.v_lead >= (self.v_cruise_cluster - SPEED_DIFF_THRESHOLD)):
      return

    # Blindspot checks
    left_clear = not getattr(carstate, 'leftBlindspot', False)
    right_clear = not getattr(carstate, 'rightBlindspot', False)

    # Use radar tracks to see if each lane is “advantageous”
    if self.sm.valid['liveTracks'] and (self.v_lead > 0.0):
      from_radar = self.sm['liveTracks']
      current_lead_speed = self.v_lead
      if left_clear:
        left_clear = check_adjacent_lead_speed(
          LaneChangeDirection.left,
          from_radar,
          frogpilotPlan,
          frogpilot_toggles.lane_detection_width,
          v_ego,
          current_lead_speed,
          lead_id
        )
      if right_clear:
        right_clear = check_adjacent_lead_speed(
          LaneChangeDirection.right,
          from_radar,
          frogpilotPlan,
          frogpilot_toggles.lane_detection_width,
          v_ego,
          current_lead_speed,
          lead_id
        )

    # Also check lane detection if needed
    if frogpilot_toggles.lane_detection:
      lw_left  = getattr(frogpilotPlan, 'laneWidthLeft', 0.0)
      lw_right = getattr(frogpilotPlan, 'laneWidthRight', 0.0)
      min_width = frogpilot_toggles.lane_detection_width
      if left_clear:
        left_clear = (lw_left >= min_width)
      if right_clear:
        right_clear = (lw_right >= min_width)

    # Decide direction (prefer left if it’s clear; else right)
    if left_clear:
      self.auto_passing_direction = LaneChangeDirection.left
    elif right_clear:
      self.auto_passing_direction = LaneChangeDirection.right
    else:
      return  # neither lane is advantageous => skip

    # Activate auto pass
    self.auto_passing_active = True
    self.is_auto_pass = True


  def get_spas_blinker_messages(self, packer, CAN, frame, carstate):
    """
    Still no physical blinkers: return empty.
    """
    return []


  def _reset_lane_change(self):
    """Helper to reset everything if lane change is canceled or finished."""
    self.lane_change_state = LaneChangeState.off
    self.lane_change_direction = LaneChangeDirection.none
    self.lane_change_timer = 0.0
    self.lane_change_ll_prob = 1.0
    self.auto_passing_active = False
    self.is_auto_pass = False
    self.turn_direction = TurnDirection.none
