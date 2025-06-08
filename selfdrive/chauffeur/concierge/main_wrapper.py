#!/usr/bin/env python3
"""
Wrapper for concierge main that ensures dependencies are installed before importing.
"""
import subprocess
import sys
import os
import runpy
import logging
from pathlib import Path

# Set up logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "main_wrapper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def ensure_dependencies():
    """Ensure all concierge dependencies are installed."""
    required_packages = [
        "pydantic",
        "fastapi", 
        "uvicorn",
        "jinja2",
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✓ {package} is available")
        except ImportError:
            missing.append(package)
            logger.warning(f"✗ {package} is missing")
    
    if not missing:
        logger.info("All dependencies are satisfied")
        return True
        
    logger.info(f"Missing packages: {missing}")
    
    # Check if we're on TICI device
    is_tici = os.path.isfile('/TICI')
    logger.info(f"Running on TICI device: {is_tici}")
    
    if is_tici:
        # Try to install on TICI
        install_success = True
        for package in missing:
            logger.info(f"Installing {package}...")
            if not install_package(package):
                install_success = False
                logger.error(f"Failed to install {package}")
        return install_success
    else:
        # On development systems, warn but continue
        logger.warning("Not on TICI device - dependency installation skipped")
        logger.warning("Attempting to continue anyway (dev environment)")
        # Try to import again in case packages are available but not in expected locations
        still_missing = []
        for package in missing:
            try:
                __import__(package)
                logger.info(f"✓ {package} found on retry")
            except ImportError:
                still_missing.append(package)
        
        if still_missing:
            logger.warning(f"Still missing: {still_missing} - Concierge may not work properly")
        
        return True  # Continue anyway on dev systems

def install_package(package):
    """Install a single package with multiple fallback methods."""
    install_methods = [
        ["sudo", "pip3", "install", package],
        ["sudo", sys.executable, "-m", "pip", "install", package],
        ["pip3", "install", "--user", package],
        [sys.executable, "-m", "pip", "install", "--user", package]
    ]
    
    for method in install_methods:
        try:
            logger.info(f"Trying: {' '.join(method)}")
            subprocess.check_call(method, 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL,
                                timeout=60)
            logger.info(f"Successfully installed {package}")
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.debug(f"Method failed: {e}")
            continue
    
    return False

if __name__ == "__main__":
    logger.info("Concierge main wrapper starting...")
    
    try:
        # Ensure dependencies are available
        if ensure_dependencies():
            logger.info("Dependencies satisfied, starting Concierge main module...")
            # Run the module directly to preserve its __main__ logic
            runpy.run_module("selfdrive.chauffeur.concierge.main", run_name="__main__")
        else:
            logger.error("ERROR: Could not ensure critical dependencies. Concierge will not start.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"CRITICAL ERROR in main wrapper: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)