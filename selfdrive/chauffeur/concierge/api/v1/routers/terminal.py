"""Terminal API endpoints"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException

from openpilot.selfdrive.chauffeur.concierge.app.dependencies import get_terminal_service
from openpilot.selfdrive.chauffeur.concierge.core.services.terminal_service import TerminalService
from openpilot.selfdrive.chauffeur.concierge.api.v1.models import CommandRequest, SessionRequest

router = APIRouter()


@router.post("/execute", summary="Execute terminal command")
async def execute_command(
    request: CommandRequest,
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> Dict[str, Any]:
    """Execute a shell command in the specified session"""
    try:
        result = await terminal_service.execute_command(
            request.command, 
            request.session_id
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Command execution failed: {str(e)}")


@router.get("/session/{session_id}/info", summary="Get session information")
async def get_session_info(
    session_id: str,
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> Dict[str, Any]:
    """Get information about the specified session"""
    try:
        info = terminal_service.get_session_info(session_id)
        return {
            "success": True,
            "data": info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")


@router.get("/session/{session_id}/history", summary="Get command history")
async def get_command_history(
    session_id: str,
    limit: int = 10,
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> Dict[str, Any]:
    """Get command history for the specified session"""
    try:
        history = terminal_service.get_command_history(session_id, limit)
        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "history": history,
                "count": len(history)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/sessions", summary="Get all session information")
async def get_all_sessions(
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> Dict[str, Any]:
    """Get information about all active sessions"""
    try:
        # Get default session info as example
        default_info = terminal_service.get_session_info("default")
        return {
            "success": True,
            "data": {
                "sessions": {
                    "default": default_info
                },
                "count": 1
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")


@router.post("/session/create", summary="Create new session")
async def create_session(
    request: SessionRequest,
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> Dict[str, Any]:
    """Create a new terminal session"""
    try:
        # Get session info (this will create it if it doesn't exist)
        info = terminal_service.get_session_info(request.session_id)
        return {
            "success": True,
            "message": f"Session {request.session_id} created",
            "data": info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/health", summary="Terminal service health check")
async def terminal_health(
    terminal_service: TerminalService = Depends(get_terminal_service)
) -> Dict[str, Any]:
    """Health check for terminal service"""
    try:
        # Test basic functionality
        default_info = terminal_service.get_session_info("default")
        return {
            "success": True,
            "status": "healthy",
            "default_session": default_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terminal service unhealthy: {str(e)}")