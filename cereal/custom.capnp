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

  // VTSC Logging
  vtscIsEnabled @35 :Bool;              // True if VTSC is actively planning with valid model data
  vtscRawTargetSpeed @36 :Float32;      // The raw target speed from VTSC's internal logic before final clamping/smoothing in the update method
  vtscCurrentAccel @37 :Float32;        // The current acceleration value tracked by VTSC's state
  vtscFilteredCurvature @38 :Float32;   // The EMA-filtered maximum curvature value
  vtscPlannedSpeedsLogging @39 :List(Float32); // Copy of VTSC's internal self.planned_speeds array (output of _plan_speed_trajectory)
  vtscVisionCurvatures @40 :List(Float32); // Calculated curvature at each point in the VTSC plan horizon
  vtscVisionVelocities @41 :List(Float32); // Predicted velocity at each point in the VTSC plan horizon
  vtscSafeSpeedsVision @42 :List(Float32); // Calculated safe speed based on vision curvature only, at each point
  vtscSafeSpeedsMap @43 :List(Float32);    // Safe speed from map data, interpolated at each point in the VTSC plan horizon
  vtscFinalSafeSpeeds @44 :List(Float32);  // Safe speed (min of vision and map) at each point, before trajectory passes
  vtscApexIndices @45 :List(UInt16);       // Indices of detected apexes in the curvature profile
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
