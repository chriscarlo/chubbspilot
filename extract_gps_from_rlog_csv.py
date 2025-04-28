#!/usr/bin/env python3
import csv
import os
import sys
import math

# --- Configuration ---
INPUT_CSV_PATH = "/home/chris/openpilot/rlogs/parsed_rlogs/asdf.csv"
OUTPUT_CSV_PATH = "/home/chris/openpilot/rlogs/parsed_logs/extracted_gps_data.csv"

# Define the columns we need and their potential names in the PlotJuggler dump
# Prioritize '__time' if available, otherwise 'unixTimestampMillis'
COLUMN_MAPPING = {
    'timestamp': ['__time'], # Assuming PlotJuggler always adds __time
    'latitude': ['/gpsLocation/Latitude'],
    'longitude': ['/gpsLocation/Longitude'],
    'bearing_deg': ['/gpsLocation/bearingDeg'] # Read bearing in degrees
}

OUTPUT_HEADER = ['timestamp', 'latitude', 'longitude', 'bearing_rad'] # Output bearing in radians
# ---------------------

def find_column_indices(header):
    """Finds the indices of the required columns based on the mapping."""
    indices = {}
    header_lower = [h.lower() for h in header] # Case-insensitive matching
    for key, potential_names in COLUMN_MAPPING.items():
        found = False
        for name in potential_names:
            try:
                indices[key] = header_lower.index(name.lower())
                print(f"Found column for '{key}': '{header[indices[key]]}' at index {indices[key]}")
                found = True
                break
            except ValueError:
                continue
        if not found:
            print(f"Error: Could not find any column for '{key}' in header: {header}")
            print(f"       Expected one of: {potential_names}")
            return None
    return indices

def main():
    print(f"Input CSV: {INPUT_CSV_PATH}")
    print(f"Output CSV: {OUTPUT_CSV_PATH}")

    if not os.path.exists(INPUT_CSV_PATH):
        print(f"Error: Input file not found: {INPUT_CSV_PATH}")
        sys.exit(1)

    try:
        # Try opening with latin-1 encoding as a fallback for potential non-UTF-8 characters
        # Reverted to default encoding (likely UTF-8)
        with open(INPUT_CSV_PATH, 'r', newline='') as infile, \
             open(OUTPUT_CSV_PATH, 'w', newline='') as outfile:

            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            # Read header
            try:
                header = next(reader)
            except StopIteration:
                print("Error: Input CSV file is empty.")
                sys.exit(1)

            # Find column indices
            indices = find_column_indices(header)
            if indices is None:
                sys.exit(1)

            # Write output header
            writer.writerow(OUTPUT_HEADER)

            processed_rows = 0
            skipped_rows = 0
            # Process data rows
            for i, row in enumerate(reader):
                try:
                    # Ensure row has enough columns (handle potentially truncated lines)
                    if len(row) <= max(indices.values()):
                        print(f"Warning: Skipping row {i+2}, not enough columns ({len(row)}).")
                        skipped_rows += 1
                        continue

                    # Extract data using found indices
                    timestamp_str = row[indices['timestamp']]
                    latitude_str = row[indices['latitude']]
                    longitude_str = row[indices['longitude']]
                    bearing_deg_str = row[indices['bearing_deg']]

                    # Check if any required GPS field is empty
                    if not latitude_str or not longitude_str or not bearing_deg_str:
                        # print(f"Warning: Skipping row {i+2}, missing GPS data. Lat='{latitude_str}', Lon='{longitude_str}', Bear='{bearing_deg_str}'")
                        skipped_rows += 1
                        continue

                    # Convert to float (now safe after check)
                    timestamp = float(timestamp_str)
                    latitude = float(latitude_str)
                    longitude = float(longitude_str)
                    bearing_deg = float(bearing_deg_str)

                    # Convert bearing from degrees to radians
                    bearing_rad = math.radians(bearing_deg)

                    # Optional: Add validity checks here if needed using columns like gpsOK etc.

                    # Write extracted row
                    writer.writerow([timestamp, latitude, longitude, bearing_rad])
                    processed_rows += 1

                except (ValueError, IndexError) as e:
                    print(f"Warning: Skipping row {i+2} due to error: {e}. Row data: {row}")
                    skipped_rows += 1
                    continue

            print(f"\nProcessing complete.")
            print(f"  Processed rows: {processed_rows}")
            print(f"  Skipped rows: {skipped_rows}")
            print(f"Output written to: {OUTPUT_CSV_PATH}")

    except FileNotFoundError:
        print(f"Error: Could not open input file: {INPUT_CSV_PATH}")
        sys.exit(1)
    except IOError as e:
        print(f"Error writing to output file: {OUTPUT_CSV_PATH}. Error: {e}")
        sys.exit(1)
    except UnicodeDecodeError as e:
        print(f"Error: Failed to decode input file '{INPUT_CSV_PATH}'. It might not be a standard text CSV or could be corrupted.")
        print(f"Specific error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()