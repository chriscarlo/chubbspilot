# CLAUDE.md - Agent Documentation

This file provides guidance to Claude Code regarding the `agentDocumentation/` directory. It explains the purpose of each document and how to maintain them.

## Documentation Directory Overview

The **`agentDocumentation/`** directory contains:
- **`DEVELOPMENT_ENVIRONMENT.md`** - Analysis of current build infrastructure, architecture differences, and setup challenges.
- **`CROSS_PLATFORM_TESTING_PLAN.md`** - Comprehensive testing strategy for validating cross-platform compatibility across supported architectures.
- **`INFRASTRUCTURE_CLEANUP_PLAN.md`** - Technical debt assessment and roadmap for cleaning and refactoring infrastructure components (implement only with explicit approval).
- **`IMMEDIATE_ACTION_PLAN.md`** - Prioritized quick-start action items for immediate development tasks.
- **`CRITICAL_RUNTIME_DEPENDENCIES.md`** - Detailed list and analysis of essential runtime dependencies required for openpilot functionality.
- **`EXTERNAL_IMPORTS_ANALYSIS.md`** - In-depth analysis and categorization of external library imports, including usage patterns and risk assessments.
- **`README.md`** - High-level overview of this directory's purpose, structure, and usage guidelines.

## Documentation Update Instructions

- When updating any of these files, update the **Last Updated** timestamp (format: `Month Day, Year HH:MM TZ`) and the **Current Commit** field in the **Current Status** section at the top of this file.
- After every commit or push, ensure this file (and its corresponding AGENTS.md) is updated with any new or changed documentation items, and that the **Last Updated** and **Current Commit** fields are refreshed accordingly.

## Current Status

**Last Updated:** [Date and Time]
**Current Commit:** `[commit-hash]` - [brief description]

## Additional Notes

- Use absolute paths from the repository root when referencing files.
- Follow the documentation update protocol for consistency across all documents.