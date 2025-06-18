import math
from common.numpy_fast import clip, interp
from selfdrive.car.interfaces import ACCEL_MIN, ACCEL_MAX
from selfdrive.controls.lib.longitudinal_planner import A_CRUISE_MIN, get_max_accel
from selfdrive.frogpilot.frogpilot_variables import CITY_SPEED_LIMIT

A_CRUISE_MIN_ECO = A_CRUISE_MIN
A_CRUISE_MIN_SPORT = max(A_CRUISE_MIN, A_CRUISE_MIN * 2)

def logistic(x, lower, upper, midpoint, scale):
  return lower + (upper - lower) / (1.0 + math.exp(-scale * (x - midpoint)))

def get_max_accel_eco(v_ego):
  v_mph = v_ego * 2.236936
  return logistic(
      x=v_mph,
      lower=1.5,
      upper=3.0,
      midpoint=35.0,
      scale=0.09
  )

def get_max_accel_standard(v_ego):
  v_mph = v_ego * 2.236936
  # Original logistic curve parameters
  lower=2.0
  upper=4.0
  midpoint=30.0
  scale=0.1

  # Calculate the standard logistic value for the current speed
  logistic_val = logistic(v_mph, lower, upper, midpoint, scale)

  # Define low-speed boost parameters
  BOOST_ACCEL = 3.0  # Desired acceleration at 0 mph
  BOOST_END_SPEED_MPH = 15.0 * 2.236936 # Speed at which boost fully blends into standard curve (10 m/s)

  # Calculate the standard logistic value *at the end of the boost phase*
  logistic_val_at_boost_end = logistic(BOOST_END_SPEED_MPH, lower, upper, midpoint, scale)

  if v_mph < BOOST_END_SPEED_MPH:
    # Linearly interpolate from BOOST_ACCEL at 0 mph down to the standard
    # curve's value at BOOST_END_SPEED_MPH.
    # This ensures a smooth transition *into* the standard curve.
    boosted_val = interp(v_mph, [0.0, BOOST_END_SPEED_MPH], [BOOST_ACCEL, logistic_val_at_boost_end])
    # Return the boosted value, ensuring it doesn't accidentally dip below the original curve
    # (though the interp above should handle this correctly given BOOST_ACCEL > initial logistic_val)
    return max(boosted_val, logistic_val)
  else:
    # Above the boost speed, use the original logistic curve
    return logistic_val

def get_max_accel_sport(v_ego):
  v_mph = v_ego * 2.236936
  return logistic(
      x=v_mph,
      lower=2.5,
      upper=5.0,
      midpoint=25.0,
      scale=0.12
  )

def get_max_accel_low_speeds(max_accel, v_cruise):
  if CITY_SPEED_LIMIT <= 0:
    return max_accel

  fraction = clip(v_cruise / CITY_SPEED_LIMIT, 0.0, 1.0)
  lower = max_accel / 1.15
  upper = max_accel

  return logistic(
      x=fraction,
      lower=lower,
      upper=upper,
      midpoint=0.25,
      scale=14.0
  )

def get_max_accel_ramp_off(max_accel, v_cruise, v_ego):
  diff = max(v_cruise - v_ego, 0.0)
  fraction = logistic(
      x=diff,
      lower=0.0,
      upper=1.0,
      midpoint=1.3,
      scale=2.0
  )
  return fraction * max_accel

def get_max_allowed_accel(v_ego):
  v_mph = v_ego * 2.236936
  base_val = logistic(
      x=v_mph,
      lower=2.0,
      upper=4.0,
      midpoint=15.0,
      scale=0.15
  )
  return base_val

class FrogPilotAcceleration:
  def __init__(self, FrogPilotPlanner):
    self.frogpilot_planner = FrogPilotPlanner
    self.max_accel = 0
    self.min_accel = 0

  def update(self, controlsState, frogpilotCarState, v_ego, frogpilot_toggles):
    eco_gear = frogpilotCarState.ecoGear
    sport_gear = frogpilotCarState.sportGear

    if frogpilotCarState.trafficModeActive:
      self.max_accel = get_max_accel(v_ego)
    elif frogpilot_toggles.map_acceleration and (eco_gear or sport_gear):
      if eco_gear:
        self.max_accel = get_max_accel_eco(v_ego)
      else:
        if frogpilot_toggles.acceleration_profile == 3:
          self.max_accel = get_max_accel_sport(v_ego)
        else:
          self.max_accel = get_max_accel_standard(v_ego)
    else:
      if frogpilot_toggles.acceleration_profile == 1:
        self.max_accel = get_max_accel_eco(v_ego)
      elif frogpilot_toggles.acceleration_profile == 2:
        self.max_accel = get_max_accel_standard(v_ego)
      elif frogpilot_toggles.acceleration_profile == 3:
        self.max_accel = get_max_accel_sport(v_ego)
      elif controlsState.experimentalMode:
        self.max_accel = ACCEL_MAX
      else:
        self.max_accel = get_max_accel(v_ego)

    if frogpilot_toggles.human_acceleration:
      if self.frogpilot_planner.frogpilot_following.following_lead and not frogpilotCarState.trafficModeActive:
        self.max_accel = clip(
          self.frogpilot_planner.lead_one.aLeadK,
          get_max_accel_sport(v_ego),
          get_max_allowed_accel(v_ego)
        )

      self.max_accel = min(
        get_max_accel_low_speeds(self.max_accel, self.frogpilot_planner.v_cruise),
        self.max_accel
      )
      self.max_accel = min(
        get_max_accel_ramp_off(self.max_accel, self.frogpilot_planner.v_cruise, v_ego),
        self.max_accel
      )

    # ---------------------------------------------------------------------
    # Adaptive catch-up boost:
    #  – Active only when a valid lead is being tracked *and* ego is falling
    #    behind its desired follow distance by a noticeable margin.
    #  – Boost size is proportional to the extra gap, but capped to maintain
    #    comfort and never exceed the globally allowed acceleration curve.
    # ---------------------------------------------------------------------
    if (self.frogpilot_planner.tracking_lead and not frogpilotCarState.trafficModeActive):
      desired_gap = self.frogpilot_planner.frogpilot_following.desired_follow_distance
      actual_gap = self.frogpilot_planner.lead_one.dRel

      gap_error = actual_gap - desired_gap  # positive means we are lagging

      if gap_error > 1.0:  # start boosting once >1 m beyond desired
        # Scale boost gently: +0.05 m/s² per metre of extra gap, up to 1.5 m/s²
        BOOST_PER_M = 0.05
        MAX_BOOST = 1.5
        accel_boost = clip(gap_error * BOOST_PER_M, 0.0, MAX_BOOST)

        self.max_accel = min(self.max_accel + accel_boost,
                             get_max_allowed_accel(v_ego))

    if controlsState.experimentalMode:
      self.min_accel = ACCEL_MIN
    elif frogpilot_toggles.map_deceleration and (eco_gear or sport_gear):
      if eco_gear:
        self.min_accel = A_CRUISE_MIN_ECO
      else:
        self.min_accel = A_CRUISE_MIN_SPORT
    else:
      if frogpilot_toggles.deceleration_profile == 1:
        self.min_accel = A_CRUISE_MIN_ECO
      elif frogpilot_toggles.deceleration_profile == 2:
        self.min_accel = A_CRUISE_MIN_SPORT
      else:
        self.min_accel = A_CRUISE_MIN
