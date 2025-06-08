# Longitudinal Control Communication Debugging Strategy

## Overview

When longitudinal control engagement triggers communication errors, it typically indicates timing issues, missing data, or process failures in the critical service chain. This document provides a systematic approach to diagnose and resolve these issues.

## The Communication Error

The error you're seeing is likely:
- **"Communication Issue Between Processes"** (`EventName.commIssue`)
- **"Low Communication Rate Between Processes"** (`EventName.commIssueAvgFreq`)

These are triggered in `controlsd.py` when service health checks fail.

## Critical Service Chain for Longitudinal Control

```
CAN Bus → pandad → carState → modelV2/radarState → longitudinalPlan → controlsState → carControl
```

Each service depends on data from previous services, and timing is critical.

## Diagnostic Tools

### 1. **Live Communication Diagnostics** (`live_comm_diagnosis.py`)
Real-time dashboard showing service health during longitudinal engagement.

**Usage:**
```bash
cd /data/openpilot
python3 tools/debug/live_comm_diagnosis.py
```

**What to look for:**
- Services marked with ✗ (not alive, invalid data, or frequency issues)
- Actual Hz vs Expected Hz mismatches
- Services that go invalid right when you engage longitudinal
- Pattern of failures (single service vs cascade)

### 2. **Longitudinal Communication Analyzer** (`longitudinal_comm_analyzer.py`)
Deep timing analysis and dependency tracking.

**Usage:**
```bash
cd /data/openpilot
python3 tools/debug/longitudinal_comm_analyzer.py
```

**What to look for:**
- High jitter warnings (>20% of expected period)
- Dependency failures (services updating without fresh dependency data)
- Sequence violations (out-of-order updates)
- State transitions coinciding with failures

### 3. **Built-in Communication Issue Checker**
```bash
cd /data/openpilot
python3 tools/debug/comm_issue_checker.py
```

This logs detailed information to `/data/openpilot_debug_comms.log` when communication issues occur.

## Common Root Causes and Solutions

### 1. **CAN Bus Issues**
**Symptoms:**
- `carState` has frequency issues or invalid data
- `pandaStates` shows CAN errors

**Diagnosis:**
```bash
# Check CAN health
python3 selfdrive/debug/can_printer.py | grep -E "err|timeout|invalid"
```

**Solutions:**
- Check physical CAN connections
- Verify CAN baudrate matches vehicle
- Check for electromagnetic interference

### 2. **CPU/Resource Constraints**
**Symptoms:**
- Multiple services with frequency issues
- High CPU usage when engaging longitudinal
- `deviceState` shows high CPU or memory usage

**Diagnosis:**
```bash
# Monitor CPU during engagement
python3 selfdrive/debug/live_cpu_and_temp.py
```

**Solutions:**
- Close unnecessary processes
- Check thermal throttling
- Reduce model complexity if using custom models

### 3. **Planning Chain Failures**
**Symptoms:**
- `longitudinalPlan` invalid or low frequency
- `modelV2` or `radarState` issues

**Diagnosis:**
- Check if model is outputting valid plans
- Verify radar data (if not radarless)
- Check calibration status

### 4. **Timing/Synchronization Issues**
**Symptoms:**
- Services updating out of order
- High jitter in service updates
- Dependency failures in analyzer

**Solutions:**
- Check system clock stability
- Verify no custom code affecting timing
- Check for priority inversions

## Step-by-Step Debugging Process

1. **Start the live diagnostics tool** before attempting to engage:
   ```bash
   python3 tools/debug/live_comm_diagnosis.py
   ```

2. **Attempt to engage longitudinal control** while watching the dashboard

3. **Note which services fail first** - this usually indicates the root cause

4. **If the issue is intermittent**, run the analyzer for extended period:
   ```bash
   python3 tools/debug/longitudinal_comm_analyzer.py
   ```

5. **Check the generated logs**:
   - `/data/longitudinal_comm_diag_*.json` - Diagnostic snapshot
   - `/data/longitudinal_comm_analysis_*.log` - Timing analysis
   - `/data/openpilot_debug_comms.log` - Detailed comm issue log

6. **Common patterns to look for**:
   - **Single service failure**: Usually indicates specific process issue
   - **Cascade failure**: Often starts with CAN or system resource issue
   - **Intermittent failures**: Typically timing or CPU issues
   - **Immediate failure on engagement**: Often calibration or configuration issue

## Advanced Debugging

### Check Process Health
```bash
# See which processes are actually running
ps aux | grep -E "pandad|plannerd|controlsd|modeld"
```

### Monitor Message Flow
```bash
# Watch specific service updates
while true; do 
  echo -n "carState: "; timeout 0.1 nc -l -u -p 8002 | wc -c
  echo -n "longitudinalPlan: "; timeout 0.1 nc -l -u -p 8018 | wc -c
  sleep 0.1
done
```

### Force Service Restart
If a specific service is problematic:
```python
from common.params import Params
Params().put_bool("IsOffroad", True)  # This will restart services
time.sleep(5)
Params().put_bool("IsOffroad", False)
```

## Preventive Measures

1. **Ensure proper initialization sequence** - Don't engage immediately after boot
2. **Wait for calibration completion** before engaging
3. **Monitor system resources** - High CPU/memory can cause timing issues
4. **Check vehicle compatibility** - Some vehicles have known CAN issues
5. **Verify hardware** - USB connection quality affects CAN reliability

## When to Report

If debugging reveals:
- Consistent service crashes
- Unexplained timing anomalies
- Hardware-specific patterns

Collect all diagnostic logs and create an issue with:
- Vehicle make/model/year
- Diagnostic outputs
- Steps to reproduce
- Any custom modifications

Remember: Communication issues are often symptoms of deeper problems. The key is identifying which service fails first and why.