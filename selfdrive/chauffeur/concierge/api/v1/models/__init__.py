"""API models for request/response validation"""

from pydantic import BaseModel
from typing import Dict, Any, List, Optional


class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    """Request model for terminal commands"""
    command: str
    session_id: str = "default"


class MonitoringRequest(BaseModel):
    """Request model for monitoring operations"""
    services: List[str]


class SessionRequest(BaseModel):
    """Request model for session operations"""
    session_id: str = "default"


__all__ = [
    "SuccessResponse",
    "ErrorResponse", 
    "CommandRequest",
    "MonitoringRequest",
    "SessionRequest"
]