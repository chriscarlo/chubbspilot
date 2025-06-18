#!/usr/bin/env python3
"""
Script to fix SSH access on TICI by properly setting up the persistent SSH configuration.
This addresses issues where AGNOS-level SSH configuration overrides OpenPilot settings.
"""

import os
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Add openpilot to path when running with sudo
if '/data/openpilot' not in sys.path:
    sys.path.insert(0, '/data/openpilot')

try:
    from common.params import Params
except ImportError as e:
    # If import fails, try to at least log the error
    error_msg = f"Failed to import Params: {e}\nPython path: {sys.path}\n"
    try:
        Path("/data/crashes").mkdir(parents=True, exist_ok=True)
        with open("/data/crashes/error.txt", "a") as f:
            f.write(f"\n\n===== SSH FIX IMPORT ERROR =====\n")
            f.write(f"Time: {datetime.now()}\n")
            f.write(error_msg)
            f.write("==================================\n")
    except:
        pass
    print(error_msg, file=sys.stderr)
    sys.exit(1)

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
        ssh_log_content = "\n===== SSH FIX LOG =====\n"
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

def ensure_directory_writable(path):
    """Ensure the directory exists and is writable."""
    log(f"Ensuring directory is writable: {path}")
    try:
        # Check if parent needs remounting
        if str(path).startswith("/etc"):
            # Remount /etc as read-write if needed
            log("Directory is under /etc, attempting to remount as read-write")
            success, _ = run_command("sudo mount -o remount,rw /")
            if success:
                log("Successfully remounted / as read-write")
        
        # Create directory if it doesn't exist
        if not path.exists():
            # Try creating with regular permissions first
            try:
                path.mkdir(parents=True, exist_ok=True)
                log(f"Created directory: {path}")
            except PermissionError:
                # If that fails, try with sudo
                log("Permission denied, trying with sudo...")
                parent_dir = str(path.parent)
                dir_name = path.name
                success, _ = run_command(f"sudo mkdir -p {path}")
                if success:
                    log(f"Created directory with sudo: {path}")
                    # Set ownership to current user
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

def check_current_ssh_status():
    """Check current SSH configuration status."""
    log("Checking current SSH configuration status...")
    
    persist_ssh_dir = Path("/data/persist/comma/ssh")
    legacy_params_dir = Path("/data/params/d")
    
    # Check persistent location
    if persist_ssh_dir.exists():
        log(f"Persistent SSH directory exists: {persist_ssh_dir}")
        for file in ["GithubUsername", "GithubSshKeys", "SshEnabled"]:
            file_path = persist_ssh_dir / file
            if file_path.exists():
                size = file_path.stat().st_size
                log(f"  - {file}: exists ({size} bytes)")
                if file == "GithubUsername":
                    try:
                        username = file_path.read_text().strip()
                        log(f"    Current username: {username}")
                    except:
                        pass
            else:
                log(f"  - {file}: NOT FOUND", "WARNING")
    else:
        log(f"Persistent SSH directory does not exist: {persist_ssh_dir}", "WARNING")
    
    # Check legacy location
    if legacy_params_dir.exists():
        log(f"Legacy params directory exists: {legacy_params_dir}")
        for file in ["GithubUsername", "GithubSshKeys", "SshEnabled"]:
            file_path = legacy_params_dir / file
            if file_path.exists():
                if file_path.is_symlink():
                    target = file_path.readlink()
                    log(f"  - {file}: symlink -> {target}")
                else:
                    size = file_path.stat().st_size
                    log(f"  - {file}: regular file ({size} bytes)")
            else:
                log(f"  - {file}: NOT FOUND")
    else:
        log(f"Legacy params directory does not exist: {legacy_params_dir}")

def fix_ssh_access():
    """Main function to fix SSH access."""
    log("Starting SSH fix process...")
    
    # First check current status
    check_current_ssh_status()
    
    params = Params()
    
    # Define paths
    persist_ssh_dir = Path("/data/persist/comma/ssh")
    legacy_params_dir = Path("/data/params/d")
    
    # Get GitHub username from various sources
    github_username = None
    
    # First try the standard OpenPilot location
    log("Checking for GitHub username in standard location...")
    username_std = params.get("GithubUsername")
    if username_std:
        github_username = username_std.decode() if isinstance(username_std, bytes) else username_std
        log(f"Found GitHub username in standard location: {github_username}")
    else:
        log("No GitHub username found in standard location")
    
    # Try the persistent location
    if not github_username and (persist_ssh_dir / "GithubUsername").exists():
        log("Checking for GitHub username in persistent location...")
        try:
            github_username = (persist_ssh_dir / "GithubUsername").read_text().strip()
            log(f"Found GitHub username in persistent location: {github_username}")
        except Exception as e:
            log(f"Error reading persistent username: {e}", "ERROR")
    
    if not github_username:
        error_msg = "No GitHub username found. Please set it through the UI first."
        log(error_msg, "ERROR")
        return False, error_msg
    
    # Create persistent directory structure
    if not ensure_directory_writable(persist_ssh_dir):
        error_msg = f"Failed to create or write to persistent SSH directory: {persist_ssh_dir}"
        log(error_msg, "ERROR")
        return False, error_msg
    
    # Fetch SSH keys from GitHub
    try:
        log(f"Fetching SSH keys for {github_username} from GitHub...")
        url = f"https://github.com/{github_username}.keys"
        log(f"URL: {url}")
        
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                ssh_keys = response.read().decode('utf-8').strip()
                
                if not ssh_keys:
                    error_msg = f"No SSH keys found for GitHub user '{github_username}'"
                    log(error_msg, "ERROR")
                    return False, error_msg
                
                key_count = len(ssh_keys.split('\n'))
                log(f"Successfully fetched {key_count} SSH key(s)")
                log("Keys preview (first 100 chars): " + ssh_keys[:100] + "...")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                error_msg = f"GitHub username '{github_username}' not found"
                log(error_msg, "ERROR")
                return False, error_msg
            else:
                error_msg = f"Failed to fetch keys: HTTP {e.code}"
                log(error_msg, "ERROR")
                return False, error_msg
    except (urllib.error.URLError, OSError) as e:
        error_msg = f"Network error fetching SSH keys: {e}"
        log(error_msg, "ERROR")
        return False, error_msg
    
    # Write to persistent location
    try:
        log("Writing SSH configuration to persistent location...")
        
        # Write GitHub username
        username_file = persist_ssh_dir / "GithubUsername"
        try:
            username_file.write_text(github_username)
            log(f"Wrote username to {username_file}")
        except PermissionError:
            log("Permission denied writing username, trying with sudo...")
            success, _ = run_command(f"echo '{github_username}' | sudo tee {username_file} > /dev/null")
            if success:
                log(f"Wrote username with sudo to {username_file}")
            else:
                raise Exception(f"Failed to write username even with sudo")
        
        # Write SSH keys
        keys_file = persist_ssh_dir / "GithubSshKeys"
        try:
            keys_file.write_text(ssh_keys)
            log(f"Wrote SSH keys to {keys_file}")
        except PermissionError:
            log("Permission denied writing keys, trying with sudo...")
            # Write to temp file first then move with sudo
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                tmp.write(ssh_keys)
                tmp_path = tmp.name
            success, _ = run_command(f"sudo mv {tmp_path} {keys_file}")
            if success:
                log(f"Wrote SSH keys with sudo to {keys_file}")
            else:
                raise Exception(f"Failed to write SSH keys even with sudo")
        
        # Write SSH enabled flag
        enabled_file = persist_ssh_dir / "SshEnabled"
        try:
            enabled_file.write_text("1")
            log(f"Wrote SSH enabled flag to {enabled_file}")
        except PermissionError:
            log("Permission denied writing enabled flag, trying with sudo...")
            success, _ = run_command(f"echo '1' | sudo tee {enabled_file} > /dev/null")
            if success:
                log(f"Wrote enabled flag with sudo to {enabled_file}")
            else:
                raise Exception(f"Failed to write enabled flag even with sudo")
        
    except Exception as e:
        error_msg = f"Failed to write SSH configuration: {e}"
        log(error_msg, "ERROR")
        return False, error_msg
    
    # Set proper permissions
    try:
        log("Setting file permissions...")
        # Make files readable by SSH daemon
        for file, perms in [("GithubSshKeys", "644"), ("GithubUsername", "644"), ("SshEnabled", "644")]:
            file_path = persist_ssh_dir / file
            try:
                os.chmod(file_path, int(perms, 8))
                log(f"Set permissions {perms} on {file}")
            except PermissionError:
                log(f"Permission denied setting perms on {file}, trying with sudo...")
                success, _ = run_command(f"sudo chmod {perms} {file_path}")
                if success:
                    log(f"Set permissions {perms} with sudo on {file}")
                else:
                    log(f"Failed to set permissions on {file} even with sudo", "WARNING")
        log("File permissions set successfully")
    except Exception as e:
        error_msg = f"Failed to set permissions: {e}"
        log(error_msg, "ERROR")
        return False, error_msg
    
    # Create symlinks for backward compatibility
    try:
        log("Creating backward compatibility symlinks...")
        legacy_params_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove existing files/links if they exist
        for file in ["GithubUsername", "GithubSshKeys", "SshEnabled"]:
            legacy_path = legacy_params_dir / file
            if legacy_path.exists() or legacy_path.is_symlink():
                log(f"Removing existing file/link: {legacy_path}")
                legacy_path.unlink()
        
        # Create symlinks
        (legacy_params_dir / "GithubUsername").symlink_to(persist_ssh_dir / "GithubUsername")
        (legacy_params_dir / "GithubSshKeys").symlink_to(persist_ssh_dir / "GithubSshKeys")
        (legacy_params_dir / "SshEnabled").symlink_to(persist_ssh_dir / "SshEnabled")
        
        log("Created backward compatibility symlinks successfully")
    except Exception as e:
        log(f"Warning: Failed to create symlinks (non-critical): {e}", "WARNING")
    
    # Update params database to match
    try:
        log("Updating params database...")
        params.put("GithubUsername", github_username)
        params.put("GithubSshKeys", ssh_keys)
        log("Updated params database successfully")
    except Exception as e:
        log(f"Warning: Failed to update params database (non-critical): {e}", "WARNING")
    
    # Restart SSH service
    try:
        log("Restarting SSH service...")
        success, output = run_command("sudo systemctl restart ssh")
        if not success:
            log("ssh service not found, trying sshd...")
            # Try alternative service name
            success, output = run_command("sudo systemctl restart sshd")
        
        if success:
            log("SSH service restarted successfully")
        else:
            log(f"Warning: Failed to restart SSH service: {output}", "WARNING")
    except Exception as e:
        log(f"Warning: Failed to restart SSH service: {e}", "WARNING")
    
    # Check SSH service status
    try:
        log("Checking SSH service status...")
        success, output = run_command("sudo systemctl status ssh")
        if not success:
            success, output = run_command("sudo systemctl status sshd")
        
        if success and output:
            log("SSH service status:")
            for line in output.split('\n')[:10]:  # First 10 lines
                if line.strip():
                    log(f"  {line.strip()}")
    except:
        pass
    
    success_msg = f"SSH access fixed for user '{github_username}'. Keys have been written to persistent storage."
    log(success_msg, "SUCCESS")
    return True, success_msg

if __name__ == "__main__":
    try:
        success, message = fix_ssh_access()
        
        # Always write logs to error file so they can be viewed in UI
        write_logs_to_error_file()
        
        print(f"\n{'Success' if success else 'Error'}: {message}")
        print("\nLogs have been written to /data/crashes/error.txt")
        print("You can view them in the UI: Settings -> Software -> Error Log")
        
        exit(0 if success else 1)
    except Exception as e:
        import traceback
        # Capture FULL traceback
        tb = traceback.format_exc()
        log(f"CRITICAL ERROR in SSH fix script:", "CRITICAL")
        for line in tb.split('\n'):
            if line.strip():
                log(line, "CRITICAL")
        
        # ALWAYS write logs even on crash
        try:
            write_logs_to_error_file()
        except:
            # If even that fails, try to at least write something
            try:
                from pathlib import Path
                from datetime import datetime
                Path("/data/crashes").mkdir(parents=True, exist_ok=True)
                with open("/data/crashes/error.txt", "a") as f:
                    f.write(f"\n\n===== SSH FIX CRITICAL ERROR =====\n")
                    f.write(f"Time: {datetime.now()}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Traceback:\n{tb}\n")
                    f.write("==================================\n")
            except:
                pass
        
        # Also print to stderr so the UI can capture it
        import sys
        print(tb, file=sys.stderr)
        exit(1)