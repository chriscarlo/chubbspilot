"""WebSocket handler for terminal connections"""

import json
import logging
import time
from typing import Optional, Dict
from fastapi import WebSocket, WebSocketDisconnect, Depends
from fastapi.websockets import WebSocketState

from openpilot.selfdrive.chauffeur.concierge.core.services.terminal.pty_manager import PTYManager
from openpilot.selfdrive.chauffeur.concierge.core.security.terminal_security import TerminalSecurityManager
from openpilot.selfdrive.chauffeur.concierge.app.dependencies import get_pty_manager

logger = logging.getLogger(__name__)

class TerminalWebSocket:
    """Handles WebSocket connections for terminal sessions"""
    
    def __init__(self, websocket: WebSocket, pty_manager: PTYManager):
        self.websocket = websocket
        self.pty_manager = pty_manager
        self.session_id: Optional[str] = None
        self.security = TerminalSecurityManager()
        
        # Rate limiting
        self.message_timestamps = []
        self.last_input_time = 0
        
    async def handle_connection(self):
        """Main WebSocket connection handler"""
        await self.websocket.accept()
        
        try:
            while True:
                # Receive message from client
                message = await self.websocket.receive_text()
                await self.handle_message(message)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {self.session_id}")
            await self.cleanup()
            
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await self.cleanup()
            
    async def handle_message(self, message: str):
        """Handle incoming WebSocket messages"""
        # Rate limiting check
        if not self._check_rate_limit():
            await self.send_error("Rate limit exceeded")
            return
        
        # Message size check
        if len(message) > 8192:  # 8KB limit
            await self.send_error("Message too large")
            return
        
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'init':
                await self.handle_init(data)
            elif msg_type == 'input':
                await self.handle_input(data)
            elif msg_type == 'resize':
                await self.handle_resize(data)
            elif msg_type == 'ping':
                await self.send_message({'type': 'pong'})
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON message")
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await self.send_error(str(e))
    
    def _check_rate_limit(self) -> bool:
        """Check if message rate is within limits"""
        now = time.time()
        
        # Clean old timestamps (keep last second)
        self.message_timestamps = [
            ts for ts in self.message_timestamps 
            if now - ts < 1.0
        ]
        
        # Check rate limit
        if len(self.message_timestamps) >= self.security.input_rate_limit:
            return False
        
        self.message_timestamps.append(now)
        return True
    
    async def handle_init(self, data: dict):
        """Initialize terminal session"""
        session_id = data.get('session_id', 'default')
        
        # Validate session ID
        if not self.security.validate_session_id(session_id):
            await self.send_error("Invalid session ID")
            return
        
        self.session_id = session_id
        rows = max(1, min(data.get('rows', 24), 200))  # Clamp rows
        cols = max(1, min(data.get('cols', 80), 300))  # Clamp cols
        
        try:
            # Create PTY process
            process = await self.pty_manager.create_pty(
                session_id=self.session_id,
                rows=rows,
                cols=cols
            )
            
            # Start reading from PTY
            await self.pty_manager.read_from_pty(
                self.session_id,
                self.handle_pty_output
            )
            
            # Send initialization success
            await self.send_message({
                'type': 'init_success',
                'session_id': self.session_id
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize terminal: {e}")
            await self.send_error(f"Initialization failed: {str(e)}")
        
    async def handle_input(self, data: dict):
        """Handle keyboard input from client"""
        if not self.session_id:
            await self.send_error("Session not initialized")
            return
            
        input_data = data.get('data', '')
        
        # Convert to bytes and write to PTY
        await self.pty_manager.write_to_pty(
            self.session_id,
            input_data.encode('utf-8')
        )
        
    async def handle_resize(self, data: dict):
        """Handle terminal resize"""
        if not self.session_id:
            return
            
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        
        await self.pty_manager.resize_pty(self.session_id, rows, cols)
        
    async def handle_pty_output(self, data: bytes):
        """Handle output from PTY"""
        # Send output to client
        await self.send_message({
            'type': 'output',
            'data': data.decode('utf-8', errors='replace')
        })
        
    async def send_message(self, message: dict):
        """Send message to client"""
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.send_text(json.dumps(message))
            
    async def send_error(self, error: str):
        """Send error message to client"""
        await self.send_message({
            'type': 'error',
            'message': error
        })
        
    async def cleanup(self):
        """Clean up resources"""
        if self.session_id:
            await self.pty_manager.terminate_pty(self.session_id)


# WebSocket endpoint
async def terminal_websocket_endpoint(
    websocket: WebSocket,
    pty_manager: PTYManager = Depends(get_pty_manager)
):
    """WebSocket endpoint for terminal connections"""
    handler = TerminalWebSocket(websocket, pty_manager)
    await handler.handle_connection()