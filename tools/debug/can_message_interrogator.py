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
from opendbc.can.common.dbc import dbc as DBCFileLoader # Renamed to avoid confusion

# Define OPENPILOT_ROOT for DBC path
OPENPILOT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../.."))

DEFAULT_DBC_PREFIX = "hyundai_kia_generic_canfd"
DEFAULT_TARGET_BUS = 2

def main(dbc_prefix, target_bus, verbose):
    dbc_file_name = dbc_prefix + ".dbc"
    # Standard location for DBC files in openpilot
    dbc_file_path = os.path.join(OPENPILOT_ROOT, "opendbc", dbc_file_name)

    if not os.path.exists(dbc_file_path):
        print(f"Error: DBC file not found at {dbc_file_path}")
        # Attempt an alternative path if opendbc is a sibling directory (e.g. in a submodule setup)
        alt_dbc_path = os.path.join(os.path.dirname(OPENPILOT_ROOT), "opendbc", dbc_file_name)
        if os.path.exists(alt_dbc_path):
            dbc_file_path = alt_dbc_path
        else:
            print(f"Error: DBC file also not found at {alt_dbc_path}")
            print("Please ensure the DBC file exists and the --dbc argument is correct.")
            sys.exit(1)

    print(f"Starting CAN Message Interrogator...")
    print(f"  Monitoring CAN Bus Source: {target_bus}")
    print(f"  Using DBC File: {dbc_file_path}")
    if verbose:
        print("  Verbose mode enabled: All decoded messages will be shown.")
    print("Waiting for CAN messages. Press Ctrl-C to exit and see summary.")
    print("-" * 70)


    try:
        loaded_dbc = DBCFileLoader(dbc_file_path, allow_duplicate_messages=True)
    except Exception as e:
        print(f"Error loading DBC {dbc_file_path}: {e}")
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
                            # Attempt to decode the message
                            decoded_signals = loaded_dbc.decode_message(addr, dat)
                            msg_stats[addr]['decoded_ok'] += 1
                            if verbose:
                                print(f"{current_event_time:.3f} BUS {c_msg.src} ID {hex(addr):<6} Data {dat.hex() :<20} - OK: {decoded_signals}")

                        except KeyError:
                            # Message ID not found in the loaded DBC
                            msg_stats[addr]['unrecognized_dbc'] += 1
                            stats['total_unrecognized_dbc'] += 1
                            print(f"{current_event_time:.3f} BUS {c_msg.src} ID {hex(addr):<6} Data {dat.hex() :<20} - FAIL: ID NOT IN DBC")

                        except Exception as e:
                            # Other decoding error (e.g., malformed payload for a known ID)
                            msg_stats[addr]['malformed'] += 1
                            stats['total_malformed'] += 1
                            error_str = str(e).replace('\n', ' ').strip() # Clean up error string
                            print(f"{current_event_time:.3f} BUS {c_msg.src} ID {hex(addr):<6} Data {dat.hex() :<20} - FAIL: DECODE ERROR: {error_str[:100]}")
            else:
                # No new 'can' message in this update cycle
                if time.monotonic() - start_time > 1 and stats['total_on_bus'] == 0:
                    print(f"No messages received on bus {target_bus} after 1 second...", end='\r')


    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Generating summary...")
    finally:
        print("\n" + "=" * 30 + " CAN Interrogation Summary " + "=" * 30)
        print(f"Target Bus: {target_bus}, DBC: {dbc_file_path}")
        print(f"Duration: {time.monotonic() - start_time:.2f} seconds")
        print(f"Total messages observed on target bus {target_bus}: {stats['total_on_bus']}")
        print(f"  Successfully decoded: {stats['total_on_bus'] - stats['total_unrecognized_dbc'] - stats['total_malformed']}")
        print(f"  ID not found in DBC (unrecognized): {stats['total_unrecognized_dbc']}")
        print(f"  Decode errors (malformed payload): {stats['total_malformed']}")
        print("\nBreakdown by Message ID (includes problematic and optionally all verbose messages):")

        # Sort by address for consistent output
        sorted_problematic_ids = sorted(msg_stats.keys())

        for addr in sorted_problematic_ids:
            id_stats = msg_stats[addr]
            unrecognized_count = id_stats['unrecognized_dbc']
            malformed_count = id_stats['malformed']
            decoded_ok_count = id_stats['decoded_ok']

            if unrecognized_count > 0 or malformed_count > 0 or (verbose and decoded_ok_count > 0):
                print(f"  ID {hex(addr):<6} -> Decoded OK: {decoded_ok_count:<7} | Unrecognized by DBC: {unrecognized_count:<7} | Malformed: {malformed_count:<7}")
        print("=" * (60 + len(" CAN Interrogation Summary ")))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CAN Message Interrogator: Diagnose DBC issues on a specific CAN bus.")
    parser.add_argument('--bus', type=int, default=DEFAULT_TARGET_BUS,
                        help=f"CAN bus source to monitor (0, 1, 2, ...). Default: {DEFAULT_TARGET_BUS}")
    parser.add_argument('--dbc', type=str, default=DEFAULT_DBC_PREFIX,
                        help=f"DBC file prefix (e.g., hyundai_kia_generic_canfd). '.dbc' will be appended. Default: {DEFAULT_DBC_PREFIX}")
    parser.add_argument('--verbose', action='store_true',
                        help="If set, prints all successfully decoded messages in real-time.")

    args = parser.parse_args()
    main(args.dbc, args.bus, args.verbose)