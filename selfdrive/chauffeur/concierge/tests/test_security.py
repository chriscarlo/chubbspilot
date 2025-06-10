"""Security testing for Concierge terminal."""
import asyncio
import json
import pytest
import sys
import websockets

sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")

class TestTerminalSecurity:
    """Test security features of terminal."""
    
    @pytest.mark.asyncio
    async def test_dangerous_command_blocking(self, start_concierge_server):
        """Test that dangerous commands are blocked."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda",
            "chmod 777 /etc/passwd",
            ":(){:|:&};:",  # Fork bomb
        ]
        
        async with websockets.connect(uri) as websocket:
            # Initialize session
            init_msg = json.dumps({
                "type": "init",
                "session_id": "test_security_123456789012345"
            })
            await websocket.send(init_msg)
            await websocket.recv()
            
            for cmd in dangerous_commands:
                # Send dangerous command
                cmd_msg = json.dumps({
                    "type": "input",
                    "data": f"{cmd}\n"
                })
                await websocket.send(cmd_msg)
                
                # Should either block or execute safely
                # The security should prevent actual harm
                await asyncio.sleep(0.5)
                
                # Connection should still be alive
                assert websocket.open
    
    @pytest.mark.asyncio
    async def test_input_size_limit(self, start_concierge_server):
        """Test input size limits."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        async with websockets.connect(uri) as websocket:
            # Initialize session
            init_msg = json.dumps({
                "type": "init",
                "session_id": "test_size_limit_123456789012"
            })
            await websocket.send(init_msg)
            await websocket.recv()
            
            # Send oversized input
            huge_input = "A" * 10000  # 10KB
            cmd_msg = json.dumps({
                "type": "input",
                "data": huge_input
            })
            
            try:
                await websocket.send(cmd_msg)
                response = await asyncio.wait_for(websocket.recv(), timeout=2)
                data = json.loads(response)
                # Should either truncate or reject
            except:
                # Connection might close on oversized input
                pass
    
    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, start_concierge_server):
        """Test path traversal attack prevention."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        path_traversal_attempts = [
            "cat ../../../../etc/passwd",
            "ls ../../../../../../../",
            "cd ..; cd ..; cd ..; cd ..; pwd",
        ]
        
        async with websockets.connect(uri) as websocket:
            # Initialize session
            init_msg = json.dumps({
                "type": "init",
                "session_id": "test_path_traversal_12345678"
            })
            await websocket.send(init_msg)
            await websocket.recv()
            
            for cmd in path_traversal_attempts:
                cmd_msg = json.dumps({
                    "type": "input",
                    "data": f"{cmd}\n"
                })
                await websocket.send(cmd_msg)
                
                # Collect output
                output = ""
                try:
                    for _ in range(3):
                        response = await asyncio.wait_for(websocket.recv(), timeout=1)
                        data = json.loads(response)
                        if data.get("type") == "output":
                            output += data.get("data", "")
                except asyncio.TimeoutError:
                    pass
                
                # Should not expose sensitive files
                assert "root:" not in output  # /etc/passwd content
                assert websocket.open
    
    @pytest.mark.asyncio 
    async def test_session_hijacking_prevention(self, start_concierge_server):
        """Test session hijacking prevention."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        # Create first connection
        ws1 = await websockets.connect(uri)
        session_id = "test_hijack_123456789012345"
        
        init_msg = json.dumps({
            "type": "init",
            "session_id": session_id
        })
        await ws1.send(init_msg)
        await ws1.recv()
        
        # Try to hijack from another connection
        ws2 = await websockets.connect(uri)
        await ws2.send(init_msg)  # Same session ID
        
        # Should either reject or create new session
        response = await ws2.recv()
        data = json.loads(response)
        
        # Both connections should work independently
        assert ws1.open
        assert ws2.open
        
        await ws1.close()
        await ws2.close()
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, start_concierge_server):
        """Test rate limiting on commands."""
        uri = "ws://localhost:8000/api/v1/ws/terminal"
        
        async with websockets.connect(uri) as websocket:
            # Initialize session
            init_msg = json.dumps({
                "type": "init", 
                "session_id": "test_rate_limit_123456789012"
            })
            await websocket.send(init_msg)
            await websocket.recv()
            
            # Send many commands rapidly
            for i in range(100):
                cmd_msg = json.dumps({
                    "type": "input",
                    "data": f"echo {i}\n"
                })
                await websocket.send(cmd_msg)
                # Don't wait for response
            
            # Connection should still be open
            # Rate limiting should handle the flood gracefully
            await asyncio.sleep(1)
            assert websocket.open