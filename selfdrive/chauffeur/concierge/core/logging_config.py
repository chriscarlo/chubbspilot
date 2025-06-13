"""Centralized logging configuration for Concierge"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime

# Ensure logs directory exists
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Create detailed formatter
DETAILED_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-40s | "
    "%(funcName)-20s | L%(lineno)-4d | %(message)s"
)

# Create formatter for console (shorter)
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"

class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logging(module_name: str, debug_mode: bool = True) -> logging.Logger:
    """
    Set up logging for a Concierge module
    
    Args:
        module_name: Name of the module (e.g., 'app.main', 'core.services.terminal')
        debug_mode: If True, set to DEBUG level, otherwise INFO
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"concierge.{module_name}")
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # File handler - module-specific log file
    log_file = LOG_DIR / f"concierge_{module_name.replace('.', '_')}_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT, datefmt='%Y-%m-%d %H:%M:%S'))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    console_handler.setFormatter(ColoredFormatter(CONSOLE_FORMAT, datefmt='%H:%M:%S'))
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Log initialization
    logger.debug(f"Logger initialized for module: {module_name}")
    logger.debug(f"Log file: {log_file}")
    logger.debug(f"Debug mode: {debug_mode}")
    
    return logger

def log_function_call(logger: logging.Logger):
    """Decorator to log function calls with arguments and return values"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Log function entry
            logger.debug(f"ENTER {func.__name__} | args={args} | kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"EXIT {func.__name__} | result={result}")
                return result
            except Exception as e:
                logger.error(f"ERROR in {func.__name__} | {type(e).__name__}: {e}")
                raise
        return wrapper
    return decorator

# Create a master logger for cross-module events
MASTER_LOGGER = setup_logging("master", debug_mode=True)