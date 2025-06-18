#!/usr/bin/env python3
"""
Simplified SSH fix script that doesn't depend on compiled modules.
Works around Python version mismatches when running with sudo.
"""

import os
import sys
import subprocess
import urllib.request
import urllib.error
import json
from pathlib import Path
from datetime import datetime

# Global log storage
log_messages = []

def log(message, level="INFO"):
    """Log message to both console and internal storage."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"
    print(log_entry)
    log_messages.append(log_entry)

def write_logs_to_error_file():
    """Write all accumulated logs to the error.txt file that UI can display."""
    try:
        # Ensure crashes directory exists
        crashes_dir = Path("/data/crashes")
        try:
            crashes_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Try with sudo
            subprocess.run(["sudo", "mkdir", "-p", str(crashes_dir)], check=True)
            subprocess.run(["sudo", "chmod", "777", str(crashes_dir)], check=True)
        
        # Write to error.txt (viewable through UI)
        error_file = crashes_dir / "error.txt"
        ssh_log_content = "\n===== SSH FIX LOG (SIMPLE VERSION) =====\n"
        ssh_log_content += f"Execution Time: {datetime.now()}\n"
        ssh_log_content += "\n".join(log_messages)
        ssh_log_content += "\n\n"
        
        # Append to existing error.txt or create new
        if error_file.exists():
            existing_content = error_file.read_text()
            # Keep only last 50KB of logs to prevent file from growing too large
            if len(existing_content) > 50000:
                existing_content = existing_content[-40000:]
            error_file.write_text(existing_content + ssh_log_content)
        else:
            error_file.write_text(ssh_log_content)
        
        # Also write to a dedicated SSH log file
        ssh_log_file = crashes_dir / "ssh_fix_log.txt"
        ssh_log_file.write_text(ssh_log_content)
        
        return True
    except Exception as e:
        print(f"Failed to write logs to error file: {e}")
        return False

def run_command(cmd):
    """Execute a shell command and return the result."""
    log(f"Running command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            log(f"Command output: {result.stdout.strip()}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        log(f"Command failed with error: {e.stderr}", "ERROR")
        return False, e.stderr

def get_github_username():
    """Get GitHub username from various sources without using Params."""
    log("Looking for GitHub username...")
    
    # Try reading from the standard params location
    username_files = [
        "/data/params/d/GithubUsername",
        "/data/persist/comma/ssh/GithubUsername",
    ]
    
    for file_path in username_files:
        try:
            if Path(file_path).exists():
                username = Path(file_path).read_text().strip()
                if username:
                    log(f"Found username '{username}' in {file_path}")
                    return username
        except Exception as e:
            log(f"Error reading {file_path}: {e}", "WARNING")
    
    # If not found, check if we can extract from existing authorized_keys
    try:
        auth_keys_path = Path("/data/persist/comma/.ssh/authorized_keys")
        if auth_keys_path.exists():
            log("Checking authorized_keys for GitHub username comment...")
            content = auth_keys_path.read_text()
            # GitHub keys often have comments like "user@github"
            for line in content.split('\n'):
                if 'github.com' in line or '@github' in line:
                    # Try to extract username from comment
                    parts = line.split()
                    if len(parts) >= 3:
                        comment = parts[-1]
                        if '@' in comment:
                            possible_user = comment.split('@')[0]
                            log(f"Possible username from authorized_keys: {possible_user}")
                            # You might want to confirm this is correct
    except:
        pass
    
    return None

def ensure_directory_writable(path):
    """Ensure the directory exists and is writable."""
    log(f"Ensuring directory is writable: {path}")
    try:
        # Create directory if it doesn't exist
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                log(f"Created directory: {path}")
            except PermissionError:
                log("Permission denied, trying with sudo...")
                success, _ = run_command(f"sudo mkdir -p {path}")
                if success:
                    log(f"Created directory with sudo: {path}")
                    run_command(f"sudo chown -R $USER:$USER {path}")
                else:
                    log(f"Failed to create directory even with sudo: {path}", "ERROR")
                    return False
        else:
            log(f"Directory already exists: {path}")
        
        # Test writability
        test_file = path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
            log(f"Directory is writable: {path}")
            return True
        except Exception as e:
            log(f"Directory is not writable: {path} - {e}", "ERROR")
            # Try to make it writable with sudo
            success, _ = run_command(f"sudo chmod 755 {path}")
            if success:
                try:
                    test_file.touch()
                    test_file.unlink()
                    log(f"Directory is now writable after chmod: {path}")
                    return True
                except:
                    pass
            return False
    except Exception as e:
        log(f"Error ensuring directory writable: {e}", "ERROR")
        return False

def fix_ssh_access():
    """Main function to fix SSH access."""
    log("Starting SSH fix process (simple version)...")
    
    # Define paths
    persist_ssh_dir = Path("/data/persist/comma/ssh")
    legacy_params_dir = Path("/data/params/d")
    
    # Get GitHub username
    github_username = get_github_username()
    
    # HARDCODE FOR NOW IF NOT FOUND
    if not github_username:
        log("No GitHub username found in files, using hardcoded 'chriscarlo'", "WARNING")
        github_username = "chriscarlo"
    
    # Create persistent directory structure
    if not ensure_directory_writable(persist_ssh_dir):
        return False, f"Failed to create or write to persistent SSH directory: {persist_ssh_dir}"
    
    # Fetch SSH keys from GitHub
    try:
        log(f"Fetching SSH keys for {github_username} from GitHub...")
        url = f"https://github.com/{github_username}.keys"
        log(f"URL: {url}")
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                ssh_keys = response.read().decode('utf-8').strip()
                
                if not ssh_keys:
                    return False, f"No SSH keys found for GitHub user '{github_username}'"
                
                key_count = len(ssh_keys.split('\n'))
                log(f"Successfully fetched {key_count} SSH key(s)")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, f"GitHub username '{github_username}' not found"
            else:
                return False, f"Failed to fetch keys: HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return False, f"Network error fetching SSH keys: {e}"
    
    # Write to persistent location with sudo
    try:
        log("Writing SSH configuration to persistent location...")
        
        # Write files using sudo commands
        files_to_write = [
            ("GithubUsername", github_username),
            ("GithubSshKeys", ssh_keys),
            ("SshEnabled", "1")
        ]
        
        for filename, content in files_to_write:
            file_path = persist_ssh_dir / filename
            log(f"Writing {filename}...")
            
            # Write to temp file first
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            # Move with sudo
            success, _ = run_command(f"sudo mv {tmp_path} {file_path}")
            if success:
                run_command(f"sudo chmod 644 {file_path}")
                log(f"Wrote {filename} successfully")
            else:
                raise Exception(f"Failed to write {filename}")
        
    except Exception as e:
        return False, f"Failed to write SSH configuration: {e}"
    
    # Create symlinks for backward compatibility
    try:
        log("Creating backward compatibility symlinks...")
        run_command(f"sudo mkdir -p {legacy_params_dir}")
        
        for file in ["GithubUsername", "GithubSshKeys", "SshEnabled"]:
            legacy_path = legacy_params_dir / file
            persist_path = persist_ssh_dir / file
            
            # Remove existing file/link
            run_command(f"sudo rm -f {legacy_path}")
            
            # Create symlink
            success, _ = run_command(f"sudo ln -s {persist_path} {legacy_path}")
            if success:
                log(f"Created symlink for {file}")
    except Exception as e:
        log(f"Warning: Failed to create symlinks (non-critical): {e}", "WARNING")
    
    # Also copy to authorized_keys location that SSH daemon reads
    try:
        log("Copying keys to authorized_keys...")
        ssh_dir = Path("/data/persist/comma/.ssh")
        run_command(f"sudo mkdir -p {ssh_dir}")
        run_command(f"sudo chmod 700 {ssh_dir}")
        
        auth_keys_path = ssh_dir / "authorized_keys"
        
        # Write SSH keys to authorized_keys
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write(ssh_keys)
            tmp_path = tmp.name
        
        success, _ = run_command(f"sudo mv {tmp_path} {auth_keys_path}")
        if success:
            run_command(f"sudo chmod 600 {auth_keys_path}")
            # TICI uses root for SSH, not comma user
            run_command(f"sudo chown root:root {auth_keys_path}")
            log("SSH keys written to authorized_keys")
    except Exception as e:
        log(f"Warning: Failed to write authorized_keys: {e}", "WARNING")
    
    # Restart SSH service
    try:
        log("Restarting SSH service...")
        success, _ = run_command("sudo systemctl restart ssh")
        if not success:
            success, _ = run_command("sudo systemctl restart sshd")
        
        if success:
            log("SSH service restarted successfully")
    except Exception as e:
        log(f"Warning: Failed to restart SSH service: {e}", "WARNING")
    
    return True, f"SSH access fixed for user '{github_username}'"

if __name__ == "__main__":
    try:
        success, message = fix_ssh_access()
        
        # Always write logs to error file
        write_logs_to_error_file()
        
        print(f"\n{'Success' if success else 'Error'}: {message}")
        print("\nLogs have been written to /data/crashes/error.txt")
        print("You can view them in the UI: Settings -> Software -> Error Log")
        
        exit(0 if success else 1)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        
        log(f"CRITICAL ERROR:", "CRITICAL")
        for line in tb.split('\n'):
            if line.strip():
                log(line, "CRITICAL")
        
        # Always try to write logs
        try:
            write_logs_to_error_file()
        except:
            try:
                with open("/data/crashes/error.txt", "a") as f:
                    f.write(f"\n\n===== SSH FIX CRITICAL ERROR =====\n")
                    f.write(f"Time: {datetime.now()}\n")
                    f.write(tb)
                    f.write("\n==================================\n")
            except:
                pass
        
        print(tb, file=sys.stderr)
        exit(1)