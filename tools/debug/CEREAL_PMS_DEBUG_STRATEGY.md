# Cereal/PMS Communication Debugging Strategy

## Overview

When custom cereal messages are added to openpilot, they can cause communication issues if not properly configured. This guide focuses on debugging problems specific to Publisher/Subscriber (PMS) configurations.

## Custom Messages in This Fork

This fork includes several custom cereal messages:

### FrogPilot Messages:
- `frogpilotCarControl` (100Hz)
- `frogpilotCarState` (100Hz)
- `frogpilotDeviceState` (2Hz)
- `frogpilotNavigation` (1Hz)
- `frogpilotPlan` (20Hz)

### Chauffeur Messages:
- `chauffeurHKGTuning` (100Hz)
- `chauffeurTurnSpeedControl` (20Hz)
- `liveMapData` (various rates)

## Common PMS Issues That Cause Communication Errors

### 1. **Multiple Publishers to Same Service**
**Symptoms:**
- Intermittent data corruption
- Services showing as "alive" but data is invalid
- Communication errors during state transitions

**Example:**
```python
# BAD: Two different processes publishing to same service
# In controlsd.py:
pm.send('frogpilotCarControl', msg)

# In frogpilot_process.py:
pm.send('frogpilotCarControl', different_msg)  # CONFLICT!
```

### 2. **Missing Service Registration**
**Symptoms:**
- Service never shows as "alive"
- SubMaster initialization fails
- "Service not found" errors

**Fix:**
```python
# In cereal/services.py, ensure service is registered:
SERVICE_LIST = {
    # ...
    "myCustomService": (True, 20., 5),  # (should_log, frequency_hz, decimation)
}
```

### 3. **Frequency Conflicts**
**Symptoms:**
- Services fighting for timing slots
- Jittery updates
- One service starving another

**Common conflict pairs:**
- `carState` (100Hz) vs `frogpilotCarState` (100Hz)
- `longitudinalPlan` (20Hz) vs `frogpilotPlan` (20Hz)

### 4. **PubMaster Not Including Custom Services**
**Symptoms:**
- Custom services never publish
- "Publisher not initialized" errors

**Fix:**
```python
# Ensure PubMaster includes all services it will publish:
pm = messaging.PubMaster(['controlsState', 'frogpilotCarControl', 'carControl'])
```

### 5. **SubMaster Missing Dependencies**
**Symptoms:**
- Subscriber doesn't receive updates
- `sm.updated['service']` always False

**Fix:**
```python
# Include all services you need to subscribe to:
sm = messaging.SubMaster(['carState', 'frogpilotPlan', 'modelV2'])
```

## Diagnostic Tools

### 1. **Cereal Message Diagnostics** (`cereal_message_diagnostics.py`)
Monitors custom services and detects conflicts.

```bash
cd /data/openpilot
python3 tools/debug/cereal_message_diagnostics.py
```

**Features:**
- Tracks all custom service status
- Detects publishing conflicts
- Monitors message sizes
- Identifies socket errors
- Shows timing conflicts

### 2. **Cereal Message Validator** (`validate_cereal_messages.py`)
Static analysis of cereal configuration.

```bash
python3 tools/debug/validate_cereal_messages.py
```

**Checks:**
- Service registration
- Publisher conflicts
- Frequency validation
- Dependency checking
- Common mistake detection

### 3. **Live Communication Diagnostics** (updated)
```bash
python3 tools/debug/live_comm_diagnosis.py
```

Now includes monitoring for custom services and PMS conflicts.

## Debugging Process

### Step 1: Validate Configuration
```bash
# First, check static configuration
python3 tools/debug/validate_cereal_messages.py
```

Look for:
- ❌ ERRORS - These must be fixed
- ⚠️ WARNINGS - These likely cause issues
- ✓ INFO - Confirmations of correct setup

### Step 2: Monitor Runtime Behavior
```bash
# Run cereal diagnostics while attempting to engage
python3 tools/debug/cereal_message_diagnostics.py
```

Watch for:
- CONFLICT alerts between services
- PUBLISHING ISSUES with custom services
- SOCKET ERRORS indicating ZMQ problems

### Step 3: Check Specific Service
If a specific service is problematic:

```python
# Quick test script
import cereal.messaging as messaging
import time

# Try to subscribe
sm = messaging.SubMaster(['frogpilotPlan'])

for _ in range(50):
    sm.update(100)
    print(f"alive: {sm.alive['frogpilotPlan']}, "
          f"valid: {sm.valid['frogpilotPlan']}, "
          f"updated: {sm.updated['frogpilotPlan']}")
    time.sleep(0.1)
```

### Step 4: Find Publisher Issues
```bash
# Search for all pm.send calls
cd /data/openpilot
grep -r "pm\.send.*frogpilot" --include="*.py" .
```

## Common Fixes

### Fix 1: Ensure Single Publisher
Each service should have exactly ONE publisher:

```python
# BAD:
class Process1:
    def __init__(self):
        self.pm = messaging.PubMaster(['frogpilotPlan'])
    
class Process2:
    def __init__(self):
        self.pm = messaging.PubMaster(['frogpilotPlan'])  # CONFLICT!

# GOOD:
# Only ONE process should publish to frogpilotPlan
```

### Fix 2: Coordinate Related Services
If you have overlapping services (e.g., `frogpilotPlan` and `longitudinalPlan`):

```python
# Option 1: Use only one
if use_frogpilot:
    pm.send('frogpilotPlan', msg)
else:
    pm.send('longitudinalPlan', msg)

# Option 2: Ensure they don't conflict
# Publish to different services based on state
```

### Fix 3: Fix Registration Order
Services must be registered before use:

```python
# In services.py - ensure custom services are added
SERVICE_LIST = {
    # Standard services first
    "carState": (True, 100., 1),
    # ...
    # Custom services
    "frogpilotCarControl": (True, 100., 10),
}
```

### Fix 4: Handle Missing Services Gracefully
```python
# When subscribing to optional services
try:
    sm = messaging.SubMaster(['carState', 'frogpilotPlan'])
except Exception as e:
    # Fall back to standard services only
    sm = messaging.SubMaster(['carState', 'longitudinalPlan'])
```

## Quick Diagnostic Commands

```bash
# 1. Check if custom services are registered
python3 -c "from cereal.services import SERVICE_LIST; print([s for s in SERVICE_LIST if 'frog' in s or 'chauffeur' in s])"

# 2. Monitor specific service
python3 -c "import cereal.messaging as messaging; sm = messaging.SubMaster(['frogpilotPlan']); [sm.update(100) or print(f'alive: {sm.alive}, updated: {sm.updated}') for _ in range(20)]"

# 3. Find all publishers
grep -r "PubMaster\|pm\.send" --include="*.py" . | grep -E "frogpilot|chauffeur"

# 4. Check for service conflicts
python3 tools/debug/validate_cereal_messages.py | grep -A5 "Multiple publishers"
```

## Prevention

1. **Always register services** in `cereal/services.py` before use
2. **One publisher per service** - enforce this strictly
3. **Check for conflicts** when adding similar services
4. **Test with diagnostics** after adding new messages
5. **Use unique service names** to avoid confusion
6. **Document service ownership** - who publishes what

## Emergency Recovery

If communication is completely broken:

```bash
# 1. Kill all openpilot processes
pkill -f "python.*openpilot"

# 2. Clear any stale sockets
rm -f /tmp/comma*

# 3. Restart with minimal services
# Temporarily disable custom services to isolate issue
```

Remember: Most cereal/PMS issues come from:
- Multiple publishers to same service (most common!)
- Services not properly registered
- Missing dependencies in SubMaster
- Timing conflicts between similar services

Use the diagnostic tools to identify which pattern you're hitting.