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
from openpilot.selfdrive.chauffeur.concierge.core.logging_config import setup_logging

logger = setup_logging("api.v1.websocket.terminal")

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
        logger.info(f"=== NEW WEBSOCKET CONNECTION ===")
        logger.debug(f"WebSocket client: {self.websocket.client}")
        logger.debug(f"WebSocket headers: {self.websocket.headers}")
        
        await self.websocket.accept()
        logger.info("WebSocket connection accepted")
        
        try:
            while True:
                # Receive message from client
                logger.debug("Waiting for client message...")
                message = await self.websocket.receive_text()
                logger.debug(f"Received message: {message[:100]}...")  # Log first 100 chars
                await self.handle_message(message)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {self.session_id}")
            await self.cleanup()
            
        except Exception as e:
            logger.error(f"WebSocket error: {type(e).__name__}: {e}", exc_info=True)
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
        logger.info("=== HANDLE INIT ===")
        logger.debug(f"Init data: {data}")
        
        session_id = data.get('session_id', 'default')
        logger.debug(f"Session ID: {session_id}")
        
        # Validate session ID
        logger.debug(f"Validating session ID: {session_id}")
        is_valid = self.security.validate_session_id(session_id)
        logger.debug(f"Session ID validation result: {is_valid}")
        
        if not is_valid:
            logger.error(f"Invalid session ID: {session_id}")
            await self.send_error("Invalid session ID")
            return
        
        self.session_id = session_id
        rows = max(1, min(data.get('rows', 24), 200))  # Clamp rows
        cols = max(1, min(data.get('cols', 80), 300))  # Clamp cols
        
        try:
            # Create PTY process
            logger.debug("Creating PTY process...")
            # Explicitly specify bash shell
            process = await self.pty_manager.create_pty(
                session_id=self.session_id,
                shell="/usr/bin/bash",  # Force bash
                rows=rows,
                cols=cols
            )
            logger.debug(f"PTY process created: {process}")
            
            # Start reading from PTY
            logger.debug("Starting PTY reader...")
            reader_task = await self.pty_manager.read_from_pty(
                self.session_id,
                self.handle_pty_output
            )
            logger.debug(f"PTY reader task: {reader_task}")
            
            # Send initialization success
            logger.debug("Sending init success...")
            await self.send_message({
                'type': 'init_success',
                'session_id': self.session_id
            })
            logger.info("Terminal initialization complete")
            
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
        logger.debug(f"handle_pty_output called with {len(data)} bytes")
        # Send output to client
        await self.send_message({
            'type': 'output',
            'data': data.decode('utf-8', errors='replace')
        })
        logger.debug("Output sent to client")
        
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
async def terminal_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for terminal connections"""
    logger.info("=== TERMINAL WEBSOCKET ENDPOINT CALLED ===")
    logger.debug(f"Client: {websocket.client}")
    logger.debug(f"Headers: {dict(websocket.headers)}")
    logger.debug(f"Query params: {dict(websocket.query_params)}")
    
    # Get PTY manager instance directly
    pty_manager = get_pty_manager()
    logger.debug(f"PTY Manager instance: {pty_manager}")
    
    handler = TerminalWebSocket(websocket, pty_manager)
    await handler.handle_connection()