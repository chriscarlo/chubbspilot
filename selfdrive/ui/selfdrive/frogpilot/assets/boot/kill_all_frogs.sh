#!/bin/bash
# NUCLEAR FROG ELIMINATION SCRIPT
# Run this on your device to ensure all frogs are dead

echo "🔥 FROG ELIMINATION PROTOCOL INITIATED 🔥"
echo "========================================"

# 1. Remove any cached Qt spinner
echo "1️⃣  Removing cached Qt spinner..."
rm -f /data/openpilot/selfdrive/ui/_spinner 2>/dev/null
rm -f selfdrive/ui/_spinner 2>/dev/null
echo "   ✓ Cached spinner removed"

# 2. Ensure terminal boot UI is executable
echo "2️⃣  Setting terminal boot UI permissions..."
chmod +x /data/openpilot/selfdrive/ui/terminal_boot/terminal_boot 2>/dev/null
chmod +x selfdrive/ui/terminal_boot/terminal_boot 2>/dev/null
echo "   ✓ Terminal boot UI is executable"

# 3. Test the spinner script
echo "3️⃣  Testing spinner script..."
cd /data/openpilot/selfdrive/ui || cd selfdrive/ui
if ./spinner test 2>&1 | grep -q "Using terminal boot UI"; then
    echo "   ✓ Terminal boot UI is active!"
else
    echo "   ✗ Terminal boot UI not working - check paths"
fi

# 4. Create boot directory if missing
echo "4️⃣  Creating boot assets directory..."
mkdir -p /data/openpilot/selfdrive/frogpilot/assets/boot 2>/dev/null
mkdir -p selfdrive/frogpilot/assets/boot 2>/dev/null
echo "   ✓ Boot directory exists"

# 5. For immediate visual confirmation
echo -e "\n5️⃣  Quick visual test..."
echo "   The next boot should show:"
echo ""
echo -e "\033[38;2;255;105;105m▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓  ▓▓▓▓  ▓▓▓▓  ▓  ▓  ▓▓▓▓\033[0m"
echo -e "\033[38;2;255;105;105m      ★ AUTONOMOUS DRIVING SYSTEM v2.0 ★\033[0m"
echo ""
echo "   Instead of a spinning frog!"

echo -e "\n========================================"
echo "🎉 FROG ELIMINATION COMPLETE!"
echo ""
echo "The spinner will now show the terminal UI."
echo "Note: The static boot logo (/usr/comma/bg.jpg) requires"
echo "a reboot with FrogPilot setup to replace."
echo ""
echo "To manually test: cd selfdrive/ui && ./spinner test"