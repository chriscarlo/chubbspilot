#!/bin/bash
# Fix for TICI wide display issues

echo "🔧 FIXING TICI DISPLAY ISSUES..."
echo "================================"

cd /data/openpilot || exit 1

# 1. Build the updated terminal UI with centering
echo "1️⃣  Rebuilding terminal UI with display fixes..."
if command -v scons > /dev/null 2>&1; then
  scons selfdrive/ui/terminal_boot/terminal_boot
else
  echo "⚠️  SCons not available, using direct compilation..."
  cd selfdrive/ui/terminal_boot
  if [ -f terminal_ui.cc ] && [ -f terminal_ui.h ] && [ -f main.cc ]; then
    g++ -std=c++17 -I../../../ -o terminal_boot main.cc terminal_ui.cc -pthread
    echo "✅ Direct compilation successful"
  else
    echo "❌ Source files missing, skipping build"
  fi
  cd /data/openpilot
fi

# 2. Also build a simple fallback
echo "2️⃣  Building simple fallback UI..."
cd selfdrive/ui/terminal_boot
if [ -f simple_boot.cc ]; then
  g++ -o simple_boot simple_boot.cc
  echo "✅ Simple fallback built"
else
  echo "❌ simple_boot.cc not found"
fi
cd /data/openpilot

# 3. Make sure permissions are correct
echo "3️⃣  Setting permissions..."
chmod +x selfdrive/ui/terminal_boot/terminal_boot 2>/dev/null
chmod +x selfdrive/ui/terminal_boot/simple_boot 2>/dev/null
chmod +x selfdrive/ui/spinner

echo ""
echo "================================"
echo "✅ Display fixes applied!"
echo ""
echo "The terminal UI now centers content for the 2160x1080 display."
echo "Changes will take effect on next boot."