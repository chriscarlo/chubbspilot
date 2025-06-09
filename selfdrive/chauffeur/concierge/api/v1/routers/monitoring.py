"""Monitoring API endpoints"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from openpilot.selfdrive.chauffeur.concierge.app.dependencies import get_monitoring_service
from openpilot.selfdrive.chauffeur.concierge.core.services.monitoring_service import MonitoringService
from openpilot.selfdrive.chauffeur.concierge.api.v1.models import MonitoringRequest

router = APIRouter()


@router.get("/services", summary="Get available services for monitoring")
async def get_available_services(
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
) -> Dict[str, Any]:
    """Get list of services available for monitoring"""
    try:
        services = monitoring_service.get_available_services()
        return {
            "success": True,
            "data": services
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get services: {str(e)}")


@router.post("/services/validate", summary="Validate service names")
async def validate_services(
    request: MonitoringRequest,
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
) -> Dict[str, Any]:
    """Validate that the requested services are available for monitoring"""
    try:
        validation = await monitoring_service.validate_services(request.services)
        return {
            "success": True,
            "data": validation
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/start", summary="Start monitoring services")
async def start_monitoring(
    request: MonitoringRequest,
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
) -> Dict[str, Any]:
    """Start monitoring the specified services"""
    try:
        # Validate services first
        validation = await monitoring_service.validate_services(request.services)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid services: {validation['invalid_services']}"
            )
        
        # Start monitoring
        monitor_id = await monitoring_service.start_monitoring(request.services)
        return {
            "success": True,
            "message": f"Started monitoring {len(request.services)} services",
            "data": {
                "monitor_id": monitor_id,
                "services": request.services
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")


@router.post("/stop", summary="Stop monitoring")
async def stop_monitoring(
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
) -> Dict[str, Any]:
    """Stop active service monitoring"""
    try:
        result = await monitoring_service.stop_monitoring()
        return {
            "success": True,
            "message": "Monitoring stopped",
            "data": {"result": result}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")


@router.get("/status", summary="Get monitoring status")
async def get_monitoring_status(
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
) -> Dict[str, Any]:
    """Get current monitoring status"""
    try:
        status = monitoring_service.get_monitoring_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/stream", summary="Get monitoring data stream")
async def get_monitoring_stream(
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
):
    """Get real-time monitoring data stream"""
    try:
        async def generate_stream():
            try:
                async for data in monitoring_service.get_monitoring_stream():
                    yield f"data: {data}\\n\\n"
            except Exception as e:
                yield f"data: {{\\\"error\\\": \\\"{str(e)}\\\"}}\\n\\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")


@router.post("/refresh", summary="Refresh services cache")
async def refresh_services(
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
) -> Dict[str, Any]:
    """Refresh the cached list of available services"""
    try:
        services = monitoring_service.refresh_services_cache()
        return {
            "success": True,
            "message": "Services cache refreshed",
            "data": services
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh cache: {str(e)}")


@router.get("/health", summary="Monitoring service health check")
async def monitoring_health(
    monitoring_service: MonitoringService = Depends(get_monitoring_service)
) -> Dict[str, Any]:
    """Health check for monitoring service"""
    try:
        services = monitoring_service.get_available_services()
        status = monitoring_service.get_monitoring_status()
        
        return {
            "success": True,
            "status": "healthy",
            "services_available": "error" not in services,
            "monitoring_active": status.get("active", False),
            "service_count": len(services.get("services", []))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Monitoring service unhealthy: {str(e)}")