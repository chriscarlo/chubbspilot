#!/usr/bin/env python3
"""Test script to debug installer issues on TICI."""

import sys
import os

print(f"Python executable: {sys.executable}", file=sys.stderr)
print(f"Python version: {sys.version}", file=sys.stderr)
print(f"Python path: {sys.path}", file=sys.stderr)
print(f"Working directory: {os.getcwd()}", file=sys.stderr)
print(f"Script location: {__file__}", file=sys.stderr)
print(f"TICI file exists: {os.path.isfile('/TICI')}", file=sys.stderr)

# Test basic imports
try:
    import subprocess
    print("subprocess: OK", file=sys.stderr)
except Exception as e:
    print(f"subprocess: FAILED - {e}", file=sys.stderr)

try:
    from pathlib import Path
    print("pathlib: OK", file=sys.stderr)
except Exception as e:
    print(f"pathlib: FAILED - {e}", file=sys.stderr)

try:
    from typing import List, Tuple
    print("typing: OK", file=sys.stderr)
except Exception as e:
    print(f"typing: FAILED - {e}", file=sys.stderr)

print("Test completed successfully", file=sys.stderr)
sys.exit(0)