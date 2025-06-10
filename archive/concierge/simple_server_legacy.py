#!/usr/bin/env python3
"""
Simple HTTP server for Concierge that doesn't require external dependencies.
Falls back to Python's built-in HTTP server when FastAPI isn't available.
"""

import http.server
import socketserver
import os
import json
import sys
from urllib.parse import urlparse, parse_qs

PORT = 5055

class ConciergeHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
<!DOCTYPE html>
<html>
<head>
    <title>Concierge - Simple Mode</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #1a1a1a; color: #e0e0e0; }
        h1 { color: #4CAF50; }
        .status { background: #2a2a2a; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .error { color: #ff6b6b; }
        .warning { color: #ffa726; }
        .info { color: #29b6f6; }
    </style>
</head>
<body>
    <h1>Concierge Web Server</h1>
    <div class="status">
        <h2>Status: Running (Simple Mode)</h2>
        <p class="warning">⚠️ Running in fallback mode without FastAPI</p>
        <p>This is a basic HTTP server providing limited functionality.</p>
    </div>
    <div class="status">
        <h3>Available Endpoints:</h3>
        <ul>
            <li><a href="/health">/health</a> - Health check</li>
            <li><a href="/api/status">/api/status</a> - System status</li>
        </ul>
    </div>
    <div class="status">
        <p class="info">ℹ️ To enable full functionality, FastAPI and uvicorn need to be installed in the TICI image.</p>
    </div>
</body>
</html>
"""
            self.wfile.write(html.encode())
            
        elif parsed_path.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "mode": "simple",
                "message": "Concierge is running in simple mode"
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif parsed_path.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "server": "Concierge Simple Mode",
                "uptime": "unknown",
                "features": ["basic HTTP", "health check"],
                "missing_features": ["WebSocket", "async support", "full API"]
            }
            self.wfile.write(json.dumps(response).encode())
            
        else:
            self.send_error(404)
    
    def log_message(self, format, *args):
        """Override to reduce log spam."""
        if '/health' not in args[0]:
            sys.stderr.write("[CONCIERGE] %s - - [%s] %s\n" %
                         (self.client_address[0],
                          self.log_date_time_string(),
                          format%args))

def main():
    """Run the simple server."""
    print(f"[CONCIERGE] Starting simple HTTP server on port {PORT}")
    print("[CONCIERGE] This is a fallback mode with limited functionality")
    
    try:
        with socketserver.TCPServer(("", PORT), ConciergeHandler) as httpd:
            httpd.allow_reuse_address = True
            print(f"[CONCIERGE] Server listening at http://0.0.0.0:{PORT}")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[CONCIERGE] Server stopped")
    except Exception as e:
        print(f"[CONCIERGE] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()