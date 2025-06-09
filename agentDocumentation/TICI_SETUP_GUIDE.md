# TICI Setup Guide

This guide covers essential setup steps for development on TICI devices, focusing on persistent storage and configuration.

## 🚨 Critical: Understanding TICI Persistence 🚨

**THE `/home/comma` DIRECTORY IS EPHEMERAL - IT GETS WIPED ON EVERY REBOOT!**

### Persistent Locations:
- `/persist/` - System config, SSH keys (only 27MB!)
- `/data/` - Application data, Python packages

### Ephemeral Locations:
- `/home/comma/` - EVERYTHING here is lost on reboot
- `/tmp/` - Standard temporary directory

## Initial Setup

### 1. SSH Key Setup

SSH keys MUST be stored in `/persist/comma/.ssh/`:

```bash
# Create persistent SSH directory
mkdir -p /persist/comma/.ssh
chmod 700 /persist/comma/.ssh

# Copy your SSH keys (example)
cp /path/to/your/ssh_key /persist/comma/.ssh/
chmod 600 /persist/comma/.ssh/your_ssh_key
```

### 2. Git Configuration

Configure git to use persistent SSH key:

```bash
# Set SSH command to use persistent key
git config --global core.sshCommand "ssh -i /persist/comma/.ssh/claude_github_key -o StrictHostKeyChecking=no"

# Set your identity
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### 3. Python Package Management

NEVER use `pip install --user` on TICI!

```bash
# Create persistent package directory
mkdir -p /data/openpilot/.local/lib/python3.11/site-packages

# Install packages to persistent location
pip3 install --target=/data/openpilot/.local/lib/python3.11/site-packages <package>

# Add to Python path (add to your scripts)
export PYTHONPATH="/data/openpilot/.local/lib/python3.11/site-packages:$PYTHONPATH"
```

## Persistent File Storage Guidelines

### What Goes Where

#### `/persist/` (27MB limit!)
- SSH keys
- Small config files
- Secrets/credentials
- Critical boot configs

Example structure:
```
/persist/
├── comma/
│   └── .ssh/
│       ├── github_key
│       └── github_key.pub
├── azure_conn_string
└── mapbox/
    └── api_key
```

#### `/data/openpilot/`
- Python packages
- Application logs
- Development tools
- Cache files
- Any large files

Example structure:
```
/data/openpilot/
├── .local/
│   └── lib/
│       └── python3.11/
│           └── site-packages/
├── tools/
├── scripts/
└── logs/
```

## Common Tasks

### Installing Python Dependencies

For a project with requirements.txt:

```bash
# Install all requirements to persistent location
pip3 install --target=/data/openpilot/.local/lib/python3.11/site-packages -r requirements.txt
```

### Creating Persistent Scripts

Create scripts that survive reboots:

```bash
# Store scripts in /data/openpilot/scripts/
mkdir -p /data/openpilot/scripts

# Example: Git setup script
cat > /data/openpilot/scripts/setup_git.sh << 'EOF'
#!/bin/bash
git config --global core.sshCommand "ssh -i /persist/comma/.ssh/claude_github_key -o StrictHostKeyChecking=no"
git config --global user.name "Claude"
git config --global user.email "claude@anthropic.com"
echo "Git configured for persistent SSH key"
EOF

chmod +x /data/openpilot/scripts/setup_git.sh
```

### Python Script Template

For Python scripts that need persistent packages:

```python
#!/usr/bin/env python3
import sys
import os

# Add persistent packages to path
PERSISTENT_PACKAGES = "/data/openpilot/.local/lib/python3.11/site-packages"
if PERSISTENT_PACKAGES not in sys.path:
    sys.path.insert(0, PERSISTENT_PACKAGES)

# Now import your packages
import requests  # Will work if installed to persistent location
```

## Troubleshooting

### "Module not found" after reboot
- Check if packages were installed to `/home/comma/.local/` (wrong!)
- Reinstall to `/data/openpilot/.local/lib/python3.11/site-packages`
- Verify PYTHONPATH includes persistent location

### "Permission denied" for git operations
- SSH key not in persistent location
- Run: `git config --global core.sshCommand "ssh -i /persist/comma/.ssh/your_key -o StrictHostKeyChecking=no"`

### Lost configuration after reboot
- Configuration was in `/home/comma/`
- Move to `/persist/comma/` or `/data/openpilot/`

## Best Practices

1. **Always test persistence**: Make changes, reboot, verify they persist
2. **Document paths**: Always use absolute paths in scripts
3. **Check storage**: Monitor `/persist/` usage (only 27MB!)
4. **Backup critical files**: Keep copies of SSH keys elsewhere
5. **Use version control**: Commit configuration scripts to git

## Quick Reference

```bash
# Check persist usage
df -h /persist

# List persistent Python packages
ls /data/openpilot/.local/lib/python3.11/site-packages/

# Test SSH key
ssh -T -i /persist/comma/.ssh/claude_github_key git@github.com

# Set Python path for session
export PYTHONPATH="/data/openpilot/.local/lib/python3.11/site-packages:$PYTHONPATH"
```

## Warning Signs You're Doing It Wrong

- Any path with `/home/comma/` in it
- Using `pip install --user`
- Putting configs in `~/.config/`
- SSH keys in `~/.ssh/`
- Assuming files will persist without checking

Remember: When in doubt, test with a reboot!