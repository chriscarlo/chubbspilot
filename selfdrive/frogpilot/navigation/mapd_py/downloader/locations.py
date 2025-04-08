"""Loads location bounding box data."""

import json
import os

# Assuming this script is run relative to the mapd_py directory
# Adjust paths if necessary based on execution context
MODULE_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.abspath(os.path.join(MODULE_DIR, "..", "..", "navigation", "mapd_source")) # Go up to frogpilot, then down

NATION_BOXES_FILE = os.path.join(SOURCE_DIR, "nation_bounding_boxes.json")
STATE_BOXES_FILE = os.path.join(SOURCE_DIR, "us_states_bounding_boxes.json")

NATION_BOXES = {}
STATE_BOXES = {}

def load_locations():
    """Loads the nation and state bounding box data from the JSON files."""
    global NATION_BOXES, STATE_BOXES
    try:
        with open(NATION_BOXES_FILE, 'r') as f:
            NATION_BOXES = json.load(f)
        print(f"Loaded {len(NATION_BOXES)} nation bounding boxes.")
    except FileNotFoundError:
        print(f"Error: Nation bounding box file not found at {NATION_BOXES_FILE}")
        NATION_BOXES = {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {NATION_BOXES_FILE}: {e}")
        NATION_BOXES = {}

    try:
        with open(STATE_BOXES_FILE, 'r') as f:
            STATE_BOXES = json.load(f)
        print(f"Loaded {len(STATE_BOXES)} state bounding boxes.")
    except FileNotFoundError:
        print(f"Error: State bounding box file not found at {STATE_BOXES_FILE}")
        STATE_BOXES = {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {STATE_BOXES_FILE}: {e}")
        STATE_BOXES = {}

# Load locations when the module is imported
load_locations()

if __name__ == "__main__":
    # Print some loaded data for verification
    print("\n--- Nation Boxes Sample ---")
    count = 0
    for k, v in NATION_BOXES.items():
        print(f" {k}: {v.get('full_name', '')}")
        count += 1
        if count >= 5:
            break

    print("\n--- State Boxes Sample ---")
    count = 0
    for k, v in STATE_BOXES.items():
        print(f" {k}: {v.get('full_name', '')}")
        count += 1
        if count >= 5:
            break