#!/bin/bash
# Quick test to verify boot UI builds correctly

echo "🔨 Testing Chauffeur Boot UI Build..."
echo "====================================="

# Test 1: Build terminal boot UI
echo -e "\n1️⃣  Building terminal boot UI..."
cd /data/openpilot
scons selfdrive/ui/terminal_boot/terminal_boot
if [ $? -eq 0 ]; then
    echo "✅ Terminal boot UI built successfully!"
else
    echo "❌ Terminal boot UI build failed!"
    exit 1
fi

# Test 2: Check executable exists
echo -e "\n2️⃣  Checking executable..."
if [ -f "selfdrive/ui/terminal_boot/terminal_boot" ]; then
    echo "✅ Terminal boot executable found!"
else
    echo "❌ Terminal boot executable not found!"
    exit 1
fi

# Test 3: Test Python wrapper
echo -e "\n3️⃣  Testing Python wrapper..."
python3 -c "
try:
    from openpilot.common.terminal_spinner import TerminalSpinner
    print('✅ Terminal spinner import successful!')
except ImportError as e:
    print(f'❌ Terminal spinner import failed: {e}')
    exit(1)
"

# Test 4: Test logo display
echo -e "\n4️⃣  Testing logo display..."
python3 selfdrive/frogpilot/assets/boot/test_logo.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Logo display test passed!"
else
    echo "❌ Logo display test failed!"
fi

# Test 5: Check error handler
echo -e "\n5️⃣  Testing error handler..."
python3 -c "
try:
    from openpilot.system.manager.error_handler import BootErrorHandler
    print('✅ Error handler import successful!')
except ImportError as e:
    print(f'❌ Error handler import failed: {e}')
"

echo -e "\n====================================="
echo "🎉 All boot UI tests completed!"
echo ""
echo "To see the boot UI in action:"
echo "  python3 common/terminal_spinner.py"
echo ""
echo "The frog is dead. Long live Chauffeur! 🔥"