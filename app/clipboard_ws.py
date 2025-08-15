import asyncio
from fastapi import WebSocket, WebSocketDisconnect, APIRouter

clipboard_ws_router = APIRouter()

class ClipboardConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

clipboard_ws_manager = ClipboardConnectionManager()

@clipboard_ws_router.websocket("/ws/clipboard")
async def websocket_endpoint(websocket: WebSocket):
    await clipboard_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep alive, ignore content
    except WebSocketDisconnect:
        clipboard_ws_manager.disconnect(websocket)
