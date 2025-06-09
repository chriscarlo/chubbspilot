# TICI Persistence Post-Mortem

**Date:** January 9, 2025  
**Incident Duration:** ~30 minutes  
**Services Affected:** Concierge, Git/SSH operations  
**Severity:** Critical - Complete development workflow breakage

## Executive Summary

After a TICI device reboot, we discovered that the entire `/home/comma` directory is ephemeral and gets wiped clean. This caused:
1. Loss of all Python packages installed via pip
2. Loss of SSH keys required for git operations
3. Complete inability to push code changes
4. Concierge service failure

## Timeline of Discovery

1. **05:14 UTC** - Concierge failed to start after TICI reboot
2. **05:16 UTC** - Discovered Python packages missing, reinstalled with `pip install --user`
3. **05:20 UTC** - Attempted to push changes, discovered SSH keys missing
4. **05:25 UTC** - Realized `/home/comma` is completely ephemeral
5. **05:28 UTC** - Found correct persist location is `/persist/` not `/data/persist/`
6. **05:35 UTC** - Located SSH keys in `/persist/ssh_keys/`
7. **05:38 UTC** - Successfully configured git and pushed changes

## Root Cause Analysis

### The Ephemeral Home Directory

TICI devices use a read-only root filesystem with specific persistent mount points:
- `/home/comma/` - **EPHEMERAL** - Cleared on every reboot
- `/data/` - Persistent but for application data
- `/persist/` - Persistent for system configuration (only 27MB)

### What We Were Doing Wrong

1. **Python packages**: Using `pip install --user` which installs to `/home/comma/.local/`
2. **SSH keys**: Storing in `~/.ssh/` which is under ephemeral `/home/comma/`
3. **Assuming home persistence**: Standard Linux behavior doesn't apply on TICI

## Solutions Implemented

### 1. Python Package Management

**Wrong way:**
```bash
pip3 install --user <package>  # Goes to /home/comma/.local/
```

**Correct way:**
```bash
pip3 install --target=/data/openpilot/.local/lib/python3.11/site-packages <package>
```

**Code changes:**
- Updated `main_wrapper.py` to add persistent path to `sys.path`
- Modified install functions to use `--target` flag
- Added `.local/` to `.gitignore`

### 2. SSH Key Management

**Location:** `/persist/comma/.ssh/`
- Moved from `/persist/ssh_keys/` to standard `.ssh` naming
- Set proper permissions (700 on directory, 600 on private key)

**Git configuration:**
```bash
git config core.sshCommand "ssh -i /persist/comma/.ssh/claude_github_key -o StrictHostKeyChecking=no"
```

This tells git to use the SSH key directly from the persistent location without relying on symlinks.

### 3. Repository URL Update

During push, discovered repository moved:
```bash
git remote set-url origin git@github.com:chriscarlo/chauffeur.git
```

## Persistent Storage Strategy

### `/persist/` (27MB total)
**Use for:**
- SSH keys
- Small configuration files
- Secrets that shouldn't be in git

**Current structure:**
```
/persist/
├── comma/
│   └── .ssh/
│       ├── claude_github_key
│       └── claude_github_key.pub
├── azure_conn_string
├── backup_files/
└── mapbox/
```

### `/data/openpilot/` (88GB available on /data)
**Use for:**
- Python packages
- Application data
- Logs
- Any larger files

**Current structure:**
```
/data/openpilot/
├── .local/
│   └── lib/
│       └── python3.11/
│           └── site-packages/  # All pip packages here
```

## Lessons Learned

### 1. TICI is Not Standard Linux
- Read-only root filesystem
- Ephemeral home directory
- Limited persistent storage locations
- Special considerations for embedded systems

### 2. Always Verify Persistence
- Test changes across reboots
- Don't assume standard Linux behavior
- Check mount points and filesystem types

### 3. Documentation is Critical
- This behavior wasn't clearly documented
- Led to significant time waste
- Now properly documented in CLAUDE.md

## Action Items Completed

- [x] Moved Python packages to `/data/openpilot/.local/`
- [x] Moved SSH keys to `/persist/comma/.ssh/`
- [x] Configured git to use persistent SSH key location
- [x] Updated all documentation
- [x] Added persistence rules to CLAUDE.md/AGENTS.md
- [x] Created comprehensive RCA

## Future Recommendations

### 1. Boot-time Setup Script
Create `/data/openpilot/scripts/tici_boot_setup.sh`:
- Set up symlinks if needed
- Configure git settings
- Verify critical files exist
- Add to system startup

### 2. Dependency Management
- Consider including critical packages in system image
- Or create a requirements file that auto-installs on boot
- Document all runtime dependencies

### 3. Developer Onboarding
- Create TICI setup guide
- Include persistence warnings prominently
- Provide setup scripts for new developers

## Configuration Reference

### Git Setup (Run after every reboot or add to profile)
```bash
git config --global core.sshCommand "ssh -i /persist/comma/.ssh/claude_github_key -o StrictHostKeyChecking=no"
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Python Path Setup
Add to scripts or wrapper files:
```python
import sys
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
```

### Environment Variables
```bash
export PYTHONPATH="/data/openpilot/.local/lib/python3.11/site-packages:$PYTHONPATH"
```

## Conclusion

The TICI ephemeral home directory is a critical architectural difference that must be understood by all developers. This incident has led to proper documentation and a robust persistent storage strategy that will prevent similar issues in the future.