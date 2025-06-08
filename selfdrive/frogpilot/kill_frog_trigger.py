#!/usr/bin/env python3
"""
Simple script to trigger frog elimination via parameters.
Can be run from any Python environment that can access openpilot params.
"""

from openpilot.common.params import Params

def trigger_frog_kill():
    """Set the parameter to trigger frog elimination."""
    params = Params()
    
    print("🎯 Setting frog kill parameter...")
    params.put_bool("KillBootFrog", True)
    
    print("✅ Kill command set!")
    print("The FrogPilot process will detect this within 5 seconds and:")
    print("1. Create a black boot image")
    print("2. Replace the frog boot logo") 
    print("3. Restart the manager to apply changes")
    print("")
    print("Check if it worked by looking for BootFrogKilled=True in params")

if __name__ == "__main__":
    trigger_frog_kill()