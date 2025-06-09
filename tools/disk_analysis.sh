#!/bin/bash
# TICI Disk Space Analysis Script
# Comprehensive storage diagnostics for openpilot TICI devices

echo "========================================="
echo "TICI Disk Space Analysis"
echo "========================================="
echo "Timestamp: $(date)"
echo

echo "=== FILESYSTEM OVERVIEW ==="
df -h

echo
echo "=== INODES USAGE ==="
df -i

echo
echo "=== MOUNT POINTS ==="
mount | grep -E '^/dev/' | sort

echo
echo "=== PARTITION TABLE ==="
lsblk -f

echo
echo "=== DISK USAGE BY DIRECTORY (/) ==="
du -h --max-depth=1 / 2>/dev/null | sort -hr | head -20

echo
echo "=== DISK USAGE BY DIRECTORY (/data) ==="
if [ -d /data ]; then
    du -h --max-depth=1 /data 2>/dev/null | sort -hr | head -20
fi

echo
echo "=== DISK USAGE BY DIRECTORY (/home) ==="
if [ -d /home ]; then
    du -h --max-depth=1 /home 2>/dev/null | sort -hr | head -20
fi

echo
echo "=== LARGEST FILES (>100MB) ==="
find / -type f -size +100M -exec ls -lh {} \; 2>/dev/null | head -20

echo
echo "=== LOG FILES ANALYSIS ==="
echo "Log directories and sizes:"
for dir in /var/log /data/logs /tmp /data/openpilot/selfdrive/logmessaged; do
    if [ -d "$dir" ]; then
        echo "$dir: $(du -sh "$dir" 2>/dev/null | cut -f1)"
        find "$dir" -name "*.log*" -o -name "*.gz" | wc -l | xargs echo "  Log files count:"
    fi
done

echo
echo "=== TEMPORARY FILES ==="
echo "/tmp usage:"
du -sh /tmp 2>/dev/null
echo "/var/tmp usage:"
du -sh /var/tmp 2>/dev/null

echo
echo "=== PACKAGE CACHE ==="
if command -v apt >/dev/null; then
    echo "APT cache:"
    du -sh /var/cache/apt 2>/dev/null
fi
if command -v pip >/dev/null; then
    echo "PIP cache:"
    du -sh ~/.cache/pip 2>/dev/null
fi

echo
echo "=== DOCKER USAGE ==="
if command -v docker >/dev/null; then
    echo "Docker system usage:"
    docker system df 2>/dev/null || echo "Docker not accessible"
fi

echo
echo "=== NVM/NODE USAGE ==="
if [ -d ~/.nvm ]; then
    echo "NVM directory:"
    du -sh ~/.nvm 2>/dev/null
    echo "Node versions:"
    ls -la ~/.nvm/versions/node/ 2>/dev/null || echo "No node versions found"
fi

echo
echo "=== OPENPILOT SPECIFIC ==="
if [ -d /data/openpilot ]; then
    echo "Openpilot directory breakdown:"
    du -sh /data/openpilot/* 2>/dev/null | sort -hr | head -10
fi

echo
echo "=== SCONS BUILD CACHE ==="
if [ -d /data/openpilot ]; then
    find /data/openpilot -name ".sconsign.dblite" -o -name "*.o" -o -name "*.pyc" | wc -l | xargs echo "Build artifacts count:"
    find /data/openpilot -name ".sconsign.dblite" -exec du -sh {} \; 2>/dev/null
fi

echo
echo "=== CLEANUP SUGGESTIONS ==="
echo "Potential cleanup targets:"

# Check for large log files
find /var/log -name "*.log*" -size +50M 2>/dev/null | head -5 | while read file; do
    echo "  Large log: $file ($(du -sh "$file" | cut -f1))"
done

# Check for old kernels
if command -v dpkg >/dev/null; then
    old_kernels=$(dpkg -l | grep linux-image | grep -v $(uname -r) | wc -l)
    if [ "$old_kernels" -gt 0 ]; then
        echo "  Old kernel packages: $old_kernels found"
    fi
fi

# Check for Python cache
find /data/openpilot -name "__pycache__" 2>/dev/null | wc -l | xargs echo "  Python cache directories:"

echo
echo "=== RECOMMENDED ACTIONS ==="
echo "1. Clean logs: sudo journalctl --vacuum-time=7d"
echo "2. Clean apt: sudo apt clean && sudo apt autoremove"
echo "3. Clean Python cache: find /data/openpilot -name '__pycache__' -exec rm -rf {} +"
echo "4. Clean build artifacts: cd /data/openpilot && scons -c"
echo "5. Clean NVM old versions: nvm use system && rm -rf ~/.nvm/versions/node/v*"
echo
echo "========================================="