#!/usr/bin/env python3
"""
Concierge web server diagnostics and status checker.
Provides comprehensive status information for the FrogPilot UI.
"""

import subprocess
import time
import socket
import json
from typing import Dict, Any
import psutil
import requests

CONCIERGE_PORT = 5055
CONCIERGE_HOST = "127.0.0.1"
CONCIERGE_URL = f"http://{CONCIERGE_HOST}:{CONCIERGE_PORT}"

def get_process_status() -> Dict[str, Any]:
    """Check if concierge process is running."""
    try:
        # Look for concierge process
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status', 'memory_info', 'cpu_percent']):
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'concierge' in cmdline.lower() and 'main' in cmdline:
                return {
                    'running': True,
                    'pid': proc.info['pid'],
                    'status': proc.info['status'],
                    'memory_mb': round(proc.info['memory_info'].rss / 1024 / 1024, 1),
                    'cpu_percent': round(proc.info['cpu_percent'], 1),
                    'cmdline': cmdline
                }
    except Exception as e:
        return {
            'running': False,
            'error': str(e)
        }
    
    return {'running': False}

def check_port_status() -> Dict[str, Any]:
    """Check if port 5055 is open and listening."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((CONCIERGE_HOST, CONCIERGE_PORT))
        sock.close()
        
        if result == 0:
            return {
                'port_open': True,
                'listening': True
            }
        else:
            return {
                'port_open': False,
                'listening': False
            }
    except Exception as e:
        return {
            'port_open': False,
            'listening': False,
            'error': str(e)
        }

def check_http_response() -> Dict[str, Any]:
    """Check if HTTP server responds properly."""
    try:
        response = requests.get(CONCIERGE_URL, timeout=5)
        return {
            'http_responding': True,
            'status_code': response.status_code,
            'response_size': len(response.content),
            'response_time_ms': round(response.elapsed.total_seconds() * 1000, 1)
        }
    except requests.exceptions.ConnectionError:
        return {
            'http_responding': False,
            'error': 'Connection refused'
        }
    except requests.exceptions.Timeout:
        return {
            'http_responding': False,
            'error': 'Request timeout'
        }
    except Exception as e:
        return {
            'http_responding': False,
            'error': str(e)
        }

def check_dependencies() -> Dict[str, Any]:
    """Check if required dependencies are available."""
    # Python dependencies
    python_deps = ['fastapi', 'uvicorn', 'jinja2', 'pydantic']
    python_missing = []
    python_available = []
    
    for dep in python_deps:
        try:
            __import__(dep)
            python_available.append(dep)
        except ImportError:
            python_missing.append(dep)
    
    # Node dependencies (check if CSS file exists as proxy)
    node_deps = []
    node_missing = []
    node_available = []
    
    # Check if tailwind CSS is built
    css_path = '/data/openpilot/selfdrive/chauffeur/concierge/static/css/tailwind.css'
    try:
        import os
        if os.path.exists(css_path):
            node_available.append('tailwindcss')
        else:
            node_missing.append('tailwindcss')
            node_missing.append('@tailwindcss/cli')
    except Exception:
        node_missing.extend(['tailwindcss', '@tailwindcss/cli'])
    
    return {
        'dependencies_ok': len(python_missing) == 0 and len(node_missing) == 0,
        'python': {
            'available': python_available,
            'missing': python_missing,
            'all_ok': len(python_missing) == 0
        },
        'node': {
            'available': node_available,
            'missing': node_missing,
            'all_ok': len(node_missing) == 0
        },
        # Legacy fields for compatibility
        'available': python_available + node_available,
        'missing': python_missing + node_missing
    }

def check_log_errors() -> Dict[str, Any]:
    """Check recent log files for concierge errors."""
    log_paths = [
        '/data/openpilot/selfdrive/chauffeur/concierge/logs/concierge_server.log',
        '/tmp/launch_log'
    ]
    
    errors = []
    warnings = []
    
    for log_path in log_paths:
        try:
            with open(log_path, 'r') as f:
                lines = f.readlines()[-50:]  # Last 50 lines
                for line in lines:
                    line_lower = line.lower()
                    if 'error' in line_lower or 'exception' in line_lower or 'traceback' in line_lower:
                        if 'concierge' in line_lower or 'uvicorn' in line_lower or 'fastapi' in line_lower:
                            errors.append(line.strip()[-100:])  # Last 100 chars
                    elif 'warning' in line_lower or 'warn' in line_lower:
                        if 'concierge' in line_lower:
                            warnings.append(line.strip()[-100:])
        except FileNotFoundError:
            continue
        except Exception:
            continue
    
    return {
        'recent_errors': errors[-3:],  # Last 3 errors
        'recent_warnings': warnings[-2:],  # Last 2 warnings
        'has_errors': len(errors) > 0
    }

def get_system_resources() -> Dict[str, Any]:
    """Get system resource information relevant to web server."""
    try:
        # Check available memory
        memory = psutil.virtual_memory()
        
        # Check disk space for logs
        disk = psutil.disk_usage('/data')
        
        # Check network interfaces
        network = psutil.net_if_stats()
        network_up = any(net.isup for net in network.values())
        
        return {
            'memory_available_mb': round(memory.available / 1024 / 1024, 0),
            'memory_percent_used': memory.percent,
            'disk_free_gb': round(disk.free / 1024 / 1024 / 1024, 1),
            'disk_percent_used': round((disk.used / disk.total) * 100, 1),
            'network_up': network_up
        }
    except Exception as e:
        return {
            'error': str(e)
        }

def get_manager_status() -> Dict[str, Any]:
    """Check if concierge is enabled in process manager."""
    try:
        # Check if concierge is in the process list
        result = subprocess.run(['pgrep', '-f', 'manager.py'], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            manager_running = True
        else:
            manager_running = False
            
        return {
            'manager_running': manager_running,
            'concierge_managed': True  # We know it's in process_config.py
        }
    except Exception as e:
        return {
            'manager_running': False,
            'error': str(e)
        }

def run_full_diagnostics() -> Dict[str, Any]:
    """Run all diagnostic checks and return comprehensive status."""
    diagnostics = {
        'timestamp': int(time.time()),
        'process': get_process_status(),
        'port': check_port_status(),
        'http': check_http_response(),
        'dependencies': check_dependencies(),
        'logs': check_log_errors(),
        'system': get_system_resources(),
        'manager': get_manager_status()
    }
    
    # Overall health assessment
    health_score = 0
    max_score = 6
    
    if diagnostics['process']['running']:
        health_score += 1
    if diagnostics['port']['port_open']:
        health_score += 1
    if diagnostics['http']['http_responding']:
        health_score += 1
    if diagnostics['dependencies']['dependencies_ok']:
        health_score += 1
    if not diagnostics['logs']['has_errors']:
        health_score += 1
    if diagnostics['manager']['manager_running']:
        health_score += 1
    
    diagnostics['health'] = {
        'score': health_score,
        'max_score': max_score,
        'percentage': round((health_score / max_score) * 100),
        'status': 'healthy' if health_score >= 5 else 'degraded' if health_score >= 3 else 'unhealthy'
    }
    
    return diagnostics

if __name__ == "__main__":
    # Command line usage
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--json':
            print(json.dumps(run_full_diagnostics(), indent=2))
        elif sys.argv[1] == '--status':
            diag = run_full_diagnostics()
            print(f"Health: {diag['health']['status']} ({diag['health']['score']}/{diag['health']['max_score']})")
            print(f"Process: {'Running' if diag['process']['running'] else 'Not running'}")
            print(f"HTTP: {'Responding' if diag['http']['http_responding'] else 'Not responding'}")
    else:
        diag = run_full_diagnostics()
        print(json.dumps(diag, indent=2))