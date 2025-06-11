#!/usr/bin/env python3
"""Interactive terminal test to check functionality"""

import asyncio
import json
import websockets
import sys

async def interactive_terminal():
    uri = "ws://localhost:5055/api/v1/terminal/ws?session_id=interactive-test"
    
    try:
        print("Connecting to Concierge terminal...")
        websocket = await websockets.connect(uri)
        print("✓ Connected!")
        
        # Initialize terminal
        init_msg = {
            "type": "init",
            "session_id": "interactive-test",
            "rows": 24,
            "cols": 80
        }
        await websocket.send(json.dumps(init_msg))
        
        # Wait for init response
        response = await websocket.recv()
        data = json.loads(response)
        if data.get("type") == "init_success":
            print("✓ Terminal initialized!")
        else:
            print(f"✗ Unexpected response: {data}")
            return
        
        # Start reader task
        async def read_output():
            try:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    if data.get("type") == "output":
                        print(data.get("data", ""), end="", flush=True)
                    elif data.get("type") == "error":
                        print(f"\n[ERROR] {data.get('error')}", file=sys.stderr)
            except websockets.exceptions.ConnectionClosed:
                print("\n[Disconnected]")
        
        # Start reader in background
        reader_task = asyncio.create_task(read_output())
        
        print("\nTerminal ready! Type commands (Ctrl+C to exit):")
        print("-" * 50)
        
        # Read user input and send commands
        try:
            while True:
                # Simple input reading (not perfect for interactive terminal)
                await asyncio.sleep(0.1)  # Give reader time to process
                cmd = input()
                if cmd:
                    msg = {
                        "type": "input",
                        "data": cmd + "\n"
                    }
                    await websocket.send(json.dumps(msg))
        except (KeyboardInterrupt, EOFError):
            print("\n\nClosing terminal...")
        
        reader_task.cancel()
        await websocket.close()
        
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("Interactive Terminal Test")
    print("=" * 50)
    asyncio.run(interactive_terminal())