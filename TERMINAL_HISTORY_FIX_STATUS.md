# Terminal History Fix Status

## Current Status
- ✅ Fixed input validation to allow terminal control sequences (arrow keys)
- ✅ Configured persistent bash history via environment variables
- 🔧 Temporarily disabled custom bashrc to debug PTY crash issue
- ⏳ History should still work via environment variables

## What Was Done
1. **Security validation fix**: Removed restriction on control characters that was blocking arrow keys
2. **History configuration**: Set up persistent history file and environment variables:
   - `HISTFILE=/data/openpilot/.concierge_bash_history`
   - `HISTSIZE=10000`
   - `HISTFILESIZE=10000`
   - `PROMPT_COMMAND='history -a'`
3. **Debugging PTY crash**: Added logging to understand why PTY terminates immediately

## To Test
1. Restart Concierge: `pkill -f concierge && python -m selfdrive.chauffeur.concierge.main_wrapper`
2. Open terminal: http://localhost:5055/terminal
3. Type some commands and press arrow up/down
4. Check if history persists between sessions

## Next Steps
Once PTY is stable:
1. Re-enable custom bashrc for better shell experience
2. Add more shell customizations (aliases, prompt, etc.)
3. Test thoroughly on TICI device