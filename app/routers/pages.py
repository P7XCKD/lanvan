
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
from app.routers.files import detect_ios_device, get_file_list
from app.routers.system import get_android_network_info
router = APIRouter()

@router.get("/", response_class=HTMLResponse, name="home") 
async def home(request: Request):
    """
    [TARGET] Universal mDNS Redirect + Main Page Handler with iOS Detection
    Handles lanvan.local access regardless of port/protocol with smart redirects
    """
    host = request.headers.get("host", "").lower()
    user_agent = request.headers.get("user-agent", "")
    
    # [MOBILE] iOS Device Detection
    ios_info = detect_ios_device(user_agent)
    
    # [TARGET] Universal mDNS Redirect Logic for lanvan.local
    if "lanvan.local" in host:
        # Get current server configuration
        actual_port = mdns_manager.actual_port
        actual_protocol = mdns_manager.actual_protocol
        current_port = request.url.port or (80 if request.url.scheme == "http" else 443)
        current_scheme = request.url.scheme
        
        #  iOS Safari Special Handling - Prefer HTTP for better compatibility
        if ios_info['is_mobile_safari'] and current_scheme == "https":
            # For iOS Safari, redirect HTTPS to HTTP for better reliability
            http_port = 5000  # Our HTTP fallback port
            redirect_url = f"http://lanvan.local:{http_port}{request.url.path}"
            if request.url.query:
                redirect_url += f"?{request.url.query}"
            
            print(f" iOS Safari detected - redirecting to HTTP for better compatibility: {redirect_url}")
            return RedirectResponse(url=redirect_url, status_code=302)
        
        #  Standard redirect logic for non-iOS devices
        if current_scheme == "http" and actual_protocol == "https" and not ios_info['is_mobile_safari']:
            # Construct correct HTTPS URL
            if actual_port == 443:
                redirect_url = f"https://lanvan.local{request.url.path}"
            else:
                redirect_url = f"https://lanvan.local:{actual_port}{request.url.path}"
            
            if request.url.query:
                redirect_url += f"?{request.url.query}"
            
            return RedirectResponse(url=redirect_url, status_code=302)
    
    #  Main page logic - direct access, no redirects
    files = get_file_list()
    
    # Add helpful debug info for protocol detection
    protocol = request.url.scheme
    host = request.headers.get("host", "unknown")
    
    # [MOBILE] iOS-specific optimizations for template
    template_context = {
        "request": request,
        "msg": "Lanvan",
        "files": [f["name"] for f in files],
        "debug_info": {
            "protocol": protocol,
            "host": host,
            "port": "5000" if ":5000" in host else "5001" if ":5001" in host else "unknown"
        },
        "show_both_sections": True,
        "default_view": "file",
        "ios_info": ios_info,  # Pass iOS detection info to template
        "is_ios_device": ios_info['is_ios'],
        "is_mobile_safari": ios_info['is_mobile_safari']
    }
    
    # [MOBILE] Log iOS device access for debugging
    if ios_info['is_ios']:
        print(f" iOS device detected: {ios_info['device_type']} - Safari: {ios_info['is_safari']} - Protocol: {protocol} - Host: {host}")
    
    return templates.TemplateResponse("index.html", template_context)

templates = Jinja2Templates(directory="app/templates")

@router.get("/ios-help", response_class=HTMLResponse)
async def ios_help_page(request: Request):
    """iOS Safari troubleshooting and help page"""
    return templates.TemplateResponse("ios-help.html", {"request": request})

@router.get("/loading", response_class=HTMLResponse, name="loading")
async def loading_page(request: Request, redirect: str = "/"):
    """Loading page shown while resources are being prepared"""
    #  Direct loading page access - no redirects
    return templates.TemplateResponse("loading.html", {
        "request": request,
        "redirect_url": redirect
    })

@router.get("/favicon.ico", name="favicon")
async def favicon():
    """Serve favicon.ico from static directory"""
    try:
        from fastapi.responses import FileResponse
        favicon_path = UPLOAD_FOLDER.parent / "static" / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(
                path=str(favicon_path),
                media_type="image/x-icon",
                headers={"Cache-Control": "public, max-age=86400"}  # Cache for 1 day
            )
        else:
            # Return a 204 No Content if favicon doesn't exist (prevents 500 errors)
            return Response(status_code=204)
    except Exception as e:
        # Return 204 instead of 500 to prevent console errors
        return Response(status_code=204)
