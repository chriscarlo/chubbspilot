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

DEFAULT_TARGET_BUS = 2 # Default, but can be overridden
DEFAULT_CAR_PLATFORM = None # Needs to be specified by user for multi-DBC logic

def get_dbc_paths_for_car(car_platform_name):
    """Fetches all relevant DBC file paths for a given car platform name."""
    dbc_paths = set()
    # Attempt to load Hyundai/Kia DBCs first
    if hasattr(HYUNDAI_CAR_PLATFORMS, car_platform_name):
        car_fingerprint = getattr(HYUNDAI_CAR_PLATFORMS, car_platform_name)
        if car_fingerprint in HYUNDAI_DBC_MAP:
            dbc_specific_map = HYUNDAI_DBC_MAP[car_fingerprint]
            # dbc_specific_map can be a dict of {dbc_name: path} or just a path string for platform_dbc
            if isinstance(dbc_specific_map, dict):
                for dbc_name, path_or_paths in dbc_specific_map.items():
                    if isinstance(path_or_paths, list):
                        for p in path_or_paths:
                           if isinstance(p, str) and p.endswith('.dbc'):
                             dbc_paths.add(os.path.join(OPENPILOT_ROOT, "opendbc", p) if not os.path.isabs(p) else p)
                    elif isinstance(path_or_paths, str) and path_or_paths.endswith('.dbc'):
                        dbc_paths.add(os.path.join(OPENPILOT_ROOT, "opendbc", path_or_paths) if not os.path.isabs(path_or_paths) else path_or_paths)
            elif isinstance(dbc_specific_map, str) and dbc_specific_map.endswith('.dbc'): # platform_dbc might be a direct string
                dbc_paths.add(os.path.join(OPENPILOT_ROOT, "opendbc", dbc_specific_map) if not os.path.isabs(dbc_specific_map) else dbc_specific_map)

    # Fallback or general DBC from get_interface_attr if Hyundai specific lookup fails or is incomplete
    # This part might be more complex depending on how get_interface_attr structures dbc_dict
    try:
        car_dbc_dict = get_interface_attr("DBC_DICT", car_platform_name)
        if car_dbc_dict:
            for dbc_key, dbc_file_or_list in car_dbc_dict.items():
                files_to_add = dbc_file_or_list if isinstance(dbc_file_or_list, list) else [dbc_file_or_list]
                for dbc_file_name_only in files_to_add:
                    if isinstance(dbc_file_name_only, str) and dbc_file_name_only.endswith('.dbc'):
                      # Construct full path, assuming it's relative to opendbc like hyundai_kia_generic.dbc etc.
                      full_path = os.path.join(OPENPILOT_ROOT, "opendbc", dbc_file_name_only)
                      dbc_paths.add(full_path)
    except Exception as e:
        print(f"Warning: Could not fully resolve DBCs via get_interface_attr for {car_platform_name}: {e}")

    if not dbc_paths:
        print(f"Error: No DBC paths found for car platform '{car_platform_name}'. Is it a valid CAR name from a values.py?")
        sys.exit(1)

    # Filter out non-existent paths as a final check
    valid_paths = {p for p in dbc_paths if os.path.exists(p)}
    if len(valid_paths) < len(dbc_paths):
        print(f"Warning: Some DBC paths were not found: {dbc_paths - valid_paths}")
    if not valid_paths:
        print(f"Error: All resolved DBC paths for {car_platform_name} do not exist. Searched: {dbc_paths}")
        sys.exit(1)
    return list(valid_paths)

def main(car_platform_name, target_bus, verbose, dbc_file_override):
    loaded_dbcs = []
    dbc_file_paths_to_load = []

    if dbc_file_override:
        # Standard location for DBC files in openpilot
        dbc_file_path = os.path.join(OPENPILOT_ROOT, "opendbc", dbc_file_override + ".dbc" if not dbc_file_override.endswith(".dbc") else dbc_file_override)
        if not os.path.exists(dbc_file_path):
            # Attempt an alternative path if opendbc is a sibling directory (e.g. in a submodule setup)
            alt_dbc_path = os.path.join(os.path.dirname(OPENPILOT_ROOT), "opendbc", dbc_file_override + ".dbc" if not dbc_file_override.endswith(".dbc") else dbc_file_override)
            if os.path.exists(alt_dbc_path):
                dbc_file_path = alt_dbc_path
            else:
                print(f"Error: DBC file {dbc_file_override} not found at {dbc_file_path} or {alt_dbc_path}")
                sys.exit(1)
        dbc_file_paths_to_load = [dbc_file_path]
        print(f"Starting CAN Message Interrogator with OVERRIDE DBC...")
        print(f"  Monitoring CAN Bus Source: {target_bus}")
        print(f"  Using DBC File (override): {dbc_file_paths_to_load[0]}")
    elif car_platform_name:
        dbc_file_paths_to_load = get_dbc_paths_for_car(car_platform_name)
        print(f"Starting CAN Message Interrogator for car: {car_platform_name}...")
        print(f"  Monitoring CAN Bus Source: {target_bus}")
        print(f"  Using {len(dbc_file_paths_to_load)} DBC Files specific to {car_platform_name}:")
        for p in dbc_file_paths_to_load:
            print(f"    - {p}")
    else:
        print("Error: You must specify either --car <CAR_PLATFORM> or --dbc <DBC_FILE_PREFIX>.")
        sys.exit(1)

    print("Waiting for CAN messages. Press Ctrl-C to exit and see summary.")
    print("-" * 70)

    try:
        for dbc_path in dbc_file_paths_to_load:
            try:
                loaded_dbcs.append(DBCFileLoader(dbc_path, allow_duplicate_messages=True))
            except Exception as e:
                print(f"Error loading DBC {dbc_path}: {e}. Skipping this DBC.")
        if not loaded_dbcs:
            print("Error: No DBC files could be loaded successfully. Exiting.")
            sys.exit(1)
    except Exception as e:
        # This catch is for unforeseen issues during the loop setup, though individual loads are caught above.
        print(f"An unexpected error occurred during DBC loading: {e}")
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