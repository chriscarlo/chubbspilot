"""Session management for terminal commands"""

from pathlib import Path
from typing import Dict, Any
from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings


class SessionManager:
    """Manages terminal session state including current working directories"""
    
    def __init__(self, settings: ConciergeSettings):
        self.settings = settings
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._default_session = "default"
    
    def get_session(self, session_id: str = None) -> Dict[str, Any]:
        """Get or create a session"""
        session_id = session_id or self._default_session
        
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "cwd": str(self.settings.openpilot_root),
                "env": {},
                "history": []
            }
        
        return self._sessions[session_id]
    
    def update_cwd(self, new_cwd: str, session_id: str = None) -> bool:
        """Update current working directory for session"""
        session = self.get_session(session_id)
        
        # Resolve path relative to current cwd
        current_cwd = Path(session["cwd"])
        new_path = current_cwd / new_cwd if not Path(new_cwd).is_absolute() else Path(new_cwd)
        
        try:
            resolved_path = new_path.resolve()
            if resolved_path.exists() and resolved_path.is_dir():
                session["cwd"] = str(resolved_path)
                return True
            else:
                return False
        except (OSError, RuntimeError):
            return False
    
    def get_cwd(self, session_id: str = None) -> str:
        """Get current working directory for session"""
        session = self.get_session(session_id)
        return session["cwd"]
    
    def add_to_history(self, command: str, session_id: str = None):
        """Add command to session history"""
        session = self.get_session(session_id)
        session["history"].append(command)
        
        # Keep only last 100 commands
        if len(session["history"]) > 100:
            session["history"] = session["history"][-100:]
    
    def get_history(self, session_id: str = None) -> list:
        """Get command history for session"""
        session = self.get_session(session_id)
        return session["history"].copy()
    
    def clear_session(self, session_id: str = None):
        """Clear session data"""
        session_id = session_id or self._default_session
        if session_id in self._sessions:
            del self._sessions[session_id]