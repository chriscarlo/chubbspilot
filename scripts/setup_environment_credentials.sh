#!/bin/bash
# Environment-specific credential setup script
# This script sets up the correct sudo password based on hostname

HOSTNAME=$(hostname)
HOME_PC_HOSTNAME="DESKTOP-BRS4719"
WORK_PC_HOSTNAME=""  # To be filled when we identify work PC hostname

# Create .environment_info file in openpilot directory for persistence
ENV_INFO_FILE="/data/openpilot/.environment_info"

# Function to setup credentials
setup_credentials() {
    if [ "$HOSTNAME" = "$HOME_PC_HOSTNAME" ]; then
        echo "HOME_PC" > "$ENV_INFO_FILE"
        echo "Ne!sonB00ger" > ~/.sudo_pass
        chmod 600 ~/.sudo_pass
        echo "Environment: HOME PC (DESKTOP-BRS4719)"
    else
        # Assume work PC for now - will update when we get work hostname
        echo "WORK_PC" > "$ENV_INFO_FILE"
        echo "On Santa's Lap333" > ~/.sudo_pass
        chmod 600 ~/.sudo_pass
        echo "Environment: WORK PC ($HOSTNAME)"
    fi
}

# Always run setup when script is executed
setup_credentials

# Also create a Python helper for scripts to use
cat > /data/openpilot/common/environment_detection.py << 'EOF'
import os
import socket

def get_environment():
    """Returns 'HOME_PC' or 'WORK_PC' based on hostname"""
    hostname = socket.gethostname()
    if hostname == "DESKTOP-BRS4719":
        return "HOME_PC"
    else:
        return "WORK_PC"

def get_sudo_password():
    """Returns the appropriate sudo password for current environment"""
    env = get_environment()
    if env == "HOME_PC":
        return "Ne!sonB00ger"
    else:
        return "On Santa's Lap333"

def is_home_pc():
    return get_environment() == "HOME_PC"

def is_work_pc():
    return get_environment() == "WORK_PC"
EOF

echo "Credential setup complete for $HOSTNAME"