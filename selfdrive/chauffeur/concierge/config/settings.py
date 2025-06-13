from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class ConciergeSettings(BaseSettings):
    """Configuration settings for Concierge web server"""
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 5055
    debug: bool = False
    reload: bool = False
    
    # Paths
    openpilot_root: Path = Path("/data/openpilot")
    crash_logs_dir: Path = Path("/data/crashes")
    log_dir: Path = Path(__file__).parent.parent / "logs"
    static_dir: Path = Path(__file__).parent.parent / "static"
    templates_dir: Path = Path(__file__).parent.parent / "templates"
    
    # ZeroMQ settings
    mapd_zmq_port: int = 8607
    zmq_timeout: int = 1000
    
    # Process settings
    command_timeout: int = 30
    max_log_lines: int = 50
    
    # Monitoring settings
    status_poll_interval: float = 0.25
    
    # Security settings
    auth_secret_key: str = "dev-secret-key-change-in-production"
    
    class Config:
        env_prefix = "CONCIERGE_"
        case_sensitive = False