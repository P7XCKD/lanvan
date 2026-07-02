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
        """Start background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = loop.create_task(self._background_cleanup())
            except RuntimeError:
                # No event loop running - cleanup will be manual
                pass

    async def _background_cleanup(self):
        """Background task to clean up stale connections"""
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if not self._shutdown_requested:
                    await self.cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but don't crash cleanup task
                print(f"WebSocket cleanup error: {e}")
        
        # Final cleanup before shutdown
        try:
            await self.cleanup_stale_connections()
        except Exception:
            pass

    async def connect(self, websocket: WebSocket) -> str:
        """Connect a new WebSocket with proper tracking"""
        # Check connection limit
        if len(self.active_connections) >= self.max_connections:
            await self.cleanup_stale_connections()
            if len(self.active_connections) >= self.max_connections:
                await websocket.close(code=1013, reason="Server overloaded")
                raise Exception("Server overloaded - too many connections")
        
        # Accept connection
        await websocket.accept()
        
        # Generate unique connection ID
        connection_id = secrets.token_hex(16)
        
        # Store connection with metadata
        self.active_connections[connection_id] = websocket
        self.connection_timeouts[connection_id] = time.time() + self.connection_timeout
        self.connection_metadata[connection_id] = {
            'connected_at': time.time(),
            'last_activity': time.time()
        }
        
        # Add to weak reference set
        self.weak_connections.add(websocket)
        
        return connection_id

    async def disconnect(self, websocket: Optional[WebSocket] = None, connection_id: Optional[str] = None):
        """Safely disconnect and clean up resources"""
        if connection_id:
            await self.force_disconnect(connection_id)
        elif websocket:
            # Find connection ID by websocket
            conn_id = None
            for cid, ws in self.active_connections.items():
                if ws == websocket:
                    conn_id = cid
                    break
            
            if conn_id:
                await self.force_disconnect(conn_id)

    async def force_disconnect(self, connection_id: str):
        """Forcefully disconnect and clean up all resources"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            
            try:
                # Try graceful close first
                await websocket.close()
            except:
                # Force close if graceful fails
                try:
                    await websocket.close(code=1006)
                except:
                    pass  # Connection already closed
            
            # Clean up all references
            del self.active_connections[connection_id]
            if connection_id in self.connection_timeouts:
                del self.connection_timeouts[connection_id]
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

    async def cleanup_stale_connections(self):
        """Clean up stale/timed-out connections"""
        current_time = time.time()
        stale_connections = [
            conn_id for conn_id, timeout in self.connection_timeouts.items()
            if current_time > timeout
        ]
        
        # Also check for weak reference cleanup
        active_ws = set(self.active_connections.values())
        weak_ws = set(self.weak_connections)
        orphaned_ws = weak_ws - active_ws
        
        # Clean up stale connections
        for conn_id in stale_connections:
            await self.force_disconnect(conn_id)
        
        # Clean up any orphaned connections
        for ws in orphaned_ws:
            try:
                await ws.close(code=1001, reason="Connection timeout")
            except:
                pass

    async def update_activity(self, connection_id: str):
        """Update last activity time for a connection"""
        if connection_id in self.connection_metadata:
            self.connection_metadata[connection_id]['last_activity'] = time.time()
            # Extend timeout
            self.connection_timeouts[connection_id] = time.time() + self.connection_timeout

    async def broadcast(self, message: str):
        """Broadcast message to all active connections with cleanup"""
        if not self.active_connections:
            return
        
        # Create a copy of connections to avoid modification during iteration
        connections_copy = list(self.active_connections.items())
        failed_connections = []
        
        for conn_id, websocket in connections_copy:
            try:
                await websocket.send_text(message)
                # Update activity on successful send
                await self.update_activity(conn_id)
            except Exception:
                # Mark connection as failed
                failed_connections.append(conn_id)
        
        # Clean up failed connections
        for conn_id in failed_connections:
            await self.force_disconnect(conn_id)

    def get_stats(self) -> Dict:
        """Get connection statistics"""
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
        """Graceful shutdown - close all connections and cleanup"""
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        connection_ids = list(self.active_connections.keys())
        for conn_id in connection_ids:
            await self.force_disconnect(conn_id)

clipboard_ws_manager = ClipboardConnectionManager()

@clipboard_ws_router.websocket("/ws/clipboard")
async def clipboard_websocket_endpoint(websocket: WebSocket):
    connection_id = None
    try:
        connection_id = await clipboard_ws_manager.connect(websocket)
        while True:
            data = await websocket.receive_text()
            # Update activity on message received
            if connection_id:
                await clipboard_ws_manager.update_activity(connection_id)
    except WebSocketDisconnect:
        if connection_id:
            await clipboard_ws_manager.disconnect(connection_id=connection_id)
        else:
            await clipboard_ws_manager.disconnect(websocket=websocket)
    except Exception:
        # Clean up on any error
        if connection_id:
            await clipboard_ws_manager.disconnect(connection_id=connection_id)
        else:
            await clipboard_ws_manager.disconnect(websocket=websocket)
