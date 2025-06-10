#!/bin/bash
# Claude Code Authentication Restoration Script
# This script restores Claude authentication from persistent storage on boot

echo "[$(date)] Starting Claude authentication restoration..."

# Create necessary directories
mkdir -p /home/comma

# Create symlinks for Claude configuration
if [ -d "/persist/claude/.claude" ]; then
    # Remove any existing directory/file
    rm -rf /home/comma/.claude 2>/dev/null || true
    # Create symlink
    ln -s /persist/claude/.claude /home/comma/.claude
    echo "[$(date)] Created symlink for .claude directory"
fi

# Create symlink for .claude.json if it exists
if [ -f "/persist/claude/.claude.json" ]; then
    rm -f /home/comma/.claude.json 2>/dev/null || true
    ln -s /persist/claude/.claude.json /home/comma/.claude.json
    echo "[$(date)] Created symlink for .claude.json"
fi

# Ensure correct permissions
chown -h comma:comma /home/comma/.claude 2>/dev/null || true
chown -h comma:comma /home/comma/.claude.json 2>/dev/null || true

# Verify credentials exist
if [ -f "/persist/claude/.claude/.credentials.json" ]; then
    echo "[$(date)] Claude credentials found and restored successfully"
else
    echo "[$(date)] WARNING: No Claude credentials found in persistent storage"
fi

echo "[$(date)] Claude authentication restoration complete"