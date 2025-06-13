#!/usr/bin/env python3
"""Test Phase 3 API layer of Concierge refactor"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_api_structure():
    """Test that API structure is properly organized"""
    base_path = Path(__file__).parent
    
    expected_files = [
        "api/__init__.py",
        "api/v1/__init__.py",
        "api/v1/models/__init__.py",
        "api/v1/routers/__init__.py",
        "api/v1/routers/status.py",
        "api/v1/routers/terminal.py",
        "api/v1/routers/monitoring.py"
    ]
    
    missing_files = []
    for file_path in expected_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"✗ Missing API files: {missing_files}")
        return False
    else:
        print(f"✓ All {len(expected_files)} API files exist")
        return True

def test_router_definitions():
    """Test that router definitions are valid"""
    base_path = Path(__file__).parent
    
    routers_to_check = {
        "api/v1/routers/status.py": ["get_status", "health_check", "start_polling"],
        "api/v1/routers/terminal.py": ["execute_command", "get_session_info", "get_command_history"],
        "api/v1/routers/monitoring.py": ["get_available_services", "start_monitoring", "stop_monitoring"]
    }
    
    try:
        for file_path, endpoints in routers_to_check.items():
            full_path = base_path / file_path
            content = full_path.read_text()
            
            # Check for router definition
            if "router = APIRouter()" not in content:
                print(f"✗ Router not defined in {file_path}")
                return False
            
            # Check for endpoint functions
            missing_endpoints = []
            for endpoint in endpoints:
                if f"async def {endpoint}" not in content:
                    missing_endpoints.append(endpoint)
            
            if missing_endpoints:
                print(f"✗ Missing endpoints in {file_path}: {missing_endpoints}")
                return False
        
        print(f"✓ All router definitions and endpoints found")
        return True
        
    except Exception as e:
        print(f"✗ Router definition check failed: {e}")
        return False

def test_model_definitions():
    """Test that API models are properly defined"""
    try:
        base_path = Path(__file__).parent
        models_file = base_path / "api" / "v1" / "models" / "__init__.py"
        content = models_file.read_text()
        
        expected_models = [
            "SuccessResponse",
            "ErrorResponse", 
            "CommandRequest",
            "MonitoringRequest",
            "SessionRequest"
        ]
        
        missing_models = []
        for model in expected_models:
            if f"class {model}" not in content:
                missing_models.append(model)
        
        if missing_models:
            print(f"✗ Missing models: {missing_models}")
            return False
        else:
            print(f"✓ All {len(expected_models)} API models found")
            return True
            
    except Exception as e:
        print(f"✗ Model definition check failed: {e}")
        return False

def test_main_app_integration():
    """Test that main app integrates v1 API"""
    try:
        base_path = Path(__file__).parent
        main_file = base_path / "app" / "main.py"
        content = main_file.read_text()
        
        # Check for v1 router import
        if "from openpilot.selfdrive.chauffeur.concierge.api.v1 import v1_router" not in content:
            print("✗ v1_router not imported in main.py")
            return False
        
        # Check for router inclusion
        if "app.include_router(v1_router" not in content:
            print("✗ v1_router not included in main.py")
            return False
        
        # Check for docs enablement
        if 'docs_url="/api/docs"' not in content:
            print("✗ API docs not enabled in main.py")
            return False
        
        print("✓ Main app properly integrates v1 API")
        return True
        
    except Exception as e:
        print(f"✗ Main app integration check failed: {e}")
        return False

def test_import_compatibility():
    """Test that imports work without circular dependencies"""
    try:
        # Test v1 router import
        from api.v1 import v1_router
        print("✓ v1_router imports successfully")
        
        # Test models import
        from api.v1.models import CommandRequest, MonitoringRequest
        print("✓ API models import successfully")
        
        # Test individual routers
        from api.v1.routers import status, terminal, monitoring
        print("✓ Individual routers import successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import compatibility check failed: {e}")
        return False

def test_app_creation():
    """Test that app can be created with new structure"""
    try:
        from app.main import create_app
        from config.settings_simple import ConciergeSettings
        
        settings = ConciergeSettings()
        app = create_app(settings)
        
        print("✓ App creation with v1 API succeeds")
        print(f"  Title: {app.title}")
        print(f"  Version: {app.version}")
        print(f"  Routes count: {len(app.routes)}")
        
        return True
        
    except Exception as e:
        print(f"✗ App creation test failed: {e}")
        return False

def main():
    """Run all Phase 3 tests"""
    print("=== Testing Phase 3 API Layer ===\\n")
    
    tests = [
        test_api_structure,
        test_router_definitions,
        test_model_definitions,
        test_main_app_integration,
        test_import_compatibility,
        test_app_creation
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}\\n")
    
    print(f"Phase 3 API Tests: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 Phase 3 API layer is complete!")
        print("\\nThe new API provides:")
        print("- Status endpoints: /api/v1/status/*")
        print("- Terminal endpoints: /api/v1/terminal/*") 
        print("- Monitoring endpoints: /api/v1/monitoring/*")
        print("- Interactive docs: /api/docs")
        print("- OpenAPI spec: /api/redoc")
        print("\\nReady for Phase 4: Infrastructure Layer")
        return True
    else:
        print("❌ Some Phase 3 API tests failed")
        return False

if __name__ == "__main__":
    main()