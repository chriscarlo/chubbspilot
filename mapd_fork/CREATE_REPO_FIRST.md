# Create the GitHub Repository First

The mapd fork is ready to push, but the repository needs to be created on GitHub first.

## Quick Steps:

1. **Go to**: https://github.com/new

2. **Fill in**:
   - Repository name: `mapd`
   - Description: `Fork of openpilot-mapd for custom 2023 Kia EV6 development`
   - Public repository: ✓
   - DO NOT initialize with README, .gitignore, or license

3. **Click "Create repository"**

4. **Then run** (from the mapd_fork directory):
   ```bash
   cd /data/openpilot/mapd_fork
   git push -u origin main
   ```

## Repository is already configured:
- Remote: git@github.com:chriscarlo/mapd.git
- SSH key: ~/.ssh/claude_github_key (already in your GitHub account)
- The code changes have been made

## What's been done:
- ✓ Cloned pfeiferj/mapd
- ✓ Set up remotes (origin = your fork, upstream = original)
- ✓ Updated README to indicate it's a fork
- ✓ Modified openpilot to check your fork first for binaries
- ✓ SSH is configured correctly

Just need to create the repo on GitHub and push!