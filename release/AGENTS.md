# CLAUDE.md - Release Directory

Release management and prebuilt workflow for fast device installation.

## Prebuilt Release Workflow

FrogPilot and openpilot use a special workflow for fast device installation:

- Build directly on TICI device using `release/build_release.sh`
- Commit compiled binaries to special release branches
- Mark with `prebuilt` file to indicate pre-compiled release
- Users get immediate functionality without 20+ minute compilation

**Near-term objective**: Implement similar prebuilt workflow for this fork to enable fast device installation.

## Release Scripts

### build_release.sh
Primary release build script that:
- Compiles all components for target architecture
- Creates optimized production builds
- Generates release artifacts
- Prepares for distribution

### build_devel.sh
Development build script for:
- Debug builds with symbols
- Development features enabled
- Testing and validation builds

## Release Process

### 1. Build Phase
```bash
# On TICI device or cross-compilation environment
./release/build_release.sh
```

### 2. Validation Phase
- Run automated tests
- Verify functionality on target hardware
- Check performance benchmarks
- Validate safety systems

### 3. Packaging Phase
- Create release branch
- Commit compiled binaries
- Add `prebuilt` marker file
- Tag release version

### 4. Distribution Phase
- Push to release repositories
- Update download links
- Notify users of new release

## Prebuilt Benefits

### Fast Installation
- No 20+ minute compilation on device
- Immediate functionality after download
- Reduced installation complexity
- Lower barrier to entry for users

### Consistency
- Builds done in controlled environment
- Consistent optimization flags
- Known good configurations
- Reduced variability across installations

### Resource Efficiency
- Saves device CPU/memory during install
- Reduces power consumption
- Minimizes thermal stress during setup
- Preserves device lifespan

## Implementation Plan

### Current Status
This fork does not yet have prebuilt releases implemented. To add this capability:

1. **Adapt build scripts** from upstream FrogPilot/openpilot
2. **Set up CI/CD pipeline** for automated builds
3. **Create release branches** with prebuilt binaries
4. **Test installation workflow** on actual TICI devices
5. **Document installation process** for end users

### Technical Requirements
- TICI build environment or cross-compilation setup
- Automated testing pipeline
- Binary artifact storage
- Release branch management
- Version tagging system

## Build System Integration

The release process integrates with the main build system:
- Uses same SCons configuration
- Respects architecture detection
- Applies optimization flags
- Handles dependencies correctly

## Cross-Platform Considerations

### Target Architecture
- Primary target: larch64 (TICI/AGNOS)
- Development: x86_64 (cross-compilation)
- Testing: Multiple architectures supported

### Build Environment
- Ensure AGNOS compatibility
- Use appropriate toolchains
- Handle library dependencies
- Validate on actual hardware