#!/usr/bin/env bash
# Build script for libyuv on TICI device
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"

# Ensure we're on TICI
if [ ! -f /TICI ]; then
  echo "This script must be run on a TICI device"
  exit 1
fi

cd $DIR

# Clone libyuv if not present
if [ ! -d libyuv ]; then
  git clone --single-branch https://chromium.googlesource.com/libyuv/libyuv
fi

cd libyuv
git checkout 4a14cb2e81235ecd656e799aecaaf139db8ce4a2

# Build with appropriate flags for TICI
cmake . -DCMAKE_C_FLAGS="-mcpu=cortex-a57" -DCMAKE_CXX_FLAGS="-mcpu=cortex-a57"
make -j$(nproc)

# Install to larch64 directory
INSTALL_DIR="$DIR/larch64"
rm -rf $INSTALL_DIR
mkdir -p $INSTALL_DIR/lib

cp libyuv.a $INSTALL_DIR/lib/
echo "libyuv built successfully for TICI/larch64"