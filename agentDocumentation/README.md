# Agent Documentation

This directory contains comprehensive documentation for AI agents working on the FrogPilot codebase. It serves as a knowledge base for development environment setup, cross-platform testing strategies, infrastructure improvements, and implementation roadmaps.

## Purpose

Multiple AI agents will be helping with various aspects of this project:
- Cross-platform development and testing
- Infrastructure cleanup and modernization
- Feature development and debugging
- Code quality and performance improvements

This documentation ensures consistency and continuity across different agents and sessions.

## Documentation Files

### Core Development Guides
- **`DEVELOPMENT_ENVIRONMENT.md`** - Analysis of current build infrastructure, architecture differences, and challenges
- **`CROSS_PLATFORM_TESTING_PLAN.md`** - Comprehensive testing strategy for x86_64 development targeting aarch64 runtime
- **`INFRASTRUCTURE_CLEANUP_PLAN.md`** - Technical debt assessment and cleanup strategy (DO NOT IMPLEMENT without explicit approval)
- **`IMMEDIATE_ACTION_PLAN.md`** - Quick start guide for cross-platform development using existing tools
- **`CRITICAL_RUNTIME_DEPENDENCIES.md`** - Analysis of essential runtime dependencies required by openpilot
- **`EXTERNAL_IMPORTS_ANALYSIS.md`** - Detailed breakdown of external library imports and their usage
- **`BOOT_SEQUENCE_ROADMAP.md`** - Comprehensive plan to replace FrogPilot boot graphics with professional terminal interface
- **`CONCIERGE_REFACTOR_PLAN.md`** - Architectural refactor plan for the Concierge web server with full implementation roadmap
- **`CONCIERGE_REFACTOR_CHECKLIST.md`** - Progress tracking checklist for the Concierge refactor (track progress here)

### Maintenance Guidelines

1. **Keep Documentation Current**: Update relevant files when making changes
2. **Track Progress**: Mark completed objectives and add new discoveries
3. **Document Decisions**: Record architectural choices and their rationale
4. **Share Knowledge**: Ensure findings are accessible to future agents

### Usage Notes

- All paths referenced in documentation use absolute paths from repository root
- Platform-specific information is clearly marked
- Risk assessments are included for infrastructure changes
- Working solutions are prioritized over theoretical improvements

## Key Principles

1. **Preserve Working Systems**: Don't break existing functionality
2. **Document Before Changing**: Understand current state thoroughly
3. **Test Cross-Platform**: Verify changes work on both development and target environments
4. **Maintain Compatibility**: Ensure changes work with existing CI/CD and deployment processes