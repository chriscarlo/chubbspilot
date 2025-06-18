#!/usr/bin/env python3
"""
Map Download Helper - Bridges UI map selection to mapd download system
"""
import json
import time
from selfdrive.frogpilot.frogpilot_variables import params, params_memory


def monitor_map_downloads():
  """Monitor for map download requests and convert to OSMDownloadLocations format"""
  
  # Default map selections for California and Nevada
  default_selections = {
    "California": {"states": ["CA"], "nations": []},
    "Nevada": {"states": ["NV"], "nations": []},
    "California and Nevada": {"states": ["CA", "NV"], "nations": []}
  }
  
  while True:
    # Check if there's a pending map download trigger
    trigger = params_memory.get("TriggerMapDownloadCheck", encoding="utf-8")
    
    if trigger:
      # Clear the trigger
      params_memory.remove("TriggerMapDownloadCheck")
      
      # Get current map selection or use default
      maps_selected = json.loads(params.get("MapsSelected", encoding="utf-8") or "{}")
      
      # If no specific selection, default to California and Nevada
      if not maps_selected.get("states") and not maps_selected.get("nations"):
        maps_selected = default_selections.get("California and Nevada", {})
        params.put("MapsSelected", json.dumps(maps_selected))
      
      # Trigger the download via OSMDownloadLocations
      if params.get("OSMDownloadProgress", encoding="utf-8") is None:
        params_memory.put("OSMDownloadLocations", json.dumps(maps_selected))
        print(f"Triggered map download for: {maps_selected}")
    
    # Also check for specific state download requests
    for state, selection in default_selections.items():
      param_name = f"Download{state.replace(' ', '')}Map"
      if params_memory.get_bool(param_name):
        params_memory.remove(param_name)
        params.put("MapsSelected", json.dumps(selection))
        if params.get("OSMDownloadProgress", encoding="utf-8") is None:
          params_memory.put("OSMDownloadLocations", json.dumps(selection))
          print(f"Triggered {state} map download")
    
    time.sleep(5)


if __name__ == "__main__":
  monitor_map_downloads()