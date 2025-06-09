# Chauffeur Development Changelog

This document tracks significant changes, implementations, and status updates for the chauffeur openpilot fork.

## January 9, 2025 - 05:28 UTC

### TICI Persistence Fix and Storage Strategy
- **Critical Discovery**: `/home/comma` is ephemeral on TICI - wiped on every reboot
- **Persistent Locations Identified**:
  - `/persist/` (27MB) - For secrets, SSH keys, configs
  - `/data/openpilot/` - For dependencies and project files
- **Concierge Dependencies Fixed**:
  - Moved from ephemeral `~/.local` to `/data/openpilot/.local/lib/python3.11/site-packages`
  - Updated `main_wrapper.py` to use persistent path
  - All packages reinstalled to persistent location
- **Documentation Updated**:
  - Added TICI PERSISTENCE RULES section to CLAUDE.md/AGENTS.md
  - Created comprehensive RCA document
  - SSH key location identified as `/persist/comma/.ssh/`

## January 9, 2025 - 05:16 UTC

### Concierge Service Recovery After TICI Reboot
- **Issue**: Concierge failed to start after TICI device reboot due to missing Python dependencies
- **Root Cause**: Python packages (pydantic, fastapi, uvicorn) were not persistent across reboots on TICI
- **Fix Applied**: 
  - Installed missing dependencies using `pip3 install --user` for persistence
  - Successfully installed: pydantic-2.11.5, fastapi-0.115.12, uvicorn-0.34.3, and related dependencies
  - Verified Concierge service is now running and responding on port 8091
- **Tested**: Manual startup confirmed working with external connections from 192.168.1.217
- **Note**: Dependencies need to be made persistent in TICI environment for production use

## January 8, 2025 - 23:03 UTC

### Environment Detection and Runtime Capabilities Enhancement
- **Enhanced CLAUDE.md**: Added comprehensive environment detection section distinguishing TICI runtime vs development environments
- **Expanded Build Documentation**: Added detailed build commands, test commands, linting, and TICI-specific commands
- **Runtime vs Development Clarity**: Clear distinction between development capabilities (code editing, building) and runtime capabilities (system services, hardware access)
- **Platform Detection**: Added Python code examples for detecting TICI vs development environments
- **TICI Authentication**: Documented that no sudo password is required on TICI runtime (running as comma user)

### Asset and Theme Updates
- **New Boot Assets**: Added chauffeur_boot_logo.png for custom boot theming
- **Active Theme Directory**: Created selfdrive/frogpilot/assets/active_theme/ with theme assets (colors, icons, steering wheel graphics)
- **Updated Boot Images**: Modified black_boot.jpg and frogpilot_boot_logo.png
- **Terminal Boot Binary**: Updated terminal_boot executable
- **Generated Files**: Added moc_concierge_toggle_control.cc and simple_boot executable

### Concierge Service Updates
- **Service Logs**: Updated concierge_server.log and main_wrapper.log with recent activity
- **Build Integration**: Added simple_boot alongside existing terminal_boot for enhanced UI fallback

## January 8, 2025

### Documentation Structure Cleanup and CSS Build (Commit: `b880da6b`)
- **Documentation Restructure**: Cleaned up ALL CLAUDE.md files to focus on agent instructions only
- **Created CHANGELOG.md**: Moved all status updates, commit tracking, and implementation details here
- **Enhanced Documentation Requirements**: Added prominent requirements at top of all CLAUDE.md files  
- **Moved BUILD_TAILWIND.md**: Relocated to agentDocumentation/ directory for better organization
- **Built Tailwind CSS**: Updated tailwind.min.css for TICI deployment readiness
- **Updated All AGENTS.md**: Ensured consistency across all documentation files

### Concierge Web Server UI Refactor (Commit: `63eed9f2`)
- **Refactored UI**: Integrated all diagnostics into the toggle control's expandable description area
- **Fixed Text Wrapping**: Long diagnostic messages now wrap at 60 characters to prevent screen overflow
- **TICI CSS Handling**: 
  - Added pre-built CSS detection on TICI devices
  - Clear error messaging when Tailwind CSS needs to be built offline
  - Created `BUILD_TAILWIND.md` with detailed instructions for building CSS on development machines
- **Improved Fix Button**: 
  - Now appears inline within the description when dependencies are missing
  - Real-time progress display during installation
  - Proper error handling and feedback
- **Simplified Architecture**: Removed separate status widget, all functionality now in single toggle control

### Concierge Web Server Management Implementation (Commit: `c7066efd`)
- **GUI Integration**: Concierge web server management now available in FrogPilot Utilities
  - Enhanced diagnostics with real-time health monitoring
  - Automatic dependency installation with Fix button (TICI-aware)
  - Platform-specific behavior:
    - TICI: Verifies pre-installed Python deps, handles Node.js deps appropriately
    - Development: Uses Poetry/npm with timeouts to prevent hanging
  - Real-time progress display with [CONCIERGE] prefixed messages
  - Timeout protection: 30s for Poetry, 60s for npm
  - Toggle disabled when dependencies missing
  - Relaunch button for easy service restart

### Boot UI Overhaul (Previous commits)
- Replaced FrogPilot graphics with terminal-based boot interface
- ASCII art Chauffeur logo with venetian blind effect
- Real-time service status display
- Actionable error reporting with stack traces
- Backward compatible with existing spinner
- Fixed TICI display rendering (centered for 2160x1080 screen)
- Added simple fallback UI for debugging display issues

## Build Status

### Current Status
- **TICI Native Builds**: All required libraries present, build should complete successfully
- **x86_64 Development**: Fully functional with all dependencies resolved
- **Runtime Dependencies**: Comprehensive multi-layered system handles 661+ external imports

### Known Issues
- **Tailwind CSS**: Must be built offline on development machines before TICI deployment
- **SSH Access**: May require manual key management on TICI devices

### Infrastructure
- **Concierge Refactor Plan**: Comprehensive architectural refactor plan created to address monolithic code structure and improve maintainability
- **Documentation**: Moved build instructions and technical details to agentDocumentation/

## Dependencies

### Runtime Dependency Analysis (Previous work)
1. **Comprehensive Analysis**: Scanned entire codebase (1260 files) and identified 661 unique external imports
   - Created `tools/analyze_imports.py` for ongoing dependency analysis
   - Generated `EXTERNAL_IMPORTS_ANALYSIS.md` with complete import breakdown
   - Created `CRITICAL_RUNTIME_DEPENDENCIES.md` with prioritized installation guide

2. **Multi-layered Installation System**: Ensures critical packages available before any imports:
   - `ensure_boot_dependencies.sh` - Early boot-time shell script (tier 1 packages)
   - `ensure_dependencies.py` - Comprehensive Python installer with special package handling
   - `mapd_daemon_wrapper.py` - Process-specific wrapper ensuring shapely before import
   - `main_wrapper.py` - Concierge wrapper ensuring web framework dependencies
   - Modified `process_config.py` to use wrappers instead of direct module imports

3. **Package Coverage**: Now handles critical packages with fallback installation methods:
   - **Tier 1 Critical**: numpy (290 usages), shapely, pydantic, uvicorn, jinja2, requests
   - **Tier 2 Important**: zmq, psutil, PIL, cv2 (opencv-python)
   - **Special Handling**: Package name mapping (cv2→opencv-python, PIL→Pillow, zmq→pyzmq)

### Current Dependencies

#### Python Dependencies (Concierge)
- fastapi >= 0.111
- uvicorn[standard] >= 0.30
- pydantic (managed by fastapi)
- jinja2 (should be available)

#### Node.js Dependencies (Concierge - Development Only)
- tailwindcss ^4.1.6
- @tailwindcss/cli ^4.1.6

#### Build Dependencies
- SCons (primary build system)
- Poetry (Python dependency management)
- clang/clang++ (required compilers)
- Python 3.11+ required

## Platform Support

- **larch64**: Linux TICI (aarch64 with AGNOS)
- **aarch64**: Linux PC aarch64  
- **x86_64**: Linux PC x64
- **Darwin**: macOS (x64/arm64)

## References

- Build instructions: `agentDocumentation/BUILD_TAILWIND.md`
- Development environment: `agentDocumentation/DEVELOPMENT_ENVIRONMENT.md`
- Infrastructure plans: `agentDocumentation/INFRASTRUCTURE_CLEANUP_PLAN.md`
- Concierge refactor: `agentDocumentation/CONCIERGE_REFACTOR_PLAN.md`