#!/bin/bash
# TICI Auto Setup - Runs at boot to ensure configurations survive reboots
# This script handles the ephemeral home directory issue

PERSISTENT_SSH_DIR="/persist/comma/.ssh"
PERSISTENT_PYTHON_DIR="/data/openpilot/.local/lib/python3.11/site-packages"

# Only run if we detect we're on a freshly booted TICI (home directory reset)
if [[ -f /TICI ]] && [[ ! -f ~/.tici_setup_done ]]; then
    echo "🔄 TICI Auto Setup: Restoring configurations after reboot..."
    
    # Set up Python path for this session
    export PYTHONPATH="$PERSISTENT_PYTHON_DIR:$PYTHONPATH"
    
    # Also add to bashrc for interactive shells
    if ! grep -q "PYTHONPATH.*site-packages" ~/.bashrc 2>/dev/null; then
        echo "export PYTHONPATH=\"$PERSISTENT_PYTHON_DIR:\$PYTHONPATH\"" >> ~/.bashrc
        echo "✓ Python path added to bashrc"
    fi
    
    # Restore git configuration if SSH keys exist
    if [[ -f "$PERSISTENT_SSH_DIR/claude_github_key" ]]; then
        git config --global core.sshCommand "ssh -i $PERSISTENT_SSH_DIR/claude_github_key -o StrictHostKeyChecking=no"
        echo "✓ Git SSH configuration restored"
    fi
    
    # Source persistent bashrc if it exists
    if [[ -f /persist/comma/.bashrc_persistent ]]; then
        source /persist/comma/.bashrc_persistent
        echo "✓ Persistent environment loaded"
    fi
    
    # Restore Claude Code authentication
    if [[ -d "/persist/claude/.claude" ]]; then
        rm -rf ~/.claude 2>/dev/null || true
        ln -s /persist/claude/.claude ~/.claude
        echo "✓ Claude authentication directory restored"
    fi
    
    if [[ -f "/persist/claude/.claude.json" ]]; then
        rm -f ~/.claude.json 2>/dev/null || true
        ln -s /persist/claude/.claude.json ~/.claude.json
        echo "✓ Claude configuration restored"
    fi
    
    # Mark setup as done for this session
    touch ~/.tici_setup_done
    echo "✓ Auto setup complete"
fi