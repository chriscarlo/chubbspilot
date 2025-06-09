# Root Cause Analysis: Concierge Service Failure After TICI Reboot

**Date:** January 9, 2025  
**Severity:** High  
**Service Affected:** Concierge Web Server  
**Environment:** TICI Device (aarch64)

## Executive Summary

The Concierge web service failed to start after a TICI device reboot due to missing Python dependencies. The service had been working correctly but Python packages installed via pip were not persistent across reboots.

## Timeline

- **Pre-reboot**: Concierge service running successfully, serving requests on port 8091
- **Reboot**: TICI device rebooted
- **Post-reboot**: Concierge service failed to start
- **05:14 UTC**: Dependencies manually reinstalled
- **05:16 UTC**: Service restored and verified operational

## Root Cause

The TICI device's `/home/comma` directory is not persistent across reboots. This causes multiple critical issues:

1. **Python packages** installed using pip are lost
2. **SSH keys** stored in `~/.ssh/` are deleted
3. Any user-specific configuration in the home directory is wiped

The following critical dependencies were lost:
- pydantic
- fastapi
- uvicorn
- jinja2
- SSH keys (`~/.ssh/claude_github_key*`)

## Technical Details

### Failure Mode
1. The `main_wrapper.py` successfully checked for dependencies but reported them as available (stale log)
2. When attempting to import modules in `main.py`, Python raised `ModuleNotFoundError`
3. The wrapper's import checking may have been checking a different Python environment

### Dependencies Installed
```
pydantic-2.11.5
fastapi-0.115.12
uvicorn-0.34.3
jinja2-3.1.3 (was already available)
```

Plus supporting packages: annotated-types, anyio, starlette, h11, httptools, python-dotenv, uvloop, watchfiles, websockets

### Installation Method
```bash
pip3 install --user pydantic fastapi uvicorn[standard] jinja2
```

## Impact

- Concierge web interface was unavailable
- SSH access to GitHub repository lost (cannot push commits)
- No data loss occurred (logs in `/data` persisted)
- Service logs continued to be written
- Other openpilot services were unaffected
- Development workflow severely impacted

## Immediate Fix

1. Manually installed missing dependencies using `pip3 install --user`
2. Verified service could start and respond to requests
3. Documented fix in CHANGELOG.md

## Long-term Recommendations

### 1. Persistent Storage Strategy (Priority: CRITICAL)
- Store secrets/keys in `/persist/` (only 27MB available - use wisely!)
- Store dependencies in `/data/openpilot/` (part of git repo)
- Create `/persist/comma/.ssh/` for SSH keys
- Use `/data/openpilot/.local/` for Python packages
- Symlink from home directory to persistent locations

### 2. Persistent Dependencies (Priority: HIGH)
- Add Concierge dependencies to the TICI system image
- OR create a startup script that ensures dependencies are installed
- OR use Poetry/requirements.txt in a way that survives reboots
- Install Python packages to `/data/.local/` instead of home

### 3. Improve Dependency Checking (Priority: MEDIUM)
- Fix `main_wrapper.py` to properly validate imports in the same environment
- Add explicit Python path checking
- Log the specific Python interpreter being used

### 4. Add Monitoring (Priority: MEDIUM)
- Implement health checks that detect missing dependencies
- Add alerts when Concierge fails to start
- Monitor service availability from the UI

### 5. Startup Resilience (Priority: LOW)
- Implement automatic dependency installation on startup
- Add retry logic with exponential backoff
- Better error reporting to UI when service is down

## Lessons Learned

1. **TICI Environment**: `/home/comma` directory is ephemeral - wiped on every reboot
2. **Critical Files**: SSH keys, Python packages, and user configs must be stored in `/data`
3. **Dependency Management**: Need a more robust solution for Python dependencies on embedded devices
4. **Monitoring**: Silent failures can go unnoticed without proper health checks
5. **Documentation**: Need to document TICI-specific deployment requirements
6. **Development Impact**: Loss of SSH keys breaks git workflow completely

## Action Items

- [ ] **CRITICAL**: Move SSH keys to `/persist/comma/.ssh/` with symlinks
- [ ] **CRITICAL**: Create persistent storage strategy for TICI
- [ ] Implement persistent dependency solution
- [ ] Add dependency installation to boot sequence
- [ ] Improve error handling in main_wrapper.py
- [ ] Document TICI deployment requirements
- [ ] Add service health monitoring to UI
- [ ] Create boot script to restore critical files/symlinks

## References

- Original implementation: See `agentDocumentation/CHANGELOG.md` (January 8, 2025 entries)
- Service configuration: `system/manager/process_config.py`
- Wrapper script: `selfdrive/chauffeur/concierge/main_wrapper.py`