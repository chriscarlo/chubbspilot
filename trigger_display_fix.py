#!/usr/bin/env python3
"""
Simple utility to trigger TICI display fixes remotely.
This sets a parameter that will be picked up by the FrogPilot process.
"""

from openpilot.common.params import Params

def main():
    params = Params()
    
    # Check if we're on TICI
    try:
        with open('/TICI', 'r'):
            pass
    except FileNotFoundError:
        print("❌ This utility is for TICI devices only")
        return
    
    print("🔧 Triggering TICI display fix...")
    
    # Set the parameter to trigger the fix
    params.put_bool("FixTICIDisplay", True)
    
    print("✅ Display fix triggered!")
    print("The fix will run in the background within 5 seconds.")
    print("Check /tmp/tici_display_fix.log for results.")

if __name__ == "__main__":
    main()