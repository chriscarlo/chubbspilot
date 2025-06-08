#!/bin/bash
# Force simple boot UI immediately

echo "🔧 FORCING SIMPLE BOOT UI..."

cd /data/openpilot

# 1. Build the minimal boot UI
echo "Building minimal boot UI..."
cd selfdrive/ui/terminal_boot
g++ -o minimal_boot minimal_boot.cc

# 2. Replace terminal_boot with minimal version
echo "Replacing terminal_boot with minimal version..."
if [ -f terminal_boot ]; then
  mv terminal_boot terminal_boot.backup
fi
cp minimal_boot terminal_boot

# 3. Also replace the Qt spinner completely
cd ..
if [ -f _spinner ]; then
  mv _spinner _spinner.backup
fi
if [ -f qt/spinner_larch64 ]; then
  mv qt/spinner_larch64 qt/spinner_larch64.backup
fi

# 4. Make spinner script use our minimal boot directly
cat > spinner << 'EOF'
#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/terminal_boot/minimal_boot" "$@"
EOF
chmod +x spinner

echo "✅ Simple boot UI forced!"
echo ""
echo "The boot screen will now show a simple centered CHAUFFEUR logo."
echo "This should work on any TICI display without rendering issues."
echo ""
echo "To restore original: cd /data/openpilot && git checkout selfdrive/ui/spinner"