from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List

clipboard_ws_router = APIRouter()

class ClipboardConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove disconnected clients
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

clipboard_ws_manager = ClipboardConnectionManager()

@clipboard_ws_router.websocket("/ws/clipboard")
async def clipboard_websocket_endpoint(websocket: WebSocket):
    await clipboard_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clipboard_ws_manager.disconnect(websocket)
