"""
[INFO] Clipboard WebSocket Manager
Implements memory-safe WebSocket connections for real-time clipboard sync across devices.

Key Features:
- Unique connection tracking with metadata registries
- Periodic background timeout pruning of idle clients
- Weakref tracking sets to prevent reference cycles and leaks
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
import asyncio
import secrets
import time
import weakref
import logging

clipboard_ws_router = APIRouter()

class ClipboardConnectionManager:
    """
    [LOCK] Memory-Safe WebSocket Connection Manager
    
    Features:
    - Connection ID tracking to prevent memory leaks
    - Automatic timeout cleanup for stale connections
    - Weak references for additional safety
    - Background cleanup task
    - Proper resource disposal
    """
    
    def __init__(self):
        # Use dictionary with connection IDs for better tracking
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_timeouts: Dict[str, float] = {}
        self.connection_metadata: Dict[str, Dict] = {}
        
        # Weak reference set for additional safety
        self.weak_connections = weakref.WeakSet()
        
        # Configuration
        self.connection_timeout = 300  # 5 minutes default timeout
        self.max_connections = 100     # Prevent DoS
        self.cleanup_interval = 60     # Cleanup every minute
        
        # Shutdown coordination
        self._shutdown_requested = False
        
        # Background cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """
        Starts the background worker task to clean up expired and stale connections.
        Ensures a single active background cleanup loop is maintained.
        """
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._background_cleanup())
            except RuntimeError:
                # No running event loop found (e.g. testing or initialization phase)
                pass

    async def _background_cleanup(self):
        """
        Background execution loop executing at regular intervals to trigger connection sweeps.
        Ensures proper resource disposal and gracefully exits upon cancellation.
        """
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if not self._shutdown_requested:
                    await self.cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Suppress errors to prevent the background loop from terminating
                print(f"WebSocket cleanup error: {e}")
        
        # Run final connection cleanup sweep during server shutdown
        try:
            await self.cleanup_stale_connections()
        except Exception:
            pass

    async def connect(self, websocket: WebSocket) -> str:
        """
        Registers and accepts a new incoming client WebSocket connection.
        
        Args:
            websocket: The incoming FastAPI WebSocket connection instance.
            
        Returns:
            str: A unique hexadecimal token assigned to this connection.
            
        Raises:
            Exception: If the server connection capacity exceeds configured limits.
        """
        # Enforce security capacity limits to prevent resource exhaustion / DoS attacks
        if len(self.active_connections) >= self.max_connections:
            await self.cleanup_stale_connections()
            if len(self.active_connections) >= self.max_connections:
                await websocket.close(code=1013, reason="Server overloaded")
                raise Exception("Server overloaded - too many connections")
        
        # Accept the handshake
        await websocket.accept()
        
        # Allocate a unique reference token
        connection_id = secrets.token_hex(16)
        
        # Register the connection mapping and keepalive markers
        self.active_connections[connection_id] = websocket
        self.connection_timeouts[connection_id] = time.time() + self.connection_timeout
        self.connection_metadata[connection_id] = {
            'connected_at': time.time(),
            'last_activity': time.time()
        }
        
        # Append connection to the weak reference tracker
        self.weak_connections.add(websocket)
        
        return connection_id

    async def disconnect(self, websocket: Optional[WebSocket] = None, connection_id: Optional[str] = None):
        """
        Gracefully disconnects a connection, locating references by socket object or connection token.
        
        Args:
            websocket: Optional WebSocket instance to close.
            connection_id: Optional string token representing the socket.
        """
        if connection_id:
            await self.force_disconnect(connection_id)
        elif websocket:
            conn_id = None
            for cid, ws in self.active_connections.items():
                if ws == websocket:
                    conn_id = cid
                    break
            
            if conn_id:
                await self.force_disconnect(conn_id)

    async def force_disconnect(self, connection_id: str):
        """
        Closes and tears down the specified connection immediately, clearing all registration metadata.
        
        Args:
            connection_id: The connection ID string of the socket.
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            
            try:
                # Attempt graceful websocket close frame
                await websocket.close()
            except Exception:
                try:
                    # Force socket closure on error
                    await websocket.close(code=1006)
                except Exception:
                    pass  # Socket was already disconnected
            
            # Clean up all tracking references
            del self.active_connections[connection_id]
            if connection_id in self.connection_timeouts:
                del self.connection_timeouts[connection_id]
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

    async def cleanup_stale_connections(self):
        """
        Sweeps the connection registers to disconnect timed-out clients and reclaim memory.
        Prunes dead weak references left behind by garbage-collected socket objects.
        """
        current_time = time.time()
        stale_connections = [
            conn_id for conn_id, timeout in self.connection_timeouts.items()
            if current_time > timeout
        ]
        
        # Identify orphaned sockets that were collected but not cleared from weak references
        active_ws = set(self.active_connections.values())
        weak_ws = set(self.weak_connections)
        orphaned_ws = weak_ws - active_ws
        
        # Clean up connections exceeding inactive timeout
        for conn_id in stale_connections:
            await self.force_disconnect(conn_id)
        
        # Clean up weak reference leftovers
        for ws in orphaned_ws:
            try:
                await ws.close(code=1001, reason="Connection timeout")
            except Exception:
                pass

    async def update_activity(self, connection_id: str):
        """
        Extends connection life-support timeout based on active transfer signals.
        
        Args:
            connection_id: The connection ID token.
        """
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]['last_activity'] = time.time()
            self.connection_timeouts[connection_id] = time.time() + self.connection_timeout

    async def broadcast(self, message: str):
        """
        Sends a payload string to all registered WebSockets, pruning dead channels automatically.
        
        Args:
            message: The string data payload to broadcast.
        """
        if not self.active_connections:
            return
        
        # Loop over copy to avoid modification conflicts
        connections_copy = list(self.active_connections.items())
        failed_connections = []
        
        for conn_id, websocket in connections_copy:
            try:
                await websocket.send_text(message)
                await self.update_activity(conn_id)
            except Exception:
                failed_connections.append(conn_id)
        
        # Purge bad connection handles
        for conn_id in failed_connections:
            await self.force_disconnect(conn_id)

    def get_stats(self) -> Dict:
        """
        Retrieves real-time utilization stats for the connection registry.
        
        Returns:
            Dict: Dictionary containing total connections, weak reference counts, and age metrics.
        """
        current_time = time.time()
        return {
            'total_connections': len(self.active_connections),
            'weak_references': len(self.weak_connections),
            'average_connection_age': sum(
                current_time - meta['connected_at'] 
                for meta in self.connection_metadata.values()
            ) / max(len(self.connection_metadata), 1),
            'cleanup_task_running': self._cleanup_task and not self._cleanup_task.done()
        }

    async def shutdown(self):
        """
        Cancels the background cleanup loop and forces closure on all active client connections.
        Registered inside application lifespan shutdown.
        """
        # Cancel the task loop
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all active sockets
        connection_ids = list(self.active_connections.keys())
        for conn_id in connection_ids:
            await self.force_disconnect(conn_id)

clipboard_ws_manager = ClipboardConnectionManager()

@clipboard_ws_router.websocket("/ws/clipboard")
async def clipboard_websocket_endpoint(websocket: WebSocket):
    """
    FastAPI WebSocket endpoint for managing live clipboard synchronization across devices.
    """
    connection_id = None
    try:
        connection_id = await clipboard_ws_manager.connect(websocket)
        while True:
            # Continuously listen for incoming client message payload frames
            await websocket.receive_text()
            if connection_id:
                await clipboard_ws_manager.update_activity(connection_id)
    except WebSocketDisconnect:
        if connection_id:
            await clipboard_ws_manager.disconnect(connection_id=connection_id)
        else:
            await clipboard_ws_manager.disconnect(websocket=websocket)
    except Exception:
        if connection_id:
            await clipboard_ws_manager.disconnect(connection_id=connection_id)
        else:
            await clipboard_ws_manager.disconnect(websocket=websocket)
