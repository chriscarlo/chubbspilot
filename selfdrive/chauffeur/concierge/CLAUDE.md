# CLAUDE.md - Concierge Web Interface

Agent instructions for Concierge - the local web interface for openpilot configuration and monitoring.

## Core Purpose

Concierge is a **local-only** web server (port 5055) providing:
- Real-time openpilot status monitoring
- Configuration management via web UI
- Service control interface
- **NO cloud connectivity** - all operations are local to TICI

## Architecture Rules

### 1. **Strict Separation of Concerns**
- **main.py** - FastAPI routes only, NO business logic
- **services/** - All business logic goes here
- **static/** - Frontend assets (CSS/JS)
- **templates/** - Jinja2 HTML templates
- **Never mix concerns** - routes call services, services handle logic

### 2. **Dependency Management**
- Core deps: fastapi, uvicorn, jinja2 (see requirements.txt)
- Install to persistent location: `/data/openpilot/.local/lib/python3.11/site-packages`
- Wrapper script handles path setup - don't duplicate

### 3. **Integration with openpilot**
- Read-only access to params via `common.params`
- Monitor processes via process manager
- **Never directly control driving processes** - safety critical
- Use existing openpilot APIs, don't reinvent

### 4. **Frontend Philosophy**
- Server-side rendering with Jinja2
- Minimal JavaScript - progressive enhancement only
- Tailwind CSS for styling (pre-built on TICI)
- Mobile-first design for TICI screen

## Development Guidelines

### Adding Features
1. Check if openpilot already has the capability
2. Create service module in `services/`
3. Add route in `main.py` that calls service
4. Create/update template with UI

### Error Handling
- All routes must have try/except
- Return user-friendly error pages
- Log errors to `logs/` directory
- Never expose internal errors to UI

### Testing
- Manual testing on TICI device required
- Check responsiveness on TICI screen (1920x1080)
- Verify no impact on driving performance

## Security

- **Local access only** - no external authentication
- No sensitive data in templates
- Params are read-only by default
- File operations restricted to safe paths

## Performance

- Concierge runs alongside critical driving processes
- Keep operations lightweight
- Cache expensive operations
- No blocking I/O in request handlers

## For Detailed Docs

See `/data/openpilot/agentDocumentation/` for:
- Full refactoring plans
- Dependency details
- Integration documentation