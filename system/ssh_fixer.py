#!/usr/bin/env python3
"""
SSH Fix Service - Ensures SSH access remains available
Runs periodically to check and fix SSH configuration
"""

import time
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime
from common.swaglog import cloudlog
from common.params import Params

SSH_CHECK_INTERVAL = 300  # Check every 5 minutes
GITHUB_USERNAME_FILE = "/data/persist/comma/ssh/github_username"


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


def get_github_username():
    """Get GitHub username from persist location or params."""
    try:
        # First check persist location (survives uninstalls)
        username_file = Path(GITHUB_USERNAME_FILE)
        if username_file.exists():
            username = username_file.read_text().strip()
            if username:
                return username
        
        # Fall back to params
        params = Params()
        username = params.get("GithubUsername", encoding='utf-8')
        if username:
            # Save to persist for future use
            username_file.parent.mkdir(parents=True, exist_ok=True)
            username_file.write_text(username)
            return username
        
        return None
    except Exception as e:
        cloudlog.error(f"Error getting GitHub username: {e}")
        return None


def fetch_github_keys(username):
    """Fetch current SSH keys from GitHub."""
    try:
        url = f"https://github.com/{username}.keys"
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status == 200:
                keys = response.read().decode('utf-8').strip()
                return keys if keys else None
        return None
    except Exception as e:
        cloudlog.error(f"Error fetching GitHub keys: {e}")
        return None


def check_ssh_access():
    """Check if SSH is properly configured with the CURRENT GitHub keys."""
    try:
        # Get the GitHub username
        username = get_github_username()
        if not username:
            cloudlog.warning("No GitHub username configured")
            return False
        
        # Check if authorized_keys exists
        authorized_keys_path = Path("/data/persist/comma/authorized_keys")
        if not authorized_keys_path.exists():
            cloudlog.warning("authorized_keys missing from persist location")
            return False
        
        # Fetch current keys from GitHub
        current_github_keys = fetch_github_keys(username)
        if not current_github_keys:
            cloudlog.warning(f"Could not fetch keys for {username} from GitHub")
            # If we can't fetch, assume current config is OK (don't break working SSH)
            return True
        
        # Read current authorized_keys
        current_authorized = authorized_keys_path.read_text().strip()
        
        # Compare keys (normalize whitespace)
        github_lines = set(line.strip() for line in current_github_keys.split('\n') if line.strip())
        authorized_lines = set(line.strip() for line in current_authorized.split('\n') if line.strip())
        
        if github_lines != authorized_lines:
            cloudlog.warning(f"GitHub keys for {username} don't match authorized_keys")
            log_to_error_file(f"GitHub keys changed for {username} - update needed")
            return False
        
        # Also ensure keys are in OpenPilot locations for consistency
        persist_keys = Path("/data/persist/comma/ssh/GithubSshKeys")
        if not persist_keys.exists():
            cloudlog.warning("Keys missing from persist SSH directory")
            return False
        
        return True
    except Exception as e:
        cloudlog.error(f"Error checking SSH access: {e}")
        # On error, assume config is OK to avoid breaking working SSH
        return True


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
    """Main loop - monitors GitHub SSH keys and keeps them in sync."""
    cloudlog.bind(daemon="ssh_fixer")
    cloudlog.info("SSH fixer service started")
    
    params = Params()
    last_fix_attempt = 0
    last_successful_check = 0
    startup_check_done = False
    
    # Log startup with username
    username = get_github_username()
    if username:
        log_to_error_file(f"SSH monitor started - tracking GitHub keys for: {username}")
    else:
        log_to_error_file("SSH monitor started - no GitHub username configured yet")
    
    while True:
        try:
            # Only check if SSH is enabled
            if params.get_bool("SshEnabled"):
                current_time = time.time()
                
                # Check SSH configuration (including GitHub key sync)
                if not check_ssh_access():
                    # On startup, fix immediately. Otherwise respect cooldown.
                    if not startup_check_done or (current_time - last_fix_attempt > 300):
                        username = get_github_username()
                        if username:
                            cloudlog.warning(f"SSH keys out of sync for {username}")
                            log_to_error_file(f"Updating SSH keys from GitHub for {username}...")
                        else:
                            cloudlog.warning("SSH broken - no GitHub username")
                            log_to_error_file("SSH broken - no GitHub username configured")
                        
                        if run_ssh_fix():
                            cloudlog.info("SSH keys synchronized successfully")
                            log_to_error_file("SUCCESS: SSH keys updated from GitHub")
                        else:
                            cloudlog.error("Failed to sync SSH keys")
                            log_to_error_file("ERROR: Failed to sync keys - use Fix SSH button")
                        
                        last_fix_attempt = current_time
                else:
                    # Log successful checks periodically
                    if current_time - last_successful_check > 3600:  # Every hour
                        username = get_github_username()
                        if username:
                            log_to_error_file(f"SSH keys verified - in sync with GitHub ({username})")
                        last_successful_check = current_time
                
                startup_check_done = True
            
            # Check every 5 minutes
            time.sleep(SSH_CHECK_INTERVAL)
            
        except Exception as e:
            cloudlog.error(f"SSH fixer error: {e}")
            log_to_error_file(f"SSH fixer error: {e}")
            time.sleep(60)  # Retry sooner on error


if __name__ == "__main__":
    main()