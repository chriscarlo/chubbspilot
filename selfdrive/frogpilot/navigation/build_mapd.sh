#!/bin/bash
# Build script for mapd binary
# This builds the mapd Go binary for the comma device (ARM64)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Use relative path to mapd_fork from navigation directory
MAPD_SOURCE_DIR="$(cd "$SCRIPT_DIR/../../../mapd_fork" 2>/dev/null && pwd)" || MAPD_SOURCE_DIR="/data/openpilot/mapd_fork"
OUTPUT_BINARY="$SCRIPT_DIR/mapd"

echo "Building mapd binary..."

# Check if source directory exists
if [ ! -d "$MAPD_SOURCE_DIR" ]; then
    echo "Error: mapd source directory not found at: $MAPD_SOURCE_DIR"
    echo "Please ensure mapd_fork repository is cloned to the openpilot directory."
    exit 1
fi

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "Error: Go is not installed. Please install Go first."
    exit 1
fi

# Navigate to mapd source directory
cd "$MAPD_SOURCE_DIR"

# Build for ARM64 (comma device architecture)
echo "Building for ARM64..."
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o "$OUTPUT_BINARY" .

# Make binary executable
chmod +x "$OUTPUT_BINARY"

echo "mapd binary built successfully at: $OUTPUT_BINARY"
echo "File size: $(du -h "$OUTPUT_BINARY" | cut -f1)"

# Verify it's an ARM64 binary
if command -v file &> /dev/null; then
    echo "Binary info: $(file "$OUTPUT_BINARY")"
fi