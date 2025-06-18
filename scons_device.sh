#!/bin/bash
# SCons wrapper for device to ensure proper Python version
export PYTHONPATH=/data/openpilot
exec python3 $(which scons) "$@"