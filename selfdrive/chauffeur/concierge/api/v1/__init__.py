"""Concierge API v1 endpoints"""

from fastapi import APIRouter
from .routers import status, terminal, monitoring

# Create v1 router
v1_router = APIRouter(prefix="/v1")

# Include endpoint routers
v1_router.include_router(status.router, prefix="/status", tags=["status"])
v1_router.include_router(terminal.router, prefix="/terminal", tags=["terminal"])
v1_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])

__all__ = ["v1_router"]