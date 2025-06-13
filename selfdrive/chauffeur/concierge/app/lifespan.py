"""Application lifecycle management for Concierge"""

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI


class GracefulShutdown:
    """Manages graceful shutdown of the application"""
    
    def __init__(self):
        self.should_exit = False
        self._tasks = set()
        self._cleanup_callbacks = []
    
    def register_task(self, task: asyncio.Task):
        """Register a background task for cleanup"""
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
    
    def register_cleanup(self, callback):
        """Register a cleanup callback"""
        self._cleanup_callbacks.append(callback)
    
    async def shutdown(self):
        """Perform graceful shutdown sequence"""
        self.should_exit = True
        
        # Cancel all background tasks
        tasks = [t for t in self._tasks if not t.done()]
        for task in tasks:
            task.cancel()
        
        # Wait for task cancellation
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # Run cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                # Log error but continue cleanup
                print(f"Error during cleanup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan with startup and shutdown"""
    
    # Startup
    shutdown_handler = GracefulShutdown()
    app.state.shutdown_handler = shutdown_handler
    
    # Register signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(shutdown_handler.shutdown())
        )
    
    # TODO: Start background tasks in Phase 2
    # - Status polling task
    # - Process monitoring task
    # - ZMQ connection management
    
    yield
    
    # Shutdown
    await shutdown_handler.shutdown()