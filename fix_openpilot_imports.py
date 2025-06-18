#!/usr/bin/env python3
"""
Script to fix all Python imports that contain "from openpilot." or "import openpilot."
by removing the "openpilot." prefix.
"""

import os
import re
import sys
from pathlib import Path

def fix_imports_in_file(file_path):
    """Fix imports in a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False
    
    original_content = content
    
    # Pattern to match "from openpilot.xxx import yyy" and replace with "from xxx import yyy"
    content = re.sub(r'^(\s*)from\s+openpilot\.(.+?)\s+import\s+(.+)$', 
                     r'\1from \2 import \3', 
                     content, 
                     flags=re.MULTILINE)
    
    # Pattern to match "import openpilot.xxx" and replace with "import xxx"
    content = re.sub(r'^(\s*)import\s+openpilot\.(.+)$', 
                     r'\1import \2', 
                     content, 
                     flags=re.MULTILINE)
    
    # Pattern to match "import openpilot.xxx as yyy" and replace with "import xxx as yyy"
    content = re.sub(r'^(\s*)import\s+openpilot\.(.+?)\s+as\s+(.+)$', 
                     r'\1import \2 as \3', 
                     content, 
                     flags=re.MULTILINE)
    
    # Also fix string literals that contain "openpilot." module paths (like in __import__ calls)
    # This handles cases like __import__('selfdrive.car.xxx')
    content = re.sub(r'(["\'])openpilot\.([^"\']+)\1', 
                     r'\1\2\1', 
                     content)
    
    # Check if any changes were made
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False
    
    return False

def find_python_files(root_dir):
    """Find all Python files in the given directory."""
    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip hidden directories and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files

def main():
    root_dir = '/data/openpilot'
    
    print(f"Searching for Python files in {root_dir}...")
    python_files = find_python_files(root_dir)
    print(f"Found {len(python_files)} Python files")
    
    # First, let's check which files have openpilot imports
    files_with_imports = []
    print("\nScanning for files with 'openpilot.' imports...")
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'from openpilot.' in content or 'import openpilot.' in content or '"openpilot.' in content or "'openpilot." in content:
                    files_with_imports.append(file_path)
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")
    
    print(f"\nFound {len(files_with_imports)} files with 'openpilot.' imports")
    
    if not files_with_imports:
        print("No files found with 'openpilot.' imports. Nothing to fix.")
        return
    
    # Fix imports in each file
    fixed_count = 0
    print("\nFixing imports...")
    
    for file_path in files_with_imports:
        if fix_imports_in_file(file_path):
            fixed_count += 1
            print(f"Fixed: {file_path}")
    
    print(f"\nSuccessfully fixed {fixed_count} files out of {len(files_with_imports)} files with imports")

if __name__ == "__main__":
    main()