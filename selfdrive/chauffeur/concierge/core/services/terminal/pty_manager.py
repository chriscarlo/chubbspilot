"""PTY (Pseudo Terminal) Manager for Concierge Terminal Emulator"""

import os
import pty
import select
import signal
import struct
import fcntl
import termios
import asyncio
import logging
import resource
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Awaitable, Union
from dataclasses import dataclass

from openpilot.selfdrive.chauffeur.concierge.core.security.terminal_security import TerminalSecurityManager
from openpilot.selfdrive.chauffeur.concierge.core.logging_config import setup_logging

logger = setup_logging("core.services.terminal.pty_manager")

@dataclass
class PTYProcess:
    """Represents a PTY process"""
    pid: int
    master_fd: int
    slave_fd: int
    
class PTYManager:
    """Manages PTY processes and I/O operations"""
    
    def __init__(self):
        self.processes: Dict[str, PTYProcess] = {}
        self.readers: Dict[str, asyncio.Task] = {}
        self.security = TerminalSecurityManager()
        
    async def create_pty(
        self, 
        session_id: str,
        shell: str = "/usr/bin/bash",  # Use bash for better compatibility
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        rows: int = 24,
        cols: int = 80
    ) -> PTYProcess:
        """Create a new PTY process"""
        logger.info(f"=== CREATE PTY ===")
        logger.debug(f"Session ID: {session_id}")
        logger.debug(f"Shell: {shell}, Rows: {rows}, Cols: {cols}")
        logger.debug(f"CWD: {cwd}")
        
        # Ensure we use bash if available
        if not os.path.exists(shell):
            logger.warning(f"Shell {shell} not found, trying alternatives")
            for alt_shell in ["/usr/bin/bash", "/bin/bash", "/bin/sh"]:
                if os.path.exists(alt_shell):
                    logger.info(f"Using alternative shell: {alt_shell}")
                    shell = alt_shell
                    break
            else:
                raise ValueError("No suitable shell found")
        
        # Security checks
        logger.debug("Validating session ID...")
        if not self.security.validate_session_id(session_id):
            logger.error(f"Invalid session ID: {session_id}")
            raise ValueError(f"Invalid session ID: {session_id}")
        
        # Check session limits
        if len(self.processes) >= self.security.max_sessions:
            raise ValueError(f"Maximum sessions ({self.security.max_sessions}) exceeded")
        
        # Validate working directory
        if cwd:
            valid, error = self.security.validate_working_directory(cwd)
            if not valid:
                raise ValueError(f"Invalid working directory: {error}")
        else:
            cwd = "/data/openpilot"  # Default to safe directory
        
        # Create master and slave PTY pair
        master_fd, slave_fd = pty.openpty()
        
        # Set terminal size
        self._set_pty_size(master_fd, rows, cols)
        
        # Prepare environment with security filtering
        base_env = {
            'TERM': 'xterm-256color',
            'COLORTERM': 'truecolor',
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'HOME': '/data/openpilot',
            'USER': 'comma',
            'SHELL': '/usr/bin/bash',  # Always set bash in environment
            # Configure bash history for persistence
            'HISTFILE': '/data/openpilot/.concierge_bash_history',
            'HISTSIZE': '10000',
            'HISTFILESIZE': '10000',
            'HISTCONTROL': 'ignoredups:erasedups',
            # Enable immediate history append
            'PROMPT_COMMAND': 'history -a'
        }
        
        if env:
            base_env.update(env)
        
        # Sanitize environment
        process_env = self.security.sanitize_environment(base_env)
        
        # Fork and exec shell
        pid = os.fork()
        
        if pid == 0:  # Child process
            try:
                # Apply resource limits before anything else
                # TEMPORARILY DISABLED for testing
                # self.security.apply_resource_limits()
                
                # Create new session and process group
                os.setsid()
                
                # Make slave PTY the controlling terminal
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY)
                
                # Close master FD in child
                os.close(master_fd)
                
                # Redirect stdin/stdout/stderr to slave PTY
                os.dup2(slave_fd, 0)  # stdin
                os.dup2(slave_fd, 1)  # stdout
                os.dup2(slave_fd, 2)  # stderr
                
                # Close original slave FD
                os.close(slave_fd)
                
                # Change working directory
                os.chdir(cwd)
                
                # Execute shell - temporarily simplified to debug crash
                os.write(2, f"About to execute shell: {shell}\n".encode())
                
                # Just run the shell without custom bashrc for now
                os.execve(shell, [shell, '-i'], process_env)  # -i for interactive
                
            except Exception as e:
                # Write error to stderr before exiting
                error_msg = f"Child process error: {type(e).__name__}: {e}\n"
                os.write(2, error_msg.encode())
                # Exit child on error
                os._exit(1)
        
        # Parent process
        os.close(slave_fd)  # Close slave in parent
        
        # Make master FD non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Create process object
        process = PTYProcess(
            pid=pid,
            master_fd=master_fd,
            slave_fd=slave_fd
        )
        
        self.processes[session_id] = process
        
        logger.info(f"Created PTY process {pid} for session {session_id}")
        return process
    
    def _set_pty_size(self, fd: int, rows: int, cols: int):
        """Set PTY window size"""
        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    
    async def resize_pty(self, session_id: str, rows: int, cols: int):
        """Resize PTY window"""
        if session_id not in self.processes:
            raise ValueError(f"Session {session_id} not found")
        
        process = self.processes[session_id]
        self._set_pty_size(process.master_fd, rows, cols)
        
        # Send SIGWINCH to notify process of resize
        try:
            os.kill(process.pid, signal.SIGWINCH)
        except ProcessLookupError:
            logger.warning(f"Process {process.pid} not found when sending SIGWINCH")
    
    async def write_to_pty(self, session_id: str, data: bytes):
        """Write data to PTY stdin"""
        if session_id not in self.processes:
            raise ValueError(f"Session {session_id} not found")
        
        # Log what we're receiving
        logger.debug(f"write_to_pty received {len(data)} bytes: {repr(data[:50])}")
        
        # Validate input data
        try:
            text_data = data.decode('utf-8', errors='replace')
            logger.debug(f"Decoded text: {repr(text_data[:50])}")
            validation_result = self.security.validate_input(text_data)
            logger.debug(f"Validation result: {validation_result}")
            if not validation_result:
                self.security.log_security_event(
                    "INVALID_INPUT", 
                    session_id, 
                    {"data_length": len(data)}
                )
                raise ValueError("Invalid input data")
        except UnicodeDecodeError:
            self.security.log_security_event(
                "INVALID_ENCODING", 
                session_id, 
                {"data_length": len(data)}
            )
            raise ValueError("Invalid UTF-8 encoding")
        
        process = self.processes[session_id]
        
        try:
            # Write data to master FD
            os.write(process.master_fd, data)
        except OSError as e:
            logger.error(f"Error writing to PTY: {e}")
            raise
    
    async def read_from_pty(
        self, 
        session_id: str, 
        callback: Union[Callable[[bytes], None], Callable[[bytes], Awaitable[None]]]
    ):
        """Read data from PTY stdout/stderr"""
        logger.info(f"Starting PTY reader for session {session_id}")
        
        if session_id not in self.processes:
            raise ValueError(f"Session {session_id} not found")
        
        process = self.processes[session_id]
        logger.debug(f"PTY process found: PID={process.pid}, FD={process.master_fd}")
        
        # Create async reader task
        async def reader():
            logger.debug(f"Reader task started for session {session_id}")
            loop = asyncio.get_event_loop()
            read_count = 0
            
            while session_id in self.processes:
                try:
                    # Wait for data to be available
                    ready, _, _ = await loop.run_in_executor(
                        None, 
                        select.select, 
                        [process.master_fd], 
                        [], 
                        [], 
                        0.1
                    )
                    
                    if ready:
                        # Read available data
                        data = os.read(process.master_fd, 4096)
                        
                        if data:
                            read_count += 1
                            # Invoke callback with data
                            logger.info(f"Read {len(data)} bytes from PTY (read #{read_count})")
                            if asyncio.iscoroutinefunction(callback):
                                await callback(data)
                            else:
                                callback(data)
                        else:
                            # EOF - process has exited
                            logger.warning(f"EOF received - process has exited")
                            break
                            
                except OSError as e:
                    if e.errno == 5:  # I/O error - PTY closed
                        logger.warning(f"PTY closed (I/O error)")
                        break
                    else:
                        logger.error(f"PTY read error: {e}", exc_info=True)
                        break
                except Exception as e:
                    logger.error(f"Unexpected error in reader: {e}", exc_info=True)
                    break
                        
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
            
            logger.info(f"PTY reader for session {session_id} stopped (read {read_count} times)")
        
        # Start reader task
        logger.debug(f"Creating reader task for session {session_id}")
        task = asyncio.create_task(reader())
        self.readers[session_id] = task
        logger.debug(f"Reader task created: {task}")
        
        return task
    
    async def terminate_pty(self, session_id: str):
        """Terminate a PTY process"""
        if session_id not in self.processes:
            return
        
        process = self.processes[session_id]
        
        try:
            # Stop reader task
            if session_id in self.readers:
                self.readers[session_id].cancel()
                del self.readers[session_id]
            
            # Send SIGHUP to process group
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGHUP)
            except ProcessLookupError:
                # Process already dead
                pass
            
            # Wait for process to exit
            await asyncio.sleep(0.5)
            
            # Force kill if still running
            try:
                os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            
            # Close master FD
            try:
                os.close(process.master_fd)
            except OSError:
                pass
            
            # Clean up process
            del self.processes[session_id]
            
            logger.info(f"Terminated PTY process for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error terminating PTY: {e}")
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a PTY session"""
        if session_id not in self.processes:
            return None
        
        process = self.processes[session_id]
        return {
            "session_id": session_id,
            "pid": process.pid,
            "master_fd": process.master_fd,
            "active": True
        }
    
    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active PTY sessions"""
        return {
            session_id: self.get_session_info(session_id)
            for session_id in self.processes
        }
    
    async def cleanup_all(self):
        """Clean up all PTY processes"""
        sessions = list(self.processes.keys())
        for session_id in sessions:
            await self.terminate_pty(session_id)