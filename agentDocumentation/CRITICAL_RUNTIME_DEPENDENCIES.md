# Critical Runtime Dependencies

**Generated:** January 7, 2025  
**Based on:** Comprehensive import analysis of entire codebase

This document lists the most critical external Python packages that must be available at runtime to prevent ModuleNotFoundError crashes.

## High Priority Dependencies (Frequent Use)

These packages are used extensively throughout the codebase and will cause immediate boot failures if missing:

### Essential Scientific Computing
- **numpy** (290 usages) - Core numerical computing, used everywhere
- **torch** (42 usages) - Deep learning framework, used in ML models
- **cv2** (9 usages) - OpenCV for computer vision
- **PIL** (23 usages) - Python Imaging Library
- **sympy** (7 usages) - Symbolic mathematics
- **onnx** (13 usages) - Open Neural Network Exchange
- **onnxruntime** (7 usages) - ONNX runtime execution

### System & Hardware
- **psutil** (4 usages) - System and process utilities
- **zmq** (5 usages) - ZeroMQ messaging
- **capnp** (27 usages) - Cap'n Proto serialization
- **serial** (3 usages) - Serial port communication
- **usb1** (6 usages) - USB device access

### Web & Network
- **requests** (31 usages) - HTTP library
- **jinja2** (4 usages) - Template engine (used by concierge)
- **uvicorn** (2 usages) - ASGI server (used by concierge)

### Geometry & Spatial
- **shapely** (4 usages total) - Geometric operations (used by mapd)

### Development & Testing
- **pytest** (56 usages) - Testing framework
- **tqdm** (32 usages total) - Progress bars

## Boot-Critical Dependencies

These packages cause immediate boot failures if missing and have been added to our dependency management system:

### Currently Managed
1. **shapely** - Used by mapd_daemon for geometric calculations
2. **pydantic** - Used by concierge for data validation  
3. **fastapi** - Used by concierge web framework (not found in scan - may be conditional)
4. **uvicorn** - Used by concierge ASGI server
5. **jinja2** - Used by concierge templating

### Should Be Added
Based on the analysis, these should be added to the dependency management system:

1. **numpy** - Most critical, used in 290 files
2. **capnp** - Used in 27 files for core messaging
3. **requests** - Used in 31 files for HTTP operations
4. **cv2** (OpenCV) - Used in 9 files for vision processing
5. **zmq** - Used in 5 files for messaging
6. **PIL** - Used in 23 files for image processing
7. **psutil** - Used in 4 files for system monitoring

## Conditional Dependencies

These packages are used in specific contexts and may not be needed for basic operation:

- **torch** - Deep learning models (may be optional)
- **onnx/onnxruntime** - Model inference (may be optional)
- **matplotlib** - Plotting (development/debugging only)
- **pytest** - Testing only
- **tqdm** - Progress display (nice-to-have)

## Installation Priority

### Tier 1 (Critical - Must Install)
```bash
sudo pip3 install numpy capnp requests shapely pydantic uvicorn jinja2
```

### Tier 2 (Important - Should Install)  
```bash
sudo pip3 install opencv-python pillow pyzmq psutil pyserial
```

### Tier 3 (Optional - Can Install)
```bash
sudo pip3 install torch onnx onnxruntime matplotlib tqdm
```

## Implementation Status

Currently implemented in:
- `/data/openpilot/system/ensure_dependencies.py`
- `/data/openpilot/system/ensure_boot_dependencies.sh`
- `/data/openpilot/selfdrive/frogpilot/navigation/mapd_py/mapd_daemon_wrapper.py`
- `/data/openpilot/selfdrive/chauffeur/concierge/main_wrapper.py`

## Recommendations

1. **Expand ensure_dependencies.py** to include Tier 1 packages
2. **Create service-specific wrappers** for high-usage packages
3. **Add fallback installation methods** (apt-get) for critical packages
4. **Monitor boot logs** for additional missing dependencies
5. **Regular analysis** to catch new dependencies as code evolves