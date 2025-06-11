#!/usr/bin/env python3
"""Test terminal history functionality"""

import asyncio
import json
import websockets
import sys
import time

async def test_terminal_history():
    uri = "ws://localhost:5055/api/v1/terminal/ws?session_id=test-history-session"
    
    print("Connecting to Concierge Terminal WebSocket...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Send init message
            init_msg = {
                "type": "init",
                "session_id": "test-history-session",
                "rows": 24,
                "cols": 80
            }
            await websocket.send(json.dumps(init_msg))
            
            # Wait for init response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Init response: {data}")
            
            # Test commands
            test_commands = [
                "echo 'Test command 1'",
                "echo 'Test command 2'", 
                "echo 'Test command 3'",
                "history | tail -5"  # Show recent history
            ]
            
            for cmd in test_commands:
                print(f"\nSending command: {cmd}")
                
                # Send each character
                for char in cmd:
                    await websocket.send(json.dumps({
                        "type": "input",
                        "data": char
                    }))
                    await asyncio.sleep(0.01)
                
                # Send enter
                await websocket.send(json.dumps({
                    "type": "input",
                    "data": "\r"
                }))
                
                # Collect output
                await asyncio.sleep(0.5)
                
            # Test arrow up (should recall previous command)
            print("\nTesting arrow up key...")
            await websocket.send(json.dumps({
                "type": "input",
                "data": "\x1b[A"  # Arrow up sequence
            }))
            
            # Wait a bit to see output
            await asyncio.sleep(1)
            
            # Send exit command
            print("\nSending exit command...")
            await websocket.send(json.dumps({
                "type": "input", 
                "data": "exit\r"
            }))
            
            # Keep receiving messages
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(response)
                    if data.get("type") == "output":
                        print(f"Output: {repr(data.get('data', ''))}")
            except asyncio.TimeoutError:
                print("No more output (timeout)")
                
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Make sure the server is running
    print("Make sure Concierge is running on port 5055")
    print("You can start it with: python -m selfdrive.chauffeur.concierge.main_wrapper")
    print()
    
    # Run the test
    result = asyncio.run(test_terminal_history())
    
    if result:
        print("\nTest completed successfully!")
        
        # Check if history file was created
        import os
        history_file = "/data/openpilot/.concierge_bash_history"
        if os.path.exists(history_file):
            print(f"\nHistory file exists: {history_file}")
            with open(history_file, 'r') as f:
                lines = f.readlines()
                print(f"History file contains {len(lines)} lines")
                if lines:
                    print("Last 5 commands:")
                    for line in lines[-5:]:
                        print(f"  {line.strip()}")
        else:
            print(f"\nHistory file not found: {history_file}")
    else:
        print("\nTest failed!")
        sys.exit(1)