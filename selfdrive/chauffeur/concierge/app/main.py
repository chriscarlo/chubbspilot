"""Application factory for Concierge web server"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.app.lifespan import lifespan
from openpilot.selfdrive.chauffeur.concierge.api.v1 import v1_router


def create_app(settings: ConciergeSettings = None) -> FastAPI:
    """Create and configure FastAPI application"""
    
    if settings is None:
        settings = ConciergeSettings()
    
    app = FastAPI(
        title="Concierge",
        description="openpilot Concierge Web Server",
        version="2.0.0",
        docs_url="/api/docs",  # Enable docs at /api/docs
        redoc_url="/api/redoc",  # Enable redoc at /api/redoc
        lifespan=lifespan
    )
    
    # Store settings in app state for access in endpoints
    app.state.settings = settings
    
    # Include v1 API router
    app.include_router(v1_router, prefix="/api")
    
    # Mount static files
    app.mount(
        "/static", 
        StaticFiles(directory=str(settings.static_dir)), 
        name="static"
    )
    
    # Configure templates
    templates = Jinja2Templates(directory=str(settings.templates_dir))
    
    # Health check endpoint
    @app.get("/")
    async def root():
        """Root endpoint - health check"""
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
    
    return app


# Create app instance for uvicorn
app = create_app()