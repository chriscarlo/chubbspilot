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
    # Tier 1 - Critical (boot failures if missing)
    "numpy",
    "shapely", 
    "pydantic",
    "uvicorn",
    "jinja2",
    "requests",
    
    # Tier 2 - Important (service failures if missing)
    "zmq",
    "psutil",
    "PIL",
    "cv2",
    
    # Tier 3 - Optional but commonly used
    "fastapi",  # May be conditionally imported
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
                        # Try alternative package names or apt-get as fallbacks
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
                        elif package == "cv2":
                            try:
                                print("Trying to install opencv-python (cv2)...")
                                subprocess.check_call([
                                    "sudo", sys.executable, "-m", "pip", "install", "opencv-python"
                                ], stderr=subprocess.STDOUT)
                                print("Successfully installed opencv-python")
                            except subprocess.CalledProcessError as e:
                                print(f"Failed to install opencv-python: {e}")
                        elif package == "PIL":
                            try:
                                print("Trying to install Pillow (PIL)...")
                                subprocess.check_call([
                                    "sudo", sys.executable, "-m", "pip", "install", "Pillow"
                                ], stderr=subprocess.STDOUT)
                                print("Successfully installed Pillow")
                            except subprocess.CalledProcessError as e:
                                print(f"Failed to install Pillow: {e}")
                        elif package == "zmq":
                            try:
                                print("Trying to install pyzmq (zmq)...")
                                subprocess.check_call([
                                    "sudo", sys.executable, "-m", "pip", "install", "pyzmq"
                                ], stderr=subprocess.STDOUT)
                                print("Successfully installed pyzmq")
                            except subprocess.CalledProcessError as e:
                                print(f"Failed to install pyzmq: {e}")
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