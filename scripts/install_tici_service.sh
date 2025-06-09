#!/bin/bash
# Install TICI auto setup service (run this once on TICI device)

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're on TICI
if [[ ! -f /TICI ]]; then
    log_error "This script is designed for TICI devices only"
    exit 1
fi

log_info "Installing TICI auto setup service..."

# Copy service file to systemd directory
SERVICE_FILE="/etc/systemd/system/tici-auto-setup.service"
if sudo cp "$SCRIPT_DIR/tici_auto_setup.service" "$SERVICE_FILE"; then
    log_info "✓ Service file copied to $SERVICE_FILE"
else
    log_error "Failed to copy service file"
    exit 1
fi

# Set proper permissions
sudo chmod 644 "$SERVICE_FILE"

# Reload systemd daemon
if sudo systemctl daemon-reload; then
    log_info "✓ Systemd daemon reloaded"
else
    log_error "Failed to reload systemd daemon"
    exit 1
fi

# Enable the service
if sudo systemctl enable tici-auto-setup.service; then
    log_info "✓ TICI auto setup service enabled"
else
    log_error "Failed to enable service"
    exit 1
fi

# Test the service (dry run)
log_info "Testing service..."
if sudo systemctl start tici-auto-setup.service; then
    log_info "✓ Service started successfully"
    
    # Check status
    if sudo systemctl is-active --quiet tici-auto-setup.service; then
        log_info "✓ Service is active"
    else
        log_warn "Service is not active, checking logs..."
        sudo journalctl -u tici-auto-setup.service --no-pager -n 10
    fi
else
    log_error "Failed to start service"
    sudo journalctl -u tici-auto-setup.service --no-pager -n 10
    exit 1
fi

log_info "🎉 TICI auto setup service installed successfully!"
echo ""
echo "📋 The service will now run automatically on every boot to:"
echo "  - Restore git SSH configuration"
echo "  - Set up Python paths"
echo "  - Load persistent environment settings"
echo ""
echo "🔍 To check service status: sudo systemctl status tici-auto-setup"
echo "📜 To view logs: sudo journalctl -u tici-auto-setup -f"