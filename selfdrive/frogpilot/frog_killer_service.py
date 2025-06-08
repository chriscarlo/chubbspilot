#!/usr/bin/env python3
"""
Frog Killer Service - Monitors for kill command and eliminates boot frog.
This runs as part of FrogPilot and can be triggered remotely via parameters.
"""

import time
import subprocess
from pathlib import Path
from openpilot.common.params import Params

def kill_the_frog():
    """Execute the frog elimination."""
    print("🐸💀 FROG KILL COMMAND RECEIVED!")
    
    # Run the kill script
    kill_script = Path(__file__).parent / "assets/boot/kill_frog_boot.py"
    if kill_script.exists():
        try:
            subprocess.run(["python3", str(kill_script)], check=True, timeout=30)
            print("✅ Frog elimination script executed")
        except Exception as e:
            print(f"❌ Kill script failed: {e}")
    
    # Force a reboot to apply changes
    try:
        print("Forcing manager restart to apply boot logo changes...")
        subprocess.run(["pkill", "-SIGHUP", "manager"], check=True)
    except Exception as e:
        print(f"Could not restart manager: {e}")
    
    return True

def monitor_kill_command():
    """Monitor for remote kill command via parameters."""
    params = Params()
    
    # Check if kill command is set
    if params.get_bool("KillBootFrog"):
        print("Kill command detected!")
        if kill_the_frog():
            # Clear the command
            params.remove("KillBootFrog")
            # Set confirmation
            params.put_bool("BootFrogKilled", True)
            return True
    
    return False

def main():
    """Main monitoring loop."""
    print("🎯 Frog Killer Service Started")
    
    # Check immediately on startup
    monitor_kill_command()
    
    # Keep monitoring
    while True:
        try:
            if monitor_kill_command():
                print("Frog eliminated! Service stopping.")
                break
            time.sleep(5)  # Check every 5 seconds
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error in frog killer service: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()