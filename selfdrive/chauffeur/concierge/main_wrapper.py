#!/usr/bin/env python3
"""
Wrapper for concierge main that ensures dependencies are installed before importing.
"""
import subprocess
import sys
import os
import runpy

def ensure_dependencies():
    """Ensure all concierge dependencies are installed."""
    required_packages = [
        "pydantic",
        "fastapi",
        "uvicorn",
        "jinja2",
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Missing packages detected: {missing}")
        
        if os.path.isfile('/TICI'):
            # Try to install on TICI
            for package in missing:
                print(f"Installing {package}...")
                try:
                    subprocess.check_call(["sudo", "pip3", "install", package], stderr=subprocess.STDOUT)
                    print(f"Successfully installed {package}")
                except subprocess.CalledProcessError:
                    try:
                        subprocess.check_call(["sudo", sys.executable, "-m", "pip", "install", package], stderr=subprocess.STDOUT)
                        print(f"Successfully installed {package}")
                    except subprocess.CalledProcessError:
                        print(f"Failed to install {package}")
        else:
            print("Not on TICI, dependency installation skipped")
            return False
    
    return True

if __name__ == "__main__":
    # Ensure dependencies are available
    if ensure_dependencies():
        # Run the module directly to preserve its __main__ logic
        runpy.run_module("openpilot.selfdrive.chauffeur.concierge.main", run_name="__main__")
    else:
        print("ERROR: Could not ensure dependencies. Concierge will not start.")
        sys.exit(1)