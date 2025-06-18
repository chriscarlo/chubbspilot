import csv
import json
import math
import os
import sys
import time
from typing import Optional

import requests

# Constants identical to navd.py logic
EARTH_RADIUS_KM = 6371.0
FETCH_DISTANCE_KM = 0.05  # 50 m

MAPBOX_DEFAULT_HOST = "https://api.mapbox.com"


def calculate_coordinate_ahead(lat_deg: float, lon_deg: float, bearing_deg: float, distance_km: float):
    """Return (lat, lon) of a point `distance_km` ahead along `bearing_deg`."""
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    bearing_rad = math.radians(bearing_deg)
    lat2_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_km / EARTH_RADIUS_KM)
        + math.cos(lat_rad) * math.sin(distance_km / EARTH_RADIUS_KM) * math.cos(bearing_rad)
    )
    lon2_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_km / EARTH_RADIUS_KM) * math.cos(lat_rad),
        math.cos(distance_km / EARTH_RADIUS_KM) - math.sin(lat_rad) * math.sin(lat2_rad),
    )
    return math.degrees(lat2_rad), math.degrees(lon2_rad)


def maxspeed_to_ms(speed_info: dict) -> Optional[float]:
    """Convert Mapbox maxspeed structure to m/s, returns None if unknown."""
    if not speed_info or "speed" not in speed_info or speed_info["speed"] is None:
        return None
    speed_val = speed_info["speed"]

    if isinstance(speed_val, (int, float)):
        # Mapbox already returns m/s when numeric
        return float(speed_val)

    if isinstance(speed_val, str):
        speed_val = speed_val.strip().lower()
        if speed_val in ("none", "unknown"):
            return None
        # Expect format like "60 kph" or "55 mph" or "120km/h"
        num = "".join(ch for ch in speed_val if ch.isdigit() or ch == ".")
        unit = "mph" if "mph" in speed_val else "kph" if "kph" in speed_val or "km" in speed_val else None
        if not num:
            return None
        try:
            num_f = float(num)
        except ValueError:
            return None
        if unit == "mph":
            return num_f * 0.44704
        elif unit == "kph":
            return num_f * 0.277778
        else:
            # Assume kph if unit missing
            return num_f * 0.277778
    return None


def fetch_speed_limit(lat: float, lon: float, bearing_deg: float, token: str, host: str = MAPBOX_DEFAULT_HOST) -> Optional[float]:
    """Call Mapbox Directions API for a tiny two-point route and return speed limit in m/s."""
    lat2, lon2 = calculate_coordinate_ahead(lat, lon, bearing_deg, FETCH_DISTANCE_KM)

    coords_str = f"{lon},{lat};{lon2},{lat2}"
    url = f"{host}/directions/v5/mapbox/driving-traffic/{coords_str}"

    params = {
        "access_token": token,
        "annotations": "maxspeed",
        "geometries": "geojson",
        "overview": "full",
        "steps": "false",
        "alternatives": "false",
        "waypoints": "0;1",
        "bearings": f"{(bearing_deg + 360) % 360:.0f},90;,180",
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        routes = data.get("routes", [])
        if not routes:
            return None
        leg = routes[0]["legs"][0]
        maxspeeds = leg.get("annotation", {}).get("maxspeed", [])
        for speed_info in maxspeeds:
            ms = maxspeed_to_ms(speed_info)
            if ms is not None:
                return ms
        return None
    except Exception as e:
        print(f"Error fetching speed limit for {lat},{lon}: {e}")
        return None


def main(csv_path: str):
    token = os.getenv("MAPBOX_TOKEN")
    if not token:
        print("Error: MAPBOX_TOKEN environment variable not set.")
        sys.exit(1)

    successes = 0
    total = 0
    with open(csv_path, newline="") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            total += 1
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            bearing_rad = float(row["bearing_rad"])
            bearing_deg = math.degrees(bearing_rad)

            ms = fetch_speed_limit(lat, lon, bearing_deg, token)
            if ms is not None:
                mph = ms * 2.23694
                kph = ms * 3.6
                print(f"{row['timestamp']}: Speed limit {kph:.1f} km/h ({mph:.1f} mph)")
                successes += 1
            else:
                print(f"{row['timestamp']}: No speed limit found")
            # be polite to API
            time.sleep(0.25)

    print("\nFinished. {}/{} points returned a speed limit.".format(successes, total))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/navd_speed_limit_checker.py <extracted_gps_data.csv>")
        sys.exit(1)
    main(sys.argv[1])