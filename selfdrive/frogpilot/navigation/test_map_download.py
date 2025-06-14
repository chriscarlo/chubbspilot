#!/usr/bin/env python3
"""Test map download functionality"""
import json
import time
from openpilot.selfdrive.frogpilot.frogpilot_variables import params, params_memory


def test_map_download():
  """Test downloading California and Nevada maps"""
  
  print("Testing map download functionality...")
  
  # Set up map selection for California and Nevada
  maps_selected = {
    "states": ["CA", "NV"],
    "nations": []
  }
  
  print(f"Setting MapsSelected to: {maps_selected}")
  params.put("MapsSelected", json.dumps(maps_selected))
  
  # Check if download is already in progress
  progress = params.get("OSMDownloadProgress", encoding="utf-8")
  if progress:
    print(f"Download already in progress: {progress}")
    print("Waiting for completion...")
    while params.get("OSMDownloadProgress", encoding="utf-8") is not None:
      progress = params.get("OSMDownloadProgress", encoding="utf-8")
      if progress:
        print(f"Progress: {progress}")
      time.sleep(5)
    print("Download completed!")
  else:
    # Trigger the download
    print("Triggering map download...")
    params_memory.put("OSMDownloadLocations", json.dumps(maps_selected))
    
    # Wait for download to start
    print("Waiting for download to start...")
    for i in range(10):
      progress = params.get("OSMDownloadProgress", encoding="utf-8")
      if progress:
        print(f"Download started: {progress}")
        break
      time.sleep(1)
    else:
      print("Download did not start within 10 seconds")
      print("Make sure mapd process is running")
      return
    
    # Monitor progress
    print("Monitoring download progress...")
    while params.get("OSMDownloadProgress", encoding="utf-8") is not None:
      progress = params.get("OSMDownloadProgress", encoding="utf-8")
      if progress:
        print(f"Progress: {progress}")
      time.sleep(5)
    
    print("Download completed!")
  
  # Check if maps directory exists
  import os
  maps_path = "/data/media/0/osm/offline"
  if os.path.exists(maps_path):
    print(f"\nMaps directory exists: {maps_path}")
    files = os.listdir(maps_path)
    if files:
      print(f"Downloaded files: {files[:5]}...")  # Show first 5 files
    else:
      print("No files downloaded yet")
  else:
    print(f"\nMaps directory does not exist: {maps_path}")


if __name__ == "__main__":
  test_map_download()