#!/bin/bash
# Ensure proper Python environment for building on device

# Find available Python versions
if command -v python3.11 &> /dev/null; then
    export PYTHON=python3.11
    echo "Using Python 3.11"
elif command -v python3.10 &> /dev/null; then
    export PYTHON=python3.10
    echo "Using Python 3.10"
else
    export PYTHON=python3
    echo "Using default Python 3"
fi

# Check Python version
$PYTHON --version

# Ensure pip is available
$PYTHON -m pip --version || {
    echo "Installing pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | $PYTHON
}

# Install critical packages if missing
$PYTHON -c "import Cython" 2>/dev/null || {
    echo "Installing Cython..."
    $PYTHON -m pip install --no-cache-dir Cython==3.0.0
}

$PYTHON -c "import numpy" 2>/dev/null || {
    echo "Installing numpy..."
    $PYTHON -m pip install --no-cache-dir numpy
}

$PYTHON -c "import capnp" 2>/dev/null || {
    echo "Installing pycapnp..."
    $PYTHON -m pip install --no-cache-dir pycapnp==2.0.0
}

# Set up environment
export PYTHONPATH=/data/openpilot
export PATH=$PATH:/data/openpilot

echo "Python environment ready"