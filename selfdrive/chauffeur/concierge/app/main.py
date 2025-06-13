"""Application factory for Concierge web server"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.app.lifespan import lifespan
from openpilot.selfdrive.chauffeur.concierge.api.v1 import v1_router
from openpilot.selfdrive.chauffeur.concierge.core.logging_config import setup_logging, log_function_call

# Set up logger for this module
logger = setup_logging("app.main")


def create_app(settings: ConciergeSettings = None) -> FastAPI:
    """Create and configure FastAPI application"""
    logger.info("=== CREATING CONCIERGE APP ===")
    
    if settings is None:
        logger.debug("No settings provided, creating default ConciergeSettings")
        settings = ConciergeSettings()
    
    logger.debug(f"Settings: host={settings.host}, port={settings.port}, debug={settings.debug}")
    logger.debug(f"Static dir: {settings.static_dir}")
    logger.debug(f"Templates dir: {settings.templates_dir}")
    
    app = FastAPI(
        title="Concierge",
        description="openpilot Concierge Web Server",
        version="2.0.0",
        docs_url="/api/docs",  # Enable docs at /api/docs
        redoc_url="/api/redoc",  # Enable redoc at /api/redoc
        lifespan=lifespan
    )
    logger.info("FastAPI app instance created")
    
    # Store settings in app state for access in endpoints
    app.state.settings = settings
    
    # Include v1 API router
    logger.info("Including v1 API router at /api")
    app.include_router(v1_router, prefix="/api")
    
    # Mount static files
    logger.info(f"Mounting static files from {settings.static_dir}")
    app.mount(
        "/static", 
        StaticFiles(directory=str(settings.static_dir)), 
        name="static"
    )
    
    # Configure templates
    logger.info(f"Configuring templates from {settings.templates_dir}")
    templates = Jinja2Templates(directory=str(settings.templates_dir))
    
    # Dashboard page endpoint
    @app.get("/")
    async def root(request: Request):
        """Root endpoint - serve dashboard page"""
        return templates.TemplateResponse("index.html", {"request": request})
    
    # API info endpoint
    @app.get("/api/info")
    async def api_info():
        """API information endpoint"""
        return {
            "message": "Concierge Web Server",
            "version": "2.0.0",
            "status": "online",
            "api": {
                "v1": "/api/v1",
                "docs": "/api/docs",
                "redoc": "/api/redoc"
            }
        }
    
    # Legacy compatibility endpoint - will be removed in Phase 5
    @app.get("/health")
    async def health_check():
        """Legacy health check endpoint"""
        return {"status": "healthy", "version": "2.0.0"}
    
    # Terminal page endpoint
    @app.get("/terminal")
    async def terminal_page(request: Request):
        """Terminal emulator page"""
        return templates.TemplateResponse("terminal.html", {"request": request})
    
    # HTMX endpoints for smooth transitions
    @app.get("/htmx/dashboard")
    async def htmx_dashboard(request: Request):
        """Dashboard content for HTMX requests"""
        if request.headers.get("X-HTMX-Request"):
            return templates.TemplateResponse("dashboard_content.html", {"request": request})
        return templates.TemplateResponse("index.html", {"request": request})
    
    @app.get("/htmx/terminal")
    async def htmx_terminal(request: Request):
        """Terminal content for HTMX requests"""
        if request.headers.get("X-HTMX-Request"):
            return templates.TemplateResponse("terminal_content.html", {"request": request})
        return templates.TemplateResponse("terminal.html", {"request": request})
    
    @app.get("/htmx/diagnostics")
    async def htmx_diagnostics(request: Request):
        """Diagnostics content for HTMX requests"""
        if request.headers.get("X-HTMX-Request"):
            return templates.TemplateResponse("diagnostics_content.html", {"request": request})
        # For now, return a placeholder
        return templates.TemplateResponse("index.html", {"request": request})
    
    @app.get("/htmx/logs")
    async def htmx_logs(request: Request):
        """Logs content for HTMX requests"""
        if request.headers.get("X-HTMX-Request"):
            return templates.TemplateResponse("logs_content.html", {"request": request})
        # For now, return a placeholder
        return templates.TemplateResponse("index.html", {"request": request})
    
    return app


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = ConciergeSettings()
    logger.info(f"Starting Concierge server on {settings.host}:{settings.port}")
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info" if not settings.debug else "debug"
    )