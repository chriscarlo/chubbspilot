#!/bin/bash
# Auto-fix TICI display at startup
# This runs early in the boot process to ensure display fixes are applied

LOG_FILE="/tmp/auto_display_fix.log"

{
  echo "=== AUTO DISPLAY FIX STARTUP ==="
  echo "Started at: $(date)"
  echo "================================"

  # Only run on TICI
  if [ ! -f /TICI ]; then
    echo "Not a TICI device, skipping display fixes"
    exit 0
  fi

  # Check if the fix script exists
  if [ ! -f "/data/openpilot/fix_tici_display.sh" ]; then
    echo "Display fix script not found, skipping"
    exit 0
  fi

  # Wait a moment for filesystem to be ready
  sleep 5

  # Run the display fix
  echo "Running TICI display fixes..."
  cd /data/openpilot
  /bin/bash fix_tici_display.sh

  echo "Display fix completed at: $(date)"
  echo "==================================="
} >> "$LOG_FILE" 2>&1

# Also create a parameter so the system knows the fix was attempted
if [ -d "/data/params" ]; then
  echo "1" > /data/params/d/TICIDisplayFixApplied
fi