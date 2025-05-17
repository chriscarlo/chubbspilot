#!/usr/bin/env python3
import cereal.messaging as messaging
import time

def main():
  print("Starting sensorEvents checker...")
  service_to_check = 'sensorEvents'
  sm = None

  print(f"Waiting 10 seconds for {service_to_check} to start publishing...")
  time.sleep(10) # Wait for sensord to be well up and running

  try:
    print(f"Attempting to subscribe to: {service_to_check}")
    sm = messaging.SubMaster([service_to_check], ignore_avg_freq=True)
    print(f"Successfully subscribed to: {service_to_check}")
  except Exception as e:
    print(f"Could not subscribe to {service_to_check}: {e}")
    print(f"Is '{service_to_check}' correctly defined in cereal.services and being published by sensord?")
    # Attempt to print SERVICE_LIST for debugging
    try:
      print("Available services in SERVICE_LIST:")
      for name, service in messaging.SERVICE_LIST.items():
          print(f"  - {name} (Port: {service.port})")
    except Exception as e_sl:
      print(f"  Could not print SERVICE_LIST: {e_sl}")
    return

  last_print_time = 0
  print_interval = 2 # seconds

  while True:
    sm.update(100)
    current_time = time.monotonic()

    if sm.updated[service_to_check] and (current_time - last_print_time > print_interval):
      msg = sm[service_to_check]
      print(f"--- {service_to_check} (Timestamp: {time.time():.2f}, LogMonoTime: {sm.logMonoTime.get(service_to_check, 'N/A')}) ---")
      print(f"  SM Valid: {sm.valid.get(service_to_check, 'N/A')}")
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
      last_print_time = current_time
      print("-" * 30)
    time.sleep(0.1)

if __name__ == "__main__":
  main()
