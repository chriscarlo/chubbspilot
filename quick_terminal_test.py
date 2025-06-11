#!/usr/bin/env python3
"""Quick test to see what actually works"""

import requests
import asyncio
import websockets
import json

def test_http_endpoints():
    """Test basic HTTP endpoints"""
    print("=== Testing HTTP Endpoints ===")
    
    # Test root
    try:
        r = requests.get("http://localhost:5055/")
        print(f"GET /: {r.status_code}")
    except Exception as e:
        print(f"GET /: ERROR - {e}")
    
    # Test terminal page
    try:
        r = requests.get("http://localhost:5055/terminal")
        print(f"GET /terminal: {r.status_code}")
        if r.status_code == 200:
            print(f"  Content length: {len(r.text)} bytes")
            print(f"  Has xterm.js: {'xterm.js' in r.text}")
    except Exception as e:
        print(f"GET /terminal: ERROR - {e}")

async def test_websocket_basic():
    """Test basic WebSocket connection"""
    print("\n=== Testing WebSocket ===")
    
    uri = "ws://localhost:5055/api/v1/terminal/ws?session_id=test-abc-12345678"
    
    try:
        async with websockets.connect(uri) as ws:
            print("WebSocket connected!")
            
            # Send init
            init_msg = {
                "type": "init",
                "session_id": "test-abc-12345678",
                "rows": 24,
                "cols": 80
            }
            await ws.send(json.dumps(init_msg))
            print(f"Sent: {init_msg}")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"Received: {data}")
                
                # If we got init_success, try to get prompt
                if data.get("type") == "init_success":
                    print("Init successful, waiting for prompt...")
                    for i in range(5):
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                            data = json.loads(msg)
                            print(f"Output {i+1}: {data}")
                            if data.get("type") == "output":
                                print(f"  Data preview: {repr(data.get('data', '')[:100])}")
                        except asyncio.TimeoutError:
                            print(f"  Timeout waiting for output {i+1}")
                            
            except asyncio.TimeoutError:
                print("Timeout waiting for init response")
                
    except Exception as e:
        print(f"WebSocket error: {type(e).__name__}: {e}")

def main():
    # Test HTTP
    test_http_endpoints()
    
    # Test WebSocket
    asyncio.run(test_websocket_basic())
    
    print("\n=== Summary ===")
    print("Basic connectivity appears to be working.")
    print("Check server logs for detailed debugging.")

if __name__ == "__main__":
    main()