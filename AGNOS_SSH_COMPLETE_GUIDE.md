# AGNOS SSH Complete Guide

## Table of Contents
1. [Overview](#overview)
2. [SSH Configuration Architecture](#ssh-configuration-architecture)
3. [Storage Locations and Persistence](#storage-locations-and-persistence)
4. [SSH Access Methods](#ssh-access-methods)
5. [Troubleshooting SSH Issues](#troubleshooting-ssh-issues)
6. [The SSH Fix Implementation](#the-ssh-fix-implementation)
7. [Lessons Learned](#lessons-learned)
8. [Technical Details](#technical-details)

## Overview

AGNOS (the underlying OS on TICI devices) uses a modified SSH configuration designed to maintain SSH access across OpenPilot installations, uninstalls, and fork switches. This guide consolidates all documentation about AGNOS SSH, including recent fixes and lessons learned.

### Key Points
- SSH runs on **port 8022** (not the standard port 22)
- Only **public key authentication** is allowed (no password access)
- SSH keys persist in `/data/persist/comma/ssh/` which survives OpenPilot uninstalls
- The standard user is `comma` (not root)

## SSH Configuration Architecture

### AGNOS-Level SSH Daemon Configuration
The SSH daemon configuration at `/etc/ssh/sshd_config` has been modified to read authorized keys from a persistent location:

```
AuthorizedKeysFile /data/persist/comma/ssh/GithubSshKeys
```

This differs from the standard OpenPilot location (`/data/params/d/GithubSshKeys`) to ensure SSH access persists.

### File Structure
```
/data/persist/comma/ssh/
├── GithubUsername    # Contains GitHub username (e.g., "chriscarlo")
├── GithubSshKeys     # Contains public SSH keys fetched from GitHub
├── SshEnabled        # Contains "1" to enable SSH
└── github_username   # Lowercase version for ssh_fixer service (survives uninstalls)

/data/persist/comma/
├── authorized_keys   # Primary AGNOS SSH authorized_keys location
└── .ssh/
    └── authorized_keys  # Alternative authorized_keys location
```

### Backward Compatibility
Most OpenPilot forks expect to write SSH configuration to `/data/params/d/`. To maintain compatibility, symlinks are created:
```
/data/params/d/GithubUsername → /data/persist/comma/ssh/GithubUsername
/data/params/d/GithubSshKeys → /data/persist/comma/ssh/GithubSshKeys
/data/params/d/SshEnabled → /data/persist/comma/ssh/SshEnabled
```

## Storage Locations and Persistence

### What Persists Across Fork Switches
- ✅ `/data/persist/` - System-level persistence directory
- ❌ `/data/params/` - Deleted during fork switches
- ❌ `/data/openpilot/` - Deleted during uninstall
- ❌ Custom directories under `/data/` - Actively cleaned by system

### Critical Discovery
Only `/data/persist/` truly persists across OpenPilot uninstalls and fork switches. This is why the AGNOS SSH configuration was modified to use this location.

## SSH Access Methods

### 1. Standard SSH Connection
```bash
ssh -p 8022 comma@<device-ip>
```

### 2. Using SSH Config
Add to `~/.ssh/config`:
```
Host comma
    HostName <device-ip>
    User comma
    Port 8022
    IdentityFile ~/.ssh/your_github_key
```

Then simply: `ssh comma`

### 3. GitHub SSH Keys
OpenPilot fetches SSH keys from: `https://github.com/<username>.keys`

This requires:
- Valid GitHub username set in the device
- Public SSH keys uploaded to your GitHub account
- Network connectivity to GitHub

## Troubleshooting SSH Issues

### Common Problems and Solutions

#### 1. "Permission denied (publickey)"
**Causes:**
- SSH keys not in `/data/persist/comma/ssh/GithubSshKeys`
- Wrong SSH key being used
- Keys have incorrect permissions

**Solution:** Use the SSH Fix button in Settings → Network → Advanced

#### 2. Python Import Errors
**Error:** `undefined symbol: Py_Version`
**Cause:** Python version mismatch between compiled modules and sudo environment
**Solution:** The fix uses `fix_ssh_simple.py` which avoids compiled modules

#### 3. Permission Denied Creating Directories
**Cause:** `/data/persist/` requires elevated permissions
**Solution:** The fix script uses sudo for all directory operations

## The SSH Fix Implementation

### Overview
The SSH fix consists of two main components:

1. **UI Button** - Manual fix via Settings → Network → Advanced → "Fix SSH"
2. **SSH Fixer Service** - Continuous monitoring and automatic repair

### Current Architecture (Latest Implementation)

#### SSH Fixer Service (`system/ssh_fixer.py`)
The service now actively monitors and maintains SSH access:

**What it does:**
- Fetches current SSH keys from GitHub every 5 minutes
- Compares GitHub keys with authorized_keys to detect changes
- Automatically updates keys when they differ
- Stores GitHub username in `/data/persist/comma/ssh/github_username` (survives OpenPilot uninstalls)
- Checks immediately on startup (no 5-minute wait)

**Key improvements:**
- Monitors ACTUAL SSH functionality, not just file existence
- Prevents lockouts when GitHub keys change
- Works across OpenPilot reinstalls
- Provides clear logging about what's happening

#### Fix SSH Button (`fix_ssh_simple.py`)
The manual fix button provides immediate SSH repair:

**Features:**
- Works around Python version issues by avoiding compiled modules
- Fetches fresh keys from GitHub
- Writes to all necessary locations:
  - `/data/persist/comma/ssh/` (for AGNOS SSH daemon)
  - `/data/persist/comma/authorized_keys` (primary AGNOS location)
  - `/data/persist/comma/.ssh/authorized_keys` (alternative location)
- Creates backward compatibility symlinks
- Provides detailed error logging to UI

### The Working Solution: fix_ssh_simple.py

This simplified script:
- Doesn't use compiled Python modules
- Reads param files directly from disk
- Writes SSH keys to multiple locations for redundancy
- Uses sudo for all privileged operations
- Works with any Python version

Key operations:
1. Reads GitHub username from param files or uses hardcoded fallback
2. Fetches SSH keys from GitHub
3. Writes to `/data/persist/comma/ssh/` (for AGNOS SSH daemon)
4. Also writes to `/data/persist/comma/.ssh/authorized_keys` (standard SSH location)
5. Creates backward compatibility symlinks
6. Restarts SSH service

## Lessons Learned

### 1. Python Environment Issues
- Compiled Python extensions (`.so` files) are tied to specific Python versions
- Running with `sudo` often uses a different Python environment
- Solution: Avoid compiled modules for system-level scripts

### 2. Persistence is Tricky
- Most directories under `/data/` are cleaned during fork switches
- Only `/data/persist/` is guaranteed to survive
- Always use `/data/persist/` for critical configuration

### 3. SSH Key Locations
- AGNOS SSH daemon can be configured to read from custom locations
- Standard location: `/root/.ssh/authorized_keys` or `/home/comma/.ssh/authorized_keys`
- AGNOS modified location: `/data/persist/comma/ssh/GithubSshKeys`
- Writing to multiple locations provides redundancy

### 4. Error Visibility
- UI dialogs have character limits and can't show full tracebacks
- Always log to `/data/crashes/error.txt` for UI visibility
- The Error Log (Settings → Software → Error Log) is the best place for detailed diagnostics

### 5. Service Startup Timing
- Don't wait 5 minutes to check SSH on a device you might be locked out of
- Run critical checks immediately on startup
- Periodic checks can have longer intervals

## Technical Details

### SSH Service Configuration
- **Service Name:** `ssh.service` (not `sshd`)
- **Port:** 8022
- **User:** comma
- **Authentication:** Public key only
- **Password Authentication:** Disabled
- **Config File:** `/etc/ssh/sshd_config`

### Directory Permissions
```bash
/data/persist/comma/ssh/          # 755 root:root
├── GithubUsername                # 644 root:root
├── GithubSshKeys                 # 644 root:root
├── SshEnabled                    # 644 root:root
└── github_username               # 644 root:root

/data/persist/comma/
├── authorized_keys               # 600 root:root
└── .ssh/                         # 700 root:root
    └── authorized_keys           # 600 root:root
```

### Key Fetching Mechanism
1. OpenPilot reads `GithubUsername` parameter
2. Fetches keys from `https://github.com/{username}.keys`
3. Writes to configured locations
4. No SSL verification (some forks disable SSL to work around certificate issues)

### Debugging Commands
```bash
# Check SSH service status
sudo systemctl status ssh

# View SSH daemon configuration
sudo cat /etc/ssh/sshd_config | grep -i authorizedkeys

# Check if keys exist
ls -la /data/persist/comma/ssh/
cat /data/persist/comma/ssh/GithubSshKeys

# Test SSH locally
ssh -p 8022 comma@localhost

# View SSH daemon logs
sudo journalctl -u ssh -n 50
```

## Summary

The AGNOS SSH system is designed for persistence but can be fragile due to:
- Python environment issues
- Permission requirements
- Multiple storage locations

The current fix implementation provides multiple fallbacks:
- Simplified Python script avoiding compiled modules
- Writing to multiple locations for redundancy
- Comprehensive error logging
- Both manual and automatic repair mechanisms

SSH will survive OpenPilot uninstalls as long as the keys are properly written to `/data/persist/comma/ssh/`.