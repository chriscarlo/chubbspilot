"""Simple configuration settings for Concierge web server (Phase 1)"""

import os
from pathlib import Path
from typing import Optional


class ConciergeSettings:
    """Configuration settings for Concierge web server"""
    
    def __init__(self):
        # Server settings
        self.host: str = os.getenv("CONCIERGE_HOST", "0.0.0.0")
        self.port: int = int(os.getenv("CONCIERGE_PORT", "5055"))
        self.debug: bool = os.getenv("CONCIERGE_DEBUG", "False").lower() == "true"
        self.reload: bool = os.getenv("CONCIERGE_RELOAD", "False").lower() == "true"
        
        # Paths
        self.openpilot_root: Path = Path(os.getenv("CONCIERGE_OPENPILOT_ROOT", "/data/openpilot"))
        self.crash_logs_dir: Path = Path(os.getenv("CONCIERGE_CRASH_LOGS_DIR", "/data/crashes"))
        self.log_dir: Path = Path(__file__).parent.parent / "logs"
        self.static_dir: Path = Path(__file__).parent.parent / "static"
        self.templates_dir: Path = Path(__file__).parent.parent / "templates"
        
        # ZeroMQ settings
        self.mapd_zmq_port: int = int(os.getenv("CONCIERGE_MAPD_ZMQ_PORT", "8607"))
        self.zmq_timeout: int = int(os.getenv("CONCIERGE_ZMQ_TIMEOUT", "1000"))
        
        # Process settings
        self.command_timeout: int = int(os.getenv("CONCIERGE_COMMAND_TIMEOUT", "30"))
        self.max_log_lines: int = int(os.getenv("CONCIERGE_MAX_LOG_LINES", "50"))
        
        # Monitoring settings
        self.status_poll_interval: float = float(os.getenv("CONCIERGE_STATUS_POLL_INTERVAL", "0.25"))
        
        # Security settings
        self.auth_secret_key: str = os.getenv("CONCIERGE_AUTH_SECRET_KEY", "dev-secret-key-change-in-production")