#!/usr/bin/env python3
"""
Check for missing dependencies during boot and log them.
This helps diagnose boot hangs without blocking the boot process.
"""
import sys
import time
from pathlib import Path

def check_imports():
    """Check critical imports and log failures."""
    print("[BOOT_CHECK] Checking critical imports...")
    
    critical_imports = [
        # Core system
        ("capnp", "pycapnp - messaging system"),
        ("zmq", "pyzmq - messaging transport"),
        ("numpy", "numpy - numerical computing"),
        ("cv2", "opencv-python - vision processing"),
        
        # Control system
        ("casadi", "casadi - MPC solver"),
        ("osqp", "osqp - optimization solver"),
        ("cvxpy", "cvxpy - convex optimization"),
        ("filterpy", "filterpy - Kalman filters"),
        
        # Hardware/sensors
        ("libusb1", "libusb1 - USB communication"),
        ("smbus2", "smbus2 - I2C communication"),
        
        # FrogPilot specific
        ("transforms3d", "transforms3d - 3D transformations"),
        ("polyline", "polyline - map data encoding"),
        ("websocket", "websocket-client - fleet manager"),
        ("pydantic", "pydantic - data validation"),
        
        # UI/Graphics
        ("OpenGL", "PyOpenGL - graphics"),
        ("pygame", "pygame - audio/graphics"),
        
        # Utilities
        ("setproctitle", "setproctitle - process naming"),
        ("psutil", "psutil - system monitoring"),
        ("requests", "requests - HTTP client"),
        ("sentry_sdk", "sentry-sdk - error reporting"),
    ]
    
    failed_imports = []
    
    for module_name, description in critical_imports:
        try:
            __import__(module_name)
            print(f"[BOOT_CHECK] ✓ {module_name}")
        except ImportError as e:
            failed_imports.append((module_name, description, str(e)))
            print(f"[BOOT_CHECK] ✗ {module_name} - {description}")
            print(f"[BOOT_CHECK]   Error: {e}")
    
    # Write results to a file for later inspection
    result_file = Path("/tmp/boot_dependency_check.txt")
    with open(result_file, "w") as f:
        f.write(f"Boot dependency check at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        
        if failed_imports:
            f.write("MISSING DEPENDENCIES:\n")
            for module, desc, error in failed_imports:
                f.write(f"\n{module} ({desc}):\n  {error}\n")
            
            f.write("\n" + "="*60 + "\n")
            f.write("To fix, run after SSH access:\n")
            f.write("python3 -m pip install " + " ".join(m[0] for m in failed_imports) + "\n")
        else:
            f.write("All dependencies OK!\n")
    
    print(f"[BOOT_CHECK] Results written to {result_file}")
    return len(failed_imports) == 0

def check_system_libs():
    """Check for required system libraries."""
    print("[BOOT_CHECK] Checking system libraries...")
    
    import subprocess
    libs_to_check = [
        "libzmq",
        "libcapnp", 
        "libusb-1.0",
        "libGL",
        "libGLES",
    ]
    
    missing_libs = []
    for lib in libs_to_check:
        try:
            result = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True)
            if lib not in result.stdout:
                missing_libs.append(lib)
                print(f"[BOOT_CHECK] ✗ {lib} not found")
            else:
                print(f"[BOOT_CHECK] ✓ {lib}")
        except Exception as e:
            print(f"[BOOT_CHECK] Could not check {lib}: {e}")
    
    return missing_libs

if __name__ == "__main__":
    print("[BOOT_CHECK] Starting dependency check...")
    
    # Don't block boot - just check and log
    try:
        imports_ok = check_imports()
        missing_libs = check_system_libs()
        
        if not imports_ok or missing_libs:
            print("[BOOT_CHECK] WARNING: Missing dependencies detected!")
            print("[BOOT_CHECK] Check /tmp/boot_dependency_check.txt for details")
            sys.exit(1)  # Non-zero exit but don't crash
        else:
            print("[BOOT_CHECK] All dependencies present")
            sys.exit(0)
    except Exception as e:
        print(f"[BOOT_CHECK] Check failed with error: {e}")
        sys.exit(2)