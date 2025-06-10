"""Pytest configuration for Concierge tests."""
import os
import sys
import asyncio
import pytest
from typing import AsyncGenerator, Generator
import subprocess
import time

# Add persistent packages to path
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")

# Import test dependencies
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    import httpx
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Fixture for using system chromium if playwright not available
@pytest.fixture
def chromium_executable():
    """Get chromium executable path."""
    # Try snap chromium first
    if os.path.exists("/snap/bin/chromium"):
        return "/snap/bin/chromium"
    # Try system chromium
    for path in ["/usr/bin/chromium-browser", "/usr/bin/chromium", "/usr/bin/google-chrome"]:
        if os.path.exists(path):
            return path
    return None

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def start_concierge_server():
    """Start the Concierge server for testing."""
    # Kill any existing server
    subprocess.run(["pkill", "-f", "concierge/app/main.py"], capture_output=True)
    
    # Start new server
    env = os.environ.copy()
    env["PYTHONPATH"] = "/data/openpilot:/data/openpilot/.local/lib/python3.11/site-packages"
    
    server_process = subprocess.Popen(
        ["python3", "/data/openpilot/selfdrive/chauffeur/concierge/app/main.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    await asyncio.sleep(3)
    
    yield server_process
    
    # Cleanup
    server_process.terminate()
    server_process.wait()

@pytest.fixture
async def test_client():
    """Create test client for API testing."""
    if not HTTPX_AVAILABLE:
        pytest.skip("httpx not available")
    
    from selfdrive.chauffeur.concierge.app.main import app
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

if PLAYWRIGHT_AVAILABLE:
    @pytest.fixture(scope="session")
    async def browser() -> AsyncGenerator[Browser, None]:
        """Create browser instance."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            yield browser
            await browser.close()

    @pytest.fixture
    async def context(browser: Browser) -> AsyncGenerator[BrowserContext, None]:
        """Create browser context."""
        context = await browser.new_context()
        yield context
        await context.close()

    @pytest.fixture
    async def page(context: BrowserContext) -> AsyncGenerator[Page, None]:
        """Create new page."""
        page = await context.new_page()
        yield page
        await page.close()
else:
    # Fallback fixtures when playwright not available
    @pytest.fixture
    async def browser():
        pytest.skip("Playwright not available")
    
    @pytest.fixture
    async def context():
        pytest.skip("Playwright not available")
    
    @pytest.fixture
    async def page():
        pytest.skip("Playwright not available")