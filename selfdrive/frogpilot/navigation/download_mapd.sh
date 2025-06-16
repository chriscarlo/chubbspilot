#!/bin/bash
# Download pre-built mapd binary from GitHub releases
# This is an alternative to building from source

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_BINARY="$SCRIPT_DIR/mapd"

# mapd release info
MAPD_VERSION="v1.10.0"  # Update this to latest version as needed
MAPD_REPO="pfeiferj/mapd"
RELEASE_URL="https://github.com/$MAPD_REPO/releases/download/$MAPD_VERSION"

echo "Downloading mapd binary version $MAPD_VERSION..."

# Determine architecture
ARCH=$(uname -m)
case "$ARCH" in
    aarch64|arm64)
        BINARY_NAME="mapd"  # The actual binary is just named 'mapd' for ARM64
        ;;
    x86_64)
        # For x86_64 development, use the stub
        echo "Note: x86_64 detected - using development stub"
        cp "$SCRIPT_DIR/mapd_stub.py" "$OUTPUT_BINARY"
        chmod +x "$OUTPUT_BINARY"
        echo "Development stub installed successfully"
        exit 0
        ;;
    *)
        echo "Error: Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Download binary
DOWNLOAD_URL="$RELEASE_URL/$BINARY_NAME"
echo "Downloading from: $DOWNLOAD_URL"

if command -v wget &> /dev/null; then
    wget --timeout=30 --tries=2 -O "$OUTPUT_BINARY" "$DOWNLOAD_URL"
elif command -v curl &> /dev/null; then
    curl --connect-timeout 10 --max-time 30 -L -o "$OUTPUT_BINARY" "$DOWNLOAD_URL"
else
    echo "Error: Neither wget nor curl is available"
    exit 1
fi

# Make binary executable
chmod +x "$OUTPUT_BINARY"

echo "mapd binary downloaded successfully to: $OUTPUT_BINARY"
echo "File size: $(du -h "$OUTPUT_BINARY" | cut -f1)"

# Verify it's a valid binary
if command -v file &> /dev/null; then
    echo "Binary info: $(file "$OUTPUT_BINARY")"
fi

echo ""
echo "To test the binary, run:"
echo "  $OUTPUT_BINARY --help"