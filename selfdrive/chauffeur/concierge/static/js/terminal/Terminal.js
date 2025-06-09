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