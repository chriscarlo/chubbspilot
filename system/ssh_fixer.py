#!/usr/bin/env python3
"""
SSH Fix Service - Ensures SSH access remains available
Runs periodically to check and fix SSH configuration
"""

import time
import subprocess
from pathlib import Path
from datetime import datetime
from openpilot.common.swaglog import cloudlog
from openpilot.common.params import Params

SSH_CHECK_INTERVAL = 300  # Check every 5 minutes


def log_to_error_file(message):
    """Write log message to error.txt for UI visibility."""
    try:
        crashes_dir = Path("/data/crashes")
        crashes_dir.mkdir(parents=True, exist_ok=True)
        error_file = crashes_dir / "error.txt"
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = f"\n[{timestamp}] [SSH-FIXER] {message}\n"
        
        if error_file.exists():
            existing = error_file.read_text()
            if len(existing) > 50000:
                existing = existing[-40000:]
            error_file.write_text(existing + log_content)
        else:
            error_file.write_text(log_content)
    except Exception as e:
        cloudlog.error(f"Failed to write to error log: {e}")


def check_ssh_access():
    """Check if SSH is ACTUALLY WORKING by verifying the AGNOS authorized_keys file."""
    try:
        # The ONLY thing that matters for AGNOS SSH is if authorized_keys exists
        # and has the right keys in /data/persist/comma/
        authorized_keys_path = Path("/data/persist/comma/authorized_keys")
        
        if not authorized_keys_path.exists():
            cloudlog.warning("authorized_keys missing from persist location")
            return False
            
        if authorized_keys_path.stat().st_size < 100:  # SSH keys are typically >200 bytes
            cloudlog.warning("authorized_keys file too small, likely corrupted")
            return False
            
        # Also check the persist SSH directory has the right structure
        persist_ssh_dir = Path("/data/persist/comma/ssh")
        if not persist_ssh_dir.exists():
            cloudlog.warning("persist SSH directory missing")
            return False
            
        # If we have keys in params but not in persist, SSH is broken
        params_keys = Path("/data/params/d/GithubSshKeys")
        persist_keys = Path("/data/persist/comma/ssh/GithubSshKeys")
        
        if params_keys.exists() and not persist_keys.exists():
            cloudlog.warning("Keys exist in params but not in persist - SSH is broken")
            return False
            
        return True
    except Exception as e:
        cloudlog.error(f"Error checking SSH access: {e}")
        return False


def run_ssh_fix():
    """Run the SSH fix script."""
    try:
        cloudlog.info("Running SSH fix script...")
        log_to_error_file("Running SSH fix script...")
        
        result = subprocess.run(
            ["sudo", "python3", "/data/openpilot/selfdrive/ui/qt/network/fix_ssh_simple.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            cloudlog.info(f"SSH fix completed: {result.stdout}")
            log_to_error_file(f"SSH fix completed successfully. Check detailed logs above.")
            return True
        else:
            cloudlog.error(f"SSH fix failed: {result.stderr}")
            log_to_error_file(f"SSH fix failed: {result.stderr}")
            return False
    except Exception as e:
        cloudlog.error(f"Exception running SSH fix: {e}")
        log_to_error_file(f"Exception running SSH fix: {e}")
        return False


def main():
    """Main loop - monitors and fixes SSH access to prevent lockouts."""
    cloudlog.bind(daemon="ssh_fixer")
    cloudlog.info("SSH fixer service started")
    log_to_error_file("SSH fixer service started - monitoring AGNOS SSH configuration")
    
    params = Params()
    last_fix_attempt = 0
    startup_check_done = False
    
    while True:
        try:
            # Only check if SSH is enabled
            if params.get_bool("SshEnabled"):
                current_time = time.time()
                
                # Check if SSH is ACTUALLY working (authorized_keys in persist location)
                if not check_ssh_access():
                    # On startup, fix immediately. Otherwise respect cooldown.
                    if not startup_check_done or (current_time - last_fix_attempt > 300):
                        cloudlog.warning("SSH is broken - authorized_keys missing or corrupted")
                        log_to_error_file("CRITICAL: SSH access broken - attempting repair...")
                        
                        if run_ssh_fix():
                            cloudlog.info("SSH access repaired successfully")
                            log_to_error_file("SUCCESS: SSH access restored - authorized_keys rebuilt")
                        else:
                            cloudlog.error("Failed to repair SSH access")
                            log_to_error_file("ERROR: SSH repair failed - use Fix SSH button in UI")
                        
                        last_fix_attempt = current_time
                
                startup_check_done = True
            
            # Check every 5 minutes
            time.sleep(SSH_CHECK_INTERVAL)
            
        except Exception as e:
            cloudlog.error(f"SSH fixer error: {e}")
            log_to_error_file(f"SSH fixer error: {e}")
            time.sleep(60)  # Retry sooner on error


if __name__ == "__main__":
    main()