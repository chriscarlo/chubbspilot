# CLAUDE.md

Agent instructions for Claude Code working with the chauffeur openpilot fork.

## 🚨 CRITICAL RULES 🚨

1. **ALWAYS keep AGENTS.md as exact copy of CLAUDE.md**
2. **"commit xyz" = commit AND push unless specified otherwise**
3. **NEVER log status/changes in CLAUDE.md - use `agentDocumentation/CHANGELOG.md`**
4. **ALWAYS update CHANGELOG.md and relevant docs with EVERY commit/push**
5. **This is SOURCE CODE ONLY - no runtime system access (no systemctl, journalctl, ps, etc)**
6. **PYTHON TRUTH: See `/data/openpilot/PYTHON_TRUTH.md` - USE ONLY Python 3.11.4**

## Environment

**Development environment for:**
- Code editing, `scons` builds, `pytest` tests, git operations
- **NOT for:** running services, checking logs, or TICI runtime behavior

**Platform detection:**
```python
TICI = os.path.isfile('/TICI')
PC = not TICI
```

## Project Structure

- **`selfdrive/`** - Core driving logic (*see selfdrive/CLAUDE.md*)
- **`system/`** - System services (*see system/CLAUDE.md*)
- **`cereal/`** - IPC messaging (*see cereal/CLAUDE.md*)
- **`tools/`** - Dev utilities (*see tools/CLAUDE.md*)
- **`release/`** - Release management (*see release/CLAUDE.md*)
- **`opendbc/`** - CAN database

## Build & Development

```bash
scons -j$(nproc)  # Build all
pytest            # Run tests
```

**Requirements:** SCons, Poetry, clang/clang++, Python 3.11+  
**Platforms:** larch64 (TICI), aarch64, x86_64, Darwin

**Style:** 
- Absolute imports (`openpilot.selfdrive`)
- 160 char lines, 2-space Python indent
- Type hints required, pytest only

## Credentials

- **SSH:** `~/.ssh/claude_github_key[.pub]`
- **Sudo:** `sudo -S cmd < ~/.sudo_pass`

## Documentation

**Status/Changes:** `agentDocumentation/CHANGELOG.md`  
**Technical Docs:** See `agentDocumentation/` for dependencies, build instructions, refactor plans

## Key Reminders

- Include timestamp/commit in CHANGELOG.md entries
- No "co-authored by claude" in commits
- For detailed info on any topic, check subdirectory CLAUDE.md files