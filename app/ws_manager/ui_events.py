"""
[INFO] Dedicated UI Events WebSocket Manager & Public Façade API
Implements memory-safe, isolated WebSocket connections for lightweight presentation-layer UI events (toasts, presence, connection state, banners, dialogs, announcements).

This channel NEVER interacts with repository state, filesystem mutations, upload status, or clipboard synchronization.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional, Any, List
import asyncio
import json
import secrets
import time
import logging

logger = logging.getLogger(__name__)

ui_events_ws_router = APIRouter()


class UIEventsConnectionManager:
    """
    [ISOLATED] UI Events WebSocket Connection Manager.
    Manages presentation-layer UI event streams across connected clients.
    """
    def __init__(self):
        # connection_id -> { "ws": WebSocket, "last_heartbeat": float, "connected_at": float, "client_id": str }
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """
        Accepts and registers a new UI Events WebSocket connection.
        """
        await websocket.accept()
        connection_id = secrets.token_hex(8)
        now = time.time()
        
        async with self.lock:
            self.active_connections[connection_id] = {
                "ws": websocket,
                "last_heartbeat": now,
                "connected_at": now,
                "client_id": client_id or connection_id
            }
            
        logger.info(f"[WS UI EVENTS] Client connected: {connection_id} (Total: {len(self.active_connections)})")
        return connection_id

    async def disconnect(self, connection_id: str):
        """
        Removes a client connection from active registry safely.
        """
        async with self.lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
        logger.info(f"[WS UI EVENTS] Client disconnected: {connection_id} (Total: {len(self.active_connections)})")

    def update_heartbeat(self, connection_id: str):
        """
        Updates last heartbeat timestamp for a client connection.
        """
        if connection_id in self.active_connections:
            self.active_connections[connection_id]["last_heartbeat"] = time.time()

    async def broadcast(self, event_type: str, payload: Optional[Dict[str, Any]] = None, exclude_connection_id: Optional[str] = None):
        """
        Broadcasts a validated, standardized UI event envelope to connected clients.
        
        Envelope Schema:
        {
          "version": 1,
          "type": event_type,
          "timestamp": int(time.time()),
          "payload": payload or {}
        }
        """
        # Strict validation before serialization
        if not event_type or not isinstance(event_type, str):
            logger.warning("[WS UI EVENTS] Broadcast rejected: event_type must be a non-empty string")
            return

        clean_payload = payload if isinstance(payload, dict) else {}

        envelope = {
            "version": 1,
            "type": event_type,
            "timestamp": int(time.time()),
            "payload": clean_payload
        }
        
        message_text = json.dumps(envelope)
        dead_connections: List[str] = []
        
        async with self.lock:
            connections_snapshot = list(self.active_connections.items())
            
        for conn_id, data in connections_snapshot:
            if exclude_connection_id and conn_id == exclude_connection_id:
                continue
            try:
                await data["ws"].send_text(message_text)
            except Exception as e:
                logger.warning(f"[WS UI EVENTS] Send failed for {conn_id}: {e}")
                dead_connections.append(conn_id)

        if dead_connections:
            async with self.lock:
                for conn_id in dead_connections:
                    self.active_connections.pop(conn_id, None)

    async def connection_count(self) -> int:
        """
        Returns active client connection count.
        """
        async with self.lock:
            return len(self.active_connections)

    async def cleanup_stale_connections(self, max_idle_seconds: float = 60.0):
        """
        Sweeps and closes stale connections that missed heartbeats.
        """
        now = time.time()
        stale_ids = []
        
        async with self.lock:
            for conn_id, data in self.active_connections.items():
                if now - data["last_heartbeat"] > max_idle_seconds:
                    stale_ids.append((conn_id, data["ws"]))

        for conn_id, ws in stale_ids:
            logger.info(f"[WS UI EVENTS] Closing stale heartbeat connection: {conn_id}")
            try:
                await ws.close(code=1000, reason="Heartbeat timeout")
            except Exception:
                pass
            await self.disconnect(conn_id)


    async def broadcast_server_shutdown(self, reason: str = "Server shutting down", graceful_time: float = 3.0):
        """
        Broadcasts a server shutdown notification to all connected UI clients.
        """
        await self.broadcast("server_shutdown", {"reason": reason, "graceful_time": graceful_time})

    async def shutdown(self):
        """
        Gracefully closes all active WebSocket connections and clears
        the connection registry. Called during server shutdown.
        """
        async with self.lock:
            connection_ids = list(self.active_connections.keys())
        for conn_id in connection_ids:
            try:
                data = self.active_connections.get(conn_id)
                if data and "ws" in data:
                    await data["ws"].close(code=1001, reason="Server shutting down")
            except Exception:
                pass
        async with self.lock:
            self.active_connections.clear()
        logger.info("[WS UI EVENTS] All connections closed — manager shut down")

ui_events_manager = UIEventsConnectionManager()


# =============================================================================
# PUBLIC FAÇADE API (Decouples backend caller logic from WebSocket internals)
# =============================================================================

async def emit_ui_event(event_type: str, payload: Optional[Dict[str, Any]] = None, exclude_connection_id: Optional[str] = None):
    """
    Public Async Façade API for emitting presentation-layer UI events.
    Decouples callers from transport mechanism.
    
    Usage:
        await emit_ui_event("ui.toast", {"message": "Hello", "level": "info"})
    """
    await ui_events_manager.broadcast(event_type, payload=payload, exclude_connection_id=exclude_connection_id)


def emit_ui_event_sync(event_type: str, payload: Optional[Dict[str, Any]] = None, exclude_connection_id: Optional[str] = None):
    """
    Public Synchronous Helper for emitting UI events from synchronous contexts.
    
    Usage:
        emit_ui_event_sync("ui.toast", {"message": "Hello", "level": "info"})
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(emit_ui_event(event_type, payload, exclude_connection_id))
    except RuntimeError:
        pass


@ui_events_ws_router.websocket("/ws/ui-events")
async def ui_events_websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
    """
    WebSocket Endpoint: /ws/ui-events
    Isolated presentation-layer UI event stream with heartbeat ping/pong support.
    """
    conn_id = await ui_events_manager.connect(websocket, client_id=client_id)
    try:
        while True:
            data = await websocket.receive_text()
            ui_events_manager.update_heartbeat(conn_id)
            
            # Application-level Ping / Pong support
            try:
                msg = json.loads(data)
                if isinstance(msg, dict):
                    msg_type = msg.get("type")
                    if msg_type == "ping":
                        pong_envelope = {
                            "version": 1,
                            "type": "pong",
                            "timestamp": int(time.time()),
                            "payload": {}
                        }
                        await websocket.send_text(json.dumps(pong_envelope))
                    elif msg_type == "pong":
                        pass
            except json.JSONDecodeError:
                logger.warning(f"[WS UI EVENTS] Received malformed packet from {conn_id}")
                pass

    except WebSocketDisconnect:
        await ui_events_manager.disconnect(conn_id)
    except Exception as e:
        logger.warning(f"[WS UI EVENTS] Connection error for {conn_id}: {e}")
        await ui_events_manager.disconnect(conn_id)
