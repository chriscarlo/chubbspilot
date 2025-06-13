"""Terminal command execution service"""

import shlex
from pathlib import Path
from typing import Dict, Any

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.core.managers.session_manager import SessionManager
from openpilot.selfdrive.chauffeur.concierge.core.managers.process_manager import ProcessManager


class TerminalService:
    """Service for executing terminal commands with session management"""
    
    def __init__(self, settings: ConciergeSettings, session_manager: SessionManager = None):
        self.settings = settings
        self.session_manager = session_manager or SessionManager(settings)
        self.process_manager = ProcessManager(settings)
    
    async def execute_command(self, command: str, session_id: str = "default") -> Dict[str, Any]:
        """Execute a shell command in the specified session"""
        if not command.strip():
            return {
                "stdout": "",
                "stderr": "Empty command",
                "exit_code": 1,
                "command": command
            }
        
        # Add to session history
        self.session_manager.add_to_history(command, session_id)
        
        # Handle cd commands specially
        if command.strip().startswith("cd"):
            return self._handle_cd_command(command, session_id)
        
        # Execute regular command
        return await self._execute_shell_command(command, session_id)
    
    def _handle_cd_command(self, command: str, session_id: str) -> Dict[str, Any]:
        """Handle directory change commands"""
        try:
            # Parse cd command safely
            parts = shlex.split(command)
            if len(parts) == 1:  # Just "cd" - go to home
                target_dir = "~"
            elif len(parts) == 2:  # "cd <path>"
                target_dir = parts[1]
            else:
                return {
                    "stdout": "",
                    "stderr": "cd: too many arguments",
                    "exit_code": 1,
                    "command": command
                }
            
            # Expand ~ to home directory
            if target_dir == "~":
                target_dir = str(Path.home())
            
            # Try to change directory
            if self.session_manager.update_cwd(target_dir, session_id):
                new_cwd = self.session_manager.get_cwd(session_id)
                return {
                    "stdout": f"Changed directory to: {new_cwd}",
                    "stderr": "",
                    "exit_code": 0,
                    "command": command
                }
            else:
                return {
                    "stdout": "",
                    "stderr": f"cd: {target_dir}: No such file or directory",
                    "exit_code": 1,
                    "command": command
                }
                
        except ValueError as e:
            return {
                "stdout": "",
                "stderr": f"cd: invalid command syntax: {str(e)}",
                "exit_code": 1,
                "command": command
            }
    
    async def _execute_shell_command(self, command: str, session_id: str) -> Dict[str, Any]:
        """Execute a non-cd shell command"""
        try:
            # Parse command safely
            parts = shlex.split(command)
            if not parts:
                return {
                    "stdout": "",
                    "stderr": "Empty command",
                    "exit_code": 1,
                    "command": command
                }
            
            # Get current working directory for this session
            cwd = Path(self.session_manager.get_cwd(session_id))
            
            # Execute command using process manager
            result = await self.process_manager.execute_command(
                parts, 
                cwd=cwd, 
                timeout=self.settings.command_timeout
            )
            
            return result
            
        except ValueError as e:
            return {
                "stdout": "",
                "stderr": f"Command parsing error: {str(e)}",
                "exit_code": 1,
                "command": command
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Command execution error: {str(e)}",
                "exit_code": -1,
                "command": command
            }
    
    def get_session_info(self, session_id: str = "default") -> Dict[str, Any]:
        """Get information about the current session"""
        session = self.session_manager.get_session(session_id)
        return {
            "session_id": session_id,
            "cwd": session["cwd"],
            "history_count": len(session["history"])
        }
    
    def get_command_history(self, session_id: str = "default", limit: int = 10) -> list:
        """Get recent command history for session"""
        history = self.session_manager.get_history(session_id)
        return history[-limit:] if limit > 0 else history