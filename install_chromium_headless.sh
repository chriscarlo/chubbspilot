#!/bin/bash
# Install chromium headless for Ubuntu 24.04

echo "Installing chromium-browser snap package..."
sudo snap install chromium

# Alternative: Install via apt if snap fails
# sudo apt-get update
# sudo apt-get install -y chromium-browser chromium-chromedriver

echo "Checking installation..."
which chromium || which chromium-browser || echo "Installation may have failed"

# Create a test script
cat > /data/openpilot/test_chromium.py << 'EOF'
#!/usr/bin/env python3
import subprocess
import sys

try:
    # Try snap version first
    result = subprocess.run(['/snap/bin/chromium', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Chromium installed (snap): {result.stdout.strip()}")
        sys.exit(0)
except:
    pass

try:
    # Try system version
    result = subprocess.run(['chromium-browser', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Chromium installed: {result.stdout.strip()}")
        sys.exit(0)
except:
    pass

print("Chromium not found. Please install manually:")
print("  sudo snap install chromium")
print("  OR")
print("  sudo apt-get install chromium-browser")
sys.exit(1)
EOF

chmod +x /data/openpilot/test_chromium.py
python3 /data/openpilot/test_chromium.py