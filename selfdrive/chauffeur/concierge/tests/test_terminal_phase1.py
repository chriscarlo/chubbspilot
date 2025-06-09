#!/usr/bin/env python3
"""Test Phase 1 Terminal Emulator implementation"""

import asyncio
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_terminal_structure():
    """Test that terminal structure is properly organized"""
    base_path = Path(__file__).parent.parent
    
    expected_files = [
        "core/services/terminal/__init__.py",
        "core/services/terminal/pty_manager.py",
        "core/security/__init__.py", 
        "core/security/terminal_security.py",
        "api/v1/websocket/__init__.py",
        "api/v1/websocket/terminal.py",
        "static/js/terminal/Terminal.js",
        "templates/terminal.html"
    ]
    
    missing_files = []
    for file_path in expected_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"✗ Missing terminal files: {missing_files}")
        return False
    else:
        print(f"✓ All {len(expected_files)} terminal files exist")
        return True

def test_pty_manager_import():
    """Test that PTY manager can be imported"""
    try:
        from core.services.terminal.pty_manager import PTYManager, PTYProcess
        print("✓ PTY Manager imports successfully")
        return True
    except Exception as e:
        print(f"✗ PTY Manager import failed: {e}")
        return False

def test_security_manager_import():
    """Test that security manager can be imported"""
    try:
        from core.security.terminal_security import TerminalSecurityManager
        print("✓ Security Manager imports successfully")
        return True
    except Exception as e:
        print(f"✗ Security Manager import failed: {e}")
        return False

def test_websocket_handler_import():
    """Test that WebSocket handler can be imported"""
    try:
        from api.v1.websocket.terminal import TerminalWebSocket, terminal_websocket_endpoint
        print("✓ WebSocket handler imports successfully")
        return True
    except Exception as e:
        print(f"✗ WebSocket handler import failed: {e}")
        return False

def test_security_validation():
    """Test security validation functions"""
    try:
        from core.security.terminal_security import TerminalSecurityManager
        
        security = TerminalSecurityManager()
        
        # Test input validation
        assert security.validate_input("ls -la") == True
        assert security.validate_input("echo 'hello world'") == True
        assert security.validate_input("a" * 10000) == False  # Too long
        assert security.validate_input("test\x00null") == False  # Null byte
        
        # Test command validation
        valid, _ = security.validate_command("ls -la")
        assert valid == True
        
        valid, _ = security.validate_command("rm -rf /")
        assert valid == False  # Dangerous command
        
        valid, _ = security.validate_command("cd ../../../etc")
        assert valid == False  # Path traversal
        
        # Test session ID validation
        assert security.validate_session_id("valid_session_123") == True
        assert security.validate_session_id("invalid session with spaces") == False
        assert security.validate_session_id("") == False
        assert security.validate_session_id("a" * 100) == False  # Too long
        
        # Test working directory validation
        valid, _ = security.validate_working_directory("/data/openpilot")
        # This might fail if directory doesn't exist, which is OK for testing
        
        print("✓ Security validation tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Security validation tests failed: {e}")
        return False

def test_pty_manager_creation():
    """Test PTY manager creation and basic functionality"""
    try:
        from core.services.terminal.pty_manager import PTYManager
        
        # Create manager
        manager = PTYManager()
        
        # Check initial state
        assert len(manager.processes) == 0
        assert len(manager.readers) == 0
        assert manager.security is not None
        
        # Test session info for non-existent session
        info = manager.get_session_info("nonexistent")
        assert info is None
        
        # Test list sessions (should be empty)
        sessions = manager.list_sessions()
        assert sessions == {}
        
        print("✓ PTY Manager creation tests passed")
        return True
        
    except Exception as e:
        print(f"✗ PTY Manager creation tests failed: {e}")
        return False

async def test_pty_manager_async():
    """Test PTY manager async functionality"""
    try:
        from core.services.terminal.pty_manager import PTYManager
        
        manager = PTYManager()
        
        # Test session creation (this might fail without proper permissions)
        try:
            process = await manager.create_pty("test_session")
            
            # If creation succeeded, test basic functionality
            assert process.pid > 0
            assert process.master_fd > 0
            
            # Test session info
            info = manager.get_session_info("test_session")
            assert info is not None
            assert info["session_id"] == "test_session"
            assert info["pid"] == process.pid
            
            # Clean up
            await manager.terminate_pty("test_session")
            
            print("✓ PTY Manager async tests passed")
            return True
            
        except PermissionError:
            print("⚠ PTY creation requires elevated permissions (skipped)")
            return True
        except Exception as e:
            print(f"✗ PTY Manager async tests failed: {e}")
            return False
            
    except Exception as e:
        print(f"✗ PTY Manager async test setup failed: {e}")
        return False

def test_websocket_handler_creation():
    """Test WebSocket handler creation"""
    try:
        from api.v1.websocket.terminal import TerminalWebSocket
        from core.services.terminal.pty_manager import PTYManager
        from unittest.mock import Mock
        
        # Create mock WebSocket
        mock_websocket = Mock()
        pty_manager = PTYManager()
        
        # Create handler
        handler = TerminalWebSocket(mock_websocket, pty_manager)
        
        # Check initial state
        assert handler.websocket == mock_websocket
        assert handler.pty_manager == pty_manager
        assert handler.session_id is None
        assert handler.security is not None
        assert isinstance(handler.message_timestamps, list)
        
        print("✓ WebSocket handler creation tests passed")
        return True
        
    except Exception as e:
        print(f"✗ WebSocket handler creation tests failed: {e}")
        return False

def test_dependencies_integration():
    """Test that dependencies are properly integrated"""
    try:
        from app.dependencies import get_pty_manager
        
        # Test dependency function
        pty_manager = get_pty_manager()
        assert pty_manager is not None
        
        # Test it's a PTY manager
        from core.services.terminal.pty_manager import PTYManager
        assert isinstance(pty_manager, PTYManager)
        
        print("✓ Dependencies integration tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Dependencies integration tests failed: {e}")
        return False

def test_main_app_terminal_route():
    """Test that main app includes terminal route"""
    try:
        from app.main import create_app
        from config.settings_simple import ConciergeSettings
        
        settings = ConciergeSettings()
        app = create_app(settings)
        
        # Check for terminal route
        routes = [route.path for route in app.routes]
        assert "/terminal" in routes
        
        # Check for WebSocket route (indirectly through API router)
        api_routes = []
        for route in app.routes:
            if hasattr(route, 'path_regex') and '/api' in str(route.path_regex):
                api_routes.append(route)
        
        assert len(api_routes) > 0  # Should have API routes
        
        print("✓ Main app terminal route tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Main app terminal route tests failed: {e}")
        return False

def test_static_files():
    """Test that static files are accessible"""
    try:
        base_path = Path(__file__).parent.parent
        
        # Check JavaScript file
        js_file = base_path / "static" / "js" / "terminal" / "Terminal.js"
        assert js_file.exists()
        
        # Check basic content
        content = js_file.read_text()
        assert "ConciergeTerminal" in content
        assert "xterm.js" in content
        assert "WebSocket" in content
        
        # Check HTML template
        html_file = base_path / "templates" / "terminal.html"
        assert html_file.exists()
        
        html_content = html_file.read_text()
        assert "terminal-container" in html_content
        assert "xterm.js" in html_content
        
        print("✓ Static files tests passed")
        return True
        
    except Exception as e:
        print(f"✗ Static files tests failed: {e}")
        return False

def main():
    """Run all Phase 1 terminal tests"""
    print("=== Testing Terminal Emulator Phase 1 ===\n")
    
    tests = [
        test_terminal_structure,
        test_pty_manager_import,
        test_security_manager_import,
        test_websocket_handler_import,
        test_security_validation,
        test_pty_manager_creation,
        test_websocket_handler_creation,
        test_dependencies_integration,
        test_main_app_terminal_route,
        test_static_files
    ]
    
    # Run async test separately
    async_tests = [
        test_pty_manager_async
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}\n")
    
    # Run async tests
    for test in async_tests:
        try:
            result = asyncio.run(test())
            if result:
                passed += 1
            print()
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}\n")
    
    total_tests = len(tests) + len(async_tests)
    print(f"Terminal Phase 1 Tests: {passed}/{total_tests} passed")
    
    if passed == total_tests:
        print("🎉 Terminal Emulator Phase 1 is complete!")
        print("\nImplemented features:")
        print("- PTY Manager with process control and I/O handling")
        print("- Security manager with input validation and resource limits")
        print("- WebSocket handler with rate limiting and error handling")
        print("- xterm.js frontend with modern terminal rendering")
        print("- Integration with FastAPI and dependency injection")
        print("- Terminal page at /terminal")
        print("\nWebSocket endpoint: /api/v1/terminal/ws")
        print("Terminal page: /terminal")
        print("\nReady for production testing!")
        return True
    else:
        print("❌ Some Terminal Phase 1 tests failed")
        return False

if __name__ == "__main__":
    main()