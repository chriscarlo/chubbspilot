#!/bin/bash
# This script ensures critical dependencies are installed at boot time
# It should be called very early in the boot process

echo "=== Checking boot dependencies ==="

# Check if we're on TICI
if [ -f /TICI ]; then
    echo "Running on TICI device"
    
    # Check and install required Python packages
    PACKAGES=("shapely" "pydantic" "fastapi" "uvicorn" "jinja2")
    
    for package in "${PACKAGES[@]}"; do
        python3 -c "import $package" 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "$package not found, attempting to install..."
            
            # Try pip3 first
            sudo pip3 install $package 2>/dev/null
            if [ $? -eq 0 ]; then
                echo "Successfully installed $package with pip3"
            else
                # Try python3 -m pip
                sudo python3 -m pip install $package 2>/dev/null
                if [ $? -eq 0 ]; then
                    echo "Successfully installed $package with python3 -m pip"
                else
                    # Try apt-get as last resort for known packages
                    if [ "$package" = "shapely" ]; then
                        echo "Trying apt-get install python3-shapely..."
                        sudo apt-get update 2>/dev/null
                        sudo apt-get install -y python3-shapely 2>/dev/null
                        if [ $? -eq 0 ]; then
                            echo "Successfully installed python3-shapely via apt"
                        else
                            echo "WARNING: Failed to install $package"
                        fi
                    else
                        echo "WARNING: Failed to install $package"
                    fi
                fi
            fi
        else
            echo "$package is already installed"
        fi
    done
else
    echo "Not running on TICI device, skipping dependency installation"
fi

echo "=== Boot dependency check complete ==="