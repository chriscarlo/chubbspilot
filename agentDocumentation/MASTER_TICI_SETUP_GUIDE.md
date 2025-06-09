# Complete TICI Setup Guide
**The Definitive Guide for Chauffeur OpenPilot on TICI Devices**

---

## 🚨 **Critical TICI Facts**

**TICI devices have unique filesystem behavior that breaks standard Linux assumptions:**

1. **`/home/comma/` is EPHEMERAL** - Wiped on every reboot
2. **`/persist/` is persistent** - But only 27MB capacity 
3. **`/data/` is persistent** - Large capacity for packages/files
4. **Root filesystem is read-only** - Special mount points for persistence

**If you ignore these facts, you will lose all your work on reboot.**

---

## 🎯 **Quick Start (TL;DR)**

```bash
# 1. First-time setup (run once)
bash /data/openpilot/scripts/tici_bootstrap.sh

# 2. Install boot service (run once)  
bash /data/openpilot/scripts/install_tici_service.sh

# 3. Verify everything works
bash /data/openpilot/scripts/verify_all_deps.sh

# 4. Copy SSH keys (if not already done)
scp ~/.ssh/claude_github_key* comma@TICI_IP:/persist/comma/.ssh/
```

**That's it!** Everything will now survive reboots automatically.

---

## 📋 **Detailed Setup Process**

### **Step 1: Initial TICI Bootstrap**

The bootstrap script handles all first-time setup:

```bash
cd /data/openpilot
bash scripts/tici_bootstrap.sh
```

**What it does:**
- ✅ Creates persistent directories (`/persist/comma/.ssh/`, `/data/openpilot/.local/`)
- ✅ Installs Python dependencies to persistent location
- ✅ Configures git to use persistent SSH keys
- ✅ Sets up persistent bashrc with aliases and environment
- ✅ Performs health checks and validation

### **Step 2: SSH Key Setup**

**Option A - Copy existing keys:**
```bash
# From your dev machine:
scp ~/.ssh/claude_github_key* comma@TICI_IP:/persist/comma/.ssh/

# On TICI, fix permissions:
chmod 700 /persist/comma/.ssh
chmod 600 /persist/comma/.ssh/claude_github_key
chmod 644 /persist/comma/.ssh/claude_github_key.pub
```

**Option B - Generate new keys on TICI:**
```bash
ssh-keygen -t ed25519 -f /persist/comma/.ssh/claude_github_key -C "tici@chauffeur.dev"
# Add public key to GitHub
```

### **Step 3: Auto-Boot Service Installation**

Install the systemd service for automatic setup after reboots:

```bash
bash scripts/install_tici_service.sh
```

**What it does:**
- ✅ Installs systemd service file
- ✅ Enables service to run on every boot
- ✅ Tests service immediately
- ✅ Shows status and logs

### **Step 4: Verification**

Run comprehensive verification:

```bash
bash scripts/verify_all_deps.sh
```

**This checks:**
- ✅ Environment detection (TICI vs dev)
- ✅ Persistent storage setup
- ✅ Python dependencies (critical and optional)
- ✅ Git SSH configuration
- ✅ GitHub connectivity
- ✅ Service-specific dependencies (Concierge)
- ✅ Bootstrap scripts availability
- ✅ Auto-boot service status

---

## 🔧 **Persistent Storage Strategy**

### **`/persist/` Directory (27MB limit)**
**Use for:** Secrets, configs, small files that shouldn't be in git

```
/persist/
├── comma/
│   ├── .ssh/              # SSH keys
│   ├── .bashrc_persistent # Environment setup
│   └── .gitconfig         # Git config backup
├── azure_conn_string      # API keys
└── mapbox/                # Other secrets
```

### **`/data/openpilot/` Directory (Large capacity)**
**Use for:** Dependencies, packages, logs, project files

```
/data/openpilot/
├── .local/
│   └── lib/python3.11/site-packages/  # All pip packages
├── scripts/              # Bootstrap scripts
├── agentDocumentation/   # This guide
└── [project files]       # Source code
```

### **Python Package Management**

**✅ Correct (Persistent):**
```bash
pip3 install --target=/data/openpilot/.local/lib/python3.11/site-packages <package>
```

**❌ Wrong (Ephemeral):**
```bash
pip3 install --user <package>  # Goes to /home/comma/.local/ - WIPED ON REBOOT
```

### **Environment Setup**

Add to your scripts:
```python
import sys
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
```

Or use environment variable:
```bash
export PYTHONPATH="/data/openpilot/.local/lib/python3.11/site-packages:$PYTHONPATH"
```

---

## 🚀 **Available Commands**

After bootstrap, these aliases are available:

```bash
# Quick commands
tici-bootstrap          # Re-run full bootstrap
tici-deps <package>     # Install package to persistent location
verify-all-deps         # Run comprehensive verification

# Shortcuts
cdop                    # cd /data/openpilot
ll                      # ls -la
gitlog                  # git log --oneline -10
gitstatus               # git status
```

---

## 🔄 **What Happens on Reboot**

### **Automatic (via systemd service):**
1. `tici-auto-setup.service` runs at boot
2. Restores git SSH configuration
3. Sets up Python paths
4. Loads persistent environment

### **Aliases and Environment:**
- Persistent bashrc is sourced automatically
- All aliases and Python paths are restored
- No manual intervention required

---

## 🔍 **Troubleshooting**

### **SSH Keys Missing After Reboot**
```bash
# Check persistent location
ls -la /persist/comma/.ssh/

# Reconfigure git if keys exist
git config --global core.sshCommand "ssh -i /persist/comma/.ssh/claude_github_key -o StrictHostKeyChecking=no"

# Test connection
ssh -T -i /persist/comma/.ssh/claude_github_key git@github.com
```

### **Python Packages Missing**
```bash
# Check persistent location
ls /data/openpilot/.local/lib/python3.11/site-packages/

# Reinstall if needed
python3 /data/openpilot/system/ensure_dependencies.py

# Or run bootstrap again
tici-bootstrap
```

### **Service Not Running**
```bash
# Check service status
sudo systemctl status tici-auto-setup

# View logs
sudo journalctl -u tici-auto-setup -f

# Restart service
sudo systemctl restart tici-auto-setup

# Reinstall service
bash /data/openpilot/scripts/install_tici_service.sh
```

### **Dependencies Still Missing**
```bash
# Run comprehensive check
verify-all-deps

# Try alternative installation
sudo pip3 install <package>

# Check specific service
python3 -c "import pydantic, fastapi, uvicorn, jinja2; print('Concierge deps OK')"
```

---

## 📚 **Background: Why This Setup Is Necessary**

### **The TICI Ephemeral Home Problem**

Traditional Linux systems have persistent home directories. TICI devices use:
- **Read-only root filesystem** for stability
- **Overlay filesystem** for /home that's rebuilt on boot
- **Specific mount points** for persistence

This causes:
- ❌ SSH keys in `~/.ssh/` are lost
- ❌ Python packages from `pip install --user` are lost  
- ❌ Git configuration is lost
- ❌ All user configs in `/home/comma/` are lost

### **Our Solution: Persistence-First Architecture**

1. **Secrets → `/persist/`** - SSH keys, API tokens, configs
2. **Dependencies → `/data/openpilot/`** - Python packages, project files
3. **Auto-restore → systemd service** - Reconfigure on every boot
4. **Verification → comprehensive checks** - Ensure everything works

### **Multi-Layered Dependency Management**

1. **`tici_bootstrap.sh`** - First-time comprehensive setup
2. **`tici_auto_setup.sh`** - Quick boot-time restoration
3. **`ensure_dependencies.py`** - System-wide package management
4. **Service wrappers** - Application-specific dependency handling

---

## 📖 **Reference Documentation**

For deep technical details, see:

- **`TICI_PERSISTENCE_POSTMORTEM.md`** - Original incident analysis
- **`CONCIERGE_REBOOT_RCA.md`** - Service failure root cause analysis  
- **`CRITICAL_RUNTIME_DEPENDENCIES.md`** - Complete dependency analysis
- **`CLAUDE.md`** - Agent instructions with TICI rules

---

## ✅ **Validation Checklist**

Use this checklist after setup or reboot:

- [ ] SSH keys present in `/persist/comma/.ssh/`
- [ ] Git SSH configuration points to persistent keys
- [ ] GitHub SSH authentication works
- [ ] Python packages in `/data/openpilot/.local/lib/python3.11/site-packages/`
- [ ] Critical packages importable (pydantic, fastapi, uvicorn, jinja2)
- [ ] Persistent bashrc loaded (aliases work)
- [ ] Auto-setup service enabled and active
- [ ] Comprehensive verification passes

**Command to check all:**
```bash
verify-all-deps
```

---

## 🎉 **Success Criteria**

**Your TICI setup is complete when:**

1. ✅ **Fresh install works** - Bootstrap script succeeds
2. ✅ **Reboots work** - Everything persists across reboots  
3. ✅ **Dependencies work** - All critical packages available
4. ✅ **Git works** - Can commit and push without manual setup
5. ✅ **Services work** - Concierge and other services start successfully
6. ✅ **Verification passes** - `verify-all-deps` shows green

**The goal: Zero manual intervention after initial setup, ever.**