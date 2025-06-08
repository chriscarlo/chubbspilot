#!/usr/bin/env python3
"""
Wrapper for mapd_daemon that ensures shapely is installed before importing.
"""
import subprocess
import sys
import os

def ensure_shapely():
    """Ensure shapely is installed before proceeding."""
    try:
        import shapely
        return True
    except ImportError:
        print("shapely not found, attempting to install...")
        
        if os.path.isfile('/TICI'):
            # Try to install shapely on TICI
            try:
                subprocess.check_call(["sudo", "pip3", "install", "shapely"], stderr=subprocess.STDOUT)
                print("Successfully installed shapely")
                return True
            except subprocess.CalledProcessError:
                try:
                    subprocess.check_call(["sudo", sys.executable, "-m", "pip", "install", "shapely"], stderr=subprocess.STDOUT)
                    print("Successfully installed shapely")
                    return True
                except subprocess.CalledProcessError:
                    try:
                        subprocess.check_call(["sudo", "apt-get", "update"], stderr=subprocess.STDOUT)
                        subprocess.check_call(["sudo", "apt-get", "install", "-y", "python3-shapely"], stderr=subprocess.STDOUT)
                        print("Successfully installed python3-shapely via apt")
                        return True
                    except subprocess.CalledProcessError:
                        print("Failed to install shapely")
                        return False
        else:
            print("Not on TICI, shapely installation skipped")
            return False

if __name__ == "__main__":
    # Ensure shapely is available
    if ensure_shapely():
        # Import and run the actual mapd_daemon
        from openpilot.selfdrive.frogpilot.navigation.mapd_py.mapd_daemon import main
        main()
    else:
        print("ERROR: Could not ensure shapely installation. mapd_daemon will not start.")
        sys.exit(1)