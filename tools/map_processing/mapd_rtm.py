#!/usr/bin/env python3
import os
import time
import math # For potential future use, e.g. more bearing calcs
import cereal.messaging as messaging
from cereal import log

def print_map_data(sm):
    """Clears screen and prints data from SubMaster"""
    # os.system('clear') # For Linux/macOS
    print("\033c", end="") # More portable ANSI escape for clearing screen

    llk = sm['liveLocationKalman']
    lmd = sm['liveMapData']

    print("--- LiveLocationKalman ---")
    print(f"  GPS OK: {llk.gpsOK}  Status: {llk.status} ({log.LiveLocationKalman.Status.names[llk.status]})")
    if llk.positionGeodetic.valid:
        print(f"  Lat: {llk.positionGeodetic.value[0]:.6f}, Lon: {llk.positionGeodetic.value[1]:.6f}, Alt: {llk.positionGeodetic.value[2]:.1f}m")
        print(f"  Speed: {llk.velocityDevice.value[0]:.2f} m/s ({(llk.velocityDevice.value[0] * 2.23694):.1f} mph)")
        # liveMapData.lastGps.bearingDeg is likely more aligned with map matching expectations
        print(f"  Bearing (from LMD): {lmd.lastGps.bearingDeg:.2f} deg")
        # print(f"  Bearing (NED Yaw): {math.degrees(llk.calibratedOrientationNED.value[2]):.2f} deg") # Yaw from North, clockwise positive
    else:
        print("  Position: Invalid or not available")
    print(f"  LLK Timestamp: {llk.unixTimestampMillis / 1000.0:.3f}")


    print("\n--- LiveMapData ---")
    print(f"  LMD GPS Has Fix: {lmd.lastGps.hasFix}")
    if lmd.lastGps.hasFix:
        print(f"  LMD GPS Lat: {lmd.lastGps.latitude:.6f}, Lon: {lmd.lastGps.longitude:.6f}, Speed: {lmd.lastGps.speed:.2f} m/s")
    print(f"  LMD Timestamp: {lmd.lastGps.unixTimestampMillis / 1000.0:.3f}")


    print(f"\n  Current Road Name: '{lmd.currentRoadName}'")
    print(f"  Speed Limit Valid: {lmd.speedLimitValid}, Limit: {lmd.speedLimit:.2f} m/s ({(lmd.speedLimit * 2.23694):.1f} mph)")
    print(f"  Speed Limit Ahead Valid: {lmd.speedLimitAheadValid}, Limit: {lmd.speedLimitAhead:.2f} m/s ({(lmd.speedLimitAhead * 2.23694):.1f} mph), Dist: {lmd.speedLimitAheadDistance:.1f}m")

    print("\n  --- Current Segment ---")
    print(f"  Segment ID: {lmd.currentSegment.segmentId if lmd.currentSegment.segmentId != 0 else 'N/A'}")
    print(f"  Distance Along Segment: {lmd.currentSegment.distanceAlongSegment:.2f}m")
    print(f"  Curvature Data Valid: {lmd.curvatureDataValid}")
    if lmd.curvatureDataValid and lmd.currentSegment.curvatureDerivedSpeedsMps:
        print(f"  Curvature Speeds Count: {len(lmd.currentSegment.curvatureDerivedSpeedsMps)}")
        # Example: print first curvature point if available
        # print(f"    First point: Dist: {lmd.currentSegment.distancesForSpeeds[0]:.1f}m, Speed: {lmd.currentSegment.curvatureDerivedSpeedsMps[0]:.1f} m/s")
    else:
        print(f"  Curvature Speeds Count: 0")


    print("\n  --- Next Segments ---")
    print(f"  Count: {len(lmd.nextSegments)}")
    for i, next_seg in enumerate(lmd.nextSegments):
        if i >= 3: # Limit printing to avoid screen clutter
            print(f"    ... and {len(lmd.nextSegments) - i} more.")
            break
        print(f"    ID: {next_seg.segmentId}, DistToStart: {next_seg.distanceToStart:.1f}m, Length: {next_seg.segmentLength:.1f}m, #Speeds: {len(next_seg.curvatureDerivedSpeedsMps)}")

    # Useful for seeing if data is fresh
    print(f"\nUpdates: LLK={sm.updated['liveLocationKalman']}, LMD={sm.updated['liveMapData']}")

def main():
    sm = messaging.SubMaster(['liveMapData', 'liveLocationKalman'], poll='liveLocationKalman') # Poll on the faster service

    print("Waiting for initial messages from liveLocationKalman and liveMapData...")
    # Wait for at least one message from each service
    while not (sm.valid['liveLocationKalman'] and sm.valid['liveMapData']):
        sm.update()
        if not sm.all_alive():
            print("ERROR: Some services are not running. Exiting.")
            return
        if not sm.all_valid(): # Print a dot to show activity
            print(".", end="", flush=True)
        time.sleep(0.1)
    print("\nInitial messages received. Starting monitor loop...")

    try:
        while True:
            sm.update(0) # Non-blocking update after initial wait

            # Update display if liveMapData changed, or if liveLocationKalman changed
            # (as LMD can depend on LLK even if LMD itself doesn't change structure but GPS does)
            if sm.updated['liveMapData'] or sm.updated['liveLocationKalman']:
                 print_map_data(sm)

            time.sleep(0.2) # Refresh rate (e.g., 5 Hz)
    except KeyboardInterrupt:
        print("\nExiting mapd_py monitor.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
