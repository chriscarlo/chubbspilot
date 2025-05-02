using Cxx = import "./include/c++.capnp";
$Cxx.namespace("cereal");

using Car = import "car.capnp";

@0xb526ba661d550a59;

# Recompile damn you

# custom.capnp: a home for empty structs reserved for custom forks
# These structs are guaranteed to remain reserved and empty in mainline
# cereal, so use these if you want custom events in your fork.

# you can rename the struct, but don't change the identifier
struct FrogPilotCarControl @0x81c2f05a394cf4af {
  accelPressed @0 :Bool;
  alwaysOnLateralActive @1 :Bool;
  decelPressed @2 :Bool;
  fcwEventTriggered @3 :Bool;
  noEntryEventTriggered @4 :Bool;
  steerSaturatedEventTriggered @5 :Bool;

  # VTSC Debug data
  vtscControllingCurve @6 :Bool;                # Whether VTSC is actively controlling due to curves
  vtscCurrentCurvature @7 :Float32;             # Current curvature detected
  vtscTargetSpeed @8 :Float32;                  # Final target speed after all calculations
  vtscRawSafeSpeed @9 :Float32;                 # Raw safe speed before smoothing
  vtscCruiseSpeed @10 :Float32;                 # Current cruise set speed
  vtscCurrentAccel @11 :Float32;                # Current acceleration/deceleration
  vtscLateralAccel @12 :Float32;                # Current lateral acceleration limit
  vtscEmergencyActive @13 :Bool;                # Emergency deceleration active
  vtscHorizonTime @14 :Float32;                 # Current horizon time

  # Torque predictor data
  vtscPredictedTorque @15 :Float32;             # Predicted torque for current conditions
  vtscMaxTorque @16 :Float32;                   # Maximum available torque
  vtscTorqueLimited @17 :Bool;                  # Whether torque is being limited
  vtscTorquePassiveMode @18 :Bool;              # Torque predictor in passive mode
  vtscTorqueSatCount @19 :UInt32;               # Count of torque saturation events
  vtscTorqueDataCount @20 :UInt32;              # Total data points collected

  # Apex data
  vtscApexCount @21 :UInt8;                     # Number of apexes detected
  vtscApexIndices @22 :List(UInt8);             # Indices of detected apexes
  vtscApexSpeeds @23 :List(Float32);            # Speeds at each apex
  vtscEarlyApproachTime @24 :Float32;           # Time before apex to start deceleration
  vtscEarlySpoolTime @25 :Float32;              # Time before/after apex for spool management

  # Scale factors
  vtscDecelScale @26 :Float32;                  # Dynamic deceleration scale
  vtscAccelScale @27 :Float32;                  # Dynamic acceleration scale
  vtscJerkScale @28 :Float32;                   # Dynamic jerk scale
  vtscShortHorizonFactor @29 :Float32;          # Short horizon adjustment factor
}

struct FrogPilotCarState @0xaedffd8f31e7b55d {
  struct ButtonEvent {
    enum Type {
      lkas @0;
    }
  }

  alwaysOnLateralDisabled @0 :Bool;
  brakeLights @1 :Bool;
  dashboardSpeedLimit @2 :Float32;
  distanceLongPressed @3 :Bool;
  ecoGear @4 :Bool;
  hasMenu @5 :Bool;
  sportGear @6 :Bool;
  trafficModeActive @7 :Bool;
}

struct FrogPilotDeviceState @0xf35cc4560bbf6ec2 {
  freeSpace @0 :Int16;
  usedSpace @1 :Int16;
}

struct FrogPilotNavigation @0xda96579883444c35 {
  approachingIntersection @0 :Bool;
  approachingTurn @1 :Bool;
  navigationSpeedLimit @2 :Float32;
}

struct FrogPilotPlan @0x80ae746ee2596b11 {
  accelerationJerk @0 :Float32;
  accelerationJerkStock @1 :Float32;
  dangerJerk @2 :Float32;
  desiredFollowDistance @3 :Int64;
  experimentalMode @4 :Bool;
  forcingStop @5 :Bool;
  forcingStopLength @6 :Float32;
  frogpilotEvents @7 :List(Car.CarEvent);
  lateralCheck @8 :Bool;
  laneWidthLeft @9 :Float32;
  laneWidthRight @10 :Float32;
  maxAcceleration @11 :Float32;
  minAcceleration @12 :Float32;
  mtscSpeed @13 :Float32;
  redLight @14 :Bool;
  slcMapSpeedLimit @15 :Float32;
  slcOverridden @16 :Bool;
  slcOverriddenSpeed @17 :Float32;
  slcSpeedLimit @18 :Float32;
  slcSpeedLimitOffset @19 :Float32;
  slcSpeedLimitSource @20 :Text;
  speedJerk @21 :Float32;
  speedJerkStock @22 :Float32;
  speedLimitChanged @23 :Bool;
  tFollow @24 :Float32;
  togglesUpdated @25 :Bool;
  unconfirmedSlcSpeedLimit @26 :Float32;
  upcomingSLCSpeedLimit @27 :Float32;
  vCruise @28 :Float32;
  vtscControllingCurve @29 :Bool;
  vtscSpeed @30 :Float32;

  #vtsc stuff
  leftCurve @31 :Bool;
  rightCurve @32 :Bool;

  # Output from MapLongPlanner: comfort-constrained speed profile
  # derived from long-range map data (e.g., 500m lookahead).
  # Parallel lists to avoid adding a new struct.
  farSpeedPlanDistances @33 :List(Float32); # meters from current pos
  farSpeedPlanSpeeds @34 :List(Float32);    # m/s target speed at distance
}

struct CustomReserved5 @0xa5cd762cd951a455 {
}

struct CustomReserved6 @0xf98d843bfd7004a3 {
}

struct CustomReserved7 @0xb86e6369214c01c8 {
}

struct CustomReserved8 @0xf416ec09499d9d19 {
}

struct CustomReserved9 @0xa1680744031fdb2d {
}
