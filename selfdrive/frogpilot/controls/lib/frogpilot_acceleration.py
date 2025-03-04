import math
from openpilot.common.numpy_fast import clip
from openpilot.selfdrive.car.interfaces import ACCEL_MIN, ACCEL_MAX
from openpilot.selfdrive.controls.lib.longitudinal_planner import A_CRUISE_MIN, get_max_accel
from openpilot.selfdrive.frogpilot.frogpilot_variables import CITY_SPEED_LIMIT

A_CRUISE_MIN_ECO = A_CRUISE_MIN / 2
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
  return logistic(
      x=v_mph,
      lower=2.0,
      upper=4.0,
      midpoint=30.0,
      scale=0.1
  )

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
