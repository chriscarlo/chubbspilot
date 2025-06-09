# Concierge Terminal Emulator - Phase 1 Implementation Guide

## Phase 1: Core Terminal Foundation

### Overview
Phase 1 establishes the fundamental terminal emulator infrastructure with PTY support, WebSocket communication, and basic xterm.js integration. This phase creates a working terminal that can execute commands and display output.

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Browser)                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐          ┌──────────────────────────┐ │
│  │   xterm.js      │          │   Terminal Component     │ │
│  │  - Rendering    │◄────────►│  - UI Management        │ │
│  │  - Input Events │          │  - Event Handling       │ │
│  └────────┬────────┘          └──────────┬───────────────┘ │
│           │                               │                  │
│           └───────────────┬───────────────┘                 │
│                           │                                  │
│                    WebSocket Client                          │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │ Binary WebSocket Protocol
                            │ (JSON + Raw bytes)
┌───────────────────────────┼──────────────────────────────────┐
│                           │        Backend (Python)          │
│                    WebSocket Server                          │
│                    (FastAPI WebSocket)                       │
│                           │                                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐     ┌──────────────────────────┐  │
│  │  Terminal Service   │     │    PTY Manager           │  │
│  │  - Message Router   │◄───►│  - Process Spawning     │  │
│  │  - Protocol Handler │     │  - I/O Handling         │  │
│  │  - Session State    │     │  - Signal Management    │  │
│  └─────────────────────┘     └────────────┬─────────────┘  │
│                                            │                 │
│                                            ▼                 │
│                                    ┌───────────────┐        │
│                                    │  Shell Process │        │
│                                    │   (bash/zsh)   │        │
│                                    └───────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### 1. Backend Implementation

#### 1.1 PTY Manager (`core/services/terminal/pty_manager.py`)
```python
"""PTY (Pseudo Terminal) Manager for Concierge Terminal Emulator"""

import os
import pty
import select
import struct
import fcntl
import termios
import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

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
        
    async def create_pty(
        self, 
        session_id: str,
        shell: str = "/bin/bash",
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        rows: int = 24,
        cols: int = 80
    ) -> PTYProcess:
        """Create a new PTY process"""
        
        # Create master and slave PTY pair
        master_fd, slave_fd = pty.openpty()
        
        # Set terminal size
        self._set_pty_size(master_fd, rows, cols)
        
        # Prepare environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        
        # Set terminal type
        process_env['TERM'] = 'xterm-256color'
        process_env['COLORTERM'] = 'truecolor'
        
        # Fork and exec shell
        pid = os.fork()
        
        if pid == 0:  # Child process
            try:
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
                
                # Change working directory if specified
                if cwd:
                    os.chdir(cwd)
                
                # Execute shell
                os.execve(shell, [shell], process_env)
                
            except Exception as e:
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
        os.kill(process.pid, signal.SIGWINCH)
    
    async def write_to_pty(self, session_id: str, data: bytes):
        """Write data to PTY stdin"""
        if session_id not in self.processes:
            raise ValueError(f"Session {session_id} not found")
        
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
        callback: Callable[[bytes], None]
    ):
        """Read data from PTY stdout/stderr"""
        if session_id not in self.processes:
            raise ValueError(f"Session {session_id} not found")
        
        process = self.processes[session_id]
        
        # Create async reader task
        async def reader():
            loop = asyncio.get_event_loop()
            
            while session_id in self.processes:
                try:
                    # Wait for data to be available
                    await loop.run_in_executor(
                        None, 
                        select.select, 
                        [process.master_fd], 
                        [], 
                        [], 
                        0.1
                    )
                    
                    # Read available data
                    data = os.read(process.master_fd, 4096)
                    
                    if data:
                        # Invoke callback with data
                        await callback(data)
                    else:
                        # EOF - process has exited
                        break
                        
                except OSError as e:
                    if e.errno == 5:  # I/O error - PTY closed
                        break
                    else:
                        logger.error(f"PTY read error: {e}")
                        break
                        
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
            
            logger.info(f"PTY reader for session {session_id} stopped")
        
        # Start reader task
        task = asyncio.create_task(reader())
        self.readers[session_id] = task
        
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
            os.killpg(os.getpgid(process.pid), signal.SIGHUP)
            
            # Wait for process to exit
            await asyncio.sleep(0.5)
            
            # Force kill if still running
            try:
                os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            
            # Close master FD
            os.close(process.master_fd)
            
            # Clean up process
            del self.processes[session_id]
            
            logger.info(f"Terminated PTY process for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error terminating PTY: {e}")
```

#### 1.2 Terminal WebSocket Handler (`api/v1/websocket/terminal.py`)
```python
"""WebSocket handler for terminal connections"""

import json
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect, Depends
from fastapi.websockets import WebSocketState

from openpilot.selfdrive.chauffeur.concierge.core.services.terminal.pty_manager import PTYManager
from openpilot.selfdrive.chauffeur.concierge.app.dependencies import get_pty_manager

logger = logging.getLogger(__name__)

class TerminalWebSocket:
    """Handles WebSocket connections for terminal sessions"""
    
    def __init__(self, websocket: WebSocket, pty_manager: PTYManager):
        self.websocket = websocket
        self.pty_manager = pty_manager
        self.session_id: Optional[str] = None
        
    async def handle_connection(self):
        """Main WebSocket connection handler"""
        await self.websocket.accept()
        
        try:
            while True:
                # Receive message from client
                message = await self.websocket.receive_text()
                await self.handle_message(message)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {self.session_id}")
            await self.cleanup()
            
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await self.cleanup()
            
    async def handle_message(self, message: str):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'init':
                await self.handle_init(data)
            elif msg_type == 'input':
                await self.handle_input(data)
            elif msg_type == 'resize':
                await self.handle_resize(data)
            elif msg_type == 'ping':
                await self.send_message({'type': 'pong'})
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON message")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await self.send_error(str(e))
    
    async def handle_init(self, data: dict):
        """Initialize terminal session"""
        self.session_id = data.get('session_id', 'default')
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        
        # Create PTY process
        process = await self.pty_manager.create_pty(
            session_id=self.session_id,
            rows=rows,
            cols=cols
        )
        
        # Start reading from PTY
        await self.pty_manager.read_from_pty(
            self.session_id,
            self.handle_pty_output
        )
        
        # Send initialization success
        await self.send_message({
            'type': 'init_success',
            'session_id': self.session_id
        })
        
    async def handle_input(self, data: dict):
        """Handle keyboard input from client"""
        if not self.session_id:
            await self.send_error("Session not initialized")
            return
            
        input_data = data.get('data', '')
        
        # Convert to bytes and write to PTY
        await self.pty_manager.write_to_pty(
            self.session_id,
            input_data.encode('utf-8')
        )
        
    async def handle_resize(self, data: dict):
        """Handle terminal resize"""
        if not self.session_id:
            return
            
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        
        await self.pty_manager.resize_pty(self.session_id, rows, cols)
        
    async def handle_pty_output(self, data: bytes):
        """Handle output from PTY"""
        # Send output to client
        await self.send_message({
            'type': 'output',
            'data': data.decode('utf-8', errors='replace')
        })
        
    async def send_message(self, message: dict):
        """Send message to client"""
        if self.websocket.client_state == WebSocketState.CONNECTED:
            await self.websocket.send_text(json.dumps(message))
            
    async def send_error(self, error: str):
        """Send error message to client"""
        await self.send_message({
            'type': 'error',
            'message': error
        })
        
    async def cleanup(self):
        """Clean up resources"""
        if self.session_id:
            await self.pty_manager.terminate_pty(self.session_id)


# WebSocket endpoint
async def terminal_websocket_endpoint(
    websocket: WebSocket,
    pty_manager: PTYManager = Depends(get_pty_manager)
):
    """WebSocket endpoint for terminal connections"""
    handler = TerminalWebSocket(websocket, pty_manager)
    await handler.handle_connection()
```

### 2. Frontend Implementation

#### 2.1 Terminal Component (`static/js/terminal/Terminal.js`)
```javascript
/**
 * Terminal Component for Concierge
 * Integrates xterm.js with WebSocket backend
 */

import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import { WebLinksAddon } from 'xterm-addon-web-links';
import { SearchAddon } from 'xterm-addon-search';

export class ConciergeTerminal {
    constructor(container, options = {}) {
        this.container = container;
        this.sessionId = options.sessionId || 'default';
        this.wsUrl = options.wsUrl || this._getWebSocketUrl();
        
        // Initialize xterm.js
        this.terminal = new Terminal({
            fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
            fontSize: 14,
            theme: {
                background: '#1e1e1e',
                foreground: '#cccccc',
                cursor: '#ffffff',
                selection: '#3e4451',
                black: '#000000',
                red: '#e06c75',
                green: '#98c379',
                yellow: '#e5c07b',
                blue: '#61afef',
                magenta: '#c678dd',
                cyan: '#56b6c2',
                white: '#abb2bf',
                brightBlack: '#5c6370',
                brightRed: '#e06c75',
                brightGreen: '#98c379',
                brightYellow: '#e5c07b',
                brightBlue: '#61afef',
                brightMagenta: '#c678dd',
                brightCyan: '#56b6c2',
                brightWhite: '#ffffff'
            },
            cursorBlink: true,
            cursorStyle: 'block',
            scrollback: 10000,
            tabStopWidth: 8,
            allowTransparency: true,
            ...options.terminalOptions
        });
        
        // Initialize addons
        this.fitAddon = new FitAddon();
        this.searchAddon = new SearchAddon();
        this.webLinksAddon = new WebLinksAddon();
        
        this.terminal.loadAddon(this.fitAddon);
        this.terminal.loadAddon(this.searchAddon);
        this.terminal.loadAddon(this.webLinksAddon);
        
        // WebSocket connection
        this.ws = null;
        this.connected = false;
        this.reconnectTimer = null;
        this.reconnectDelay = 1000;
        
        // Initialize
        this._init();
    }
    
    _getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/api/v1/terminal/ws`;
    }
    
    _init() {
        // Open terminal in container
        this.terminal.open(this.container);
        
        // Fit terminal to container
        this.fitAddon.fit();
        
        // Set up event handlers
        this._setupEventHandlers();
        
        // Connect WebSocket
        this.connect();
    }
    
    _setupEventHandlers() {
        // Handle terminal input
        this.terminal.onData((data) => {
            if (this.connected) {
                this.sendInput(data);
            }
        });
        
        // Handle resize
        this.terminal.onResize((size) => {
            if (this.connected) {
                this.sendResize(size.cols, size.rows);
            }
        });
        
        // Handle window resize
        window.addEventListener('resize', () => {
            this.fit();
        });
        
        // Handle paste
        this.terminal.onPaste((data) => {
            if (this.connected) {
                this.sendInput(data);
            }
        });
    }
    
    connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }
        
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onopen = () => {
            console.log('Terminal WebSocket connected');
            this.connected = true;
            this.reconnectDelay = 1000;
            
            // Clear any reconnect timer
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            
            // Send initialization message
            this.sendMessage({
                type: 'init',
                session_id: this.sessionId,
                rows: this.terminal.rows,
                cols: this.terminal.cols
            });
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
        
        this.ws.onerror = (error) => {
            console.error('Terminal WebSocket error:', error);
        };
        
        this.ws.onclose = () => {
            console.log('Terminal WebSocket disconnected');
            this.connected = false;
            
            // Schedule reconnection
            this.scheduleReconnect();
        };
    }
    
    scheduleReconnect() {
        if (this.reconnectTimer) {
            return;
        }
        
        this.terminal.write('\r\n\x1b[31mConnection lost. Reconnecting...\x1b[0m\r\n');
        
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, this.reconnectDelay);
        
        // Exponential backoff
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
    }
    
    handleMessage(message) {
        switch (message.type) {
            case 'init_success':
                this.terminal.write('\x1b[32mTerminal initialized\x1b[0m\r\n');
                break;
                
            case 'output':
                this.terminal.write(message.data);
                break;
                
            case 'error':
                this.terminal.write(`\r\n\x1b[31mError: ${message.message}\x1b[0m\r\n`);
                break;
                
            case 'pong':
                // Heartbeat response
                break;
                
            default:
                console.warn('Unknown message type:', message.type);
        }
    }
    
    sendMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }
    
    sendInput(data) {
        this.sendMessage({
            type: 'input',
            data: data
        });
    }
    
    sendResize(cols, rows) {
        this.sendMessage({
            type: 'resize',
            cols: cols,
            rows: rows
        });
    }
    
    fit() {
        this.fitAddon.fit();
    }
    
    focus() {
        this.terminal.focus();
    }
    
    clear() {
        this.terminal.clear();
    }
    
    reset() {
        this.terminal.reset();
    }
    
    destroy() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
        
        if (this.ws) {
            this.ws.close();
        }
        
        this.terminal.dispose();
    }
}
```

#### 2.2 Terminal Page (`templates/terminal.html`)
```html
<!DOCTYPE html>
<html>
<head>
    <title>Concierge Terminal</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css">
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #1e1e1e;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        
        #terminal-container {
            position: absolute;
            top: 40px;
            left: 0;
            right: 0;
            bottom: 0;
            padding: 10px;
        }
        
        #terminal-header {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 40px;
            background: #2d2d2d;
            border-bottom: 1px solid #3e3e3e;
            display: flex;
            align-items: center;
            padding: 0 10px;
        }
        
        .header-title {
            color: #cccccc;
            font-size: 14px;
            font-weight: 500;
        }
        
        .header-actions {
            margin-left: auto;
            display: flex;
            gap: 10px;
        }
        
        .header-button {
            background: none;
            border: 1px solid #3e3e3e;
            color: #cccccc;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .header-button:hover {
            background: #3e3e3e;
        }
        
        #connection-status {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #e06c75;
            margin-right: 5px;
        }
        
        #connection-status.connected {
            background: #98c379;
        }
    </style>
</head>
<body>
    <div id="terminal-header">
        <div class="header-title">
            <span id="connection-status"></span>
            Concierge Terminal
        </div>
        <div class="header-actions">
            <button class="header-button" onclick="terminal.clear()">Clear</button>
            <button class="header-button" onclick="terminal.reset()">Reset</button>
            <button class="header-button" onclick="terminal.fit()">Fit</button>
        </div>
    </div>
    <div id="terminal-container"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-web-links@0.9.0/lib/xterm-addon-web-links.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-search@0.13.0/lib/xterm-addon-search.js"></script>
    
    <script type="module">
        // Import terminal class
        import { ConciergeTerminal } from '/static/js/terminal/Terminal.js';
        
        // Create terminal instance
        const terminal = new ConciergeTerminal(
            document.getElementById('terminal-container'),
            {
                sessionId: 'main',
                terminalOptions: {
                    // Custom options can be added here
                }
            }
        );
        
        // Update connection status
        setInterval(() => {
            const status = document.getElementById('connection-status');
            if (terminal.connected) {
                status.classList.add('connected');
            } else {
                status.classList.remove('connected');
            }
        }, 1000);
        
        // Make terminal available globally for header buttons
        window.terminal = terminal;
        
        // Focus terminal on load
        terminal.focus();
    </script>
</body>
</html>
```

### 3. Integration with Existing Concierge

#### 3.1 Update Router (`api/v1/routers/terminal.py`)
Add WebSocket endpoint:
```python
from fastapi import APIRouter, WebSocket

# ... existing code ...

# Add WebSocket route
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for terminal connections"""
    from openpilot.selfdrive.chauffeur.concierge.api.v1.websocket.terminal import (
        terminal_websocket_endpoint
    )
    await terminal_websocket_endpoint(websocket)
```

#### 3.2 Update Dependencies (`app/dependencies.py`)
Add PTY manager:
```python
from openpilot.selfdrive.chauffeur.concierge.core.services.terminal.pty_manager import PTYManager

# ... existing code ...

@lru_cache()
def get_pty_manager() -> PTYManager:
    """Get PTY manager instance"""
    return PTYManager()
```

### 4. Testing

#### 4.1 Unit Tests (`tests/test_pty_manager.py`)
```python
import pytest
import asyncio
from openpilot.selfdrive.chauffeur.concierge.core.services.terminal.pty_manager import PTYManager

@pytest.mark.asyncio
async def test_create_pty():
    """Test PTY creation"""
    manager = PTYManager()
    
    # Create PTY
    process = await manager.create_pty("test-session")
    
    assert process.pid > 0
    assert process.master_fd > 0
    
    # Write command
    await manager.write_to_pty("test-session", b"echo hello\n")
    
    # Read output
    output = []
    async def collector(data):
        output.append(data)
    
    reader = await manager.read_from_pty("test-session", collector)
    
    # Wait for output
    await asyncio.sleep(0.5)
    
    # Check output contains "hello"
    full_output = b''.join(output).decode()
    assert "hello" in full_output
    
    # Cleanup
    await manager.terminate_pty("test-session")
```

### 5. Security Considerations

1. **Input Validation**
   - Sanitize all input before sending to PTY
   - Limit input size to prevent buffer overflow
   - Rate limit input to prevent abuse

2. **Process Isolation**
   - Run shells with limited privileges
   - Consider using containers for isolation
   - Implement resource limits (CPU, memory, disk)

3. **Session Security**
   - Generate secure session IDs
   - Implement session timeouts
   - Add authentication before allowing terminal access

4. **WebSocket Security**
   - Use WSS (WebSocket Secure) in production
   - Implement origin validation
   - Add CSRF protection

### 6. Performance Optimizations

1. **Buffering**
   - Implement output buffering to reduce WebSocket messages
   - Batch multiple small writes into single messages
   - Use binary WebSocket frames for efficiency

2. **Flow Control**
   - Implement backpressure handling
   - Pause reading when client is slow
   - Add write buffer limits

3. **Resource Management**
   - Limit number of concurrent sessions
   - Implement session cleanup on disconnect
   - Monitor and limit resource usage

### 7. Next Steps

After Phase 1 is complete and working:

1. **Phase 2 Preparation**
   - Add full ANSI escape sequence parsing
   - Implement color themes
   - Add clipboard support
   - Enhance scrollback buffer

2. **Testing**
   - Test with various shells (bash, zsh, fish)
   - Test special characters and Unicode
   - Test under load (multiple sessions)
   - Test reconnection scenarios

3. **Documentation**
   - API documentation
   - WebSocket protocol specification
   - Security guidelines
   - Deployment instructions

This implementation provides a solid foundation for a professional terminal emulator that can be expanded with additional features in subsequent phases.