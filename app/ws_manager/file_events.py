"""
[INFO] Real-Time File Events WebSocket Manager
Implements memory-safe WebSocket connections for broadcasting real-time file system mutations (mkdir, rename, delete, upload) across devices.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional
import asyncio
import json
import secrets
import time
import logging

logger = logging.getLogger(__name__)

file_events_ws_router = APIRouter()

class FileEventsConnectionManager:
    """
    [LOCK] Memory-Safe File Events WebSocket Connection Manager
    
    Broadcasts instantaneous file mutation events to all connected clients on the local network.
    """
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = secrets.token_hex(8)
        async with self.lock:
            self.active_connections[connection_id] = websocket
        logger.info(f"[WS FILE EVENTS] Client connected: {connection_id} (Total: {len(self.active_connections)})")
        return connection_id

    async def disconnect(self, connection_id: str):
        async with self.lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
        logger.info(f"[WS FILE EVENTS] Client disconnected: {connection_id}")

    async def broadcast_file_event(self, action: str, target_dir: str = "", path: str = ""):
        """
        Broadcasts a file mutation event payload to all active WebSocket connections across all devices.
        """
        payload = json.dumps({
            "type": "file_change",
            "action": action,
            "target_dir": target_dir,
            "path": path,
            "timestamp": time.time()
        })
        
        dead_connections = []
        async with self.lock:
            connections_snapshot = list(self.active_connections.items())
            
        for conn_id, ws in connections_snapshot:
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning(f"[WS FILE EVENTS] Send failed for {conn_id}: {e}")
                dead_connections.append(conn_id)

        if dead_connections:
            async with self.lock:
                for conn_id in dead_connections:
                    self.active_connections.pop(conn_id, None)

file_events_manager = FileEventsConnectionManager()

def broadcast_file_event_sync(action: str, target_dir: str = "", path: str = ""):
    """
    Synchronous helper to schedule a broadcast on the main running event loop.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(file_events_manager.broadcast_file_event(action, target_dir, path))
    except RuntimeError:
        # Fallback if called outside active event loop
        asyncio.run(file_events_manager.broadcast_file_event(action, target_dir, path))

@file_events_ws_router.websocket("/ws/file_events")
async def file_events_websocket_endpoint(websocket: WebSocket):
    """Primary WebSocket endpoint for real-time file mutation events."""
    connection_id = await file_events_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await file_events_manager.disconnect(connection_id)
    except Exception as e:
        logger.warning(f"[WS FILE EVENTS] Socket error {connection_id}: {e}")
        await file_events_manager.disconnect(connection_id)

@file_events_ws_router.websocket("/ws/file-events")
async def file_events_websocket_endpoint_alias(websocket: WebSocket):
    """Alias endpoint (hyphenated URL convention) for the same file events manager."""
    connection_id = await file_events_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await file_events_manager.disconnect(connection_id)
    except Exception as e:
        logger.warning(f"[WS FILE EVENTS] Socket error {connection_id}: {e}")
        await file_events_manager.disconnect(connection_id)

