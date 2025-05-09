#!/usr/bin/env python3
import os
import time
import math
from cereal import messaging

def clear_screen():
  """Clears the terminal screen."""
  os.system('clear' if os.name == 'posix' else 'cls')

def format_value(val, precision=2, width=7, default_na=True):
  """Formats a value for display, handling floats, NaNs, bools, and strings."""
  if isinstance(val, float):
    if math.isnan(val):
      return "NaN".rjust(width)
    return f"{val:.{precision}f}".rjust(width)
  if isinstance(val, bool):
    return ("✅ Yes" if val else "❌ No").ljust(width)
  if isinstance(val, str):
    if not val and default_na:
      return "N/A".ljust(width)
    return val.ljust(width)
  return str(val).ljust(width)

def print_row(label, value_str, unit=""):
  """Prints a formatted row."""
  print(f"{label:<45}: {value_str} {unit}")

def display_longitudinal_data(fpcc):
  """Clears screen and prints formatted longitudinal data."""
  clear_screen()
  print("--- FrogPilot Longitudinal Tuning Monitor ---")
  print(f"Timestamp: {fpcc.logMonoTime / 1e9:.2f} s\n")

  print_row("HKG Tuning Enabled (Param)", format_value(fpcc.longHkgTuningEnabled, width=7))
  print_row("HKG Braking Enabled (Param)", format_value(fpcc.longHkgBrakingEnabled, width=7))

  print_row("Current Mode", format_value(fpcc.longCurrentMode, width=10, default_na=False))
  print_row("Mode Transitioning", format_value(fpcc.longTransitioning, width=7))
  print_row("Controls Experimental Mode", format_value(fpcc.longControlsStateExperimentalMode, width=7))
  print("-" * 55)

  print_row("Ego Speed (vEgo)", format_value(fpcc.longVEgo, 2), "m/s")
  print_row("Ego Accel (aEgo)", format_value(fpcc.longAEgo, 2), "m/s²")
  print_row("Planner Target Accel (actuators.accel)", format_value(fpcc.longTargetAccelInput, 2), "m/s²")
  print_row("Smoothed Accel Request", format_value(fpcc.longAccelRequest, 2), "m/s²")
  print_row("Accel Pre-Clip (Limited Accel)", format_value(fpcc.longAccelPreClip, 2), "m/s²")
  print_row("Final Commanded Accel", format_value(fpcc.longFinalAccel, 2), "m/s²")
  print_row("Previous Step Final Accel (accel_last)", format_value(fpcc.longAccelLast, 2), "m/s²")
  print_row("Long Control State", format_value(str(fpcc.longLongControlState).split('.')[-1], width=10, default_na=False)) # Show only enum name
  print("-" * 55)

  print_row("Calculated Jerk", format_value(fpcc.longCalculatedJerk, 2), "m/s³")
  print_row("Jerk Upper Limit", format_value(fpcc.longJerkUpperLimit, 2), "m/s³")
  print_row("Jerk Lower Limit", format_value(fpcc.longJerkLowerLimit, 2), "m/s³")
  print_row("Braking Rate Limit Active", format_value(fpcc.longBrakingRateLimitActive, width=7))
  if fpcc.longBrakingRateLimitActive:
    print_row("  Brake Ratio", format_value(fpcc.longBrakeRatio, 2))
    print_row("  Baseline Jerk", format_value(fpcc.longBaselineJerk, 2), "m/s³")
    print_row("  Effective Jerk", format_value(fpcc.longEffectiveJerk, 2), "m/s³")
    print_row("  Max Delta Accel (Jerk * DT)", format_value(fpcc.longMaxDelta, 3), "m/s²")
  print("-" * 55)

  if fpcc.longBrakingRateLimitActive: # Only show physics if rate limiting is active
    print_row("Lead Valid (for physics calc)", format_value(fpcc.longLeadValid, width=7))
    if fpcc.longLeadValid:
      print_row("  Lead Relative Velocity (vRel)", format_value(fpcc.longVRel, 2), "m/s")
      print_row("  Lead Relative Distance (dRel)", format_value(fpcc.longDRel, 1), "m")
      print_row("  Lead Acceleration (aLeadK)", format_value(fpcc.longALeadK, 2), "m/s²")
      print_row("  dGap (dRel - stop_buffer)", format_value(fpcc.longDGap, 1), "m")
      print_row("  Required Accel (aReq)", format_value(fpcc.longAReq, 2), "m/s²")
      print_row("  Urgency (Total)", format_value(fpcc.longUrgency, 2))
      print_row("    Urgency (TTC)", format_value(fpcc.longUrgTtc, 2))
      print_row("    Urgency (Lead Decel)", format_value(fpcc.longUrgLeadDecel, 2))
      print_row("  Physics TTC", format_value(fpcc.longTtcPhysics, 2), "s")
      print_row("  Jerk Needed (Planner)", format_value(fpcc.longJerkNeeded, 2), "m/s³")
      print_row("  Jerk Ceiling", format_value(fpcc.longJerkCeiling, 2), "m/s³")
    print("-" * 55)

  print_row("Overreaction Mitigation Active", format_value(fpcc.longOverreactionMitigationActive, width=7))
  if fpcc.longOverreactionMitigationActive:
    print_row("  Mitigation Accel Limited", format_value(fpcc.longOverreactionMitigationAccelLimited, width=7))
    print_row("  Original Accel (Before Mit.)", format_value(fpcc.longOverreactionMitigationOriginalAccel, 2), "m/s²")
    print_row("  Mitigation Accel Limit", format_value(fpcc.longOverreactionMitigationLimit, 2), "m/s²")
    print_row("  Mitigation Closing Fast", format_value(fpcc.longOverreactionMitigationClosingFast, width=7))
    print_row("  Mitigation Safe TTC", format_value(fpcc.longOverreactionMitigationSafeTtc, width=7))

  print("\nPress Ctrl+C to exit.")

def main():
  sm = messaging.SubMaster(['chauffeurHKGTuning'])
  fpcc_prev = None
  no_data_counter = 0
  print("Waiting for chauffeurHKGTuning messages...")

  while True:
    sm.update()

    if sm.updated['chauffeurHKGTuning']:
      if sm.valid['chauffeurHKGTuning']:
        fpcc = sm['chauffeurHKGTuning']
        display_longitudinal_data(fpcc)
        fpcc_prev = fpcc # Store for potential future diffing
        no_data_counter = 0 # Reset counter on successful data
      else: # Data updated, but not valid
        if no_data_counter % 20 == 0: # Print every second (20 * 0.05s)
          clear_screen()
          print(f"Timestamp: {time.time():.2f} s")
          print("Invalid data received on chauffeurHKGTuning.")
        no_data_counter += 1
    else: # No new data
      if no_data_counter % 20 == 0: # Print every second
        clear_screen()
        print(f"Timestamp: {time.time():.2f} s")
        print("No new data on chauffeurHKGTuning.")
      no_data_counter += 1

    time.sleep(0.05) # Refresh rate control (e.g., 20Hz)

if __name__ == "__main__":
  try:
    main()
  except KeyboardInterrupt:
    clear_screen()
    print("Exiting longitudinal monitor.")
