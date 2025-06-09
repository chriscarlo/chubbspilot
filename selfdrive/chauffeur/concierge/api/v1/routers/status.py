"""Status API endpoints"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException

from openpilot.selfdrive.chauffeur.concierge.app.dependencies import get_status_service
from openpilot.selfdrive.chauffeur.concierge.core.services.status_service import StatusService

router = APIRouter()


@router.get("/", summary="Get current system status")
async def get_status(
    status_service: StatusService = Depends(get_status_service)
) -> Dict[str, Any]:
    """Get current openpilot system status"""
    try:
        status = status_service.get_current_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/health", summary="Health check endpoint")
async def health_check(
    status_service: StatusService = Depends(get_status_service)
) -> Dict[str, Any]:
    """Simple health check"""
    return {
        "success": True,
        "status": "healthy",
        "messaging_available": status_service.is_available,
        "service_count": len(status_service.available_services)
    }


@router.post("/polling/start", summary="Start status polling")
async def start_polling(
    status_service: StatusService = Depends(get_status_service)
) -> Dict[str, Any]:
    """Start background status polling"""
    try:
        await status_service.start_polling()
        return {
            "success": True,
            "message": "Status polling started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start polling: {str(e)}")


@router.post("/polling/stop", summary="Stop status polling")
async def stop_polling(
    status_service: StatusService = Depends(get_status_service)
) -> Dict[str, Any]:
    """Stop background status polling"""
    try:
        await status_service.stop_polling()
        return {
            "success": True,
            "message": "Status polling stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop polling: {str(e)}")


@router.get("/services", summary="Get available services")
async def get_services(
    status_service: StatusService = Depends(get_status_service)
) -> Dict[str, Any]:
    """Get list of available openpilot services"""
    return {
        "success": True,
        "services": status_service.available_services,
        "count": len(status_service.available_services)
    }