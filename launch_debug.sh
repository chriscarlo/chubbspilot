#!/bin/bash
# Debug launch script that shows actual build output

echo "=== DEBUG LAUNCH SCRIPT ==="
echo "This will show actual build output instead of the spinner"

cd /data/openpilot

# Source the environment
source launch_env.sh

# Remove prebuilt flag
rm -f prebuilt

# Run the debug build
echo "Starting debug build..."
python3 debug_build.py

# If build succeeds, start manager
if [ $? -eq 0 ]; then
    echo "Build successful, starting manager..."
    cd system/manager
    exec ./manager.py
else
    echo "Build failed! Check output above"
    # Keep terminal open
    while true; do sleep 1; done
fi