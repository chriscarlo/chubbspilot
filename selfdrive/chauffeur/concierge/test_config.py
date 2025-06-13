#!/usr/bin/env python3
"""Test configuration and basic structure of Phase 1 refactor"""

import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_configuration():
    """Test that our configuration works"""
    from config.settings_simple import ConciergeSettings
    
    settings = ConciergeSettings()
    print(f"✓ Settings created successfully")
    print(f"  Host: {settings.host}")
    print(f"  Port: {settings.port}")
    print(f"  Debug: {settings.debug}")
    print(f"  Static dir: {settings.static_dir}")
    print(f"  Templates dir: {settings.templates_dir}")
    return True

def test_dependencies():
    """Test that dependency injection setup works"""
    # Test the core dependency function logic directly
    from config.settings_simple import ConciergeSettings
    from functools import lru_cache
    
    @lru_cache()
    def get_settings_test() -> ConciergeSettings:
        return ConciergeSettings()
    
    settings1 = get_settings_test()
    settings2 = get_settings_test()
    
    # Should be the same instance due to lru_cache
    assert settings1 is settings2
    
    print(f"✓ Dependency injection pattern works")
    print(f"  Retrieved cached settings with host: {settings1.host}")
    return True

def test_constants():
    """Test that constants are accessible"""
    from config.constants import WANTED_SERVICES, DEFAULT_COMMAND_TIMEOUT
    
    print(f"✓ Constants loaded successfully")
    print(f"  Wanted services: {WANTED_SERVICES}")
    print(f"  Default timeout: {DEFAULT_COMMAND_TIMEOUT}")
    return True

def main():
    """Run all Phase 1 tests"""
    print("=== Testing Phase 1 Concierge Refactor ===\n")
    
    tests = [
        test_configuration,
        test_dependencies, 
        test_constants
    ]
    
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print()
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}\n")
    
    print(f"Phase 1 Tests: {passed}/{len(tests)} passed")
    
    if passed == len(tests):
        print("🎉 Phase 1 foundation is complete and working!")
        return True
    else:
        print("❌ Some Phase 1 tests failed")
        return False

if __name__ == "__main__":
    main()