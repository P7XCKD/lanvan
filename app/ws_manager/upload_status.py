"""
[RETRY] Upload Status WebSocket Manager
Implements memory-safe WebSockets for tracking file upload progress in real time.

Key Features:
- Per-session upload subscription mapping
- Broadcast progress updates using JSON serialization
- Weak references to WebSocket objects for automatic lifecycle protection
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional, Any
import asyncio
import secrets
import time
import weakref
import json

upload_status_ws_router = APIRouter()

class UploadStatusConnectionManager:
    """
    [STATS] Memory-Safe Upload Status WebSocket Manager
    
    Features:
    - Per-upload session tracking
    - Automatic cleanup of completed uploads
    - Connection timeout management
    - Resource leak prevention
    """
    
    def __init__(self):
        # Connection tracking
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_timeouts: Dict[str, float] = {}
        self.connection_uploads: Dict[str, List[str]] = {}  # Track uploads per connection
        
        # Upload session tracking
        self.upload_sessions: Dict[str, Dict[str, Any]] = {}  # upload_id -> session data
        self.session_connections: Dict[str, List[str]] = {}   # upload_id -> connection_ids
        
        # Weak references for safety
        self.weak_connections = weakref.WeakSet()
        
        # Configuration
        self.connection_timeout = 600  # 10 minutes for uploads
        self.max_connections = 50
        self.cleanup_interval = 120    # Cleanup every 2 minutes
        
        # Shutdown coordination
        self._shutdown_requested = False
        
        # Background cleanup
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
                pass

    async def _background_cleanup(self):
        """
        Background cleanup worker task that executes periodic connection sweeps and expired upload removals.
        """
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if not self._shutdown_requested:
                    await self.cleanup_stale_connections()
                    await self.cleanup_completed_uploads()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Upload WebSocket cleanup error: {e}")
        
        # Run final connection cleanup sweep during server shutdown
        try:
            await self.cleanup_stale_connections()
        except Exception:
            pass

    async def connect(self, websocket: WebSocket, upload_id: Optional[str] = None) -> str:
        """
        Registers and accepts a new incoming upload tracking client WebSocket.
        
        Args:
            websocket: The incoming FastAPI WebSocket connection instance.
            upload_id: Optional upload ID to automatically subscribe to on connection.
            
        Returns:
            str: A unique hexadecimal token assigned to this connection.
            
        Raises:
            Exception: If the server connection capacity exceeds configured limits.
        """
        # Enforce limits to prevent resource exhaustion
        if len(self.active_connections) >= self.max_connections:
            await self.cleanup_stale_connections()
            if len(self.active_connections) >= self.max_connections:
                await websocket.close(code=1013, reason="Server overloaded")
                raise Exception("Too many upload status connections")
        
        await websocket.accept()
        
        # Generate connection token
        connection_id = secrets.token_hex(16)
        
        # Store connection references
        self.active_connections[connection_id] = websocket
        self.connection_timeouts[connection_id] = time.time() + self.connection_timeout
        self.connection_uploads[connection_id] = []
        
        # Associate with upload session if provided
        if upload_id:
            await self.subscribe_to_upload(connection_id, upload_id)
        
        self.weak_connections.add(websocket)
        return connection_id

    async def subscribe_to_upload(self, connection_id: str, upload_id: str):
        """
        Subscribes a WebSocket connection to progress changes for a given upload session.
        
        Args:
            connection_id: The connection ID token.
            upload_id: The upload ID string to subscribe to.
        """
        if connection_id in self.connection_uploads:
            self.connection_uploads[connection_id].append(upload_id)
        
        if upload_id not in self.session_connections:
            self.session_connections[upload_id] = []
        self.session_connections[upload_id].append(connection_id)
        
        # Initialize upload session if not exists
        if upload_id not in self.upload_sessions:
            self.upload_sessions[upload_id] = {
                'created_at': time.time(),
                'status': 'started',
                'progress': 0,
                'total_size': 0,
                'uploaded_size': 0,
                'files': []
            }

    async def update_upload_progress(self, upload_id: str, progress_data: Dict[str, Any]):
        """
        Updates the progress of an upload session and broadcasts it to all subscribed clients.
        
        Args:
            upload_id: The upload ID string.
            progress_data: Dict containing updated progress parameters.
        """
        if upload_id in self.upload_sessions:
            # Update session data
            self.upload_sessions[upload_id].update(progress_data)
            self.upload_sessions[upload_id]['last_update'] = time.time()
            
            # Notify all subscribed connections
            if upload_id in self.session_connections:
                message = json.dumps({
                    'type': 'upload_progress',
                    'upload_id': upload_id,
                    'data': progress_data
                })
                
                failed_connections = []
                for conn_id in self.session_connections[upload_id]:
                    if conn_id in self.active_connections:
                        try:
                            await self.active_connections[conn_id].send_text(message)
                            self.connection_timeouts[conn_id] = time.time() + self.connection_timeout
                        except Exception:
                            failed_connections.append(conn_id)
                
                # Clean up failed connections
                for conn_id in failed_connections:
                    await self.disconnect(connection_id=conn_id)

    async def complete_upload(self, upload_id: str, final_data: Optional[Dict[str, Any]] = None):
        """
        Marks an upload session as completed and broadcasts final details to clients.
        
        Args:
            upload_id: The upload ID string.
            final_data: Optional Dict containing final response fields.
        """
        if upload_id in self.upload_sessions:
            self.upload_sessions[upload_id]['status'] = 'completed'
            self.upload_sessions[upload_id]['completed_at'] = time.time()
            
            if final_data:
                self.upload_sessions[upload_id].update(final_data)
            
            # Notify subscribers
            message = json.dumps({
                'type': 'upload_complete',
                'upload_id': upload_id,
                'data': final_data or {}
            })
            
            if upload_id in self.session_connections:
                for conn_id in self.session_connections[upload_id]:
                    if conn_id in self.active_connections:
                        try:
                            await self.active_connections[conn_id].send_text(message)
                        except Exception:
                            pass
            
            # Also broadcast completion to all clients for cross-device sync
            await self.notify_file_list_updated([upload_id])

    async def broadcast_to_all(self, message: str):
        """
        Broadcasts a text message to ALL active WebSocket connections across all devices.
        """
        failed_connections = []
        for conn_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_text(message)
                self.connection_timeouts[conn_id] = time.time() + self.connection_timeout
            except Exception:
                failed_connections.append(conn_id)
        
        for conn_id in failed_connections:
            await self.disconnect(connection_id=conn_id)

    async def notify_file_list_updated(self, files: Optional[List[str]] = None):
        """
        Broadcasts a file_list_updated event to all clients so connected devices update immediately.
        """
        msg = json.dumps({
            "type": "file_list_updated",
            "files": files or [],
            "timestamp": time.time()
        })
        await self.broadcast_to_all(msg)

    async def disconnect(self, websocket: Optional[WebSocket] = None, connection_id: Optional[str] = None):
        """
        Gracefully disconnects a connection, locating references by socket object or connection token.
        """
        if connection_id:
            await self._force_disconnect(connection_id)
        elif websocket:
            conn_id = None
            for cid, ws in self.active_connections.items():
                if ws == websocket:
                    conn_id = cid
                    break
            if conn_id:
                await self._force_disconnect(conn_id)

    async def _force_disconnect(self, connection_id: str):
        """
        Closes and tears down the specified connection immediately, clearing all registration metadata.
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            
            try:
                await websocket.close()
            except Exception:
                pass
            
            # Clean up connection references
            del self.active_connections[connection_id]
            if connection_id in self.connection_timeouts:
                del self.connection_timeouts[connection_id]
            
            # Clean up upload subscriptions
            if connection_id in self.connection_uploads:
                upload_ids = self.connection_uploads[connection_id]
                for upload_id in upload_ids:
                    if upload_id in self.session_connections:
                        if connection_id in self.session_connections[upload_id]:
                            self.session_connections[upload_id].remove(connection_id)
                        # Clean up empty session connection lists
                        if not self.session_connections[upload_id]:
                            del self.session_connections[upload_id]
                
                del self.connection_uploads[connection_id]

    async def cleanup_stale_connections(self):
        """
        Sweeps the connection registers to disconnect timed-out clients.
        """
        current_time = time.time()
        stale_connections = [
            conn_id for conn_id, timeout in self.connection_timeouts.items()
            if current_time > timeout
        ]
        
        for conn_id in stale_connections:
            await self._force_disconnect(conn_id)

    async def cleanup_completed_uploads(self):
        """
        Cleans up upload sessions that have been completed for longer than 5 minutes to release memory.
        Also caps total sessions at 200, evicting oldest completed sessions first.
        """
        current_time = time.time()
        retention_seconds = 300  # 5 minutes (reduced from 1 hour)
        
        old_sessions = [
            upload_id for upload_id, session in self.upload_sessions.items()
            if (session.get('status') == 'completed' and 
                current_time - session.get('completed_at', 0) > retention_seconds)
        ]
        
        for upload_id in old_sessions:
            if upload_id in self.session_connections:
                del self.session_connections[upload_id]
            del self.upload_sessions[upload_id]
        
        # Cap total sessions at 200 — evict oldest completed sessions if exceeded
        if len(self.upload_sessions) > 200:
            completed = [(uid, s) for uid, s in self.upload_sessions.items() if s.get('status') == 'completed']
            completed.sort(key=lambda x: x[1].get('completed_at', 0))  # oldest first
            excess = len(self.upload_sessions) - 200
            for uid, _ in completed[:excess]:
                if uid in self.session_connections:
                    del self.session_connections[uid]
                del self.upload_sessions[uid]

    def get_stats(self) -> Dict[str, Any]:
        """
        Retrieves real-time utilization stats for the connection registry.
        """
        return {
            'active_connections': len(self.active_connections),
            'active_uploads': len([s for s in self.upload_sessions.values() if s.get('status') != 'completed']),
            'completed_uploads': len([s for s in self.upload_sessions.values() if s.get('status') == 'completed']),
            'total_sessions': len(self.upload_sessions),
            'weak_references': len(self.weak_connections)
        }

    async def shutdown(self):
        """
        Cancels the background cleanup loop and forces closure on all active client connections.
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        connection_ids = list(self.active_connections.keys())
        for conn_id in connection_ids:
            await self._force_disconnect(conn_id)

# Global manager instance
upload_status_manager = UploadStatusConnectionManager()

@upload_status_ws_router.websocket("/ws/upload-status")
async def upload_status_websocket_endpoint(websocket: WebSocket):
    """
    FastAPI WebSocket endpoint for managing live upload status updates.
    """
    connection_id = None
    try:
        connection_id = await upload_status_manager.connect(websocket)
        
        while True:
            # Listen for client messages (e.g., subscribe to specific uploads)
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                if message.get('type') == 'subscribe' and message.get('upload_id'):
                    await upload_status_manager.subscribe_to_upload(
                        connection_id, 
                        message['upload_id']
                    )
            except (json.JSONDecodeError, KeyError):
                # Ignore invalid formatting
                pass
            
    except WebSocketDisconnect:
        if connection_id:
            await upload_status_manager.disconnect(connection_id=connection_id)
    except Exception:
        if connection_id:
            await upload_status_manager.disconnect(connection_id=connection_id)

@upload_status_ws_router.websocket("/ws/upload-status/{upload_id}")
async def upload_specific_websocket_endpoint(websocket: WebSocket, upload_id: str):
    """
    FastAPI WebSocket endpoint for managing status tracking for a specific upload ID.
    """
    connection_id = None
    try:
        connection_id = await upload_status_manager.connect(websocket, upload_id)
        
        # Dispatch initial session status details immediately if available
        if upload_id in upload_status_manager.upload_sessions:
            session_data = upload_status_manager.upload_sessions[upload_id]
            initial_message = json.dumps({
                'type': 'upload_status',
                'upload_id': upload_id,
                'data': session_data
            })
            await websocket.send_text(initial_message)
        
        while True:
            # Keep the socket connection active
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        if connection_id:
            await upload_status_manager.disconnect(connection_id=connection_id)
    except Exception:
        if connection_id:
            await upload_status_manager.disconnect(connection_id=connection_id)
