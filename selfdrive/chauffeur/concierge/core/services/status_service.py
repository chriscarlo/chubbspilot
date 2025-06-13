"""Status service for system monitoring"""

import asyncio
import json
from typing import Dict, Any, AsyncGenerator

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.config.constants import WANTED_SERVICES

# Conditional import for cereal messaging
try:
    from cereal import messaging
    MESSAGING_AVAILABLE = True
except ImportError:
    MESSAGING_AVAILABLE = False
    messaging = None


class StatusService:
    """Service for handling system status monitoring"""
    
    def __init__(self, settings: ConciergeSettings):
        self.settings = settings
        self.wanted_services = WANTED_SERVICES
        self._status_snapshot: Dict[str, Any] = {}
        self._poller_task: asyncio.Task = None
        self._is_available = MESSAGING_AVAILABLE
        
        if self._is_available:
            self.available_services = [
                s for s in self.wanted_services 
                if s in messaging.SERVICE_LIST
            ]
            self._sm = messaging.SubMaster(self.available_services)
        else:
            self.available_services = []
            self._sm = None
    
    @property
    def is_available(self) -> bool:
        """Check if messaging is available in this environment"""
        return self._is_available
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current system status snapshot"""
        if not self._is_available:
            return {
                "error": "Messaging not available in this environment",
                "time": 0
            }
        
        return self._status_snapshot.copy()
    
    def _update_snapshot(self):
        """Update the internal status snapshot"""
        if not self._is_available or not self._sm:
            return
        
        self._sm.update(0)
        snapshot = {"time": self._sm.frame}
        
        for service in self.available_services:
            try:
                snapshot[service] = self._sm[service].to_dict()
            except Exception as e:
                snapshot[service] = {"error": str(e)}
        
        self._status_snapshot = snapshot
    
    async def _status_poller(self):
        """Background task to continuously poll status"""
        if not self._is_available:
            return
        
        try:
            while True:
                self._update_snapshot()
                await asyncio.sleep(self.settings.status_poll_interval)
                
        except asyncio.CancelledError:
            print("Status poller cancelled")
        except Exception as e:
            print(f"Error in status poller: {e}")
    
    def start_polling(self):
        """Start background status polling"""
        if self._poller_task and not self._poller_task.done():
            return  # Already running
        
        if not self._is_available:
            print("Cannot start polling - messaging not available")
            return
        
        self._poller_task = asyncio.create_task(self._status_poller())
    
    async def stop_polling(self):
        """Stop background status polling"""
        if self._poller_task and not self._poller_task.done():
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError:
                print("Status poller successfully cancelled")
    
    async def get_status_stream(self) -> AsyncGenerator[str, None]:
        """Get real-time status as SSE stream"""
        last_frame = -1
        
        while True:
            current_status = self.get_current_status()
            frame = current_status.get("time", -1)
            
            if frame != last_frame:
                last_frame = frame
                yield f"data: {json.dumps(current_status)}\n\n"
            
            await asyncio.sleep(self.settings.status_poll_interval)
    
    async def check_messaging(self) -> bool:
        """Health check for messaging system"""
        if not self._is_available:
            return False
        
        try:
            # Try to get a status update
            self._update_snapshot()
            return True
        except Exception:
            return False


# Global instance for backward compatibility
_global_status_service: StatusService = None


def get_global_status():
    """Legacy function for backward compatibility"""
    global _global_status_service
    if _global_status_service is None:
        from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
        _global_status_service = StatusService(ConciergeSettings())
        _global_status_service.start_polling()
    
    return _global_status_service.get_current_status()