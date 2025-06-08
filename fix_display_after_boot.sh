#!/bin/bash
# Post-boot display fix for TICI
# This script can be run manually after the system boots

echo "🔧 POST-BOOT TICI DISPLAY FIX"
echo "============================="

cd /data/openpilot || exit 1

# Check if we're on TICI
if [ ! -f /TICI ]; then
  echo "❌ This script is for TICI devices only"
  exit 1
fi

echo "🔍 Checking current display issues..."

# Check if terminal_boot exists and works
if [ -f selfdrive/ui/terminal_boot/terminal_boot ]; then
  echo "✅ Terminal boot UI found"
  
  # Test the UI quickly
  echo "🧪 Testing terminal UI..."
  echo "test" | timeout 5s ./selfdrive/ui/terminal_boot/terminal_boot > /tmp/ui_test.log 2>&1
  
  if [ $? -eq 0 ]; then
    echo "✅ Terminal UI responds correctly"
  else
    echo "⚠️  Terminal UI may have issues, checking logs..."
    head -10 /tmp/ui_test.log
  fi
else
  echo "❌ Terminal boot UI missing, rebuilding..."
  /bin/bash fix_tici_display.sh
fi

# Check the spinner script
echo "🔍 Checking spinner configuration..."
if grep -q "Running TICI display fixes" selfdrive/ui/spinner; then
  echo "✅ Spinner script has auto-fix enabled"
else
  echo "⚠️  Spinner script needs updating"
fi

# Show current screen resolution if possible
echo "🖥️  Display information:"
if command -v xrandr > /dev/null 2>&1; then
  xrandr | grep " connected" | head -1
elif [ -f /sys/class/graphics/fb0/virtual_size ]; then
  echo "Framebuffer size: $(cat /sys/class/graphics/fb0/virtual_size)"
else
  echo "Display size: Assumed 2160x1080 (TICI standard)"
fi

echo ""
echo "============================="
echo "✅ Post-boot check complete!"
echo ""
echo "If you're still seeing display issues:"
echo "1. Reboot the device to trigger auto-fix"
echo "2. Check /tmp/tici_display_fix.log for boot-time fix results"
echo "3. Try the simple fallback UI if needed"
echo ""
echo "To manually switch to simple UI:"
echo "  cd /data/openpilot/selfdrive/ui/terminal_boot"
echo "  cp simple_boot terminal_boot"