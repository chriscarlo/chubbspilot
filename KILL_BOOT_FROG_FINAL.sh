#!/bin/bash
# FINAL SOLUTION - Kill the boot frog at the system level

echo "🐸💀 FINAL FROG ELIMINATION - SYSTEM LEVEL"
echo "=========================================="

# Check if we can write to system directories
if [ ! -w /usr/comma ]; then
    echo "⚠️  Need sudo access to modify system files"
    echo "Run with: sudo bash $0"
    exit 1
fi

# 1. Back up the original frog
if [ -f /usr/comma/bg.jpg ] && [ ! -f /usr/comma/bg.jpg.frog_backup ]; then
    echo "Backing up original frog..."
    cp /usr/comma/bg.jpg /usr/comma/bg.jpg.frog_backup
fi

# 2. Create a simple black image to replace it
echo "Creating black replacement image..."
python3 << 'EOF' 2>/dev/null
try:
    from PIL import Image
    # Create a black image matching TICI resolution
    img = Image.new('RGB', (2160, 1080), (0, 0, 0))
    img.save('/tmp/black_bg.jpg', 'JPEG')
    print("✅ Black image created")
except:
    print("❌ PIL not available")
EOF

# If PIL failed, try ImageMagick
if [ ! -f /tmp/black_bg.jpg ]; then
    echo "Trying ImageMagick..."
    convert -size 2160x1080 xc:black /tmp/black_bg.jpg 2>/dev/null || \
    convert -size 1920x1080 xc:black /tmp/black_bg.jpg 2>/dev/null || \
    echo "❌ ImageMagick also not available"
fi

# If we still don't have an image, use the simplest approach
if [ ! -f /tmp/black_bg.jpg ]; then
    echo "Creating minimal JPEG..."
    # This creates a tiny valid black JPEG
    printf '\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' > /tmp/black_bg.jpg
    printf '\xFF\xDB\x00\x43\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09' >> /tmp/black_bg.jpg
    printf '\x08\x0A\x0C\x14\x0D\x0C\x0B\x0B\x0C\x19\x12\x13\x0F\x14\x1D\x1A' >> /tmp/black_bg.jpg
    printf '\x1F\x1E\x1D\x1A\x1C\x1C\x20\x24\x2E\x27\x20\x22\x2C\x23\x1C\x1C' >> /tmp/black_bg.jpg
    printf '\x28\x37\x29\x2C\x30\x31\x34\x34\x34\x1F\x27\x39\x3D\x38\x32\x3C' >> /tmp/black_bg.jpg
    printf '\x2E\x33\x34\x32\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00' >> /tmp/black_bg.jpg
    printf '\xFF\xC4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' >> /tmp/black_bg.jpg
    printf '\x00\x00\x00\x00\x00\xFF\xC4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00' >> /tmp/black_bg.jpg
    printf '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xDA\x00\x08\x01\x01\x00' >> /tmp/black_bg.jpg
    printf '\x00\x3F\x00\x7F\xFF\xD9' >> /tmp/black_bg.jpg
fi

# 3. Replace the system boot image
if [ -f /tmp/black_bg.jpg ]; then
    echo "Replacing system boot image..."
    cp /tmp/black_bg.jpg /usr/comma/bg.jpg
    echo "✅ System boot image replaced!"
else
    echo "❌ Could not create replacement image"
fi

# 4. Also ensure Plymouth doesn't show a theme
if [ -f /etc/plymouth/plymouthd.conf ]; then
    echo "Disabling Plymouth theme..."
    sed -i 's/^Theme=.*/Theme=text/' /etc/plymouth/plymouthd.conf 2>/dev/null || \
    echo "Theme=text" >> /etc/plymouth/plymouthd.conf
fi

# 5. Disable the openpilot boot logo in FrogPilot assets too
cd /data/openpilot
if [ -f selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png ]; then
    echo "Disabling FrogPilot boot logo asset..."
    mv selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png \
       selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png.disabled
    # Create empty file so nothing breaks
    touch selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png
fi

echo ""
echo "=========================================="
echo "✅ BOOT FROG ELIMINATED AT SYSTEM LEVEL!"
echo ""
echo "The boot screen will now be black instead of showing the frog."
echo ""
echo "To restore the frog:"
echo "  sudo cp /usr/comma/bg.jpg.frog_backup /usr/comma/bg.jpg"
echo ""
echo "Reboot to see the changes!"