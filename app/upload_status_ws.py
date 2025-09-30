"""
Real-time Upload Status WebSocket Handler
Provides live updates for folder and file uploads
"""
import json
import asyncio
from typing import Dict, Set, Any
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from fastapi.websockets import WebSocketState

router = APIRouter()

class UploadStatusManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.upload_sessions: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"📡 WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        print(f"📡 WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message_str)
            except Exception as e:
                print(f"❌ Error sending to WebSocket: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    async def notify_folder_start(self, folder_name: str, total_files: int):
        """Notify start of folder upload"""
        message = {
            "type": "folder_start",
            "folder_name": folder_name,
            "total_files": total_files,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast(message)
    
    async def notify_file_progress(self, folder_name: str, file_name: str, 
                                  current_file: int, total_files: int, 
                                  file_progress: float = 100.0):
        """Notify progress of individual file in folder upload"""
        message = {
            "type": "file_progress",
            "folder_name": folder_name,
            "file_name": file_name,
            "current_file": current_file,
            "total_files": total_files,
            "file_progress": file_progress,
            "overall_progress": (current_file / total_files) * 100,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast(message)
    
    async def notify_folder_complete(self, folder_name: str, uploaded_files: list, 
                                   failed_files: list, total_time: float = 0):
        """Notify completion of folder upload"""
        message = {
            "type": "folder_complete",
            "folder_name": folder_name,
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "success_count": len(uploaded_files),
            "total_files": len(uploaded_files) + len(failed_files),
            "total_time": total_time,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast(message)
    
    async def notify_folder_error(self, folder_name: str, error_message: str):
        """Notify error during folder upload"""
        message = {
            "type": "folder_error",
            "folder_name": folder_name,
            "error": error_message,
            "timestamp": asyncio.get_event_loop().time()
        }
        await self.broadcast(message)

# Global instance
upload_status_manager = UploadStatusManager()

@router.websocket("/ws/upload-status")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time upload status updates"""
    await upload_status_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and listen for client messages
            data = await websocket.receive_text()
            # Echo back for connection testing
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        upload_status_manager.disconnect(websocket)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        upload_status_manager.disconnect(websocket)