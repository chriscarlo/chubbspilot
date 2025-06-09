"""ZMQ connection management for Concierge"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

# Conditional import for ZMQ - handle case where it's not available
try:
    import zmq
    import zmq.asyncio
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    zmq = None

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings


class ZMQManager:
    """Manages ZeroMQ connections and contexts"""
    
    def __init__(self, settings: ConciergeSettings):
        self.settings = settings
        self._context: Optional[zmq.asyncio.Context] = None
        self._is_available = ZMQ_AVAILABLE
    
    @property
    def is_available(self) -> bool:
        """Check if ZMQ is available in this environment"""
        return self._is_available
    
    @property
    def context(self) -> zmq.asyncio.Context:
        """Get or create ZMQ context"""
        if not self._is_available:
            raise RuntimeError("ZMQ is not available in this environment")
        
        if self._context is None:
            self._context = zmq.asyncio.Context()
        return self._context
    
    @asynccontextmanager
    async def create_socket(self, socket_type: int):
        """Create and manage a ZMQ socket with proper cleanup"""
        if not self._is_available:
            raise RuntimeError("ZMQ is not available in this environment")
        
        socket = self.context.socket(socket_type)
        try:
            yield socket
        finally:
            socket.close()
    
    async def create_mapd_subscriber(self, port: int = None):
        """Create subscriber socket for MapD logs"""
        if not self._is_available:
            raise RuntimeError("ZMQ is not available in this environment")
        
        port = port or self.settings.mapd_zmq_port
        
        async with self.create_socket(zmq.SUB) as socket:
            socket.connect(f"tcp://localhost:{port}")
            socket.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all messages
            yield socket
    
    async def is_healthy(self) -> bool:
        """Check if ZMQ manager is healthy"""
        if not self._is_available:
            return False
        
        try:
            # Try to create a context if none exists
            if self._context is None:
                test_context = zmq.asyncio.Context()
                test_context.term()
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close ZMQ context and cleanup"""
        if self._context and self._is_available:
            self._context.term()
            self._context = None


# Backward compatibility - global context getter for existing code
_global_zmq_manager: Optional[ZMQManager] = None


def get_mapd_log_zmq_context():
    """Legacy function for backward compatibility"""
    global _global_zmq_manager
    if _global_zmq_manager is None:
        from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
        _global_zmq_manager = ZMQManager(ConciergeSettings())
    
    if not _global_zmq_manager.is_available:
        return None
    
    return _global_zmq_manager.context