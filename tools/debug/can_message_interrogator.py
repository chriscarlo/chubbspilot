#!/usr/bin/env python3
"""
can_message_interrogator.py
===========================

A diagnostic tool to monitor a specific CAN bus, attempt to decode all messages
using a given DBC file, and report on unrecognized or malformed messages in
real-time. This helps identify potential DBC issues or unexpected CAN traffic.

Usage:
  ./can_message_interrogator.py --bus <BUS_NUM> --dbc <DBC_NAME_PREFIX> [--verbose]

Arguments:
  --bus <BUS_NUM>:         The CAN bus source to monitor (e.g., 0, 1, 2).
                           Default: 2.
  --dbc <DBC_NAME_PREFIX>: The prefix of the DBC file to use (e.g.,
                           hyundai_kia_generic_canfd). The script will
                           append '.dbc'. Default: hyundai_kia_generic_canfd.
  --verbose:               If set, prints successfully decoded messages too.

Example:
  ./tools/debug/can_message_interrogator.py --bus 0 --dbc hyundai_kia_generic_canfd

The script will print problematic messages (ID not in DBC, or malformed)
as they are received. Press Ctrl-C to stop and see a summary.
"""
import os
import sys
import time
import argparse
from collections import defaultdict
import cereal.messaging as messaging

try:
    from opendbc.can.common.dbc import dbc as DBCFileLoader # Renamed to avoid confusion
except ImportError as e:
    print(f"Error: Failed to import DBC loader from opendbc.can.common.dbc: {e}")
    print("Please ensure that opendbc is correctly installed and in your PYTHONPATH.")
    print("You might need to run: pip install -e . (from the openpilot/third_party/opendbc directory if it's a submodule setup)")
    print("Or ensure your openpilot environment is sourced correctly.")
    sys.exit(1)

# Define OPENPILOT_ROOT for DBC path
OPENPILOT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))

DEFAULT_TARGET_BUS = 2

# Hardcoded list of DBCs relevant for Hyundai/Kia CANFD HDA2 (e.g., EV6 context)
RELEVANT_DBC_FILES = {
    1: "hyundai_canfd.dbc",  # General platform messages
    2: "hyundai_kia_mando_front_radar_point.dbc", # Specific front radar
    3: "hyundai_kia_mando_corner_radar_generated.dbc", # Specific corner radar
    4: "hyundai_kia_generic_canfd.dbc" # Broader generic CANFD as a fallback/comparison
}

def get_selected_dbc_path():
    print("Please select which DBC to use for this session:")
    for key, name in RELEVANT_DBC_FILES.items():
        print(f"  {key}: {name}")

    while True:
        try:
            choice = int(input("Enter the number for your DBC choice: "))
            if choice in RELEVANT_DBC_FILES:
                dbc_file_name = RELEVANT_DBC_FILES[choice]
                # Standard location for DBC files in openpilot
                dbc_file_path = os.path.join(OPENPILOT_ROOT, "opendbc", dbc_file_name)
                if not os.path.exists(dbc_file_path):
                    # Attempt an alternative path
                    alt_dbc_path = os.path.join(os.path.dirname(OPENPILOT_ROOT), "opendbc", dbc_file_name)
                    if os.path.exists(alt_dbc_path):
                        return alt_dbc_path
                    else:
                        print(f"Error: Selected DBC file '{dbc_file_name}' not found at {dbc_file_path} or {alt_dbc_path}. Please ensure it exists.")
                        # Let user retry or exit by themseleves if file not found for selection
                        # This could loop forever if user doesn't provide valid file, but it's interactive.
                        # Alternatively, sys.exit(1) here.
                        continue # Or sys.exit to be stricter
                return dbc_file_path
            else:
                print("Invalid choice. Please enter a number from the list.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def main(target_bus, verbose):
    selected_dbc_path = get_selected_dbc_path()
    if not selected_dbc_path:
      print("No DBC file selected or found. Exiting.")
      sys.exit(1)

    print(f"Starting CAN Message Interrogator...")
    print(f"  Monitoring CAN Bus Source: {target_bus}")
    print(f"  Using DBC File: {selected_dbc_path}")

    if verbose:
        print("  Verbose mode enabled: All decoded messages will be shown.")
    print("Waiting for CAN messages. Press Ctrl-C to exit and see summary.")

    try:
        # Load the single selected DBC
        loaded_dbc = DBCFileLoader(selected_dbc_path, allow_duplicate_messages=True)
    except Exception as e:
        print(f"Error loading selected DBC {selected_dbc_path}: {e}")
        sys.exit(1)

    sm = messaging.SubMaster(['can'])

    stats = defaultdict(int)
    # msg_id: {'unrecognized_dbc': count, 'malformed': count, 'decoded_ok': count}
    msg_stats = defaultdict(lambda: defaultdict(int))
    start_time = time.monotonic()

    try:
        while True:
            sm.update(100) # Wait up to 100ms for new messages

            if sm.updated['can']:
                current_event_time = sm.logMonoTime['can'] / 1e9 # seconds
                for c_msg in sm['can']:
                    if c_msg.src == target_bus:
                        stats['total_on_bus'] += 1
                        addr = c_msg.address
                        dat = c_msg.dat

                        try:
                            # Attempt to decode the message using the single selected DBC
                            decoded_signals = loaded_dbc.decode_message(addr, dat)
                            msg_stats[addr]['decoded_ok'] += 1 # Simplified stat for single DBC
                            stats['total_decoded_ok'] = stats.get('total_decoded_ok', 0) + 1
                            if verbose:
                                print(f"{current_event_time:.3f} BUS {c_msg.src} ID {hex(addr):<6} Data {dat.hex() :<20} - OK: {decoded_signals}")

                        except KeyError:
                            # Message ID not found in the selected DBC
                            msg_stats[addr]['unrecognized_dbc'] += 1
                            stats['total_unrecognized_dbc'] += 1
                            print(f"{current_event_time:.3f} BUS {c_msg.src} ID {hex(addr):<6} Data {dat.hex() :<20} - FAIL: ID NOT IN SELECTED DBC ({os.path.basename(selected_dbc_path)})")

                        except Exception as e:
                            # Other decoding error (e.g., malformed payload for a known ID)
                            msg_stats[addr]['malformed'] += 1
                            stats['total_malformed'] += 1
                            error_str = str(e).replace('\n', ' ').strip() # Clean up error string
                            print(f"{current_event_time:.3f} BUS {c_msg.src} ID {hex(addr):<6} Data {dat.hex() :<20} - FAIL: DECODE ERROR ({os.path.basename(selected_dbc_path)}): {error_str[:100]}")
            else:
                # No new 'can' message in this update cycle
                if time.monotonic() - start_time > 1 and stats['total_on_bus'] == 0:
                    print(f"No messages received on bus {target_bus} after 1 second...", end='\r')

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Generating summary...")
    finally:
        print("\n" + "=" * 30 + " CAN Interrogation Summary " + "=" * 30)
        print(f"Target Bus: {target_bus}, Selected DBC: {selected_dbc_path}")
        print(f"Duration: {time.monotonic() - start_time:.2f} seconds")
        print(f"Total messages observed on target bus {target_bus}: {stats['total_on_bus']}")
        print(f"  Successfully decoded: {stats.get('total_decoded_ok', 0)}")
        print(f"  ID not found in selected DBC: {stats.get('total_unrecognized_dbc', 0)}")
        print(f"  Decode errors (malformed payload for known ID in at least one loaded DBC): {stats['total_malformed']}")
        print("\nBreakdown by Message ID (includes problematic and optionally all verbose messages):")

        # Sort by address for consistent output
        sorted_problematic_ids = sorted(msg_stats.keys())

        for addr in sorted_problematic_ids:
            id_stats = msg_stats[addr]
            unrecognized_count = id_stats.get('unrecognized_dbc', 0)
            malformed_count = id_stats.get('malformed', 0)
            decoded_ok_count = id_stats.get('decoded_ok', 0)

            if unrecognized_count > 0 or malformed_count > 0 or (verbose and decoded_ok_count > 0):
                print(f"  ID {hex(addr):<6} -> Decoded OK: {decoded_ok_count:<7} | Unrecognized by DBC: {unrecognized_count:<7} | Malformed: {malformed_count:<7}")

        print("=" * (60 + len(" CAN Interrogation Summary ")))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAN Message Interrogator: Interactively select a DBC to diagnose issues on a specific CAN bus.",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--bus', type=int, default=DEFAULT_TARGET_BUS,
                        help=f"CAN bus source to monitor (0, 1, 2, ...). Default: {DEFAULT_TARGET_BUS}")
    parser.add_argument('--verbose', action='store_true',
                        help="If set, prints all successfully decoded messages in real-time.")

    args = parser.parse_args()
    main(args.bus, args.verbose)