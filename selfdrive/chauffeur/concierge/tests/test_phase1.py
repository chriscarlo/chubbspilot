"""Test Phase 1 foundation components"""

import pytest
from fastapi.testclient import TestClient

from openpilot.selfdrive.chauffeur.concierge.config.settings import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.app.main import create_app
from openpilot.selfdrive.chauffeur.concierge.app.dependencies import get_settings


def test_settings_creation():
    """Test that settings can be created with defaults"""
    settings = ConciergeSettings()
    assert settings.host == "0.0.0.0"
    assert settings.port == 5055
    assert settings.debug is False


def test_app_creation():
    """Test that FastAPI app can be created"""
    settings = ConciergeSettings(debug=True)
    app = create_app(settings)
    assert app.title == "Concierge"
    assert app.state.settings.debug is True


def test_app_with_client():
    """Test that app responds to requests"""
    app = create_app()
    client = TestClient(app)
    
    response = client.get("/")
    assert response.status_code == 200
    assert "Concierge refactor in progress" in response.json()["message"]


def test_dependency_injection():
    """Test that dependency injection works"""
    settings = get_settings()
    assert isinstance(settings, ConciergeSettings)