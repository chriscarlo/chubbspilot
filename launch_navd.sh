#!/usr/bin/bash

# Setups the environment similar to the main launch script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $DIR

source ./launch_env.sh

# Set PYTHONPATH. Must be absolute path
export PYTHONPATH="$DIR"

echo "Launching navd.py directly..."
# Execute navd.py - output will appear here
python selfdrive/navd/navd.py