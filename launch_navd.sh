#!/usr/bin/bash

# Setups the environment similar to the main launch script
# DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" # No longer needed
# cd $DIR # No longer needed

# Source environment from standard location
source /data/openpilot/launch_env.sh

# Set PYTHONPATH explicitly to the standard openpilot directory
export PYTHONPATH="/data/openpilot"

# echo "Launching navd.py directly..." # Removed echo line
# Execute navd.py using its absolute path
python /data/openpilot/selfdrive/navd/navd.py