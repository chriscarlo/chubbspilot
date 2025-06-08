#!/usr/bin/env python3
"""
Ensure critical Python dependencies are installed on TICI device.
This is a temporary workaround for missing dependencies at runtime.
"""
import subprocess
import sys
import os
import time

REQUIRED_PACKAGES = [
    "shapely",
    "pydantic",
    "fastapi",
    "uvicorn",
    "jinja2",
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
        
        # On TICI, use sudo for system-wide installation (no password required)
        if os.path.isfile('/TICI'):
            for package in missing_packages:
                try:
                    # First try with pip3
                    print(f"Installing {package} with pip3...")
                    subprocess.check_call([
                        "sudo", "pip3", "install", package
                    ], stderr=subprocess.STDOUT)
                    print(f"Successfully installed {package}")
                except subprocess.CalledProcessError:
                    try:
                        # Fallback to python -m pip
                        print(f"Retrying {package} with python -m pip...")
                        subprocess.check_call([
                            "sudo", sys.executable, "-m", "pip", "install", package
                        ], stderr=subprocess.STDOUT)
                        print(f"Successfully installed {package}")
                    except subprocess.CalledProcessError as e:
                        print(f"Failed to install {package}: {e}")
                        # Try apt-get as last resort for shapely
                        if package == "shapely":
                            try:
                                print("Trying apt-get install python3-shapely...")
                                subprocess.check_call([
                                    "sudo", "apt-get", "update"
                                ], stderr=subprocess.STDOUT)
                                subprocess.check_call([
                                    "sudo", "apt-get", "install", "-y", "python3-shapely"
                                ], stderr=subprocess.STDOUT)
                                print("Successfully installed python3-shapely via apt")
                            except subprocess.CalledProcessError as e:
                                print(f"Failed to install via apt: {e}")
        else:
            # Non-TICI environment, use --user flag
            for package in missing_packages:
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", 
                        "--user", "--no-deps", package
                    ])
                    print(f"Successfully installed {package}")
                except subprocess.CalledProcessError as e:
                    print(f"Failed to install {package}: {e}")
    
    # Verify installation
    print("\nVerifying installations...")
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
            print(f"✓ {package} is available")
        except ImportError:
            print(f"✗ {package} is still missing")

if __name__ == "__main__":
    check_and_install_packages()