#!/usr/bin/env python3
"""Test script for Concierge terminal WebSocket"""

import asyncio
import json
import websockets

async def test_terminal():
    uri = "ws://localhost:5055/api/v1/terminal/ws?session_id=terminal-main-session"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        
        # Send init message
        init_msg = {
            "type": "init",
            "session_id": "terminal-main-session",
            "rows": 24,
            "cols": 80
        }
        await websocket.send(json.dumps(init_msg))
        print(f"Sent init: {init_msg}")
        
        # Listen for messages
        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                print(f"Received: {data}")
                
                if data.get('type') == 'output':
                    print(f"Terminal output: {data.get('data', '')}")
                elif data.get('type') == 'init_success':
                    print("Terminal initialized successfully!")
                    # Send a test command
                    await asyncio.sleep(0.5)
                    test_cmd = {
                        "type": "input",
                        "data": "echo 'Hello from terminal!'\n"
                    }
                    await websocket.send(json.dumps(test_cmd))
                    print(f"Sent command: {test_cmd}")
                    
        except KeyboardInterrupt:
            print("\nDisconnecting...")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_terminal())