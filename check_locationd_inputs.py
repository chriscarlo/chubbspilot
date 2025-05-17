#!/usr/bin/env python3
import cereal.messaging as messaging
import time

def main():
  print("Starting input checker for locationd...")
  # Try to subscribe to all, gracefully handle if some are not available
  services_to_check = ['sensorEvents', 'gpsLocationExternal', 'gnssMeasurements']
  active_services = []
  for service in services_to_check:
    try:
      # Check if service is listed/valid before adding to SubMaster
      # This is a bit of a hack, SubMaster would normally raise if a service isn't in SERVICE_LIST
      # but we want to be robust to different device configurations.
      if messaging.SERVICE_LIST[service].port is not None: # A simple check
        active_services.append(service)
      else:
        print(f"Service {service} does not seem to be available/configured. Skipping.")
    except KeyError:
      print(f"Service {service} not found in SERVICE_LIST. Skipping.")

  if not active_services:
    print("No relevant services to monitor. Exiting.")
    return

  sm = messaging.SubMaster(active_services, ignore_avg_freq=True)

  last_print_time = {s: 0 for s in active_services}
  print_interval = 5 # seconds

  print(f"Monitoring services: {active_services}")

  while True:
    sm.update(100) # Update with a timeout
    current_time = time.monotonic()

    for service_name in active_services:
      if sm.updated[service_name] and (current_time - last_print_time[service_name] > print_interval):
        msg = sm[service_name]
        print(f"--- {service_name} (Timestamp: {time.time():.2f}, LogMonoTime: {sm.logMonoTime[service_name]}) ---")

        # Generic SubMaster validity for the socket/message envelope
        print(f"  SM Valid: {sm.valid[service_name]}")

        # Service-specific validity and data
        if service_name == 'sensorEvents':
          print(f"  Message Count: {len(msg)}")
          if len(msg) > 0:
            event = msg[0] # Sample first event
            print(f"  Sample Event (type {event.type}, version {event.version}):")
            if event.which() == 'acceleration':
              print(f"    Accel: {event.acceleration.v}")
            elif event.which() == 'gyroUncalibrated':
              print(f"    Gyro: {event.gyroUncalibrated.v}")
            # Add more sensor types as needed for debugging
          else:
            print("  Msg list empty")

        elif service_name == 'gpsLocationExternal':
          # gpsLocationExternal has its own 'valid' flag in older schemas, but newer ones use 'flags'
          print(f"  Flags: {msg.flags} (Bit 0 for fix: {msg.flags & 1})") # flags & 1 is usually fixOK
          print(f"  Lat: {msg.latitude}, Lon: {msg.longitude}, Alt: {msg.altitude}")
          print(f"  Speed: {msg.speed}, Bearing: {msg.bearingDeg}, Accuracy: {msg.accuracy}")
          print(f"  Source: {msg.source}")
          print(f"  Vertical Accuracy: {msg.verticalAccuracy}, Bearing Accuracy: {msg.bearingAccuracyDeg}, Speed Accuracy: {msg.speedAccuracy}")

        elif service_name == 'gnssMeasurements':
          # gnssMeasurements itself doesn't have a top-level 'valid' field in log.capnp.
          # Its validity is often inferred from contents like positionEcef.valid or sv measurements.
          print(f"  MeasurementTime: {msg.measTime}")
          if hasattr(msg, 'positionEcef') and msg.positionEcef.valid:
              print(f"  PositionECEF: {msg.positionEcef.value} (Valid)")
          else:
              print(f"  PositionECEF: (Not valid or not present)")
          if hasattr(msg, 'sv') :
            print(f"  Satellite Vehicles: {len(msg.sv)} signals")
          else:
            print(f"  Satellite Vehicles: (sv field not present)")

        last_print_time[service_name] = current_time
        print("-" * 30) # Separator

    time.sleep(0.1) # Loop fairly quickly, print less often

if __name__ == "__main__":
  main()
