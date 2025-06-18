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
    """Check if SSH keys are properly configured."""
    persist_path = Path("/data/persist/comma/ssh/GithubSshKeys")
    standard_path = Path("/data/params/d/GithubSshKeys")
    
    # Check if keys exist in persistent location
    if persist_path.exists() and persist_path.stat().st_size > 0:
        return True
    
    # Check if keys exist in standard location
    if standard_path.exists() and standard_path.stat().st_size > 0:
        return True
    
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
    """Main loop - periodically check and fix SSH access."""
    cloudlog.bind(daemon="ssh_fixer")
    cloudlog.info("SSH fixer service started")
    log_to_error_file("SSH fixer service started")
    
    params = Params()
    last_fix_attempt = 0
    check_count = 0
    
    # CHECK IMMEDIATELY ON STARTUP - DON'T WAIT!
    cloudlog.info("Running initial SSH check on startup...")
    log_to_error_file("Running initial SSH check on startup...")
    
    if params.get_bool("SshEnabled") and not check_ssh_access():
        cloudlog.warning("SSH access appears broken on startup, attempting immediate fix...")
        log_to_error_file("SSH access appears broken on startup, attempting immediate fix...")
        
        if run_ssh_fix():
            cloudlog.info("SSH access restored on startup")
            log_to_error_file("SSH access restored on startup")
        else:
            log_to_error_file("SSH fix attempt failed on startup")
        
        last_fix_attempt = time.time()
    
    # Now enter the regular check loop
    while True:
        try:
            check_count += 1
            
            # Check if SSH is enabled
            if params.get_bool("SshEnabled"):
                # Check if SSH access is working
                if not check_ssh_access():
                    current_time = time.time()
                    # Avoid fixing too frequently
                    if current_time - last_fix_attempt > 60:
                        cloudlog.warning("SSH access appears broken, attempting fix...")
                        log_to_error_file(f"Check #{check_count}: SSH access appears broken, attempting fix...")
                        
                        if run_ssh_fix():
                            cloudlog.info("SSH access restored")
                            log_to_error_file("SSH access restored successfully")
                        else:
                            log_to_error_file("SSH fix attempt failed")
                        
                        last_fix_attempt = current_time
                else:
                    # Log periodically that SSH is working
                    if check_count % 12 == 0:  # Every hour
                        log_to_error_file(f"Check #{check_count}: SSH access is working properly")
            
            # Sleep before next check
            time.sleep(SSH_CHECK_INTERVAL)
            
        except Exception as e:
            cloudlog.error(f"SSH fixer error: {e}")
            log_to_error_file(f"SSH fixer error: {e}")
            time.sleep(60)  # Sleep shorter on error


if __name__ == "__main__":
    main()