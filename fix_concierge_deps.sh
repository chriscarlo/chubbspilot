#!/bin/bash
# Fix Concierge dependencies on TICI

echo "[CONCIERGE] Checking Python environment..."

# Get Python path
PYTHON_PATH=$(which python3)
echo "[CONCIERGE] Python: $PYTHON_PATH"

# Check if we're on TICI
if [ -f /TICI ]; then
    echo "[CONCIERGE] Running on TICI device"
    
    # Find site-packages directory
    SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
    echo "[CONCIERGE] Site packages: $SITE_PACKAGES"
    
    # Check if dependencies exist
    echo "[CONCIERGE] Checking for dependencies..."
    for dep in fastapi uvicorn pydantic jinja2; do
        if python3 -c "import $dep" 2>/dev/null; then
            echo "[CONCIERGE] ✓ $dep is available"
        else
            echo "[CONCIERGE] ✗ $dep is MISSING"
            
            # Try to find it in the file system
            find /data/openpilot -name "$dep" -type d 2>/dev/null | head -5
        fi
    done
    
    # Check Poetry environment
    if [ -d /data/openpilot/.venv ]; then
        echo "[CONCIERGE] Found Poetry venv at /data/openpilot/.venv"
        
        # Activate it and check
        source /data/openpilot/.venv/bin/activate
        echo "[CONCIERGE] Activated venv, checking again..."
        
        for dep in fastapi uvicorn pydantic jinja2; do
            if python3 -c "import $dep" 2>/dev/null; then
                echo "[CONCIERGE] ✓ $dep is available in venv"
            else
                echo "[CONCIERGE] ✗ $dep is MISSING from venv"
            fi
        done
    fi
    
    # Check PYTHONPATH
    echo "[CONCIERGE] PYTHONPATH: $PYTHONPATH"
    
    # Suggest fix
    echo ""
    echo "[CONCIERGE] To fix missing dependencies:"
    echo "1. SSH into your device"
    echo "2. Run: cd /data/openpilot"
    echo "3. Run: poetry install"
    echo "4. Or if poetry not available: pip3 install fastapi uvicorn pydantic"
    
else
    echo "[CONCIERGE] Not on TICI - running in development environment"
fi