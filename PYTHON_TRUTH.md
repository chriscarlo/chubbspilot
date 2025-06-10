# 🚨 PYTHON TRUTH - THE ONLY SOURCE OF TRUTH 🚨

**THIS DOCUMENT SUPERSEDES ALL OTHER PYTHON/DEPENDENCY INFORMATION**

## 1. Python Version
- **ONLY USE**: `/home/chris/.pyenv/versions/3.11.4/bin/python3`
- **VERSION**: Python 3.11.4
- **NEVER USE**: System Python 3.12 at `/usr/bin/python3`

## 2. Package Installation
```bash
# THE ONLY CORRECT WAY TO INSTALL PACKAGES
/home/chris/.pyenv/versions/3.11.4/bin/python3 -m pip install \
  --target=/data/openpilot/.local/lib/python3.11/site-packages \
  <package>
```

**NEVER DO THIS:**
- ❌ `pip install <package>` 
- ❌ `pip3 install <package>`
- ❌ `pip install --user <package>`
- ❌ `sudo pip install <package>`

## 3. PYTHONPATH
```bash
# ALWAYS SET THIS BEFORE RUNNING PYTHON
export PYTHONPATH="/data/openpilot:/data/openpilot/.local/lib/python3.11/site-packages"
```

## 4. In Python Scripts
```python
# ADD THIS TO THE TOP OF EVERY SCRIPT
import sys
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")
```

## 5. Why This Matters
- **TICI DEVICES**: `/home/comma` is EPHEMERAL - wiped on reboot
- **PERSISTENCE**: Only `/data/openpilot/` and `/persist/` survive reboots
- **WRONG PYTHON**: System pip3 uses Python 3.12, not our 3.11

## 6. Validation Check
```bash
# Run this to verify your environment
python3 --version  # Should show 3.11.4
which python3      # Should show /home/chris/.pyenv/shims/python3
echo $PYTHONPATH   # Should include both paths above
```

## 7. Common Mistakes
- Using `pip3` instead of explicit Python path
- Forgetting `--target` flag
- Not setting PYTHONPATH
- Using system Python locations

**IF YOU'RE UNSURE, REFER TO THIS DOCUMENT**