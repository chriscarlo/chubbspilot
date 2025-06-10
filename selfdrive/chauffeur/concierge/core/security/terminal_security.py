"""Security manager for terminal operations"""

import re
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from openpilot.selfdrive.chauffeur.concierge.core.logging_config import setup_logging

logger = setup_logging("core.security.terminal_security")

class TerminalSecurityManager:
    """Manages security for terminal operations"""
    
    def __init__(self):
        # Input validation settings
        self.max_input_size = 8192  # 8KB max input
        self.max_command_length = 1024
        self.input_rate_limit = 100  # messages per second
        
        # Resource limits
        self.max_sessions = 10
        self.session_timeout = 3600  # 1 hour
        
        # Restricted commands (could be made configurable)
        self.dangerous_commands = [
            r'^rm\s+-rf\s+/',  # rm -rf /
            r'^dd\s+.*of=/dev/',  # dd to device files
            r'^mkfs',  # filesystem creation
            r'^fdisk',  # disk partitioning
            r'^format',  # formatting
            r'>\s*/dev/(null|zero|random|urandom)',  # writing to special devices
            r'^chmod\s+777',  # overly permissive permissions
            r'^chown\s+.*:.*\s+/',  # changing ownership of root files
        ]
        
        # Restricted paths
        self.restricted_paths = [
            '/proc',
            '/sys',
            '/dev',
            '/boot',
            '/etc/passwd',
            '/etc/shadow',
            '/etc/sudoers',
        ]
        
        # Safe commands that are always allowed
        self.safe_commands = [
            'ls', 'pwd', 'cd', 'cat', 'less', 'more', 'head', 'tail',
            'grep', 'find', 'wc', 'sort', 'uniq', 'date', 'whoami',
            'ps', 'top', 'df', 'du', 'free', 'uptime', 'uname',
            'echo', 'history', 'which', 'type', 'help', 'man',
        ]
    
    def validate_input(self, data: str) -> bool:
        """Validate input data for safety"""
        # Check input size
        if len(data) > self.max_input_size:
            logger.warning(f"Input too large: {len(data)} bytes")
            return False
        
        # Check for null bytes
        if '\x00' in data:
            logger.warning("Null bytes in input")
            return False
        
        # Check for control characters (except common ones)
        control_chars = set(range(32)) - {7, 8, 9, 10, 13, 27}  # Allow bell, backspace, tab, newline, carriage return, escape
        if any(ord(c) in control_chars for c in data):
            logger.warning("Dangerous control characters in input")
            return False
        
        return True
    
    def validate_command(self, command: str) -> tuple[bool, Optional[str]]:
        """Validate a command for execution"""
        command = command.strip()
        
        # Check command length
        if len(command) > self.max_command_length:
            return False, f"Command too long: {len(command)} characters"
        
        # Check for dangerous patterns
        for pattern in self.dangerous_commands:
            if re.match(pattern, command, re.IGNORECASE):
                return False, f"Dangerous command pattern detected: {pattern}"
        
        # Check for path traversal attempts
        if '../' in command or '..\\' in command:
            return False, "Path traversal attempt detected"
        
        # Check for attempts to access restricted paths
        for restricted_path in self.restricted_paths:
            if restricted_path in command:
                return False, f"Access to restricted path: {restricted_path}"
        
        return True, None
    
    def sanitize_environment(self, env: Dict[str, str]) -> Dict[str, str]:
        """Sanitize environment variables"""
        safe_env = {}
        
        # Whitelist of safe environment variables
        safe_vars = {
            'PATH', 'HOME', 'USER', 'SHELL', 'TERM', 'LANG', 'LC_ALL',
            'PWD', 'OLDPWD', 'SHLVL', 'PS1', 'PS2', 'COLORTERM'
        }
        
        for key, value in env.items():
            # Only allow safe variables
            if key in safe_vars:
                # Sanitize value
                if self.validate_input(value):
                    safe_env[key] = value
                else:
                    logger.warning(f"Unsafe environment variable value: {key}")
            else:
                logger.info(f"Filtered environment variable: {key}")
        
        # Ensure required variables
        safe_env.setdefault('TERM', 'xterm-256color')
        safe_env.setdefault('PATH', '/usr/local/bin:/usr/bin:/bin')
        
        return safe_env
    
    def validate_working_directory(self, cwd: str) -> tuple[bool, Optional[str]]:
        """Validate working directory"""
        try:
            path = Path(cwd).resolve()
            
            # Check if path exists
            if not path.exists():
                return False, f"Directory does not exist: {cwd}"
            
            # Check if it's a directory
            if not path.is_dir():
                return False, f"Not a directory: {cwd}"
            
            # Check for restricted paths
            for restricted in self.restricted_paths:
                if str(path).startswith(restricted):
                    return False, f"Access to restricted directory: {restricted}"
            
            # Ensure it's under allowed paths (e.g., /data, /home)
            allowed_prefixes = ['/data', '/home', '/tmp', '/var/tmp']
            if not any(str(path).startswith(prefix) for prefix in allowed_prefixes):
                return False, f"Directory not in allowed paths: {cwd}"
            
            return True, None
            
        except Exception as e:
            return False, f"Invalid directory path: {str(e)}"
    
    def generate_session_id(self) -> str:
        """Generate a secure session ID"""
        import secrets
        import string
        
        # Generate a random session ID
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    def validate_session_id(self, session_id: str) -> bool:
        """Validate session ID format"""
        logger.debug(f"Validating session ID: {session_id}")
        
        # Check length
        if len(session_id) < 8 or len(session_id) > 64:
            logger.error(f"Session ID length invalid: {len(session_id)} (must be 8-64)")
            return False
        
        # Check for valid characters (alphanumeric only)
        if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
            logger.error(f"Session ID contains invalid characters: {session_id}")
            return False
        
        logger.debug(f"Session ID valid: {session_id}")
        return True
    
    def get_resource_limits(self) -> Dict[str, Any]:
        """Get resource limits for PTY processes"""
        import resource
        
        limits = {}
        
        # CPU time limit (5 minutes)
        limits[resource.RLIMIT_CPU] = (300, 300)
        
        # Memory limit (1GB) - increased for normal bash operation
        limits[resource.RLIMIT_AS] = (1024 * 1024 * 1024, 1024 * 1024 * 1024)
        
        # File size limit (100MB) - increased for logs/outputs
        limits[resource.RLIMIT_FSIZE] = (100 * 1024 * 1024, 100 * 1024 * 1024)
        
        # Number of open files (1024) - standard limit
        limits[resource.RLIMIT_NOFILE] = (1024, 1024)
        
        # Number of processes (200) - bash needs to fork for commands
        limits[resource.RLIMIT_NPROC] = (200, 200)
        
        return limits
    
    def apply_resource_limits(self):
        """Apply resource limits to the current process"""
        import resource
        
        limits = self.get_resource_limits()
        
        for resource_type, (soft, hard) in limits.items():
            try:
                resource.setrlimit(resource_type, (soft, hard))
            except Exception as e:
                logger.warning(f"Failed to set resource limit {resource_type}: {e}")
    
    def log_security_event(self, event_type: str, session_id: str, details: Dict[str, Any]):
        """Log security-related events"""
        logger.warning(f"SECURITY EVENT: {event_type} for session {session_id}: {details}")
        
        # In a production environment, this could send to a SIEM or alerting system