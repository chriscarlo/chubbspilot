#!/bin/bash
# Fix for TICI wide display issues

echo "🔧 FIXING TICI DISPLAY ISSUES..."
echo "================================"

cd /data/openpilot || exit 1

# 1. Build the updated terminal UI with centering
echo "1️⃣  Rebuilding terminal UI with display fixes..."
scons selfdrive/ui/terminal_boot/terminal_boot

# 2. Also build a simple fallback
echo "2️⃣  Building simple fallback UI..."
cd selfdrive/ui/terminal_boot
g++ -o simple_boot simple_boot.cc

# 3. Test which one works better
echo "3️⃣  Testing displays..."
echo ""
echo "Testing complex UI:"
echo "test" | ./terminal_boot 2>&1 | head -20
echo ""
echo "Testing simple UI:"
echo "test" | ./simple_boot 2>&1 | head -20

echo ""
echo "================================"
echo "✅ Display fixes applied!"
echo ""
echo "The terminal UI now centers content for the 2160x1080 display."
echo "If you still see rendering issues, try using simple_boot instead."
echo ""
echo "To use simple boot as fallback, edit spinner script:"
echo "  exec \"\$DIR/terminal_boot/simple_boot\" \"\$@\""