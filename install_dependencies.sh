#!/bin/bash
# Install missing dependencies for FrogPilot/OpenPilot on TICI
# This script should be run after cloning but before building

set -e

echo "[DEPS] Checking and installing dependencies for TICI..."

# Function to check if a Python package is installed
check_python_package() {
    python3 -c "import $1" 2>/dev/null && echo "[DEPS] ✓ $1 installed" || return 1
}

# Function to install Python packages
install_python_packages() {
    echo "[DEPS] Installing missing Python packages..."
    
    # Core packages that might be missing
    PACKAGES=(
        "casadi"
        "filterpy"
        "osqp"
        "cvxpy"
        "transforms3d"
        "scikit-image"
        "aenum"
        "lru-dict"
        "websocket-client"
        "polyline"
        "pycryptodome"
        "setproctitle"
        "libusb1"
        "zstandard"
        "pydantic"
        "fastapi"
        "uvicorn"
        "aiofiles"
        "websockets"
        "jinja2"
        "python-multipart"
    )
    
    # Check each package and build list of missing ones
    MISSING=""
    for pkg in "${PACKAGES[@]}"; do
        if ! check_python_package "$pkg"; then
            MISSING="$MISSING $pkg"
        fi
    done
    
    if [ -n "$MISSING" ]; then
        echo "[DEPS] Missing packages:$MISSING"
        echo "[DEPS] Installing via pip..."
        python3 -m pip install --no-cache-dir $MISSING || {
            echo "[DEPS] WARNING: Some packages failed to install"
            echo "[DEPS] Trying individual installs..."
            for pkg in $MISSING; do
                echo "[DEPS] Installing $pkg..."
                python3 -m pip install --no-cache-dir "$pkg" || echo "[DEPS] WARNING: Failed to install $pkg"
            done
        }
    else
        echo "[DEPS] All Python packages already installed!"
    fi
}

# Function to check system dependencies
check_system_deps() {
    echo "[DEPS] Checking system dependencies..."
    
    # These should mostly be present on TICI, but let's verify
    MISSING_SYS=""
    
    # Check for critical libraries
    ldconfig -p | grep -q libzmq || MISSING_SYS="$MISSING_SYS libzmq"
    ldconfig -p | grep -q libcapnp || MISSING_SYS="$MISSING_SYS libcapnp"
    
    if [ -n "$MISSING_SYS" ]; then
        echo "[DEPS] WARNING: Missing system libraries:$MISSING_SYS"
        echo "[DEPS] These may need to be installed via the AGNOS package manager"
    fi
}

# Main execution
main() {
    # Ensure pip is up to date
    echo "[DEPS] Updating pip..."
    python3 -m pip install --upgrade pip 2>/dev/null || echo "[DEPS] WARNING: Could not upgrade pip"
    
    # Check and install Python packages
    install_python_packages
    
    # Check system dependencies
    check_system_deps
    
    # Special handling for pycapnp which often has issues
    if ! check_python_package "capnp"; then
        echo "[DEPS] Special handling for pycapnp..."
        # Try pre-built wheel first
        python3 -m pip install --no-cache-dir pycapnp==2.0.0 || {
            echo "[DEPS] Pre-built pycapnp failed, trying source build..."
            python3 -m pip install --no-cache-dir --no-binary pycapnp pycapnp || {
                echo "[DEPS] ERROR: Could not install pycapnp - this may cause issues"
            }
        }
    fi
    
    echo "[DEPS] Dependency check complete!"
}

# Run main function
main