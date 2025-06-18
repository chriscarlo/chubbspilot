#!/usr/bin/env python3
"""
Debug build script that shows ACTUAL FUCKING OUTPUT
instead of a useless spinning frog
"""
import os
import subprocess
import sys
from pathlib import Path

os.chdir('/data/openpilot')

print("=== DEBUG BUILD STARTING ===")
print(f"Python: {sys.executable}")
print(f"Working directory: {os.getcwd()}")

# Check Python version
print(f"\nPython version: {sys.version}")

# Show environment
print("\nBuild environment:")
print(f"PATH: {os.environ.get('PATH', 'NOT SET')}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'NOT SET')}")

# Create obj directories
print("\nCreating obj directories...")
os.makedirs("body/board/obj", exist_ok=True)
os.makedirs("panda/board/obj", exist_ok=True)
print("✓ obj directories created")

# Run scons with full output
print("\n=== STARTING SCONS BUILD ===")
print("Running: scons -j1 --cache-populate")
print("-" * 60)

env = os.environ.copy()
env['PYTHONPATH'] = '/data/openpilot'

# Run scons with real-time output
proc = subprocess.Popen(
    ["scons", "-j1", "--cache-populate"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1,
    env=env
)

# Print output in real-time
for line in proc.stdout:
    print(line, end='', flush=True)

proc.wait()

print("-" * 60)
print(f"\nBuild finished with return code: {proc.returncode}")

if proc.returncode != 0:
    print("\n!!! BUILD FAILED !!!")
    sys.exit(1)
else:
    print("\n✓ BUILD SUCCESSFUL")