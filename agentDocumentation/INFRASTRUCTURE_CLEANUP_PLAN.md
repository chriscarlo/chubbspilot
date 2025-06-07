# Infrastructure Cleanup Plan

## Overview
This document outlines the "junk" identified in the current infrastructure and a plan to streamline without breaking existing functionality.

## Identified Infrastructure Issues

### 1. Docker Configuration Redundancy
- **Multiple Dockerfiles**: Different files for base, build, CI
- **Overlapping configurations**: Similar setups repeated
- **Outdated base images**: Some using older Ubuntu versions
- **Recommendation**: Consolidate into modular Docker setup

### 2. Build System Complexity
- **Multiple build paths**: Native, Docker, remote device
- **Redundant scripts**: Similar functionality in different scripts
- **Legacy configurations**: Old compiler flags and paths
- **Recommendation**: Unified build interface with clear options

### 3. Testing Infrastructure
- **Scattered test configurations**: Tests in various locations
- **Duplicate test utilities**: Similar helpers in multiple places
- **Outdated test data**: Old recordings and fixtures
- **Recommendation**: Centralized test framework

### 4. Third-Party Dependencies
- **Vendored libraries**: Some may have system packages now
- **Multiple versions**: Different components using different versions
- **Unused dependencies**: Libraries no longer referenced
- **Recommendation**: Dependency audit and cleanup

### 5. CI/CD Pipeline
- **Complex Jenkins setup**: Hard to understand flow
- **Missing documentation**: Pipeline steps unclear
- **Device pool management**: Manual and error-prone
- **Recommendation**: Modernize and document CI/CD

## Cleanup Strategy (DO NOT IMPLEMENT YET)

### Phase 1: Documentation and Analysis
1. Document all build paths and their purposes
2. Map dependencies and their usage
3. Identify critical vs. optional components
4. Create deprecation plan for unused items

### Phase 2: Consolidation
1. Merge similar Docker configurations
2. Create unified build script interface
3. Consolidate test utilities
4. Standardize dependency management

### Phase 3: Modernization
1. Update base images and dependencies
2. Implement modern CI/CD practices
3. Add automated cleanup processes
4. Improve developer documentation

### Phase 4: Optimization
1. Remove confirmed unused components
2. Optimize build times
3. Reduce image sizes
4. Streamline deployment process

## Risk Mitigation

### Before Any Changes
1. **Full backup** of current state
2. **Document** all current workflows
3. **Test** in isolated environment
4. **Gradual rollout** with rollback plan

### Critical Components (DO NOT TOUCH)
- Core build system (SConstruct)
- Hardware-specific code
- Safety-critical components
- Production deployment scripts

### Safe to Consider
- Development-only Docker setups
- Duplicate test utilities
- Outdated documentation
- Development helper scripts

## Metrics for Success

1. **Build Time**: Reduce by 30%
2. **Image Size**: Reduce by 40%
3. **Setup Time**: New developer setup <1 hour
4. **Maintenance**: Reduce weekly maintenance time by 50%
5. **Reliability**: No increase in build failures

## Next Steps

1. **Inventory**: Complete audit of all infrastructure
2. **Prioritize**: Rank cleanup tasks by impact/risk
3. **Plan**: Detailed implementation plan for each phase
4. **Review**: Get team consensus before changes
5. **Execute**: Implement with careful monitoring

## Notes for Future Reference

### Current Working Elements
- SCons build system (core functionality)
- Remote device building (build_chubbspilot.sh)
- Jenkins CI pipeline (device testing)
- pytest infrastructure (test execution)

### Known Issues
- Docker builds are slow
- Cross-compilation setup is complex
- Test data is large and unwieldy
- Documentation is scattered

### Opportunities
- Modern container orchestration
- Cloud-based device testing
- Automated performance tracking
- Self-documenting build system