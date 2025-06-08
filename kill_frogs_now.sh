#!/bin/bash
# Nuclear option - completely disable all boot graphics

echo "🐸💀 KILLING ALL FROGS..."

cd /data/openpilot

# 1. Create a dummy spinner that does nothing
cat > selfdrive/ui/spinner << 'EOF'
#!/bin/sh
# Dummy spinner - just pass through stdin to stdout
cat
EOF
chmod +x selfdrive/ui/spinner

# 2. Remove/rename all spinner binaries
cd selfdrive/ui
for file in _spinner qt/spinner_larch64 terminal_boot/terminal_boot; do
  if [ -f "$file" ]; then
    mv "$file" "${file}.disabled" 2>/dev/null || true
  fi
done

# 3. Remove the frog boot logo
cd /data/openpilot
if [ -f selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png ]; then
  mv selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png \
     selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png.disabled
fi

# 4. Create empty replacement
touch selfdrive/frogpilot/assets/other_images/frogpilot_boot_logo.png

echo "✅ ALL FROGS ELIMINATED!"
echo ""
echo "Boot graphics completely disabled. You'll see standard text output only."
echo "To restore: cd /data/openpilot && git checkout selfdrive/ui/spinner"