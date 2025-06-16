#!/usr/bin/env python3
"""
Simplified mapd launcher that won't block boot.
Falls back to simple subprocess management like upstream.
"""

import os
import subprocess
import time
import threading
from pathlib import Path

from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.frogpilot.frogpilot_variables import MAPD_PATH


def download_mapd_binary():
    """Attempt to download mapd binary in background."""
    try:
        # Try to download using the existing download script if available
        download_script = Path(__file__).parent / "download_mapd.sh"
        if download_script.exists():
            subprocess.run([str(download_script)], capture_output=True, timeout=30)
    except Exception as e:
        cloudlog.error(f"Failed to download mapd binary: {e}")


def launch_mapd_subprocess():
    """Launch mapd as a simple subprocess if binary exists."""
    binary_path = str(MAPD_PATH)
    
    if not os.path.exists(binary_path):
        # Try to download in background, but don't block
        threading.Thread(target=download_mapd_binary, daemon=True).start()
        return None
    
    if not os.access(binary_path, os.X_OK):
        try:
            os.chmod(binary_path, 0o755)
        except Exception:
            pass
    
    try:
        # Launch mapd as a simple subprocess
        process = subprocess.Popen([binary_path])
        cloudlog.info(f"Started mapd with PID {process.pid}")
        return process
    except Exception as e:
        cloudlog.error(f"Failed to start mapd: {e}")
        return None


def main():
    """Simple mapd launcher that won't block boot."""
    cloudlog.info("mapd simple launcher starting")
    
    # Give system time to initialize
    time.sleep(5)
    
    mapd_process = None
    
    while True:
        try:
            # If mapd isn't running, try to start it
            if mapd_process is None or mapd_process.poll() is not None:
                mapd_process = launch_mapd_subprocess()
                if mapd_process is None:
                    # Binary doesn't exist yet, wait and retry
                    time.sleep(30)
                    continue
            
            # Check every 10 seconds
            time.sleep(10)
            
        except Exception as e:
            cloudlog.error(f"Error in mapd launcher: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()