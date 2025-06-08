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
        import importlib
        # Handle uvicorn[standard] format
        pkg_name = package.split("[")[0]
        importlib.import_module(pkg_name)
        return True
    except ImportError:
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
    
    print(f"Installing Python dependencies: {', '.join(missing)}")
    
    # Use poetry if available (preferred)
    poetry_path = Path("/data/openpilot/pyproject.toml")
    if poetry_path.exists():
        try:
            # Add dependencies to pyproject.toml
            for dep in missing:
                dep_name = dep.split("[")[0]
                cmd = ["poetry", "add", dep]
                if PYTHON_DEPENDENCIES.get(dep):
                    cmd.append(f"@{PYTHON_DEPENDENCIES[dep]}")
                
                result = subprocess.run(cmd, cwd="/data/openpilot", capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Failed to add {dep}: {result.stderr}")
                    return False
            
            # Install everything
            result = subprocess.run(
                ["poetry", "install"],
                cwd="/data/openpilot",
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Poetry installation failed: {e}")
    
    # Fallback to pip
    try:
        cmd = [sys.executable, "-m", "pip", "install"]
        for dep in missing:
            if PYTHON_DEPENDENCIES.get(dep):
                cmd.append(f"{dep}{PYTHON_DEPENDENCIES[dep]}")
            else:
                cmd.append(dep)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Pip installation failed: {e}")
        return False


def install_node_dependencies(missing: List[str]) -> bool:
    """Install missing Node.js dependencies."""
    if not missing:
        return True
    
    print(f"Installing Node.js dependencies: {', '.join(missing)}")
    
    # Check if npm is available
    try:
        subprocess.run(["npm", "--version"], check=True, capture_output=True)
    except Exception:
        print("npm not found. Please install Node.js first.")
        return False
    
    # Install in project directory
    try:
        os.chdir("/data/openpilot")
        for dep in missing:
            version = NODE_DEPENDENCIES.get(dep, "latest")
            cmd = ["npm", "install", f"{dep}@{version}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Failed to install {dep}: {result.stderr}")
                return False
        return True
    except Exception as e:
        print(f"Node installation failed: {e}")
        return False


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
    import argparse
    
    parser = argparse.ArgumentParser(description="Install Concierge dependencies")
    parser.add_argument("--python", nargs="+", help="Specific Python packages to install")
    parser.add_argument("--node", nargs="+", help="Specific Node packages to install")
    parser.add_argument("--check-only", action="store_true", help="Only check, don't install")
    
    args = parser.parse_args()
    
    if args.check_only:
        missing_py, missing_node = get_missing_dependencies()
        if missing_py:
            print(f"Missing Python: {', '.join(missing_py)}")
        if missing_node:
            print(f"Missing Node: {', '.join(missing_node)}")
        sys.exit(0 if not (missing_py or missing_node) else 1)
    
    # Install specified or all missing
    success = install_missing_dependencies(args.python, args.node)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()