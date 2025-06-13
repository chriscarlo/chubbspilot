#!/usr/bin/env python3
"""Simple test for Phase 2 structure and imports"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_file_structure():
    """Test that all expected files exist"""
    base_path = Path(__file__).parent
    
    expected_files = [
        "core/managers/zmq_manager.py",
        "core/managers/process_manager.py", 
        "core/managers/session_manager.py",
        "core/services/status_service.py",
        "core/services/terminal_service.py",
        "core/services/monitoring_service.py"
    ]
    
    missing_files = []
    for file_path in expected_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"✗ Missing files: {missing_files}")
        return False
    else:
        print(f"✓ All {len(expected_files)} expected files exist")
        return True

def test_basic_imports():
    """Test that modules can be imported"""
    try:
        from config.settings_simple import ConciergeSettings
        settings = ConciergeSettings()
        print(f"✓ Settings can be imported and created")
        print(f"  Host: {settings.host}, Port: {settings.port}")
        return True
    except Exception as e:
        print(f"✗ Settings import failed: {e}")
        return False

def test_class_definitions():
    """Test that class definitions are valid"""
    try:
        # Test if we can read the files and they contain class definitions
        base_path = Path(__file__).parent
        
        classes_to_check = {
            "core/managers/zmq_manager.py": "ZMQManager",
            "core/managers/process_manager.py": "ProcessManager",
            "core/managers/session_manager.py": "SessionManager", 
            "core/services/status_service.py": "StatusService",
            "core/services/terminal_service.py": "TerminalService",
            "core/services/monitoring_service.py": "MonitoringService"
        }
        
        for file_path, class_name in classes_to_check.items():
            full_path = base_path / file_path
            content = full_path.read_text()
            if f"class {class_name}" not in content:
                print(f"✗ {class_name} not found in {file_path}")
                return False
        
        print(f"✓ All {len(classes_to_check)} expected classes found")
        return True
        
    except Exception as e:
        print(f"✗ Class definition check failed: {e}")
        return False

def test_method_signatures():
    """Test that key methods exist in class definitions"""
    base_path = Path(__file__).parent
    
    method_checks = {
        "core/services/status_service.py": ["get_current_status", "start_polling"],
        "core/services/terminal_service.py": ["execute_command", "get_session_info"],
        "core/managers/process_manager.py": ["start_service_monitoring", "stop_service_monitoring"],
        "core/managers/zmq_manager.py": ["create_socket", "is_available"]
    }
    
    try:
        for file_path, methods in method_checks.items():
            full_path = base_path / file_path
            content = full_path.read_text()
            
            missing_methods = []
            for method in methods:
                if f"def {method}" not in content:
                    missing_methods.append(method)
            
            if missing_methods:
                print(f"✗ Missing methods in {file_path}: {missing_methods}")
                return False
        
        print(f"✓ All expected methods found in classes")
        return True
        
    except Exception as e:
        print(f"✗ Method signature check failed: {e}")
        return False

def test_dependency_structure():
    """Test that dependency injection structure is sound"""
    try:
        base_path = Path(__file__).parent
        deps_file = base_path / "app" / "dependencies.py"
        content = deps_file.read_text()
        
        expected_functions = [
            "get_settings",
            "get_zmq_manager", 
            "get_process_manager",
            "get_status_service",
            "get_terminal_service",
            "get_monitoring_service"
        ]
        
        missing_functions = []
        for func in expected_functions:
            if f"def {func}" not in content:
                missing_functions.append(func)
        
        if missing_functions:
            print(f"✗ Missing dependency functions: {missing_functions}")
            return False
        else:
            print(f"✓ All {len(expected_functions)} dependency functions found")
            return True
            
    except Exception as e:
        print(f"✗ Dependency structure check failed: {e}")
        return False

def main():
    """Run all Phase 2 structure tests"""
    print("=== Testing Phase 2 Structure ===\n")
    
    tests = [
        test_file_structure,
        test_basic_imports,
        test_class_definitions,
        test_method_signatures,
        test_dependency_structure
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}\n")
    
    print(f"Phase 2 Structure Tests: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 Phase 2 business logic structure is complete!")
        print("\nAll classes and methods are properly defined.")
        print("Ready for Phase 3: API Layer Restructure")
        return True
    else:
        print("❌ Some Phase 2 structure tests failed")
        return False

if __name__ == "__main__":
    main()