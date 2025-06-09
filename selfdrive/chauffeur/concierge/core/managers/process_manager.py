"""Process management for Concierge"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings
from openpilot.selfdrive.chauffeur.concierge.config.constants import MAX_CONCURRENT_PROCESSES


class ProcessManager:
    """Manages external processes and subprocesses"""
    
    def __init__(self, settings: ConciergeSettings):
        self.settings = settings
        self._active_processes: Dict[str, asyncio.subprocess.Process] = {}
        self._service_monitor_process: Optional[asyncio.subprocess.Process] = None
        self._service_monitor_active_services: List[str] = []
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROCESSES)
    
    async def start_service_monitoring(self, services: List[str]) -> str:
        """Start monitoring specified services"""
        if self._service_monitor_process and self._service_monitor_process.returncode is None:
            raise ValueError("Service monitoring is already in progress")
        
        if not services:
            raise ValueError("No services selected for monitoring")
        
        self._service_monitor_active_services = services
        
        # Build command for monitor script
        script_path = str(self.settings.openpilot_root / "tools" / "debug" / "monitor_service.py")
        command = [
            sys.executable, 
            "-u",  # Unbuffered output for timely SSE
            script_path
        ] + services + [
            "-r", str(self.settings.status_poll_interval),
            "-d", "0"
        ]
        
        try:
            self._service_monitor_process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.settings.openpilot_root)
            )
            
            # Give process time to start or fail early
            await asyncio.sleep(0.1)
            
            if self._service_monitor_process.returncode is not None:
                # Process exited immediately - capture error
                stderr_output = b""
                if self._service_monitor_process.stderr:
                    stderr_output = await self._service_monitor_process.stderr.read()
                
                self._service_monitor_process = None
                error_msg = stderr_output.decode('utf-8', errors='replace')
                raise RuntimeError(f"Monitor process failed to start: {error_msg}")
            
            return f"Service monitoring started for: {', '.join(services)}"
            
        except Exception as e:
            self._service_monitor_process = None
            raise RuntimeError(f"Failed to start service monitoring: {str(e)}")
    
    async def stop_service_monitoring(self) -> str:
        """Stop active service monitoring"""
        if not self._service_monitor_process or self._service_monitor_process.returncode is not None:
            return "No active monitoring to stop"
        
        try:
            self._service_monitor_process.terminate()
            await asyncio.wait_for(self._service_monitor_process.wait(), timeout=5.0)
            result = "Service monitoring stopped"
        except asyncio.TimeoutError:
            self._service_monitor_process.kill()
            await self._service_monitor_process.wait()
            result = "Service monitoring forcefully terminated"
        finally:
            self._service_monitor_process = None
            self._service_monitor_active_services = []
        
        return result
    
    async def get_monitoring_stream(self) -> AsyncGenerator[str, None]:
        """Get service monitoring data stream"""
        if not self._service_monitor_process or self._service_monitor_process.returncode is not None:
            raise RuntimeError("No active service monitoring")
        
        if not self._service_monitor_process.stdout:
            raise RuntimeError("Monitor process has no stdout")
        
        try:
            while self._service_monitor_process.returncode is None:
                line = await self._service_monitor_process.stdout.readline()
                if not line:
                    break
                
                # Yield SSE formatted data
                yield f"data: {line.decode('utf-8', errors='replace').strip()}\n\n"
                
        except asyncio.CancelledError:
            # Client disconnected - this is normal
            pass
        except Exception as e:
            yield f"data: {{\"error\": \"Stream error: {str(e)}\"}}\n\n"
    
    def get_monitoring_status(self) -> Dict[str, any]:
        """Get current monitoring status"""
        if self._service_monitor_process and self._service_monitor_process.returncode is None:
            return {
                "active": True,
                "services": self._service_monitor_active_services,
                "pid": self._service_monitor_process.pid
            }
        else:
            return {
                "active": False,
                "services": [],
                "pid": None
            }
    
    async def execute_command(
        self, 
        command: List[str], 
        cwd: Path = None, 
        timeout: int = None
    ) -> Dict[str, any]:
        """Execute a command with timeout and resource management"""
        timeout = timeout or self.settings.command_timeout
        cwd = cwd or self.settings.openpilot_root
        
        async with self._semaphore:
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(cwd)
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
                
                return {
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace'),
                    "exit_code": process.returncode,
                    "command": ' '.join(command)
                }
                
            except asyncio.TimeoutError:
                if 'process' in locals():
                    process.kill()
                    await process.wait()
                
                return {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "exit_code": -1,
                    "command": ' '.join(command)
                }
            
            except Exception as e:
                return {
                    "stdout": "",
                    "stderr": f"Command failed: {str(e)}",
                    "exit_code": -1,
                    "command": ' '.join(command)
                }
    
    async def cleanup_terminated(self):
        """Remove terminated processes from tracking"""
        terminated = [
            process_id for process_id, process in self._active_processes.items()
            if process.returncode is not None
        ]
        
        for process_id in terminated:
            del self._active_processes[process_id]
    
    async def terminate_all(self):
        """Terminate all managed processes"""
        # Stop service monitoring
        if self._service_monitor_process:
            await self.stop_service_monitoring()
        
        # Terminate all other active processes
        for process in self._active_processes.values():
            if process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        
        self._active_processes.clear()