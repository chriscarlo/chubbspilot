"""Service monitoring and management"""

import re
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.core.managers.process_manager import ProcessManager


class MonitoringService:
    """Service for monitoring external processes and services"""
    
    def __init__(self, settings: ConciergeSettings):
        self.settings = settings
        self.process_manager = ProcessManager(settings)
        self._cached_services = None
    
    def get_available_services(self) -> Dict[str, List[str]]:
        """Get list of available services for monitoring"""
        if self._cached_services is None:
            self._cached_services = self._parse_capnp_services()
        return self._cached_services
    
    def _parse_capnp_services(self) -> Dict[str, List[str]]:
        """Parse capnp files to find available services"""
        log_capnp_path = self.settings.openpilot_root / "cereal" / "log.capnp"
        
        if not log_capnp_path.exists():
            return {"services": [], "error": "log.capnp file not found"}
        
        try:
            with open(log_capnp_path, 'r') as f:
                content = f.read()
            
            # Extract union members from Event struct
            event_match = re.search(r'struct Event.*?union\s*\{(.*?)\}', content, re.DOTALL)
            if not event_match:
                return {"services": [], "error": "Could not find Event union"}
            
            union_content = event_match.group(1)
            
            # Find all service names
            service_pattern = r'(\w+)\s*@\d+\s*:\s*\w+'
            services = re.findall(service_pattern, union_content)
            
            # Filter out non-service entries
            filtered_services = [
                s for s in services 
                if not s.startswith(('deprecated', 'placeholder', 'reserved'))
            ]
            
            return {"services": sorted(filtered_services)}
            
        except Exception as e:
            return {"services": [], "error": f"Failed to parse capnp: {str(e)}"}
    
    async def start_monitoring(self, services: List[str]) -> str:
        """Start monitoring specified services"""
        # Validate services
        available = self.get_available_services()
        if "error" in available:
            raise ValueError(f"Cannot get available services: {available['error']}")
        
        invalid_services = [s for s in services if s not in available["services"]]
        if invalid_services:
            raise ValueError(f"Invalid services: {', '.join(invalid_services)}")
        
        # Delegate to process manager
        return await self.process_manager.start_service_monitoring(services)
    
    async def stop_monitoring(self) -> str:
        """Stop active service monitoring"""
        return await self.process_manager.stop_service_monitoring()
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return self.process_manager.get_monitoring_status()
    
    async def get_monitoring_stream(self) -> AsyncGenerator[str, None]:
        """Get service monitoring data stream"""
        async for data in self.process_manager.get_monitoring_stream():
            yield data
    
    async def validate_services(self, services: List[str]) -> Dict[str, Any]:
        """Validate that the requested services are available"""
        available = self.get_available_services()
        
        if "error" in available:
            return {
                "valid": False,
                "error": available["error"],
                "available_services": []
            }
        
        available_services = available["services"]
        valid_services = [s for s in services if s in available_services]
        invalid_services = [s for s in services if s not in available_services]
        
        return {
            "valid": len(invalid_services) == 0,
            "valid_services": valid_services,
            "invalid_services": invalid_services,
            "available_services": available_services
        }
    
    def refresh_services_cache(self):
        """Refresh the cached services list"""
        self._cached_services = None
        return self.get_available_services()