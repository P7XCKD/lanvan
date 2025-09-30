"""
Real-time Upload Status WebSocket Handler
Provides live updates for upload progress, folder uploads, and system status
"""

import asyncio
import json
import time
from typing import Dict, Set, Optional, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

# Global connection manager for upload status updates
class UploadStatusManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.upload_status: Dict[str, Dict[str, Any]] = {}
        self.folder_uploads: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"📡 Upload status WebSocket connected (total: {len(self.active_connections)})")
        
        # Send current upload status to new connection
        await self.send_current_status(websocket)
        
    async def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"📡 Upload status WebSocket disconnected (total: {len(self.active_connections)})")
        
    async def send_current_status(self, websocket: WebSocket):
        """Send current upload status to a specific connection"""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                status_data = {
                    "type": "system_status",
                    "active_uploads": len(self.upload_status),
                    "folder_uploads": len(self.folder_uploads),
                    "timestamp": time.time()
                }
                await websocket.send_text(json.dumps(status_data))
        except Exception as e:
            print(f"Error sending current status: {e}")
            
    async def broadcast(self, message: Dict[str, Any]):
        """Send message to all connected clients"""
        if not self.active_connections:
            return
            
        message_text = json.dumps(message)
        disconnected = set()
        
        for connection in self.active_connections.copy():
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message_text)
                else:
                    disconnected.add(connection)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                disconnected.add(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.active_connections.discard(connection)
    
    async def update_upload_progress(self, upload_id: str, progress_data: Dict[str, Any]):
        """Update and broadcast upload progress"""
        self.upload_status[upload_id] = {
            **self.upload_status.get(upload_id, {}),
            **progress_data,
            "last_update": time.time()
        }
        
        message = {
            "type": "upload_progress",
            "upload_id": upload_id,
            **progress_data
        }
        await self.broadcast(message)
    
    async def update_folder_progress(self, folder_name: str, folder_data: Dict[str, Any]):
        """Update and broadcast folder upload progress"""
        self.folder_uploads[folder_name] = {
            **self.folder_uploads.get(folder_name, {}),
            **folder_data,
            "last_update": time.time()
        }
        
        message = {
            "type": "folder_progress",
            "folder_name": folder_name,
            **folder_data
        }
        await self.broadcast(message)
    
    async def upload_completed(self, upload_id: str, completion_data: Dict[str, Any]):
        """Mark upload as completed and notify clients"""
        message = {
            "type": "upload_complete",
            "upload_id": upload_id,
            **completion_data
        }
        await self.broadcast(message)
        
        # Remove from active status
        self.upload_status.pop(upload_id, None)
    
    async def upload_error(self, upload_id: str, error_data: Dict[str, Any]):
        """Handle upload error and notify clients"""
        message = {
            "type": "upload_error",
            "upload_id": upload_id,
            **error_data
        }
        await self.broadcast(message)
        
        # Remove from active status
        self.upload_status.pop(upload_id, None)

# Global manager instance
upload_status_manager = UploadStatusManager()

# Router for WebSocket endpoints
upload_ws_router = APIRouter()

@upload_ws_router.websocket("/ws/upload-status")
async def upload_status_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time upload status updates"""
    try:
        await upload_status_manager.connect(websocket)
        
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle client requests
                if message.get("type") == "get_status":
                    await upload_status_manager.send_current_status(websocket)
                elif message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in upload status WebSocket: {e}")
                break
                
    except Exception as e:
        print(f"Upload status WebSocket connection error: {e}")
    finally:
        await upload_status_manager.disconnect(websocket)

# Helper functions for integration with upload routes
async def notify_upload_progress(upload_id: str, progress: float, speed: float = 0, 
                                uploaded_bytes: int = 0, time_remaining: float = 0,
                                status: str = "uploading"):
    """Notify clients of upload progress"""
    progress_data = {
        "progress": progress,
        "speed": speed,
        "uploaded_bytes": uploaded_bytes,
        "time_remaining": time_remaining,
        "status": status
    }
    await upload_status_manager.update_upload_progress(upload_id, progress_data)

async def notify_folder_progress(folder_name: str, total_files: int, completed_files: int,
                                current_file: str = "", file_progress: float = 0,
                                overall_progress: float = 0, file_status: str = "uploading"):
    """Notify clients of folder upload progress"""
    folder_data = {
        "total_files": total_files,
        "completed_files": completed_files,
        "current_file": current_file,
        "file_progress": file_progress,
        "overall_progress": overall_progress,
        "file_status": file_status
    }
    await upload_status_manager.update_folder_progress(folder_name, folder_data)

async def notify_upload_complete(upload_id: str, filename: str, file_size: int, duration: float):
    """Notify clients of upload completion"""
    completion_data = {
        "filename": filename,
        "file_size": file_size,
        "duration": duration
    }
    await upload_status_manager.upload_completed(upload_id, completion_data)

async def notify_upload_error(upload_id: str, filename: str, error_message: str):
    """Notify clients of upload error"""
    error_data = {
        "filename": filename,
        "error_message": error_message
    }
    await upload_status_manager.upload_error(upload_id, error_data)