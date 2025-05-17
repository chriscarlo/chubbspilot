#!/usr/bin/env python3
import cereal.messaging as messaging
import time

def main():
  print("Starting input checker for locationd...")

  services_to_try = ['sensorEvents', 'gpsLocationExternal', 'gnssMeasurements']
  sm = None
  monitored_services = []

  # Attempt to build SubMaster with available services
  for i in range(len(services_to_try), 0, -1):
    candidate_services = services_to_try[:i]
    try:
      print(f"Attempting to subscribe to: {candidate_services}")
      sm = messaging.SubMaster(candidate_services, ignore_avg_freq=True)
      monitored_services = candidate_services
      print(f"Successfully subscribed to: {monitored_services}")
      break
    except Exception as e:
      print(f"Could not subscribe to {candidate_services}: {e}")
      if i == 1: # Last attempt failed
        print("Failed to subscribe to any essential services. Exiting.")
        return
      print("Retrying with fewer services...")

  if sm is None or not monitored_services:
    print("Could not initialize SubMaster with any services. Exiting.")
    return

  last_print_time = {s: 0 for s in monitored_services}
  print_interval = 5 # seconds

  while True:
    sm.update(100)
    current_time = time.monotonic()

    for service_name in monitored_services:
      if sm.updated[service_name] and (current_time - last_print_time[service_name] > print_interval):
        # Check if the service actually exists in sm.data before trying to access it
        # This is a safeguard in case a service was in SERVICE_LIST but doesn't publish
        if service_name not in sm.data:
            print(f"Service {service_name} was in sm.updated but not sm.data. Skipping.")
            continue

        msg = sm[service_name]
        print(f"--- {service_name} (Timestamp: {time.time():.2f}, LogMonoTime: {sm.logMonoTime.get(service_name, 'N/A')}) ---")

        print(f"  SM Valid: {sm.valid.get(service_name, 'N/A')}")

        if service_name == 'sensorEvents':
          print(f"  Message Count: {len(msg) if msg is not None else 'N/A'}")
          if msg is not None and len(msg) > 0:
            event = msg[0]
            print(f"  Sample Event (type {event.type if hasattr(event, 'type') else 'N/A'}, version {event.version if hasattr(event, 'version') else 'N/A'}):")
            if hasattr(event, 'which'):
              event_type = event.which()
              if event_type == 'acceleration':
                print(f"    Accel: {event.acceleration.v}")
              elif event_type == 'gyroUncalibrated':
                print(f"    Gyro: {event.gyroUncalibrated.v}")
          elif msg is not None:
            print("  Msg list empty")

        elif service_name == 'gpsLocationExternal':
          if msg is not None:
            print(f"  Flags: {msg.flags if hasattr(msg, 'flags') else 'N/A'} (Bit 0 for fix: {(msg.flags & 1) if hasattr(msg, 'flags') else 'N/A'})")
            print(f"  Lat: {msg.latitude if hasattr(msg, 'latitude') else 'N/A'}, Lon: {msg.longitude if hasattr(msg, 'longitude') else 'N/A'}")
            print(f"  Accuracy: {msg.accuracy if hasattr(msg, 'accuracy') else 'N/A'}")
            print(f"  Source: {msg.source if hasattr(msg, 'source') else 'N/A'}")

        elif service_name == 'gnssMeasurements':
          if msg is not None:
            print(f"  MeasurementTime: {msg.measTime if hasattr(msg, 'measTime') else 'N/A'}")
            if hasattr(msg, 'positionEcef') and hasattr(msg.positionEcef, 'valid') and msg.positionEcef.valid:
                print(f"  PositionECEF: {msg.positionEcef.value} (Valid)")
            else:
                print(f"  PositionECEF: (Not valid or not present)")
            if hasattr(msg, 'sv') :
              print(f"  Satellite Vehicles: {len(msg.sv)} signals")
            else:
              print(f"  Satellite Vehicles: (sv field not present)")

        last_print_time[service_name] = current_time
        print("-" * 30)

    time.sleep(0.1)

if __name__ == "__main__":
  main()
