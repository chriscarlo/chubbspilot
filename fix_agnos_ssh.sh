#!/bin/bash
# Emergency SSH fix for AGNOS-level configuration
# This ensures SSH keys are in both locations

echo "[SSH FIX] Starting emergency SSH fix..."

# Create directories
mkdir -p /data/persist/comma/ssh
mkdir -p /data/params/d

# Set username
echo "chriscarlo" > /data/persist/comma/ssh/GithubUsername
echo "chriscarlo" > /data/params/d/GithubUsername

# Write the known working SSH key
KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPTHWjyGrpClCVb/rK9rR2PmID3KbjUPMVFEMRsCjV/q claude-code-temp"
echo "$KEY" > /data/persist/comma/ssh/GithubSshKeys
echo "$KEY" > /data/params/d/GithubSshKeys

# Try to fetch all keys from GitHub (might fail if no network yet)
if curl -s https://github.com/chriscarlo.keys > /tmp/github_keys 2>/dev/null; then
  cp /tmp/github_keys /data/persist/comma/ssh/GithubSshKeys
  cp /tmp/github_keys /data/params/d/GithubSshKeys
  echo "[SSH FIX] Fetched keys from GitHub"
else
  echo "[SSH FIX] Using hardcoded key (network not ready)"
fi

echo "[SSH FIX] SSH keys populated in both locations"
echo "[SSH FIX] /data/persist/comma/ssh/ (for AGNOS sshd)"
echo "[SSH FIX] /data/params/d/ (for fork compatibility)"