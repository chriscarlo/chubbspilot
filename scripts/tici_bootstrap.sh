#!/bin/bash
# TICI Bootstrap Script - Ensures all dependencies and configurations are set up
# This script should be run after every fresh TICI install or can be called from boot

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
OPENPILOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 TICI Bootstrap Starting..."
echo "OpenPilot Root: $OPENPILOT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

log_info "Running on TICI device"

# 1. PERSISTENT DIRECTORY SETUP
log_info "Setting up persistent directories..."

# Create persistent Python packages directory
PERSISTENT_PYTHON_DIR="/data/openpilot/.local/lib/python3.11/site-packages"
mkdir -p "$PERSISTENT_PYTHON_DIR"

# Create persistent SSH directory
PERSISTENT_SSH_DIR="/persist/comma/.ssh"
mkdir -p "$PERSISTENT_SSH_DIR"
chmod 700 "$PERSISTENT_SSH_DIR"

# Create persistent git config directory  
PERSISTENT_GIT_DIR="/persist/comma/.gitconfig"
mkdir -p "$(dirname "$PERSISTENT_GIT_DIR")"

log_info "✓ Persistent directories created"

# 2. SSH KEY SETUP
log_info "Setting up SSH keys..."

if [[ -f "$PERSISTENT_SSH_DIR/claude_github_key" ]]; then
    log_info "✓ SSH keys already exist in persistent storage"
    chmod 600 "$PERSISTENT_SSH_DIR/claude_github_key"
    chmod 644 "$PERSISTENT_SSH_DIR/claude_github_key.pub" 2>/dev/null || true
else
    log_warn "SSH keys not found in $PERSISTENT_SSH_DIR"
    log_warn "Please copy your SSH keys to $PERSISTENT_SSH_DIR manually"
    log_warn "Example: scp ~/.ssh/claude_github_key* comma@TICI_IP:$PERSISTENT_SSH_DIR/"
fi

# 3. GIT CONFIGURATION
log_info "Setting up Git configuration..."

# Configure git to use persistent SSH key
git config --global core.sshCommand "ssh -i $PERSISTENT_SSH_DIR/claude_github_key -o StrictHostKeyChecking=no"

# Set git user (can be overridden later)
git config --global user.name "TICI User"
git config --global user.email "tici@chauffeur.dev"

# Configure git to store config in persistent location
if [[ ! -f "$PERSISTENT_GIT_DIR" ]]; then
    cp ~/.gitconfig "$PERSISTENT_GIT_DIR" 2>/dev/null || touch "$PERSISTENT_GIT_DIR"
fi

log_info "✓ Git configured for persistent SSH key"

# 4. PYTHON DEPENDENCIES INSTALLATION
log_info "Installing Python dependencies..."

install_python_deps() {
    local requirements_file="$1"
    local target_dir="$PERSISTENT_PYTHON_DIR"
    
    if [[ -f "$requirements_file" ]]; then
        log_info "Installing from $requirements_file"
        pip3 install --target="$target_dir" -r "$requirements_file" || {
            log_warn "pip3 failed, trying with python3 -m pip"
            python3 -m pip install --target="$target_dir" -r "$requirements_file" || {
                log_error "Failed to install dependencies from $requirements_file"
                return 1
            }
        }
    else
        log_warn "Requirements file not found: $requirements_file"
        return 1
    fi
}

# Install Concierge dependencies (critical for web interface)
if install_python_deps "$OPENPILOT_ROOT/selfdrive/chauffeur/concierge/requirements.txt"; then
    log_info "✓ Concierge dependencies installed"
else
    log_error "Failed to install Concierge dependencies - Concierge may not work"
fi

# Install main openpilot dependencies (optional, for development)
if install_python_deps "$OPENPILOT_ROOT/requirements.txt"; then
    log_info "✓ Main openpilot dependencies installed"
else
    log_warn "Failed to install main dependencies - some features may not work"
fi

# 5. ENVIRONMENT SETUP
log_info "Setting up environment..."

# Create persistent bashrc additions
PERSISTENT_BASHRC="/persist/comma/.bashrc_persistent"
cat > "$PERSISTENT_BASHRC" << 'EOF'
# TICI Persistent Environment Setup
export PYTHONPATH="/data/openpilot/.local/lib/python3.11/site-packages:$PYTHONPATH"

# Aliases for common tasks
alias ll='ls -la'
alias cdop='cd /data/openpilot'
alias tici-bootstrap='bash /data/openpilot/scripts/tici_bootstrap.sh'
alias tici-deps='pip3 install --target=/data/openpilot/.local/lib/python3.11/site-packages'
alias verify-all-deps='bash /data/openpilot/scripts/verify_all_deps.sh'

# Git shortcuts
alias gitlog='git log --oneline -10'
alias gitstatus='git status'
EOF

# Add to ~/.bashrc if not already there
if ! grep -q "source /persist/comma/.bashrc_persistent" ~/.bashrc 2>/dev/null; then
    echo "source /persist/comma/.bashrc_persistent" >> ~/.bashrc
    log_info "✓ Added persistent bashrc to ~/.bashrc"
fi

# 6. SERVICE HEALTH CHECK
log_info "Performing health checks..."

# Test Python imports
python3 -c "
import sys
sys.path.insert(0, '/data/openpilot/.local/lib/python3.11/site-packages')
try:
    import fastapi, uvicorn, pydantic
    print('✓ Concierge dependencies importable')
except ImportError as e:
    print(f'✗ Import error: {e}')
"

# Test git SSH
if ssh -T -i "$PERSISTENT_SSH_DIR/claude_github_key" git@github.com 2>&1 | grep -q "successfully authenticated"; then
    log_info "✓ GitHub SSH authentication working"
else
    log_warn "GitHub SSH authentication not working - check keys"
fi

# 7. CLEANUP AND FINAL SETUP
log_info "Final setup tasks..."

# Set proper permissions
find "$PERSISTENT_PYTHON_DIR" -type d -exec chmod 755 {} \;
find "$PERSISTENT_PYTHON_DIR" -type f -exec chmod 644 {} \;

# Create status file
echo "$(date): TICI Bootstrap completed successfully" > /persist/comma/.tici_bootstrap_status

log_info "🎉 TICI Bootstrap completed!"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Copy SSH keys to $PERSISTENT_SSH_DIR if not already done"
echo "2. Test Concierge: systemctl status manager"
echo "3. Access web interface: http://TICI_IP:8091"
echo "4. Run 'source ~/.bashrc' to load new environment"
echo ""
echo "🔄 To re-run bootstrap: tici-bootstrap"