# TICI Build Fixes

## libyuv Missing Library Error

**Error**: `/usr/bin/ld: cannot find -lyuv`

**Root Cause**: The prebuilt libyuv library for larch64 architecture is missing from the repository.

**Solution**: Build libyuv directly on the TICI device:

```bash
# On the TICI device:
cd /data/openpilot/third_party/libyuv
chmod +x build_tici.sh
./build_tici.sh
```

This will:
1. Clone the libyuv source code
2. Build it with appropriate TICI/cortex-a57 optimizations
3. Install the library to `third_party/libyuv/larch64/lib/libyuv.a`

## libgcc_s.so.1 Incompatibility Warning

**Error**: `/usr/bin/ld: skipping incompatible /usr/lib/libgcc_s.so.1 when searching for libgcc_s.so.1`

**Status**: This is a warning, not an error. The build system has been updated to include proper AGNOS library paths:
- `/lib/aarch64-linux-gnu`
- `/usr/lib/gcc/aarch64-linux-gnu/9`

The linker will find the correct libgcc_s.so.1 in these paths and link successfully.

**Note**: If this becomes an actual error (not just a warning), verify that the correct library exists:
```bash
ls -la /lib/aarch64-linux-gnu/libgcc_s.so.1
ls -la /usr/lib/gcc/aarch64-linux-gnu/9/libgcc_s.so
```