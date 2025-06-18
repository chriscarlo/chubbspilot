#!/bin/bash
# Enable debug build mode - run this on device before rebooting

echo "Enabling debug build mode..."

# Create a file that persists the debug setting
echo "export OPENPILOT_DEBUG_BUILD=1" > /data/persist/comma/debug_build.sh

# Make it executable
chmod +x /data/persist/comma/debug_build.sh

# Add to launch_env.sh so it's sourced on boot
if ! grep -q "debug_build.sh" launch_env.sh; then
    echo "" >> launch_env.sh
    echo "# Enable debug build if requested" >> launch_env.sh
    echo "[ -f /data/persist/comma/debug_build.sh ] && source /data/persist/comma/debug_build.sh" >> launch_env.sh
fi

echo "Debug build mode enabled!"
echo "The device will show actual build output on next boot"
echo ""
echo "To disable debug mode later, run:"
echo "  rm /data/persist/comma/debug_build.sh"