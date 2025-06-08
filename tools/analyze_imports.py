#!/usr/bin/env python3
"""
Comprehensive import analysis tool for openpilot codebase.
Scans all Python files and extracts external module imports.
"""

import ast
import os
import sys
import datetime
from pathlib import Path
from collections import defaultdict, Counter
from typing import Set, Dict, List, Tuple
import re

# Standard library modules (Python 3.11+)
STDLIB_MODULES = {
    # Core system
    'os', 'sys', 'subprocess', 'signal', 'threading', 'multiprocessing', 'asyncio',
    'queue', 'time', 'datetime', 'calendar', 'locale', 'platform', 'resource',
    'getpass', 'pwd', 'grp', 'ctypes', 'mmap', 'gc', 'atexit',
    
    # Data structures & types
    'collections', 'typing', 'enum', 'dataclasses', 'functools', 'itertools',
    'operator', 'copy', 'weakref', 'heapq', 'bisect', 'array', 'types',
    
    # File & path operations
    'pathlib', 'glob', 'shutil', 'tempfile', 'zipfile', 'tarfile', 'gzip',
    'bz2', 'lzma', 'io', 'fileinput', 'linecache', 'fnmatch',
    
    # Text & data processing
    'json', 'csv', 're', 'string', 'textwrap', 'codecs', 'base64', 'hashlib',
    'hmac', 'pickle', 'struct', 'difflib', 'pprint', 'reprlib', 'unicodedata',
    
    # Mathematical
    'math', 'statistics', 'random', 'decimal', 'fractions', 'cmath',
    
    # Networking & internet
    'socket', 'urllib', 'http', 'email', 'ssl', 'ipaddress', 'select',
    'selectors', 'socketserver',
    
    # Logging & debugging
    'logging', 'traceback', 'pdb', 'warnings', 'inspect', 'dis', 'trace',
    'profile', 'cProfile', 'pstats', 'timeit',
    
    # Concurrency & async
    'concurrent', 'contextlib', '_thread', 'dummy_threading',
    
    # Testing & development
    'unittest', 'doctest', 'test',
    
    # Build & packaging
    'importlib', 'pkgutil', 'modulefinder', 'runpy', 'site', 'sysconfig',
    
    # GUI (though these might not be available on all systems)
    'tkinter', 'turtle',
    
    # XML
    'xml', 'html',
    
    # Compression
    'zlib',
    
    # Database
    'sqlite3', 'dbm',
    
    # Configuration
    'configparser', 'argparse', 'optparse', 'getopt',
    
    # Misc
    'keyword', 'token', 'tokenize', 'ast', 'py_compile', 'compileall',
    'secrets', 'uuid', 'mailbox', 'mimetypes', 'mailcap', 'quopri', 'uu',
    'binascii', 'binhex', 'encodings', 'colorsys', 'imghdr', 'sndhdr',
    'sunau', 'wave', 'aifc', 'audioop', 'chunk', 'cgi', 'cgitb', 'wsgiref',
    'xdrlib', 'plistlib', 'netrc', 'pipes', 'posix', 'pwd', 'spwd', 'crypt',
    'termios', 'tty', 'pty', 'fcntl', 'pipes', 'resource', 'nis', 'syslog',
    'winsound', 'winreg', 'msvcrt'
}

# Known openpilot internal modules
OPENPILOT_MODULES = {
    'openpilot', 'cereal', 'selfdrive', 'system', 'common', 'tools', 'panda',
    'body', 'rednose', 'tinygrad', 'teleoprtc', 'msgq', 'third_party'
}

class ImportAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.imports = []
        self.from_imports = []
        
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)
    
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                full_name = f"{node.module}.{alias.name}" if alias.name != '*' else node.module
                self.from_imports.append((node.module, alias.name, full_name))
        self.generic_visit(node)

def get_top_level_module(module_name: str) -> str:
    """Extract the top-level module name."""
    return module_name.split('.')[0]

def is_external_import(module_name: str) -> bool:
    """Check if a module is external (not stdlib or openpilot internal)."""
    top_level = get_top_level_module(module_name)
    
    # Check if it's a standard library module
    if top_level in STDLIB_MODULES:
        return False
        
    # Check if it's an openpilot internal module
    if top_level in OPENPILOT_MODULES:
        return False
        
    # Check for relative imports
    if module_name.startswith('.'):
        return False
        
    return True

def scan_file(file_path: Path) -> Tuple[List[str], List[str], List[str]]:
    """Scan a Python file for imports."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        analyzer = ImportAnalyzer()
        analyzer.visit(tree)
        
        # Categorize imports
        stdlib_imports = []
        external_imports = []
        internal_imports = []
        
        all_imports = analyzer.imports + [imp[2] for imp in analyzer.from_imports]
        
        for imp in all_imports:
            if imp == '*':
                continue
                
            top_level = get_top_level_module(imp)
            
            if top_level in STDLIB_MODULES:
                stdlib_imports.append(imp)
            elif top_level in OPENPILOT_MODULES or imp.startswith('.'):
                internal_imports.append(imp)
            else:
                external_imports.append(imp)
        
        return stdlib_imports, external_imports, internal_imports
        
    except Exception as e:
        print(f"Error scanning {file_path}: {e}")
        return [], [], []

def scan_directory(root_path: Path) -> Dict:
    """Scan all Python files in a directory recursively."""
    results = {
        'files_scanned': 0,
        'files_with_errors': 0,
        'stdlib_imports': Counter(),
        'external_imports': Counter(),
        'internal_imports': Counter(),
        'files_by_external_import': defaultdict(list),
        'external_imports_by_file': defaultdict(list)
    }
    
    # Skip certain directories
    skip_dirs = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv'}
    
    for py_file in root_path.rglob('*.py'):
        # Skip if in a skip directory
        if any(skip_dir in py_file.parts for skip_dir in skip_dirs):
            continue
            
        results['files_scanned'] += 1
        
        try:
            stdlib, external, internal = scan_file(py_file)
            
            # Update counters
            for imp in stdlib:
                results['stdlib_imports'][imp] += 1
            for imp in external:
                results['external_imports'][imp] += 1
                results['files_by_external_import'][imp].append(str(py_file.relative_to(root_path)))
                results['external_imports_by_file'][str(py_file.relative_to(root_path))].append(imp)
            for imp in internal:
                results['internal_imports'][imp] += 1
                
        except Exception as e:
            results['files_with_errors'] += 1
            print(f"Error processing {py_file}: {e}")
    
    return results

def generate_report(results: Dict, output_file: Path):
    """Generate a comprehensive import analysis report."""
    
    with open(output_file, 'w') as f:
        f.write("# Comprehensive Import Analysis Report\n\n")
        f.write(f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Summary statistics
        f.write("## Summary Statistics\n\n")
        f.write(f"- **Files scanned:** {results['files_scanned']}\n")
        f.write(f"- **Files with errors:** {results['files_with_errors']}\n")
        f.write(f"- **Unique stdlib imports:** {len(results['stdlib_imports'])}\n")
        f.write(f"- **Unique external imports:** {len(results['external_imports'])}\n")
        f.write(f"- **Unique internal imports:** {len(results['internal_imports'])}\n\n")
        
        # External imports (most critical for dependency management)
        f.write("## External Dependencies\n\n")
        f.write("These are third-party packages that need to be installed:\n\n")
        
        if results['external_imports']:
            f.write("| Package | Usage Count | Files Using |\n")
            f.write("|---------|-------------|-------------|\n")
            
            for imp, count in results['external_imports'].most_common():
                files = results['files_by_external_import'][imp]
                files_str = f"{len(files)} files" if len(files) > 3 else ", ".join(files[:3])
                f.write(f"| `{imp}` | {count} | {files_str} |\n")
        else:
            f.write("*No external dependencies found.*\n")
        
        f.write("\n")
        
        # Detailed file breakdown for external imports
        f.write("## Files with External Dependencies\n\n")
        
        files_with_external = {k: v for k, v in results['external_imports_by_file'].items() if v}
        
        if files_with_external:
            for file_path, imports in sorted(files_with_external.items()):
                f.write(f"### {file_path}\n")
                for imp in sorted(set(imports)):
                    f.write(f"- `{imp}`\n")
                f.write("\n")
        else:
            f.write("*No files with external dependencies found.*\n\n")
        
        # Most commonly used stdlib modules
        f.write("## Most Used Standard Library Modules\n\n")
        if results['stdlib_imports']:
            f.write("| Module | Usage Count |\n")
            f.write("|--------|-----------|\n")
            for imp, count in results['stdlib_imports'].most_common(20):
                f.write(f"| `{imp}` | {count} |\n")
        else:
            f.write("*No standard library imports found.*\n")
        
        f.write("\n")
        
        # Internal module usage
        f.write("## Most Used Internal Modules\n\n")
        if results['internal_imports']:
            f.write("| Module | Usage Count |\n")
            f.write("|--------|-----------|\n")
            for imp, count in results['internal_imports'].most_common(20):
                f.write(f"| `{imp}` | {count} |\n")
        else:
            f.write("*No internal imports found.*\n")

def main():
    if len(sys.argv) > 1:
        root_path = Path(sys.argv[1])
    else:
        root_path = Path("/data/openpilot")
    
    if not root_path.exists():
        print(f"Error: {root_path} does not exist")
        sys.exit(1)
    
    print(f"Scanning {root_path} for Python imports...")
    results = scan_directory(root_path)
    
    output_file = root_path / "agentDocumentation" / "EXTERNAL_IMPORTS_ANALYSIS.md"
    print(f"Generating report: {output_file}")
    
    generate_report(results, output_file)
    
    print(f"Analysis complete!")
    print(f"Files scanned: {results['files_scanned']}")
    print(f"External dependencies found: {len(results['external_imports'])}")
    
    # Print critical external dependencies
    if results['external_imports']:
        print("\nCritical external dependencies:")
        for imp, count in results['external_imports'].most_common(10):
            print(f"  {imp}: {count} usages")

if __name__ == "__main__":
    main()