"""Autonomous tests for Terminal WebSocket functionality."""
import asyncio
import json
import pytest
import sys
import os
import websockets
from typing import Optional

# Add packages to path
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")

class TestTerminalWebSocket:
    """Test suite for terminal WebSocket functionality."""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self, start_concierge_server):
        """Test basic WebSocket connection."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Connection should be established
                assert websocket.open
                
                # Send init message
                init_msg = json.dumps({
                    "type": "init",
                    "session_id": "test_session_123456789012345"
                })
                await websocket.send(init_msg)
                
                # Should receive response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                
                # Verify response
                assert data.get("type") in ["output", "error", "status"]
                
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_command_execution(self, start_concierge_server):
        """Test command execution through WebSocket."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        async with websockets.connect(uri) as websocket:
            # Initialize session
            init_msg = json.dumps({
                "type": "init",
                "session_id": "test_command_exec_123456789"
            })
            await websocket.send(init_msg)
            await websocket.recv()  # Consume init response
            
            # Send echo command
            cmd_msg = json.dumps({
                "type": "input",
                "data": "echo 'Hello from test'\n"
            })
            await websocket.send(cmd_msg)
            
            # Collect output
            output = ""
            timeout = 5
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < timeout:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1)
                    data = json.loads(response)
                    if data.get("type") == "output":
                        output += data.get("data", "")
                        if "Hello from test" in output:
                            break
                except asyncio.TimeoutError:
                    continue
            
            assert "Hello from test" in output
    
    @pytest.mark.asyncio
    async def test_resize_handling(self, start_concierge_server):
        """Test terminal resize functionality."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        async with websockets.connect(uri) as websocket:
            # Initialize session
            init_msg = json.dumps({
                "type": "init",
                "session_id": "test_resize_123456789012345"
            })
            await websocket.send(init_msg)
            await websocket.recv()
            
            # Send resize message
            resize_msg = json.dumps({
                "type": "resize",
                "cols": 120,
                "rows": 40
            })
            await websocket.send(resize_msg)
            
            # Should not crash
            await asyncio.sleep(0.5)
            assert websocket.open
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, start_concierge_server):
        """Test session cleanup on disconnect."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        websocket = await websockets.connect(uri)
        
        # Initialize session
        init_msg = json.dumps({
            "type": "init",
            "session_id": "test_cleanup_123456789012345"
        })
        await websocket.send(init_msg)
        await websocket.recv()
        
        # Close connection
        await websocket.close()
        
        # Try to reconnect with same session - should work
        async with websockets.connect(uri) as new_websocket:
            await new_websocket.send(init_msg)
            response = await new_websocket.recv()
            assert json.loads(response).get("type") in ["output", "error", "status"]
    
    @pytest.mark.asyncio
    async def test_invalid_session_id(self, start_concierge_server):
        """Test rejection of invalid session IDs."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        async with websockets.connect(uri) as websocket:
            # Send invalid session ID (too short)
            init_msg = json.dumps({
                "type": "init",
                "session_id": "short"
            })
            await websocket.send(init_msg)
            
            # Should receive error
            response = await websocket.recv()
            data = json.loads(response)
            
            assert data.get("type") == "error"
            assert "session" in data.get("data", "").lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_connections(self, start_concierge_server):
        """Test multiple concurrent WebSocket connections."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        # Create multiple connections
        connections = []
        for i in range(3):
            ws = await websockets.connect(uri)
            connections.append(ws)
            
            # Initialize each
            init_msg = json.dumps({
                "type": "init",
                "session_id": f"test_concurrent_{i}_123456789"
            })
            await ws.send(init_msg)
            await ws.recv()
        
        # All should be open
        for ws in connections:
            assert ws.open
        
        # Clean up
        for ws in connections:
            await ws.close()
    
    @pytest.mark.asyncio
    async def test_malformed_json(self, start_concierge_server):
        """Test handling of malformed JSON messages."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        async with websockets.connect(uri) as websocket:
            # Send malformed JSON
            await websocket.send("not valid json{")
            
            # Should receive error response
            response = await websocket.recv()
            data = json.loads(response)
            
            assert data.get("type") == "error"
            assert "json" in data.get("data", "").lower() or "parse" in data.get("data", "").lower()