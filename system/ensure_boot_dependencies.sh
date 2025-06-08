#!/bin/bash
# This script ensures critical dependencies are installed at boot time
# It should be called very early in the boot process

echo "=== Checking boot dependencies ==="

# Check if we're on TICI
if [ -f /TICI ]; then
    echo "Running on TICI device"
    
    # Check if shapely is available
    python3 -c "import shapely" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "shapely not found, attempting to install..."
        
        # Try pip3 first
        sudo pip3 install shapely 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "Successfully installed shapely with pip3"
        else
            # Try python3 -m pip
            sudo python3 -m pip install shapely 2>/dev/null
            if [ $? -eq 0 ]; then
                echo "Successfully installed shapely with python3 -m pip"
            else
                # Try apt-get as last resort
                echo "Trying apt-get install..."
                sudo apt-get update 2>/dev/null
                sudo apt-get install -y python3-shapely 2>/dev/null
                if [ $? -eq 0 ]; then
                    echo "Successfully installed python3-shapely via apt"
                else
                    echo "WARNING: Failed to install shapely"
                fi
            fi
        fi
    else
        echo "shapely is already installed"
    fi
else
    echo "Not running on TICI device, skipping dependency installation"
fi

echo "=== Boot dependency check complete ==="