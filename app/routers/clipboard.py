
import os
import io
import sys
import json
import time
import gc
import socket
import shutil
import hashlib
import zipfile
import base64
import tempfile
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from mimetypes import guess_type
from zipfile import ZipFile

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Query, Form, HTTPException, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from starlette.status import (
    HTTP_302_FOUND,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR
)

# Import common app utilities
from app.aes_utils import encrypt_session_data, decrypt_session_data, encrypt_file_http_safe, decrypt_http_safe_file, decrypt_file_stream
from app.aes_utils import AESConfig
from app.metadata_protection import generate_secure_filename, obfuscate_file_size, generate_decoy_requests
from app.validation import (
    validate_upload_files, 
    validate_upload_files_enhanced,
    validate_upload_files_enhanced_async,
    validate_upload_files_enhanced_fast,
    secure_filename,
    is_allowed_file,
    FileValidator,
    AdvancedFileValidator
)
from app.simple_mdns import mdns_manager
from app.file_locking import get_file_lock_manager, cleanup_stale_locks
from app.termux_compat import get_platform_info, detect_platform, is_android, is_termux
from app.clipboard_ws import clipboard_ws_manager
from app.concurrent_upload_manager import concurrent_upload_manager, ConcurrentUploadManager
from app.windows_file_manager import WindowsFileManager
from app.streaming_assembly import get_streaming_assembler, add_streaming_chunk, check_streaming_status, get_assembled_file

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
CLIPBOARD_FOLDER = Path("app/clipboard_data")

CLIPBOARD_HISTORY_FILE = CLIPBOARD_FOLDER / "clipboard_history.json"

clipboard_history = []

clipboard_id_counter = 0

def load_clipboard_history():
    """Load clipboard history from persistent storage on startup"""
    global clipboard_history, clipboard_id_counter
    
    try:
        if CLIPBOARD_HISTORY_FILE.exists():
            with open(CLIPBOARD_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                clipboard_history = data.get('items', [])
                clipboard_id_counter = data.get('last_id', 0)
                print(f"[INFO] Loaded {len(clipboard_history)} clipboard items from persistent storage")
        else:
            print("[INFO] No persistent clipboard history found, starting fresh")
    except Exception as e:
        print(f"[ERR] Error loading clipboard history: {e}")
        clipboard_history = []
        clipboard_id_counter = 0

def save_clipboard_history():
    """Save clipboard history to persistent storage"""
    global clipboard_history, clipboard_id_counter
    
    try:
        # Prepare data for saving (convert binary data to base64 for JSON serialization)
        save_data = {
            'items': [],
            'last_id': clipboard_id_counter
        }
        
        for item in clipboard_history:
            save_item = item.copy()
            
            # Handle binary data for files
            if item['type'] == 'file' and 'data' in item:
                import base64
                save_item['data'] = base64.b64encode(item['data']).decode('utf-8')
                save_item['data_encoding'] = 'base64'
            
            save_data['items'].append(save_item)
        
        # Write to file atomically
        temp_file = CLIPBOARD_HISTORY_FILE.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        
        # Atomic rename
        temp_file.replace(CLIPBOARD_HISTORY_FILE)
        
    except Exception as e:
        print(f"[ERR] Error saving clipboard history: {e}")

def restore_clipboard_data(items):
    """Restore clipboard data after loading from JSON (decode base64 data)"""
    global clipboard_history
    
    for item in items:
        if item.get('data_encoding') == 'base64' and 'data' in item:
            import base64
            try:
                item['data'] = base64.b64decode(item['data'])
                del item['data_encoding']  # Remove the encoding marker
            except Exception as e:
                print(f"[ERR] Error decoding clipboard item {item.get('id', 'unknown')}: {e}")
                # Remove corrupted item
                continue
    
    return items

def initialize_clipboard_persistence():
    """Initialize clipboard persistence after all imports are complete"""
    try:
        load_clipboard_history()
        global clipboard_history
        if clipboard_history:
            clipboard_history = restore_clipboard_data(clipboard_history)
        print(f"[INFO] Clipboard persistence initialized successfully with {len(clipboard_history)} items")
    except Exception as e:
        print(f"[ERR] Error initializing clipboard persistence: {e}")
        clipboard_history.clear()
        global clipboard_id_counter
        clipboard_id_counter = 0

@router.get("/clipboard", response_class=HTMLResponse, name="clipboard_page")
async def clipboard_page(request: Request):
    """Full page clipboard route"""
    #  Direct clipboard access - no redirects
    files = get_file_list()  # Include files for seamless switching
    
    # Render the same template, but with clipboard as default view
    return templates.TemplateResponse("index.html", {
        "request": request,
        "msg": "Lanvan",
        "files": [f["name"] for f in files],
        "show_both_sections": True,  # Show both sections
        "default_view": "clipboard"  # Default to clipboard view
    })

@router.post("/api/clipboard/add", name="clipboard_add")
async def add_to_clipboard(
    request: Request,
    data: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """Add content to clipboard - supports text and files (no image preview)"""
    global clipboard_id_counter, clipboard_history
    
    try:
        clipboard_id_counter += 1
        timestamp = time.time()
        
        if file:
            # Handle file upload to clipboard
            if not file.filename:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "msg": "No filename provided"}
                )
            
            # Validate file type for clipboard
            allowed_types = {
                'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'],
                'text': ['txt', 'md', 'json', 'csv', 'xml'],
                'document': ['pdf', 'doc', 'docx'],
                'other': ['zip', 'rar', '7z']
            }
            
            file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
            content_type = 'other'
            
            for type_name, extensions in allowed_types.items():
                if file_ext in extensions:
                    content_type = type_name
                    break
            
            # [RETRY] MEMORY FIX: Use Termux-optimized chunk size for clipboard streaming
            from app.universal_optimizer import get_adaptive_chunk_size
            CHUNK_SIZE = get_adaptive_chunk_size(1024 * 1024)  # Get platform-optimal chunk size
            MAX_SIZE = 10 * 1024 * 1024  # 10MB limit
            file_content = b""
            file_size = 0
            
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                file_size += len(chunk)
                
                # Check size limit as we read
                if file_size > MAX_SIZE:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "msg": "File too large for clipboard (max 10MB)"}
                    )
                
                file_content += chunk
            
            # Create clipboard item for file (with base64 image preview)
            preview = generate_simple_file_preview(file.filename, file_content, content_type)
            
            clipboard_item = {
                "id": clipboard_id_counter,
                "type": "file",
                "content_type": content_type,
                "filename": file.filename,
                "size": file_size,
                "data": file_content,
                "timestamp": timestamp,
                "formatted_time": time.strftime("%I:%M:%S %p", time.localtime(timestamp)),
                "preview": preview,
                "is_image_preview": content_type == 'image' and preview.startswith('data:')
            }
            
        elif data:
            # Handle text/data content
            content_size = len(data.encode('utf-8'))
            
            # Detect content type
            if data.startswith('data:image/'):
                content_type = 'image_base64'
                preview = "Base64 image data (no preview)"  # No image preview
            elif data.startswith('http://') or data.startswith('https://'):
                content_type = 'url'
                preview = data[:100] + "..." if len(data) > 100 else data
            else:
                content_type = 'text'
                preview = data[:200] + "..." if len(data) > 200 else data
            
            clipboard_item = {
                "id": clipboard_id_counter,
                "type": "text",
                "content_type": content_type,
                "data": data,
                "size": content_size,
                "timestamp": timestamp,
                "formatted_time": time.strftime("%I:%M:%S %p", time.localtime(timestamp)),
                "preview": preview
            }
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "msg": "No content provided"}
            )
        
        # Add to clipboard history (newest first)
        clipboard_history.insert(0, clipboard_item)

        # Keep only last 50 items to prevent memory bloat
        if len(clipboard_history) > 50:
            clipboard_history = clipboard_history[:50]
        
        # Save to persistent storage
        save_clipboard_history()

        # Notify all websocket clients (real-time clipboard update)
        try:
            import asyncio
            asyncio.create_task(clipboard_ws_manager.broadcast("refresh"))
        except Exception:
            pass

        return JSONResponse(content={
            "status": "success",
            "msg": f"Added to clipboard: {clipboard_item['type']}",
            "item": {
                "id": clipboard_item["id"],
                "type": clipboard_item["type"],
                "content_type": clipboard_item["content_type"],
                "size": clipboard_item["size"],
                "timestamp": clipboard_item["formatted_time"],
                "preview": clipboard_item["preview"],
                "is_image_preview": clipboard_item.get("is_image_preview", False)
            }
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to add to clipboard: {str(e)}"}
        )

@router.get("/api/clipboard/list", name="clipboard_list")
async def get_clipboard_history():
    """Get clipboard history for current session"""
    global clipboard_history
    
    try:
        # Return sanitized clipboard history (without large data but with image previews)
        history = []
        for item in clipboard_history:
            sanitized_item = {
                "id": item["id"],
                "type": item["type"],
                "content_type": item["content_type"],
                "size": item["size"],
                "timestamp": item["formatted_time"],
                "preview": item["preview"],
                "is_image_preview": item.get("is_image_preview", False)
            }
            
            # Add filename for file items
            if item["type"] == "file":
                sanitized_item["filename"] = item["filename"]
                
            history.append(sanitized_item)
        
        return JSONResponse(content={
            "status": "success",
            "items": history,
            "count": len(history)
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to get clipboard history: {str(e)}"}
        )

@router.get("/api/clipboard/get/{item_id}", name="clipboard_get")
async def get_clipboard_item(item_id: int):
    """Get specific clipboard item by ID"""
    try:
        # Find item by ID
        item = None
        for clipboard_item in clipboard_history:
            if clipboard_item["id"] == item_id:
                item = clipboard_item
                break
        
        if not item:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "msg": "Clipboard item not found"}
            )
        
        if item["type"] == "file":
            # Return file as download
            import io
            file_data = item["data"]
            filename = item["filename"]
            
            # Determine MIME type
            mime_type, _ = guess_type(filename)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            return StreamingResponse(
                io.BytesIO(file_data),
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(len(file_data))
                }
            )
        else:
            # Return text content
            return JSONResponse(content={
                "status": "success",
                "item": {
                    "id": item["id"],
                    "type": item["type"],
                    "content_type": item["content_type"],
                    "data": item["data"],
                    "size": item["size"],
                    "timestamp": item["formatted_time"]
                }
            })
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to get clipboard item: {str(e)}"}
        )

@router.delete("/api/clipboard/clear", name="clipboard_clear")
async def clear_clipboard():
    """Clear all clipboard history"""
    global clipboard_history
    try:
        count = len(clipboard_history)
        clipboard_history.clear()
        
        # Clear persistent storage
        save_clipboard_history()
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"Cleared {count} clipboard items"
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to clear clipboard: {str(e)}"}
        )

@router.delete("/api/clipboard/remove/{item_id}", name="clipboard_remove")
async def remove_clipboard_item(item_id: int):
    """Remove specific clipboard item"""
    global clipboard_history
    try:
        # Find and remove item
        for i, item in enumerate(clipboard_history):
            if item["id"] == item_id:
                removed_item = clipboard_history.pop(i)
                
                # Save to persistent storage
                save_clipboard_history()
                
                return JSONResponse(content={
                    "status": "success",
                    "msg": f"Removed clipboard item: {removed_item.get('filename', 'text content')}"
                })
        
        return JSONResponse(
            status_code=404,
            content={"status": "error", "msg": "Clipboard item not found"}
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to remove clipboard item: {str(e)}"}
        )

@router.get("/api/clipboard", name="clipboard_status")
async def clipboard_status():
    """Get clipboard status and content"""
    try:
        # Try to get clipboard content
        try:
            import pyperclip
            clipboard_content = pyperclip.paste()
            return JSONResponse(content={
                "status": "success",
                "clipboard_available": True,
                "clipboard_content": clipboard_content[:100] + "..." if len(clipboard_content) > 100 else clipboard_content,
                "content_length": len(clipboard_content)
            })
        except ImportError:
            return JSONResponse(content={
                "status": "success", 
                "clipboard_available": False,
                "msg": "pyperclip not available"
            })
        except Exception as e:
            return JSONResponse(content={
                "status": "success",
                "clipboard_available": False,
                "msg": f"Clipboard access failed: {str(e)}"
            })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Clipboard status check failed: {str(e)}"}
        )

@router.post("/api/clipboard", name="clipboard_write")
async def clipboard_write(request: Request):
    """Write to clipboard"""
    try:
        data = await request.json()
        text = data.get("text", "")
        
        try:
            import pyperclip
            pyperclip.copy(text)
            return JSONResponse(content={
                "status": "success",
                "msg": f"Copied {len(text)} characters to clipboard"
            })
        except ImportError:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "msg": "pyperclip not available"}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "msg": f"Failed to copy to clipboard: {str(e)}"}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Clipboard write failed: {str(e)}"}
        )
