#!/usr/bin/env python3
"""
Ensure critical Python dependencies are installed on TICI device.
This is a temporary workaround for missing dependencies at runtime.
"""
import subprocess
import sys

REQUIRED_PACKAGES = [
    "shapely",
]

def check_and_install_packages():
    missing_packages = []
    
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing packages detected: {missing_packages}")
        print("Attempting to install...")
        
        # Use pip with --user flag to install in user directory
        for package in missing_packages:
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", 
                    "--user", "--no-deps", package
                ])
                print(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}: {e}")
                # Continue anyway - the system might still work

if __name__ == "__main__":
    check_and_install_packages()