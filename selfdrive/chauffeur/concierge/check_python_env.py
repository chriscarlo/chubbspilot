#!/usr/bin/env python3
"""Check Python environment and dependencies on TICI."""

import sys
import os
import site
import subprocess

print("=== Python Environment Check ===")
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")
print(f"Platform: {sys.platform}")
print(f"TICI: {os.path.isfile('/TICI')}")

print("\n=== Python Path ===")
for i, path in enumerate(sys.path):
    print(f"{i}: {path}")

print("\n=== Site Packages ===")
for path in site.getsitepackages():
    print(f"- {path}")
    if os.path.exists(path):
        # Check if fastapi exists there
        fastapi_path = os.path.join(path, "fastapi")
        if os.path.exists(fastapi_path):
            print(f"  ✓ Found fastapi at {fastapi_path}")

print("\n=== User Site ===")
user_site = site.getusersitepackages()
print(f"User site: {user_site}")
if os.path.exists(user_site):
    print("  (exists)")

print("\n=== Checking openpilot environment ===")
try:
    # Add openpilot to path
    openpilot_root = "/data/openpilot"
    if openpilot_root not in sys.path:
        sys.path.insert(0, openpilot_root)
        print(f"Added {openpilot_root} to sys.path")
    
    # Check for .pyenv or virtualenv
    pyenv_path = os.path.join(openpilot_root, ".pyenv")
    venv_path = os.path.join(openpilot_root, ".venv")
    poetry_venv = os.path.join(openpilot_root, ".poetry")
    
    for env_path in [pyenv_path, venv_path, poetry_venv]:
        if os.path.exists(env_path):
            print(f"Found environment: {env_path}")
            # Look for site-packages
            for root, dirs, files in os.walk(env_path):
                if "site-packages" in root:
                    print(f"  Site-packages: {root}")
                    if "fastapi" in dirs:
                        print(f"    ✓ Contains fastapi")
                    if "uvicorn" in dirs:
                        print(f"    ✓ Contains uvicorn")
                    break

except Exception as e:
    print(f"Error checking environments: {e}")

print("\n=== Attempting imports ===")
deps = ['fastapi', 'uvicorn', 'pydantic', 'jinja2']
for dep in deps:
    try:
        mod = __import__(dep)
        print(f"✓ {dep}: {mod.__file__ if hasattr(mod, '__file__') else 'built-in'}")
    except ImportError as e:
        print(f"✗ {dep}: {e}")

print("\n=== pip list check ===")
try:
    result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        lines = result.stdout.split('\n')
        for line in lines:
            if any(dep in line.lower() for dep in ['fastapi', 'uvicorn', 'pydantic']):
                print(f"  {line}")
except Exception as e:
    print(f"Could not run pip list: {e}")

print("\n=== PYTHONPATH ===")
print(f"PYTHONPATH env: {os.environ.get('PYTHONPATH', '(not set)')}")

print("\nDone.")