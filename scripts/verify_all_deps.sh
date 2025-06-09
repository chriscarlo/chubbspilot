#!/bin/bash
# Comprehensive dependency verification script for both TICI and dev environments

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
OPENPILOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_section() {
    echo -e "${BLUE}[SECTION]${NC} $1"
}

# Detect environment
IS_TICI=false
IS_DEV=false
ARCH=$(uname -m)

if [[ -f /TICI ]]; then
    IS_TICI=true
    log_info "Environment: TICI device (aarch64)"
elif [[ "$ARCH" == "x86_64" ]]; then
    IS_DEV=true
    log_info "Environment: Development environment (x86_64)"
else
    log_warn "Environment: Unknown ($ARCH)"
fi

echo "═══════════════════════════════════════════════════════════════"
echo "🔍 COMPREHENSIVE DEPENDENCY VERIFICATION"
echo "═══════════════════════════════════════════════════════════════"

# 1. ENVIRONMENT VERIFICATION
log_section "1. Environment Verification"

echo "Architecture: $ARCH"
echo "OpenPilot Root: $OPENPILOT_ROOT"
echo "Python Version: $(python3 --version)"
echo "Current User: $(whoami)"
echo "Working Directory: $(pwd)"

if $IS_TICI; then
    echo "TICI Marker File: ✓ Present"
    echo "Persistent Storage: $(df -h /persist | tail -1 | awk '{print $4}') available"
    echo "Data Storage: $(df -h /data | tail -1 | awk '{print $4}') available"
else
    echo "Development Environment: ✓ Detected"
fi

# 2. PERSISTENT STORAGE VERIFICATION (TICI only)
if $IS_TICI; then
    log_section "2. Persistent Storage Verification"
    
    # Check persistent directories
    PERSISTENT_PYTHON_DIR="/data/openpilot/.local/lib/python3.11/site-packages"
    PERSISTENT_SSH_DIR="/persist/comma/.ssh"
    
    if [[ -d "$PERSISTENT_PYTHON_DIR" ]]; then
        PYTHON_PACKAGES=$(find "$PERSISTENT_PYTHON_DIR" -maxdepth 1 -type d | wc -l)
        log_info "✓ Python packages directory exists ($((PYTHON_PACKAGES-1)) packages)"
    else
        log_error "✗ Python packages directory missing: $PERSISTENT_PYTHON_DIR"
    fi
    
    if [[ -d "$PERSISTENT_SSH_DIR" ]]; then
        if [[ -f "$PERSISTENT_SSH_DIR/claude_github_key" ]]; then
            log_info "✓ SSH keys present and accessible"
        else
            log_warn "✗ SSH keys directory exists but keys missing"
        fi
    else
        log_error "✗ SSH directory missing: $PERSISTENT_SSH_DIR"
    fi
fi

# 3. PYTHON PATH VERIFICATION
log_section "3. Python Path Verification"

if $IS_TICI; then
    # Add persistent path for verification
    export PYTHONPATH="/data/openpilot/.local/lib/python3.11/site-packages:$PYTHONPATH"
fi

echo "Python Path:"
python3 -c "import sys; [print(f'  {p}') for p in sys.path if p]"

# 4. CRITICAL DEPENDENCIES CHECK
log_section "4. Critical Dependencies Check"

# Essential packages from the RCA documents
CRITICAL_PACKAGES=(
    "numpy"
    "requests" 
    "shapely"
    "pydantic"
    "fastapi"
    "uvicorn"
    "jinja2"
)

OPTIONAL_PACKAGES=(
    "capnp"
    "zmq" 
    "psutil"
    "PIL"
    "cv2"
    "serial"
    "usb1"
)

check_package() {
    local package=$1
    local is_critical=$2
    
    python3 -c "import $package" 2>/dev/null
    if [[ $? -eq 0 ]]; then
        if $is_critical; then
            log_info "✓ $package (critical)"
        else
            log_info "✓ $package (optional)"
        fi
        return 0
    else
        if $is_critical; then
            log_error "✗ $package (CRITICAL - missing)"
        else
            log_warn "✗ $package (optional - missing)"
        fi
        return 1
    fi
}

missing_critical=0
missing_optional=0

echo "Critical packages:"
for package in "${CRITICAL_PACKAGES[@]}"; do
    if ! check_package "$package" true; then
        ((missing_critical++))
    fi
done

echo ""
echo "Optional packages:"
for package in "${OPTIONAL_PACKAGES[@]}"; do
    if ! check_package "$package" false; then
        ((missing_optional++))
    fi
done

# 5. GIT CONFIGURATION CHECK (TICI only)
if $IS_TICI; then
    log_section "5. Git Configuration Check"
    
    # Check git SSH configuration
    SSH_COMMAND=$(git config --global core.sshCommand 2>/dev/null || echo "not set")
    if [[ "$SSH_COMMAND" == *"/persist/comma/.ssh/claude_github_key"* ]]; then
        log_info "✓ Git SSH command configured for persistent key"
    else
        log_warn "✗ Git SSH command not configured: $SSH_COMMAND"
    fi
    
    # Test GitHub connectivity (non-blocking)
    log_info "Testing GitHub SSH connectivity..."
    if timeout 10 ssh -T -i "/persist/comma/.ssh/claude_github_key" git@github.com 2>&1 | grep -q "successfully authenticated"; then
        log_info "✓ GitHub SSH authentication working"
    else
        log_warn "✗ GitHub SSH authentication failed or timed out"
    fi
fi

# 6. SERVICE SPECIFIC CHECKS
log_section "6. Service-Specific Checks"

# Check Concierge dependencies specifically
echo "Concierge dependencies:"
CONCIERGE_DEPS=("pydantic" "fastapi" "uvicorn" "jinja2")
concierge_ok=true

for dep in "${CONCIERGE_DEPS[@]}"; do
    if check_package "$dep" true; then
        :  # Already logged
    else
        concierge_ok=false
    fi
done

if $concierge_ok; then
    log_info "✓ Concierge service dependencies satisfied"
else
    log_error "✗ Concierge service missing dependencies"
fi

# 7. BOOTSTRAP SCRIPTS CHECK
log_section "7. Bootstrap Scripts Check"

BOOTSTRAP_SCRIPT="$OPENPILOT_ROOT/scripts/tici_bootstrap.sh"
AUTO_SETUP_SCRIPT="$OPENPILOT_ROOT/scripts/tici_auto_setup.sh"

if [[ -f "$BOOTSTRAP_SCRIPT" ]]; then
    if [[ -x "$BOOTSTRAP_SCRIPT" ]]; then
        log_info "✓ TICI bootstrap script present and executable"
    else
        log_warn "✗ TICI bootstrap script not executable"
    fi
else
    log_error "✗ TICI bootstrap script missing"
fi

if [[ -f "$AUTO_SETUP_SCRIPT" ]]; then
    if [[ -x "$AUTO_SETUP_SCRIPT" ]]; then
        log_info "✓ TICI auto setup script present and executable"
    else
        log_warn "✗ TICI auto setup script not executable"
    fi
else
    log_error "✗ TICI auto setup script missing"
fi

# Check if service is installed (TICI only)
if $IS_TICI; then
    if systemctl is-enabled tici-auto-setup.service >/dev/null 2>&1; then
        log_info "✓ TICI auto setup service enabled"
    else
        log_warn "✗ TICI auto setup service not enabled (run scripts/install_tici_service.sh)"
    fi
fi

# 8. SUMMARY
echo ""
echo "═══════════════════════════════════════════════════════════════"
log_section "8. Summary"

if [[ $missing_critical -eq 0 ]]; then
    log_info "✓ All critical dependencies satisfied"
else
    log_error "✗ $missing_critical critical dependencies missing"
fi

if [[ $missing_optional -eq 0 ]]; then
    log_info "✓ All optional dependencies satisfied"
else
    log_warn "✗ $missing_optional optional dependencies missing"
fi

# 9. RECOMMENDATIONS
echo ""
log_section "9. Recommendations"

if [[ $missing_critical -gt 0 ]]; then
    if $IS_TICI; then
        echo "Run: tici-bootstrap (or bash $BOOTSTRAP_SCRIPT)"
        echo "Or: python3 $OPENPILOT_ROOT/system/ensure_dependencies.py"
    else
        echo "Install missing packages in your development environment"
        echo "Consider setting up a virtual environment"
    fi
fi

if $IS_TICI && [[ $missing_critical -eq 0 && $missing_optional -gt 0 ]]; then
    echo "Run: python3 $OPENPILOT_ROOT/system/ensure_dependencies.py"
fi

echo ""
if [[ $missing_critical -eq 0 ]]; then
    log_info "🎉 System is ready for operation!"
else
    log_error "⚠️  System requires dependency installation before use"
fi