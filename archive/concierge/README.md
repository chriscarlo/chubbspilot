# Archived Concierge Legacy Code

This directory contains legacy Concierge code that has been replaced by the refactored implementation.

## Archived Files

### main_legacy.py
- **Original location:** `/selfdrive/chauffeur/concierge/main.py`
- **Size:** 879 lines
- **Description:** The original monolithic FastAPI implementation with all routes, business logic, and services mixed in a single file
- **Replaced by:** The new layered architecture in `app/`, `api/`, `core/`, etc.
- **Archived:** June 10, 2025

### simple_server_legacy.py
- **Original location:** `/selfdrive/chauffeur/concierge/simple_server.py`
- **Description:** A fallback HTTP server using Python's built-in http.server for when FastAPI dependencies weren't available
- **Status:** No longer needed as dependency management is handled by main_wrapper.py
- **Archived:** June 10, 2025

## Current Implementation

The current Concierge implementation uses a clean, layered architecture:
- Entry point: `main_wrapper.py` → `app/main.py`
- API routes: `api/v1/`
- Business logic: `core/services/`
- Configuration: `config/`
- Terminal emulator: Fully implemented in Phase 1

## Note

These files are preserved for historical reference. The new implementation maintains all functionality while providing better separation of concerns, testability, and maintainability.