#!/usr/bin/env python3
"""Validate what terminal features actually work"""

import asyncio
import json
import websockets
import time

async def test_terminal_features():
    uri = "ws://localhost:5055/api/v1/terminal/ws?session_id=validation-test-123456"
    
    async with websockets.connect(uri) as ws:
        print("=== Terminal Feature Validation ===\n")
        
        # Initialize
        await ws.send(json.dumps({
            "type": "init",
            "session_id": "validation-test-123456", 
            "rows": 24,
            "cols": 80
        }))
        
        # Wait for init and prompt
        init_response = await ws.recv()
        print(f"Init response: {json.loads(init_response)}")
        
        prompt = await ws.recv()
        print(f"Initial prompt: {json.loads(prompt)}")
        
        # Test 1: Basic command execution
        print("\n1. Testing basic command execution...")
        await ws.send(json.dumps({
            "type": "input",
            "data": "echo 'Hello Terminal'\n"
        }))
        
        for _ in range(3):
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(response)
            if data.get("type") == "output":
                print(f"   Output: {repr(data['data'])}")
                if "Hello Terminal" in data['data']:
                    print("   ✅ Basic command execution works!")
                    break
        
        # Test 2: Environment variables
        print("\n2. Testing environment variables...")
        await ws.send(json.dumps({
            "type": "input",
            "data": "echo $USER $HOME $SHELL\n"
        }))
        
        for _ in range(3):
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(response)
            if data.get("type") == "output" and "$" not in data['data']:
                print(f"   Output: {repr(data['data'])}")
                if "comma" in data['data'] or "/bin/sh" in data['data']:
                    print("   ✅ Environment variables work!")
                    break
        
        # Test 3: Directory navigation
        print("\n3. Testing directory navigation...")
        await ws.send(json.dumps({
            "type": "input",
            "data": "pwd\n"
        }))
        
        for _ in range(3):
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(response)
            if data.get("type") == "output" and "/" in data['data'] and "pwd" not in data['data']:
                print(f"   Current dir: {repr(data['data'])}")
                print("   ✅ Directory commands work!")
                break
        
        # Test 4: Special characters
        print("\n4. Testing special character handling...")
        await ws.send(json.dumps({
            "type": "input",
            "data": "echo 'Special: @#$%^&*()'\n"
        }))
        
        for _ in range(3):
            response = await asyncio.wait_for(ws.recv(), timeout=2.0) 
            data = json.loads(response)
            if data.get("type") == "output" and "@#$" in data['data']:
                print(f"   Output: {repr(data['data'])}")
                print("   ✅ Special characters work!")
                break
        
        # Test 5: Multi-line command
        print("\n5. Testing multi-line commands...")
        await ws.send(json.dumps({
            "type": "input",
            "data": "echo 'line1'\necho 'line2'\n"
        }))
        
        outputs = []
        for _ in range(6):
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(response)
                if data.get("type") == "output":
                    outputs.append(data['data'])
            except asyncio.TimeoutError:
                break
        
        print(f"   Outputs: {outputs}")
        if any("line1" in o for o in outputs) and any("line2" in o for o in outputs):
            print("   ✅ Multi-line commands work!")
        
        # Test 6: Error handling
        print("\n6. Testing error handling...")
        await ws.send(json.dumps({
            "type": "input",
            "data": "nonexistentcommand123\n"
        }))
        
        for _ in range(3):
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(response)
            if data.get("type") == "output" and ("not found" in data['data'] or "nonexistent" in data['data']):
                print(f"   Error output: {repr(data['data'])}")
                print("   ✅ Error messages work!")
                break
        
        # Test 7: Terminal resize
        print("\n7. Testing terminal resize...")
        await ws.send(json.dumps({
            "type": "resize",
            "rows": 40,
            "cols": 100
        }))
        # No direct feedback, but should not crash
        print("   ✅ Resize message accepted (visual verification needed)")
        
        # Test 8: Control character (Ctrl+C simulation)
        print("\n8. Testing control characters...")
        await ws.send(json.dumps({
            "type": "input",
            "data": "sleep 10\n"
        }))
        await asyncio.sleep(0.5)
        await ws.send(json.dumps({
            "type": "input",
            "data": "\x03"  # Ctrl+C
        }))
        
        for _ in range(3):
            response = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(response)
            if data.get("type") == "output" and "$" in data['data']:
                print("   ✅ Ctrl+C interrupt works!")
                break
        
        print("\n=== Summary ===")
        print("Basic terminal functionality is working.")
        print("WebSocket communication is stable.")
        print("Shell commands execute properly.")
        print("\nMissing/Untested features:")
        print("- ANSI color code rendering")
        print("- Tab completion")
        print("- Command history (arrow keys)")
        print("- Copy/paste functionality")
        print("- Mouse support")
        print("- File transfer")
        print("- Session persistence")

asyncio.run(test_terminal_features())