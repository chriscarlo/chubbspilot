#!/usr/bin/env python3
"""
Dependency installer for Concierge web server.
Handles individual or combined installation of missing dependencies.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Ensure we can run on TICI
try:
    # Add openpilot to path if needed
    openpilot_path = '/data/openpilot'
    if openpilot_path not in sys.path:
        sys.path.insert(0, openpilot_path)
except Exception as e:
    print(f"[CONCIERGE] Path setup error: {e}", file=sys.stderr)
    pass

# Core Python dependencies for Concierge
PYTHON_DEPENDENCIES = {
    "fastapi": ">=0.111",
    "uvicorn[standard]": ">=0.30",
    "pydantic": None,  # Version managed by fastapi
    "jinja2": None,    # Should already be available
}

# Node.js dependencies
NODE_DEPENDENCIES = {
    "tailwindcss": "^4.1.6",
    "@tailwindcss/cli": "^4.1.6",
}


def check_python_dependency(package: str) -> bool:
    """Check if a Python package is installed."""
    try:
        # First try direct import
        import importlib
        # Handle uvicorn[standard] format
        pkg_name = package.split("[")[0]
        importlib.import_module(pkg_name)
        return True
    except ImportError:
        # Check if it's in the poetry environment
        try:
            result = subprocess.run(
                ["poetry", "show", pkg_name],
                cwd="/data/openpilot",
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False


def check_node_dependency(package: str) -> bool:
    """Check if a Node.js package is installed."""
    try:
        # Check in local node_modules
        node_modules = Path("/data/openpilot/node_modules")
        if node_modules.exists():
            pkg_path = node_modules / package
            if pkg_path.exists():
                return True
        
        # Check global install
        result = subprocess.run(
            ["npm", "list", "-g", package, "--depth=0"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def install_python_dependencies(missing: List[str]) -> bool:
    """Install missing Python dependencies."""
    if not missing:
        return True
    
    print(f"[CONCIERGE] Python dependencies requested: {', '.join(missing)}")
    
    # On TICI, we can just install with pip like you did
    if os.path.isfile('/TICI'):
        print("[CONCIERGE] Running on TICI - installing with pip")
        
        try:
            # Install each missing dependency
            for dep in missing:
                pkg_name = dep.split("[")[0]  # Handle uvicorn[standard] format
                print(f"[CONCIERGE] Installing {dep}...")
                
                # Build pip install command
                version_spec = PYTHON_DEPENDENCIES.get(dep, "")
                package_spec = f"{dep}{version_spec}" if version_spec else dep
                
                # Try with --break-system-packages first (needed on newer Python)
                cmd = [sys.executable, "-m", "pip", "install", "--break-system-packages", package_spec]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                # If that fails, try without the flag
                if result.returncode != 0 and "no such option" in result.stderr.lower():
                    print("[CONCIERGE] Retrying without --break-system-packages")
                    cmd = [sys.executable, "-m", "pip", "install", package_spec]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    print(f"[CONCIERGE] Successfully installed {dep}")
                else:
                    print(f"[CONCIERGE] Failed to install {dep}: {result.stderr}")
                    return False
            
            print("[CONCIERGE] All Python dependencies installed successfully")
            return True
            
        except subprocess.TimeoutExpired:
            print("[CONCIERGE] Installation timed out")
            return False
        except Exception as e:
            print(f"[CONCIERGE] Installation error: {e}")
            return False
    
    # For development environment, use poetry
    poetry_path = Path("/data/openpilot/pyproject.toml")
    if poetry_path.exists():
        try:
            print("[CONCIERGE] Checking Poetry environment...")
            # Quick timeout for poetry commands
            all_installed = True
            for dep in missing:
                pkg_name = dep.split("[")[0]
                try:
                    result = subprocess.run(
                        ["poetry", "show", pkg_name],
                        cwd="/data/openpilot",
                        capture_output=True,
                        text=True,
                        timeout=5  # 5 second timeout
                    )
                    if result.returncode != 0:
                        all_installed = False
                        break
                except subprocess.TimeoutExpired:
                    print(f"[CONCIERGE] Timeout checking {pkg_name}")
                    all_installed = False
                    break
            
            if all_installed:
                print("[CONCIERGE] All dependencies already installed in Poetry environment")
                return True
            
            # Run poetry install with timeout
            print("[CONCIERGE] Running poetry install --no-root (may take up to 30 seconds)...")
            try:
                result = subprocess.run(
                    ["poetry", "install", "--no-root"],
                    cwd="/data/openpilot",
                    capture_output=True,
                    text=True,
                    timeout=30  # 30 second timeout
                )
                
                if result.returncode == 0:
                    print("[CONCIERGE] Poetry install succeeded")
                    return True
                else:
                    print(f"[CONCIERGE] Poetry install failed: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("[CONCIERGE] Poetry install timed out after 30 seconds")
                return False
                    
        except FileNotFoundError:
            print("[CONCIERGE] Poetry command not found")
        except Exception as e:
            print(f"[CONCIERGE] Poetry error: {e}")
    
    # Last resort - direct pip
    print("[CONCIERGE] WARNING: Dependencies may need to be installed manually")
    return False


def install_node_dependencies(missing: List[str]) -> bool:
    """Install missing Node.js dependencies."""
    if not missing:
        return True
    
    print(f"[CONCIERGE] Node.js dependencies requested: {', '.join(missing)}")
    
    # On TICI, npm is typically not available and not needed
    if os.path.isfile('/TICI'):
        print("[CONCIERGE] Running on TICI - Node.js dependencies are optional")
        print("[CONCIERGE] Tailwind CSS is only needed for development")
        return True  # Don't fail on TICI
    
    # Check if npm is available with timeout
    try:
        print("[CONCIERGE] Checking for npm...")
        result = subprocess.run(
            ["npm", "--version"], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print("[CONCIERGE] npm not found. Node.js dependencies are optional.")
            return True
    except subprocess.TimeoutExpired:
        print("[CONCIERGE] npm check timed out")
        return True
    except Exception:
        print("[CONCIERGE] npm not available. Node.js dependencies are optional.")
        return True
    
    # Install in project directory
    try:
        os.chdir("/data/openpilot")
        print("[CONCIERGE] Installing Node.js packages (may take up to 60 seconds)...")
        
        # Install with timeout
        cmd = ["npm", "install", "--save-dev"]
        for dep in missing:
            version = NODE_DEPENDENCIES.get(dep, "latest")
            cmd.append(f"{dep}@{version}")
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=60  # 60 second timeout
            )
            if result.returncode != 0:
                print(f"[CONCIERGE] npm install failed: {result.stderr[:200]}")
                return False
            else:
                print("[CONCIERGE] npm install succeeded")
                return True
        except subprocess.TimeoutExpired:
            print("[CONCIERGE] npm install timed out after 60 seconds")
            return False
            
    except Exception as e:
        print(f"[CONCIERGE] Node installation error: {e}")
        return True  # Don't fail the whole process


def get_missing_dependencies() -> Tuple[List[str], List[str]]:
    """Get lists of missing Python and Node dependencies."""
    missing_python = []
    missing_node = []
    
    # Check Python dependencies
    for dep in PYTHON_DEPENDENCIES:
        if not check_python_dependency(dep):
            missing_python.append(dep)
    
    # Check Node dependencies
    for dep in NODE_DEPENDENCIES:
        if not check_node_dependency(dep):
            missing_node.append(dep)
    
    return missing_python, missing_node


def install_missing_dependencies(python_deps: List[str] = None, node_deps: List[str] = None) -> bool:
    """
    Install specific missing dependencies.
    If no specific deps provided, check and install all missing.
    """
    if python_deps is None and node_deps is None:
        # Auto-detect missing
        python_deps, node_deps = get_missing_dependencies()
    
    success = True
    
    # Install Python dependencies
    if python_deps:
        success &= install_python_dependencies(python_deps)
    
    # Install Node dependencies
    if node_deps:
        success &= install_node_dependencies(node_deps)
    
    return success


def main():
    """Main entry point for dependency installation."""
    try:
        print("[CONCIERGE] Dependency installer started", file=sys.stderr)
        print(f"[CONCIERGE] Python: {sys.version}", file=sys.stderr)
        print(f"[CONCIERGE] Platform: {sys.platform}", file=sys.stderr)
        print(f"[CONCIERGE] TICI: {'YES' if os.path.isfile('/TICI') else 'NO'}", file=sys.stderr)
        sys.stderr.flush()
        
        import argparse
        parser = argparse.ArgumentParser(description="Install Concierge dependencies")
        parser.add_argument("--python", nargs="+", help="Specific Python packages to install")
        parser.add_argument("--node", nargs="+", help="Specific Node packages to install")
        parser.add_argument("--check-only", action="store_true", help="Only check, don't install")
        
        args = parser.parse_args()
        
        if args.check_only:
            print("[CONCIERGE] Running in check-only mode")
            missing_py, missing_node = get_missing_dependencies()
            if missing_py:
                print(f"[CONCIERGE] Missing Python: {', '.join(missing_py)}")
            if missing_node:
                print(f"[CONCIERGE] Missing Node: {', '.join(missing_node)}")
            sys.exit(0 if not (missing_py or missing_node) else 1)
        
        # Install specified or all missing
        print("[CONCIERGE] Starting installation process...")
        sys.stdout.flush()
        success = install_missing_dependencies(args.python, args.node)
        print(f"[CONCIERGE] Installation {'SUCCEEDED' if success else 'FAILED'}")
        sys.exit(0 if success else 1)
    except SystemExit:
        raise  # Let sys.exit work normally
    except Exception as e:
        print(f"[CONCIERGE] FATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()