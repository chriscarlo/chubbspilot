#!/usr/bin/env python3
"""SSH Bridge - Syncs SSH keys from params to persist location for AGNOS-level SSH"""

import time
from pathlib import Path
from openpilot.common.params import Params

def sync_ssh_keys():
  """Sync SSH keys from params to persist location"""
  params = Params()
  persist_ssh_dir = Path("/data/persist/comma/ssh")
  
  # Create persist directory if it doesn't exist
  persist_ssh_dir.mkdir(parents=True, exist_ok=True)
  
  # Get values from params
  github_username = params.get("GithubUsername", encoding='utf8') or ""
  github_ssh_keys = params.get("GithubSshKeys", encoding='utf8') or ""
  
  # Write to persist location
  if github_username:
    (persist_ssh_dir / "GithubUsername").write_text(github_username)
    print(f"Synced GitHub username: {github_username}")
  
  if github_ssh_keys:
    (persist_ssh_dir / "GithubSshKeys").write_text(github_ssh_keys)
    print(f"Synced SSH keys to persist location")
    
    # Also ensure params location has the keys (for compatibility)
    params_dir = Path("/data/params/d")
    if params_dir.exists():
      (params_dir / "GithubSshKeys").write_text(github_ssh_keys)

def main():
  print("SSH Bridge starting - syncing SSH keys to AGNOS persist location")
  
  # Run once at startup
  sync_ssh_keys()
  
  # Then watch for changes
  params = Params()
  last_keys = params.get("GithubSshKeys", encoding='utf8') or ""
  
  while True:
    time.sleep(5)  # Check every 5 seconds
    
    current_keys = params.get("GithubSshKeys", encoding='utf8') or ""
    if current_keys != last_keys:
      print("SSH keys changed, syncing...")
      sync_ssh_keys()
      last_keys = current_keys

if __name__ == "__main__":
  main()