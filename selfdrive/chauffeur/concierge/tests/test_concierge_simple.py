#!/usr/bin/env python3
"""Simple autonomous tests for Concierge that don't require playwright."""
import sys
import os

# PYTHON TRUTH VALIDATION - SEE /data/openpilot/PYTHON_TRUTH.md
EXPECTED_PYTHON = "3.11"
current_version = f"{sys.version_info.major}.{sys.version_info.minor}"
if current_version != EXPECTED_PYTHON:
    print(f"ERROR: Wrong Python version {current_version}, expected {EXPECTED_PYTHON}")
    print("See /data/openpilot/PYTHON_TRUTH.md for correct setup")
    sys.exit(1)

# Add packages to path - REQUIRED FOR ALL SCRIPTS
sys.path.insert(0, "/data/openpilot/.local/lib/python3.11/site-packages")
sys.path.insert(0, "/data/openpilot")

import asyncio
import json
import subprocess
import time
import signal

import websockets
import httpx

class ConciergeAutoTest:
    """Autonomous test suite for Concierge."""
    
    def __init__(self):
        self.server_process = None
        self.base_url = "http://localhost:5055"
        self.ws_url = "ws://localhost:5055/api/v1/terminal/ws?session_id=test-session"
        self.results = []
    
    def start_server(self):
        """Start Concierge server."""
        print("Starting Concierge server...")
        
        # Kill any existing server
        subprocess.run(["pkill", "-f", "concierge/app/main.py"], capture_output=True)
        time.sleep(1)
        
        # Start new server
        env = os.environ.copy()
        env["PYTHONPATH"] = "/data/openpilot:/data/openpilot/.local/lib/python3.11/site-packages"
        
        self.server_process = subprocess.Popen(
            ["python3", "/data/openpilot/selfdrive/chauffeur/concierge/app/main.py"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        # Wait for server to start
        print("Waiting for server to start...")
        time.sleep(5)
        
        # Check if server is running
        try:
            response = httpx.get(f"{self.base_url}/", timeout=5)
            print(f"✅ Server started successfully (status: {response.status_code})")
            return True
        except Exception as e:
            print(f"❌ Server failed to start: {e}")
            return False
    
    def stop_server(self):
        """Stop Concierge server."""
        if self.server_process:
            print("Stopping Concierge server...")
            os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
            self.server_process.wait()
            print("✅ Server stopped")
    
    async def test_websocket_connection(self):
        """Test basic WebSocket connection."""
        test_name = "WebSocket Connection"
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Send init message
                init_msg = json.dumps({
                    "type": "init",
                    "session_id": "test-session",
                    "rows": 24,
                    "cols": 80
                })
                await websocket.send(init_msg)
                
                # Get response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(response)
                
                if data.get("type") == "init_success":
                    self.results.append({"test": test_name, "status": "PASSED"})
                    print(f"✅ {test_name} - PASSED")
                else:
                    self.results.append({"test": test_name, "status": "FAILED", "reason": "Invalid response"})
                    print(f"❌ {test_name} - FAILED: Invalid response")
                    
        except Exception as e:
            self.results.append({"test": test_name, "status": "FAILED", "reason": str(e)})
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def test_command_execution(self):
        """Test command execution."""
        test_name = "Command Execution"
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Initialize
                init_msg = json.dumps({
                    "type": "init",
                    "session_id": "test-session",
                    "rows": 24,
                    "cols": 80
                })
                await websocket.send(init_msg)
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                init_data = json.loads(response)
                if init_data.get("type") != "init_success":
                    raise Exception("Failed to initialize terminal")
                
                # Send command
                cmd_msg = json.dumps({
                    "type": "input",
                    "data": "echo 'CONCIERGE_TEST_OUTPUT'\n"
                })
                await websocket.send(cmd_msg)
                
                # Collect output
                output = ""
                for _ in range(10):
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1)
                        data = json.loads(response)
                        if data.get("type") == "output":
                            output += data.get("data", "")
                    except asyncio.TimeoutError:
                        break
                
                if "CONCIERGE_TEST_OUTPUT" in output:
                    self.results.append({"test": test_name, "status": "PASSED"})
                    print(f"✅ {test_name} - PASSED")
                else:
                    self.results.append({"test": test_name, "status": "FAILED", "reason": "Output not found"})
                    print(f"❌ {test_name} - FAILED: Expected output not found")
                    
        except Exception as e:
            self.results.append({"test": test_name, "status": "FAILED", "reason": str(e)})
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def test_api_endpoints(self):
        """Test REST API endpoints."""
        test_name = "API Endpoints"
        try:
            async with httpx.AsyncClient() as client:
                # Test root endpoint
                response = await client.get(f"{self.base_url}/")
                if response.status_code == 200:
                    self.results.append({"test": test_name, "status": "PASSED"})
                    print(f"✅ {test_name} - PASSED")
                else:
                    self.results.append({"test": test_name, "status": "FAILED", "reason": f"Status {response.status_code}"})
                    print(f"❌ {test_name} - FAILED: Status {response.status_code}")
                    
        except Exception as e:
            self.results.append({"test": test_name, "status": "FAILED", "reason": str(e)})
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def test_terminal_features(self):
        """Test terminal-specific features."""
        test_name = "Terminal Features"
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Initialize
                init_msg = json.dumps({
                    "type": "init",
                    "session_id": "test-session",
                    "rows": 24,
                    "cols": 80
                })
                await websocket.send(init_msg)
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                init_data = json.loads(response)
                if init_data.get("type") != "init_success":
                    raise Exception("Failed to initialize terminal")
                
                # Test resize
                resize_msg = json.dumps({
                    "type": "resize",
                    "cols": 100,
                    "rows": 30
                })
                await websocket.send(resize_msg)
                
                # Test multi-line command
                cmd_msg = json.dumps({
                    "type": "input",
                    "data": "pwd\nls\n"
                })
                await websocket.send(cmd_msg)
                
                # Should still be connected - test by sending a noop message
                await asyncio.sleep(1)
                try:
                    # Try to send another message to verify connection
                    noop_msg = json.dumps({"type": "noop"})
                    await websocket.send(noop_msg)
                    self.results.append({"test": test_name, "status": "PASSED"})
                    print(f"✅ {test_name} - PASSED")
                except Exception:
                    self.results.append({"test": test_name, "status": "FAILED", "reason": "Connection closed"})
                    print(f"❌ {test_name} - FAILED: Connection closed")
                    
        except Exception as e:
            self.results.append({"test": test_name, "status": "FAILED", "reason": str(e)})
            print(f"❌ {test_name} - FAILED: {e}")
    
    async def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("RUNNING CONCIERGE AUTONOMOUS TESTS")
        print("="*60 + "\n")
        
        # Start server
        if not self.start_server():
            print("Failed to start server, aborting tests")
            return
        
        # Run tests
        tests = [
            self.test_websocket_connection(),
            self.test_command_execution(),
            self.test_api_endpoints(),
            self.test_terminal_features(),
        ]
        
        print("\nRunning tests...")
        print("-"*60)
        
        for test in tests:
            await test
            await asyncio.sleep(0.5)
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.results if r["status"] == "PASSED")
        failed = sum(1 for r in self.results if r["status"] == "FAILED")
        
        print(f"Total: {len(self.results)} | Passed: {passed} | Failed: {failed}")
        print("-"*60)
        
        for result in self.results:
            status = result["status"]
            icon = "✅" if status == "PASSED" else "❌"
            print(f"{icon} {result['test']:<30} {status}")
            if "reason" in result:
                print(f"   Reason: {result['reason']}")
        
        # Stop server
        self.stop_server()
        
        return failed == 0

async def main():
    """Main test runner."""
    tester = ConciergeAutoTest()
    success = await tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)