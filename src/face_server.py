"""
Face WebSocket Server - Bridges Python FaceController to browser renderer

Runs a simple WebSocket server that:
1. Accepts connections from the browser UI
2. Broadcasts face state updates from FaceController
3. Serves the UI files via HTTP
"""

import asyncio
import json
import threading
from pathlib import Path
from typing import Set, Optional
import http.server
import socketserver

try:
    import websockets
    from websockets.server import serve
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("Warning: websockets not installed. Run: pip install websockets")

from .face import FaceController, FaceState, Expression


class FaceServer:
    """
    WebSocket server for face state synchronization.
    
    Usage:
        server = FaceServer(port=18793)
        server.start()  # runs in background thread
        
        # Update face state
        server.controller.set_expression(Expression.HAPPY)
        server.controller.start_speaking()
        
        # Stop when done
        server.stop()
    """
    
    def __init__(self, port: int = 18793, ui_port: int = 8080):
        self.ws_port = port
        self.ui_port = ui_port
        self.controller = FaceController(on_state_change=self._on_state_change)
        self._clients: Set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._http_thread: Optional[threading.Thread] = None
        self._running = False
        self._pending_state: Optional[FaceState] = None
        
    def _on_state_change(self, state: FaceState):
        """Called when face state changes - broadcast to all clients."""
        if self._loop and self._running:
            # Schedule broadcast on the event loop
            asyncio.run_coroutine_threadsafe(
                self._broadcast(state.to_json()),
                self._loop
            )
        else:
            # Store for when we have clients
            self._pending_state = state
    
    async def _broadcast(self, message: str):
        """Send message to all connected clients."""
        if self._clients:
            await asyncio.gather(
                *[client.send(message) for client in self._clients],
                return_exceptions=True
            )
    
    async def _handler(self, websocket):
        """Handle a WebSocket connection."""
        self._clients.add(websocket)
        print(f"[FaceServer] Client connected ({len(self._clients)} total)")
        
        # Send current state to new client
        await websocket.send(self.controller.state.to_json())
        
        try:
            async for message in websocket:
                # Handle incoming commands from browser (if any)
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            print(f"[FaceServer] Client disconnected ({len(self._clients)} total)")
    
    async def _run_ws_server(self):
        """Run the WebSocket server."""
        async with serve(self._handler, "0.0.0.0", self.ws_port):
            print(f"[FaceServer] WebSocket server running on ws://0.0.0.0:{self.ws_port}/face")
            while self._running:
                await asyncio.sleep(0.1)
    
    def _ws_thread_target(self):
        """Thread target for WebSocket server."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_ws_server())
        finally:
            self._loop.close()
    
    def _run_http_server(self):
        """Serve the UI files via HTTP."""
        ui_dir = Path(__file__).parent.parent / "ui"
        
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(ui_dir), **kwargs)
            
            def log_message(self, format, *args):
                pass  # Suppress logging
        
        with socketserver.TCPServer(("0.0.0.0", self.ui_port), Handler) as httpd:
            print(f"[FaceServer] HTTP server running on http://0.0.0.0:{self.ui_port}")
            while self._running:
                httpd.handle_request()
    
    def start(self):
        """Start the face server (WebSocket + HTTP) in background threads."""
        if not WEBSOCKETS_AVAILABLE:
            print("[FaceServer] Cannot start - websockets not installed")
            return False
        
        self._running = True
        
        # Start WebSocket server thread
        self._ws_thread = threading.Thread(target=self._ws_thread_target, daemon=True)
        self._ws_thread.start()
        
        # Start HTTP server thread
        self._http_thread = threading.Thread(target=self._run_http_server, daemon=True)
        self._http_thread.start()
        
        print(f"[FaceServer] Started - UI at http://localhost:{self.ui_port}")
        return True
    
    def stop(self):
        """Stop the face server."""
        self._running = False
        if self._ws_thread:
            self._ws_thread.join(timeout=2.0)
        if self._http_thread:
            self._http_thread.join(timeout=2.0)
        print("[FaceServer] Stopped")
    
    # Convenience methods that delegate to controller
    
    def set_expression(self, expression: Expression):
        self.controller.set_expression(expression)
    
    def start_speaking(self):
        self.controller.start_speaking()
    
    def stop_speaking(self):
        self.controller.stop_speaking()
    
    def thinking(self):
        self.controller.thinking()
    
    def listening(self):
        self.controller.listening()


# Standalone test
if __name__ == "__main__":
    import time
    
    server = FaceServer()
    server.start()
    
    print("\nFace server running!")
    print(f"  UI: http://localhost:{server.ui_port}")
    print(f"  WS: ws://localhost:{server.ws_port}/face")
    print("\nPress Ctrl+C to stop, or test expressions:\n")
    
    expressions = [
        Expression.NEUTRAL,
        Expression.HAPPY,
        Expression.THINKING,
        Expression.SURPRISED,
        Expression.TALKING,
        Expression.SLEEPY,
    ]
    
    try:
        i = 0
        while True:
            time.sleep(3)
            expr = expressions[i % len(expressions)]
            print(f"  → {expr.value}")
            server.set_expression(expr)
            i += 1
    except KeyboardInterrupt:
        print("\nStopping...")
        server.stop()
