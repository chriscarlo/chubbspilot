#!/usr/bin/env python3
"""Simple WebSocket test with timeout"""

import asyncio
import json
import websockets
import sys

async def test_terminal():
    uri = "ws://localhost:5055/api/v1/terminal/ws?session_id=test-session"
    
    try:
        print(f"Attempting to connect to {uri}")
        # Don't use timeout in connect() for older websockets versions
        websocket = await websockets.connect(uri)
        print("✓ Connected to WebSocket")
        
        try:
            # Send init message
            init_msg = {
                "type": "init",
                "session_id": "test-session",
                "rows": 24,
                "cols": 80
            }
            await websocket.send(json.dumps(init_msg))
            print(f"✓ Sent init message")
            
            # Wait for response with timeout
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(message)
                print(f"✓ Received: {data}")
                await websocket.close()
                return True
            except asyncio.TimeoutError:
                print("✗ Timeout waiting for response")
                await websocket.close()
                return False
        except Exception as e:
            await websocket.close()
            raise e
                
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ WebSocket error: HTTP {e.status_code} - {e.headers}")
        return False
    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket error: {e}")
        return False
    except Exception as e:
        print(f"✗ Connection error: {type(e).__name__}: {e}")
        return False

async def main():
    success = await test_terminal()
    if success:
        print("\n✓ WebSocket test passed!")
        sys.exit(0)
    else:
        print("\n✗ WebSocket test failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())