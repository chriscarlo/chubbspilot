"""Application factory for Concierge web server"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.app.lifespan import lifespan


def create_app(settings: ConciergeSettings = None) -> FastAPI:
    """Create and configure FastAPI application"""
    
    if settings is None:
        settings = ConciergeSettings()
    
    app = FastAPI(
        title="Concierge",
        description="openpilot Concierge Web Server",
        version="2.0.0",
        docs_url=None,  # Disable automatic docs
        redoc_url=None,  # Disable automatic redoc
        lifespan=lifespan
    )
    
    # Store settings in app state for access in endpoints
    app.state.settings = settings
    
    # TODO: Include routers in Phase 3
    # app.include_router(api_v1_router, prefix="/api/v1")
    # app.include_router(frontend_router)
    
    # Mount static files
    app.mount(
        "/static", 
        StaticFiles(directory=str(settings.static_dir)), 
        name="static"
    )
    
    # Temporary legacy compatibility endpoint - will be removed in Phase 5
    @app.get("/")
    async def legacy_redirect():
        """Temporary redirect to maintain compatibility during refactor"""
        return {"message": "Concierge refactor in progress", "status": "Phase 1 complete"}
    
    return app


# Create app instance for uvicorn
app = create_app()