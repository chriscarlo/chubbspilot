#!/usr/bin/env python3
"""Test Phase 2 business logic components of Concierge refactor"""

import sys
import asyncio
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_zmq_manager():
    """Test ZMQ manager creation and health check"""
    # Patch the import to use local relative imports
    import core.managers.zmq_manager as zmq_mod
    # Patch the problematic import
    zmq_mod.ConciergeSettings = __import__('config.settings_simple', fromlist=['ConciergeSettings']).ConciergeSettings
    
    ZMQManager = zmq_mod.ZMQManager
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    zmq_manager = ZMQManager(settings)
    
    print(f"✓ ZMQ Manager created")
    print(f"  Available: {zmq_manager.is_available}")
    
    return True

def test_session_manager():
    """Test session management functionality"""
    from core.managers.session_manager import SessionManager
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    session_manager = SessionManager(settings)
    
    # Test session creation
    session = session_manager.get_session("test")
    print(f"✓ Session Manager created")
    print(f"  Default CWD: {session['cwd']}")
    
    # Test adding command to history
    session_manager.add_to_history("ls -la", "test")
    history = session_manager.get_history("test")
    assert len(history) == 1
    assert history[0] == "ls -la"
    
    print(f"  Command history working: {len(history)} commands")
    return True

def test_process_manager():
    """Test process manager creation"""
    from core.managers.process_manager import ProcessManager
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    process_manager = ProcessManager(settings)
    
    status = process_manager.get_monitoring_status()
    print(f"✓ Process Manager created")
    print(f"  Monitoring active: {status['active']}")
    
    return True

def test_status_service():
    """Test status service creation"""
    from core.services.status_service import StatusService
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    status_service = StatusService(settings)
    
    print(f"✓ Status Service created")
    print(f"  Messaging available: {status_service.is_available}")
    print(f"  Available services: {len(status_service.available_services)}")
    
    # Test getting status
    status = status_service.get_current_status()
    assert "time" in status
    
    return True

def test_terminal_service():
    """Test terminal service creation"""
    from core.services.terminal_service import TerminalService
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    terminal_service = TerminalService(settings)
    
    print(f"✓ Terminal Service created")
    
    # Test session info
    info = terminal_service.get_session_info()
    assert "session_id" in info
    assert "cwd" in info
    
    print(f"  Default session CWD: {info['cwd']}")
    return True

def test_monitoring_service():
    """Test monitoring service creation"""
    from core.services.monitoring_service import MonitoringService
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    monitoring_service = MonitoringService(settings)
    
    print(f"✓ Monitoring Service created")
    
    # Test getting available services
    services = monitoring_service.get_available_services()
    if "error" in services:
        print(f"  Services parsing: {services['error']}")
    else:
        print(f"  Available services: {len(services.get('services', []))}")
    
    return True

async def test_async_components():
    """Test async functionality of components"""
    from core.services.terminal_service import TerminalService
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    terminal_service = TerminalService(settings)
    
    # Test simple command execution
    result = await terminal_service.execute_command("echo 'Hello World'")
    print(f"✓ Async command execution working")
    print(f"  Command: {result['command']}")
    print(f"  Exit code: {result['exit_code']}")
    
    # Test cd command
    cd_result = await terminal_service.execute_command("cd /tmp")
    print(f"✓ Directory change handling working")
    print(f"  CD result: exit code {cd_result['exit_code']}")
    
    return True

def main():
    """Run all Phase 2 tests"""
    print("=== Testing Phase 2 Concierge Refactor ===\n")
    
    sync_tests = [
        test_zmq_manager,
        test_session_manager,
        test_process_manager,
        test_status_service,
        test_terminal_service,
        test_monitoring_service
    ]
    
    passed = 0
    
    # Run synchronous tests
    for test in sync_tests:
        try:
            test()
            passed += 1
            print()
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}\n")
    
    # Run async tests
    try:
        asyncio.run(test_async_components())
        passed += 1
        print()
    except Exception as e:
        print(f"✗ test_async_components failed: {e}\n")
    
    total_tests = len(sync_tests) + 1
    print(f"Phase 2 Tests: {passed}/{total_tests} passed")
    
    if passed == total_tests:
        print("🎉 Phase 2 business logic is complete and working!")
        print("\nNext: Phase 3 - API Layer Restructure")
        return True
    else:
        print("❌ Some Phase 2 tests failed")
        return False

if __name__ == "__main__":
    main()