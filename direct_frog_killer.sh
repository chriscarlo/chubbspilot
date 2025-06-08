#!/bin/bash
# Direct approach - replace frog image with empty/black image

echo "🎯 DIRECT FROG ELIMINATION..."

cd /data/openpilot

# 1. Create a 1x1 black pixel PNG
echo "Creating black pixel image..."
python3 << 'EOF'
try:
    from PIL import Image
    img = Image.new('RGB', (1, 1), (0, 0, 0))
    img.save('/tmp/black.png')
    print("Black image created")
except:
    # Create using ImageMagick if available
    import subprocess
    try:
        subprocess.run(['convert', '-size', '1x1', 'xc:black', '/tmp/black.png'])
        print("Black image created with ImageMagick")
    except:
        print("Cannot create image - PIL and ImageMagick not available")
EOF

# 2. Replace the frog boot logo
if [ -f /tmp/black.png ]; then
    echo "Replacing frog boot logo..."
    cp selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png \
       selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png.original 2>/dev/null || true
    cp /tmp/black.png selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png
    echo "✅ Frog boot logo replaced with black image"
else
    echo "⚠️  Could not create replacement image"
fi

# 3. Find and disable any Plymouth theme using the frog
echo "Checking for Plymouth themes..."
if [ -d /usr/share/plymouth/themes ]; then
    find /usr/share/plymouth/themes -name "*frog*" -o -name "*pilot*" | while read theme; do
        echo "Found theme: $theme"
    done
fi

# 4. Replace spinner with text-only version
echo "Creating text-only spinner..."
cat > selfdrive/ui/spinner << 'EOF'
#!/bin/sh
echo "CHAUFFEUR AUTONOMOUS DRIVING SYSTEM"
echo "==================================="
echo "INITIALIZING..."
echo ""
# Just pass through any status messages
while read line; do
    echo "[*] $line"
done
EOF
chmod +x selfdrive/ui/spinner

echo ""
echo "✅ DIRECT FROG ELIMINATION COMPLETE!"
echo ""
echo "Changes made:"
echo "- Boot logo replaced with black pixel"
echo "- Spinner replaced with text-only version"
echo ""
echo "The frogs should be gone on next boot!"