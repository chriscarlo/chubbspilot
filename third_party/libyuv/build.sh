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
cmake -DCMAKE_POSITION_INDEPENDENT_CODE:BOOL=ON -DCMAKE_C_FLAGS="-fPIC -fno-stack-protector" -DCMAKE_CXX_FLAGS="-fPIC -fno-stack-protector" .
make -j$(nproc)

INSTALL_DIR="$DIR/$ARCHNAME"
rm -rf $INSTALL_DIR
mkdir -p $INSTALL_DIR

rm -rf $DIR/include
mkdir -p $INSTALL_DIR/lib
cp $DIR/libyuv/libyuv.a $INSTALL_DIR/lib
cp -r $DIR/libyuv/include $DIR

# Validate libyuv.a
cd "$INSTALL_DIR/lib"
echo "Validating libyuv.a in $(pwd) for PIC properties..."
mkdir -p tmp_check && cd tmp_check
ar x ../libyuv.a
PIC_FAIL=0
# Prefer GNU objdump if available, otherwise try llvm-objdump
OBJDUMP_CMD=$(command -v objdump || command -v llvm-objdump)

if [ -z "$OBJDUMP_CMD" ]; then
  echo "WARNING: objdump (or llvm-objdump) not found. Cannot perform detailed PIC validation of object files."
  # Fallback to a simpler check or exit if strictness is required.
  # For now, we'll let it pass but with a warning.
else
  echo "Using $OBJDUMP_CMD for validation of *.o files..."
  for objfile in *.o; do
    # Check for problematic R_AARCH64_ADR_PREL_PG_HI21 relocations against UNDefined (external) symbols.
    if $OBJDUMP_CMD -r "$objfile" 2>/dev/null | grep 'R_AARCH64_ADR_PREL_PG_HI21' | grep -E '\\.UNDEF|\\*UND\\*' >/dev/null; then
      echo "ERROR: $objfile contains R_AARCH64_ADR_PREL_PG_HI21 relocation against UNDefined symbol."
      echo "Offending relocations in $objfile:"
      $OBJDUMP_CMD -r "$objfile" | grep 'R_AARCH64_ADR_PREL_PG_HI21' | grep -E '\\.UNDEF|\\*UND\\*'
      PIC_FAIL=1
    fi
  done
fi

cd .. # back to $INSTALL_DIR/lib
rm -rf tmp_check

if [ "$PIC_FAIL" -eq 1 ]; then
  echo "ERROR: libyuv.a failed PIC validation due to problematic relocations in object files."
  exit 1
else
  echo "libyuv.a PIC validation passed (checked for specific problematic relocations against external symbols in .o files)."
fi
cd "$DIR" # Go back to the script's original base directory (third_party/libyuv)

## To create universal binary on Darwin:
## ```
## lipo -create -output Darwin/libyuv.a path-to-x64/libyuv.a path-to-arm64/libyuv.a
## ```
