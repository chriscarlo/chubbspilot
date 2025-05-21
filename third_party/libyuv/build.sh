#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"

ARCHNAME=$(uname -m)
if [ -f /TICI ]; then
  ARCHNAME="larch64"
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  ARCHNAME="Darwin"
fi

cd $DIR
if [ ! -d libyuv ]; then
  git clone --single-branch https://chromium.googlesource.com/libyuv/libyuv
fi

cd libyuv
git checkout 4a14cb2e81235ecd656e799aecaaf139db8ce4a2

# Remove any existing built library to force a clean build
rm -f $DIR/$ARCHNAME/lib/libyuv.a

# Ensure static library is built with -fPIC for use in shared objects (required for AArch64 and most modern Linux systems)
export CFLAGS="-fPIC $CFLAGS"
export CXXFLAGS="-fPIC $CXXFLAGS"

# build
cmake -DCMAKE_POSITION_INDEPENDENT_CODE=ON .
make -j$(nproc)

INSTALL_DIR="$DIR/$ARCHNAME"
rm -rf $INSTALL_DIR
mkdir -p $INSTALL_DIR

rm -rf $DIR/include
mkdir -p $INSTALL_DIR/lib
cp $DIR/libyuv/libyuv.a $INSTALL_DIR/lib
cp -r $DIR/libyuv/include $DIR

# Validate that libyuv.a contains PIC object files
cd $INSTALL_DIR/lib
mkdir -p tmp_check && cd tmp_check
ar x ../libyuv.a > /dev/null 2>&1
# Check the first object file for 'Flags' containing 'PIC'
OBJFILE=$(ls | head -n1)
if ! readelf -A "$OBJFILE" 2>/dev/null | grep -q 'Flags:.*: PIC'; then
  echo "\nERROR: libyuv.a was not built with -fPIC. This will cause linker errors on AArch64.\n"
  exit 1
fi
cd ../..
rm -rf lib/tmp_check

## To create universal binary on Darwin:
## ```
## lipo -create -output Darwin/libyuv.a path-to-x64/libyuv.a path-to-arm64/libyuv.a
## ```
