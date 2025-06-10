#!/bin/bash
# Python Environment Pre-flight Check
# This script validates the Python environment matches PYTHON_TRUTH.md

set -e

echo "🚨 PYTHON ENVIRONMENT PRE-FLIGHT CHECK 🚨"
echo "========================================"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Expected values per PYTHON_TRUTH.md
EXPECTED_PYTHON_VERSION="3.11.4"
EXPECTED_PYTHON_PATH="/home/chris/.pyenv/versions/3.11.4/bin/python3"
EXPECTED_SITE_PACKAGES="/data/openpilot/.local/lib/python3.11/site-packages"
EXPECTED_PYTHONPATH="/data/openpilot:/data/openpilot/.local/lib/python3.11/site-packages"

errors=0

# Check Python version
echo -n "Checking Python version... "
ACTUAL_VERSION=$(python3 --version | cut -d' ' -f2)
if [ "$ACTUAL_VERSION" = "$EXPECTED_PYTHON_VERSION" ]; then
    echo -e "${GREEN}✓ $ACTUAL_VERSION${NC}"
else
    echo -e "${RED}✗ Found $ACTUAL_VERSION, expected $EXPECTED_PYTHON_VERSION${NC}"
    errors=$((errors + 1))
fi

# Check Python path
echo -n "Checking Python executable... "
ACTUAL_PYTHON=$(which python3)
if [[ "$ACTUAL_PYTHON" == *"pyenv"* ]]; then
    echo -e "${GREEN}✓ $ACTUAL_PYTHON${NC}"
else
    echo -e "${RED}✗ Found $ACTUAL_PYTHON${NC}"
    echo -e "${YELLOW}  Expected: pyenv managed Python${NC}"
    errors=$((errors + 1))
fi

# Check PYTHONPATH
echo -n "Checking PYTHONPATH... "
if [ -z "$PYTHONPATH" ]; then
    echo -e "${RED}✗ NOT SET!${NC}"
    echo -e "${YELLOW}  Run: export PYTHONPATH=\"$EXPECTED_PYTHONPATH\"${NC}"
    errors=$((errors + 1))
elif [[ "$PYTHONPATH" == *"$EXPECTED_SITE_PACKAGES"* ]] && [[ "$PYTHONPATH" == *"/data/openpilot"* ]]; then
    echo -e "${GREEN}✓ $PYTHONPATH${NC}"
else
    echo -e "${RED}✗ Incorrect: $PYTHONPATH${NC}"
    echo -e "${YELLOW}  Expected: $EXPECTED_PYTHONPATH${NC}"
    errors=$((errors + 1))
fi

# Check site-packages directory
echo -n "Checking persistent site-packages... "
if [ -d "$EXPECTED_SITE_PACKAGES" ]; then
    echo -e "${GREEN}✓ Directory exists${NC}"
else
    echo -e "${RED}✗ Directory missing!${NC}"
    echo -e "${YELLOW}  Create with: mkdir -p $EXPECTED_SITE_PACKAGES${NC}"
    errors=$((errors + 1))
fi

# Check for Python 3.12 contamination
echo -n "Checking for Python 3.12 contamination... "
CONTAMINATED=$(find "$EXPECTED_SITE_PACKAGES" -name "*.so" 2>/dev/null | grep -E "cp312|cpython-312" | wc -l)
if [ "$CONTAMINATED" -eq 0 ]; then
    echo -e "${GREEN}✓ No contamination found${NC}"
else
    echo -e "${RED}✗ Found $CONTAMINATED files compiled for Python 3.12!${NC}"
    echo -e "${YELLOW}  Run: find $EXPECTED_SITE_PACKAGES -name \"*.so\" | grep -E \"cp312|cpython-312\" | xargs rm -f${NC}"
    errors=$((errors + 1))
fi

# Check pip
echo -n "Checking pip installation method... "
PIP_VERSION=$(/home/chris/.pyenv/versions/3.11.4/bin/python3 -m pip --version 2>&1)
if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✓ pip available via python3 -m pip${NC}"
else
    echo -e "${RED}✗ pip not available!${NC}"
    echo -e "${YELLOW}  Install with: /home/chris/.pyenv/versions/3.11.4/bin/python3 -m ensurepip${NC}"
    errors=$((errors + 1))
fi

echo "========================================"

if [ $errors -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED!${NC}"
    echo ""
    echo "To install packages, use:"
    echo "  /home/chris/.pyenv/versions/3.11.4/bin/python3 -m pip install \\"
    echo "    --target=$EXPECTED_SITE_PACKAGES \\"
    echo "    <package>"
    exit 0
else
    echo -e "${RED}❌ FAILED: $errors checks failed!${NC}"
    echo ""
    echo "See PYTHON_TRUTH.md for the correct configuration."
    echo ""
    echo "Quick fix:"
    echo "  export PYTHONPATH=\"$EXPECTED_PYTHONPATH\""
    echo "  /home/chris/.pyenv/versions/3.11.4/bin/python3 -m ensurepip"
    exit 1
fi