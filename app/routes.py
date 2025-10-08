import os
import io
import json
import time
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
from mimetypes import guess_type
from zipfile import ZipFile
import base64

# Android/Termux QR code support with fallbacks
try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    print("⚠️ QR code library not available - installing for Android/Termux...")
    QR_AVAILABLE = False
    try:
        import subprocess
        import sys
        # Try to install qrcode for Android/Termux
        subprocess.check_call([sys.executable, "-m", "pip", "install", "qrcode[pil]"])
        import qrcode
        QR_AVAILABLE = True
        print("✅ QR code library installed successfully")
    except Exception as install_error:
        print(f"❌ Could not install QR code library: {install_error}")
        print("📱 Android/Termux: QR codes will use text fallback")

# WebSocket support with Android/Termux fallback
try:
    from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Query, Form, HTTPException, WebSocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    print("⚠️ WebSocket support not available - installing for Android/Termux...")
    WEBSOCKET_AVAILABLE = False
    try:
        import subprocess
        import sys
        # Try to install WebSocket support for Android/Termux
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn[standard]"])
        from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Query, Form, HTTPException, WebSocket
        WEBSOCKET_AVAILABLE = True
        print("✅ WebSocket support installed successfully")
    except Exception as ws_error:
        print(f"❌ Could not install WebSocket support: {ws_error}")
        print("📱 Android/Termux: Real-time features will use polling fallback")
        from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Query, Form, HTTPException
        # Create dummy WebSocket class to prevent import errors
        class WebSocket:
            pass
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse,
    JSONResponse, Response
)
from fastapi.templating import Jinja2Templates
from app.clipboard_ws import clipboard_ws_manager
from starlette.status import HTTP_302_FOUND, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR

from app.aes_utils import encrypt_session_data, decrypt_session_data
from app.aes_config import AESConfig
from app.http_safe_aes import encrypt_file_http_safe, decrypt_http_safe_file
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
# Import mDNS manager with universal support
try:
    from app.universal_mdns import get_mdns_manager
    # Get the global mDNS manager instance
    def get_current_mdns_manager():
        from app.main import current_mdns_manager
        return current_mdns_manager
    UNIVERSAL_MDNS_AVAILABLE = True
except ImportError:
    # Fallback to simple mDNS
    try:
        from app.simple_mdns import mdns_manager
        def get_current_mdns_manager():
            return mdns_manager
        UNIVERSAL_MDNS_AVAILABLE = False
    except ImportError:
        def get_current_mdns_manager():
            return None
        UNIVERSAL_MDNS_AVAILABLE = False

# Android/Termux network utilities
def get_android_network_info():
    """Get network information optimized for Android/Termux"""
    try:
        import socket
        # Android-specific network detection
        hostname = socket.gethostname()
        
        # Try multiple methods to get correct IP on Android
        methods = [
            lambda: socket.gethostbyname(hostname),
            lambda: get_android_wifi_ip(),
            lambda: get_android_cellular_ip(),
            lambda: "192.168.1.100"  # Fallback
        ]
        
        for method in methods:
            try:
                ip = method()
                if ip and not ip.startswith('127.') and ip != '192.0.0.4':
                    return ip, hostname
            except:
                continue
                
        return "192.168.1.100", hostname  # Ultimate fallback
    except Exception as e:
        print(f"📱 Android network detection error: {e}")
        return "192.168.1.100", "android-device"

def get_android_wifi_ip():
    """Get WiFi IP on Android using ifconfig parsing"""
    try:
        import subprocess
        result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Parse IP from route output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'src' in line:
                    parts = line.split()
                    src_idx = parts.index('src')
                    if src_idx + 1 < len(parts):
                        return parts[src_idx + 1]
    except:
        pass
    return None

def get_android_cellular_ip():
    """Get cellular IP on Android"""
    try:
        import socket
        # Connect to external service to determine our IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except:
        return None

# Android/Termux network utilities
def get_android_network_info():
    """Get network information optimized for Android/Termux"""
    try:
        import socket
        # Android-specific network detection
        hostname = socket.gethostname()
        
        # Try multiple methods to get correct IP on Android
        methods = [
            lambda: socket.gethostbyname(hostname),
            lambda: get_android_wifi_ip(),
            lambda: get_android_cellular_ip(),
            lambda: "192.168.1.100"  # Fallback
        ]
        
        for method in methods:
            try:
                ip = method()
                if ip and not ip.startswith('127.') and ip != '192.0.0.4':
                    return ip, hostname
            except:
                continue
                
        return "192.168.1.100", hostname  # Ultimate fallback
    except Exception as e:
        print(f"📱 Android network detection error: {e}")
        return "192.168.1.100", "android-device"

def get_android_wifi_ip():
    """Get WiFi IP on Android using ifconfig parsing"""
    try:
        import subprocess
        result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Parse IP from route output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'src' in line:
                    parts = line.split()
                    src_idx = parts.index('src')
                    if src_idx + 1 < len(parts):
                        return parts[src_idx + 1]
    except:
        pass
    return None

def get_android_cellular_ip():
    """Get cellular IP on Android"""
    try:
        import socket
        # Connect to external service to determine our IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except:
        return None
from app.streaming_assembly import (
    initialize_streaming_assembly, 
    get_streaming_assembler,
    shutdown_streaming_assembly
)

# === Setup ===
router = APIRouter()
UPLOAD_FOLDER = Path("app/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# === iOS Device Detection ===
def detect_ios_device(user_agent: str) -> dict:
    """Detect iOS devices and Safari browser"""
    user_agent_lower = user_agent.lower()
    is_ios = any(ios_indicator in user_agent_lower for ios_indicator in [
        'iphone', 'ipad', 'ipod', 'ios'
    ])
    is_safari = 'safari' in user_agent_lower and 'chrome' not in user_agent_lower
    is_mobile_safari = is_ios and is_safari
    
    device_type = 'unknown'
    if 'iphone' in user_agent_lower:
        device_type = 'iPhone'
    elif 'ipad' in user_agent_lower:
        device_type = 'iPad'
    elif 'ipod' in user_agent_lower:
        device_type = 'iPod'
    
    return {
        'is_ios': is_ios,
        'is_safari': is_safari,
        'is_mobile_safari': is_mobile_safari,
        'device_type': device_type,
        'user_agent': user_agent
    }

# === Universal mDNS Redirect Handler ===
@router.get("/", response_class=HTMLResponse, name="home") 
async def home(request: Request):
    """
    🎯 Universal mDNS Redirect + Main Page Handler with iOS Detection
    Handles lanvan.local access regardless of port/protocol with smart redirects
    """
    host = request.headers.get("host", "").lower()
    user_agent = request.headers.get("user-agent", "")
    
    # 📱 iOS Device Detection
    ios_info = detect_ios_device(user_agent)
    
    # 🎯 Universal mDNS Redirect Logic for lanvan.local
    if "lanvan.local" in host:
        # Get current server configuration
        current_mdns = get_current_mdns_manager()
        if current_mdns and hasattr(current_mdns, 'actual_port'):
            actual_port = current_mdns.actual_port
            actual_protocol = current_mdns.actual_protocol
        else:
            # Fallback values
            actual_port = int(os.environ.get('PORT', 5000))
            actual_protocol = "http"
        current_port = request.url.port or (80 if request.url.scheme == "http" else 443)
        current_scheme = request.url.scheme
        
        # � iOS Safari Special Handling - Prefer HTTP for better compatibility
        if ios_info['is_mobile_safari'] and current_scheme == "https":
            # For iOS Safari, redirect HTTPS to HTTP for better reliability
            http_port = 5000  # Our HTTP fallback port
            redirect_url = f"http://lanvan.local:{http_port}{request.url.path}"
            if request.url.query:
                redirect_url += f"?{request.url.query}"
            
            print(f"🍎 iOS Safari detected - redirecting to HTTP for better compatibility: {redirect_url}")
            return RedirectResponse(url=redirect_url, status_code=302)
        
        # 🔀 Standard redirect logic for non-iOS devices
        if current_scheme == "http" and actual_protocol == "https" and not ios_info['is_mobile_safari']:
            # Construct correct HTTPS URL
            if actual_port == 443:
                redirect_url = f"https://lanvan.local{request.url.path}"
            else:
                redirect_url = f"https://lanvan.local:{actual_port}{request.url.path}"
            
            if request.url.query:
                redirect_url += f"?{request.url.query}"
            
            return RedirectResponse(url=redirect_url, status_code=302)
    
    # 🏠 Main page logic - direct access, no redirects
    files = get_file_list()
    
    # Add helpful debug info for protocol detection
    protocol = request.url.scheme
    host = request.headers.get("host", "unknown")
    
    # 📱 iOS-specific optimizations for template
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
    
    # 📱 Log iOS device access for debugging
    if ios_info['is_ios']:
        print(f"🍎 iOS device detected: {ios_info['device_type']} - Safari: {ios_info['is_safari']} - Protocol: {protocol} - Host: {host}")
    
    return templates.TemplateResponse("index.html", template_context)

# === Chunked Upload Setup ===
# Move temp_chunks to project root to keep it separate from uploaded files
TEMP_CHUNKS_FOLDER = Path("temp_chunks")
TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)

# === Concurrent Upload Configuration ===
MAX_CONCURRENT_UPLOADS = 5  # Maximum parallel uploads per session

# === Streaming Assembly Setup ===
# Initialize streaming assembly system on first use (lazy initialization)
_streaming_initialized = False

def ensure_streaming_initialized():
    """Ensure streaming assembly is initialized"""
    global _streaming_initialized
    if not _streaming_initialized:
        initialize_streaming_assembly(TEMP_CHUNKS_FOLDER, UPLOAD_FOLDER)
        _streaming_initialized = True

def cleanup_orphaned_temp_files():
    """
    🧹 Clean up orphaned .tmp files on startup (from interrupted uploads)
    """
    try:
        temp_files = list(UPLOAD_FOLDER.glob("*.tmp"))
        if temp_files:
            print(f"🧹 Cleaning up {len(temp_files)} orphaned .tmp files...")
            for temp_file in temp_files:
                try:
                    temp_file.unlink()
                    print(f"[CLEANUP] Removed: {temp_file.name}")
                except Exception as e:
                    print(f"[WARNING] Failed to remove {temp_file.name}: {e}")
        else:
            print(f"[OK] No orphaned .tmp files found")
    except Exception as e:
        print(f"[ERROR] Error during temp file cleanup: {e}")

# Clean up orphaned temp files on startup
cleanup_orphaned_temp_files()

# Templates - keep local for routes that need it
templates = Jinja2Templates(directory="app/templates")

# === iOS Compatibility Route ===
@router.get("/ios-check", response_class=JSONResponse)
async def ios_compatibility_check(request: Request):
    """iOS device compatibility check endpoint"""
    user_agent = request.headers.get("user-agent", "")
    ios_info = detect_ios_device(user_agent)
    
    # Get server info
    host = request.headers.get("host", "")
    protocol = request.url.scheme
    
    # Get local IP for direct access suggestions
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except:
        local_ip = "127.0.0.1"
    
    response_data = {
        "is_ios": ios_info['is_ios'],
        "device_type": ios_info['device_type'],
        "is_safari": ios_info['is_safari'],
        "current_protocol": protocol,
        "current_host": host,
        "suggestions": []
    }
    
    if ios_info['is_ios']:
        if protocol == "https":
            response_data["suggestions"].append({
                "type": "protocol_switch",
                "message": "For better iOS compatibility, try HTTP instead",
                "url": f"http://{local_ip}:5000",
                "priority": "high"
            })
        
        if "lanvan.local" not in host:
            response_data["suggestions"].append({
                "type": "direct_ip",
                "message": "Try direct IP access if .local domains don't work",
                "url": f"http://{local_ip}:5000",
                "priority": "medium"
            })
    
    return JSONResponse(response_data)

# === Server Status Endpoint ===
@router.get("/api/server-status", response_class=JSONResponse)
async def server_status(request: Request):
    """Server status endpoint for loading page and diagnostics"""
    user_agent = request.headers.get("user-agent", "")
    ios_info = detect_ios_device(user_agent)
    
    # Check if resources are ready (similar to main.py logic)
    import time
    server_start_time = getattr(server_status, 'start_time', time.time())
    resources_ready = (time.time() - server_start_time) > 3  # 3 second grace period
    
    # Get server configuration
    protocol = request.url.scheme
    host = request.headers.get("host", "")
    
    status_data = {
        "status": "online",
        "timestamp": time.time(),
        "resources_ready": resources_ready,
        "server_info": {
            "protocol": protocol,
            "host": host,
            "version": "1.0.0",
            "features": ["file_transfer", "clipboard", "real_time_sync"]
        },
        "ios_optimizations": {
            "detected": ios_info['is_ios'],
            "safari": ios_info['is_safari'],
            "mobile_safari": ios_info['is_mobile_safari'],
            "device_type": ios_info['device_type']
        }
    }
    
    # Add iOS-specific recommendations
    if ios_info['is_ios']:
        status_data["ios_recommendations"] = []
        
        if protocol == "https":
            status_data["ios_recommendations"].append({
                "type": "protocol",
                "message": "Consider using HTTP for better iOS compatibility",
                "action": "switch_to_http"
            })
        
        if ".local" in host:
            status_data["ios_recommendations"].append({
                "type": "hostname", 
                "message": "If .local domains don't work, try direct IP",
                "action": "use_direct_ip"
            })
    
    return JSONResponse(status_data)

# Initialize server start time
server_status.start_time = time.time()

# === iOS Help Page ===
@router.get("/ios-help", response_class=HTMLResponse)
async def ios_help_page(request: Request):
    """iOS Safari troubleshooting and help page"""
    return templates.TemplateResponse("ios-help.html", {"request": request})

# === 🔍 CONSTANTS ===
MAX_CONCURRENT_UPLOADS = 5  # Maximum parallel uploads per session

# === Utility Functions ===
def format_size(size_bytes):
    """Format bytes to human readable string"""
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def should_ignore_file(filename: str) -> bool:
    """
    Check if a file should be ignored based on qt.py patterns from .gitignore
    🚫 Filters out qt.py generated test files from file listings
    """
    qt_patterns = [
        # Direct qt.py test file patterns
        "quick_test", "test_output", "temp_test", "debug_test",
        # Qt.py generated logs and debug files  
        "qt_test_", "qt_debug_", "qt_output_", "test_results_", "test_log_",
        # Any files that look like qt.py test files
        "test_file_"
    ]
    
    # Check if filename matches any qt.py test patterns
    filename_lower = filename.lower()
    for pattern in qt_patterns:
        if pattern in filename_lower:
            return True
    
    # Additional specific extensions for qt.py test files
    if filename_lower.endswith(('.tmp', '.log')) and any(p in filename_lower for p in qt_patterns):
        return True
        
    return False

def get_file_list():
    return sorted([
        {
            "name": f.name,
            "size": format_size(f.stat().st_size),
            "mtime": f.stat().st_mtime
        }
        for f in UPLOAD_FOLDER.iterdir() 
        if f.is_file() and not f.name.endswith('.tmp') and not should_ignore_file(f.name)  # 🚫 Filter out temporary files and qt.py test files
    ], key=lambda x: x["mtime"], reverse=True)

async def get_file_list_async():
    """
    🚀 Async file list with yielding for large directories
    🚫 RACE CONDITION FIX: Filter out .tmp files to prevent downloading partial uploads
    🚫 Qt.py FILTER: Hide qt.py generated test files from listings
    """
    files = []
    file_count = 0
    
    for f in UPLOAD_FOLDER.iterdir():
        if f.is_file() and not f.name.endswith('.tmp') and not should_ignore_file(f.name):  # 🚫 Filter out temporary files and qt.py test files
            files.append({
                "name": f.name,
                "size": format_size(f.stat().st_size),
                "mtime": f.stat().st_mtime
            })
            file_count += 1
            
            # Yield every 50 files to prevent blocking on large directories
            if file_count % 50 == 0:
                await asyncio.sleep(0.01)  # OPTIMIZED: 10ms instead of 1ms
    
    return sorted(files, key=lambda x: x["mtime"], reverse=True)

def get_unique_filename(directory: Path, filename: str) -> str:
    base = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    new_name = filename
    while (directory / new_name).exists():
        new_name = f"{base}_{counter}{ext}"
        counter += 1
    return new_name

async def save_upload_file_async(upload_file: UploadFile, destination: Path, encrypt=False):
    """
    🔄 ASYNC Universal Streaming Upload Handler - Non-blocking optimized for ALL platforms
    🔒 RACE CONDITION FIX: Upload to .tmp file first, then atomically move to final name
    Processes files in chunks asynchronously to avoid memory exhaustion and server blocking
    """
    import os
    import hashlib
    import gc
    import asyncio
    from .android_optimizer import optimize_for_upload, get_adaptive_chunk_size, should_run_gc, universal_optimizer
    
    # 🚀 TEMPORARY FILE STRATEGY: Upload to .tmp extension first
    temp_destination = destination.with_suffix(destination.suffix + '.tmp')
    print(f"🔄 Uploading to temporary file: {temp_destination.name}")
    
    # 📱 Platform Detection (but optimizations apply to ALL)
    is_android = ("ANDROID_STORAGE" in os.environ or 
                 os.path.exists("/data/data/com.termux") or 
                 "TERMUX_VERSION" in os.environ)
    
    is_windows = os.name == 'nt'
    is_linux = os.name == 'posix' and not is_android
    
    platform_name = "Android/Termux" if is_android else "Windows" if is_windows else "Linux/Unix"
    
    # 📊 ASYNC File size estimation for progress tracking (NON-BLOCKING)
    await asyncio.to_thread(upload_file.file.seek, 0, 2)  # Seek to end - ASYNC
    file_size = await asyncio.to_thread(upload_file.file.tell)  # Tell position - ASYNC  
    await asyncio.to_thread(upload_file.file.seek, 0)  # Reset to beginning - ASYNC
    
    # � Apply optimizations for large files on ALL platforms
    if file_size > 50 * 1024 * 1024:  # Files > 50MB
        print(f"🔄 Large file detected ({file_size//1024//1024}MB) - enabling streaming optimizations")
        
        # Android-specific feasibility check (but streaming works everywhere)
        if is_android:
            feasibility = optimize_for_upload(file_size)
            if feasibility.get('warnings'):
                for warning in feasibility['warnings']:
                    print(f"⚠️ {warning}")
            if feasibility.get('recommendations'):
                print(f"💡 Android recommendations:")
                for rec in feasibility['recommendations']:
                    print(f"   • {rec}")
        else:
            # General recommendations for PC/Linux/Mac
            feasibility = optimize_for_upload(file_size)
            if feasibility.get('warnings'):
                for warning in feasibility['warnings']:
                    print(f"⚠️ {warning}")
            if feasibility.get('recommendations'):
                print(f"💡 {platform_name} recommendations:")
                for rec in feasibility['recommendations']:
                    print(f"   • {rec}")
    
    # 🎯 Universal adaptive chunk sizing optimized for each platform
    CHUNK_SIZE = universal_optimizer.get_adaptive_chunk_size(file_size)
    print(f"🎯 {platform_name} - chunk size: {CHUNK_SIZE//1024}KB")
    
    print(f"🔄 ASYNC Upload: {destination.name} ({file_size:,} bytes)")
    
    if encrypt:
        # 🔒 For now, fall back to original method for encrypted files
        # TODO: Implement true streaming encryption in future update
        print(f"🔒 Using existing encryption method (will be optimized in future)")
        try:
            data = await asyncio.to_thread(upload_file.file.read)
            
            # Import streaming encryption functions
            from .aes_utils import encrypt_file_stream
            
            # Add file integrity validation for encrypted files
            original_hash = hashlib.sha256(data).hexdigest()
            print(f"🔒 Original file hash: {original_hash}")
            
            # Use memory-efficient streaming encryption
            encrypted_data, metadata = encrypt_file_stream(data, chunk_size=CHUNK_SIZE)
            
            # Enhanced metadata with integrity information
            metadata['original_hash'] = original_hash
            metadata['original_size'] = str(len(data))
            metadata['encrypted_size'] = str(len(encrypted_data))
            
            # Write encrypted data to file using async I/O
            import aiofiles
            async with aiofiles.open(temp_destination, 'wb') as f:
                await f.write(encrypted_data)
            
            # 🎯 ATOMIC MOVE: Move encrypted file from .tmp to final destination
            import shutil
            max_retries = 3 if is_windows else 1
            retry_delay = 0.3 if is_windows else 0.1
            
            for attempt in range(max_retries):
                try:
                    print(f"🔄 Moving encrypted {temp_destination.name} → {destination.name} (attempt {attempt + 1})")
                    
                    if is_windows:
                        # Use shutil.move for better Windows compatibility
                        await asyncio.to_thread(shutil.move, str(temp_destination), str(destination))
                    else:
                        temp_destination.rename(destination)
                    
                    print(f"✅ Encrypted file atomically moved to final destination: {destination.name}")
                    break
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Encrypted move attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                    else:
                        # Final attempt failed, clean up and raise
                        if temp_destination.exists():
                            try:
                                temp_destination.unlink()
                            except:
                                pass
                        print(f"❌ Failed to move encrypted temp file after {max_retries} attempts: {e}")
                        raise Exception(f"Failed to finalize encrypted upload after {max_retries} attempts: {e}")
            
            # Yield control periodically - OPTIMIZED: 10ms instead of 1ms for better performance
            await asyncio.sleep(0.01)
            
        except Exception as e:
            # Clean up encrypted temp file
            if temp_destination.exists():
                temp_destination.unlink()
            print(f"❌ Encryption error: {e}")
            raise
    else:
        # 📦 Async Streaming upload without encryption
        try:
            import aiofiles
            bytes_written = 0
            hash_calculator = hashlib.sha256()
            processed_chunks = 0  # Initialize chunk counter
            
            # Open file, write data, and explicitly close before moving
            async with aiofiles.open(temp_destination, 'wb') as f:
                while True:
                    # Read chunk asynchronously
                    chunk = await asyncio.to_thread(upload_file.file.read, CHUNK_SIZE)
                    if not chunk:
                        break
                    
                    # Write chunk asynchronously
                    await f.write(chunk)
                    await f.flush()  # Ensure data is written
                    
                    bytes_written += len(chunk)
                    hash_calculator.update(chunk)
                    processed_chunks += 1
                    
                    # Yield control every 5 chunks to prevent blocking - OPTIMIZED: Less frequent yielding
                    if processed_chunks % 5 == 0:
                        await asyncio.sleep(0.01)  # OPTIMIZED: 10ms instead of 1ms
                    
                    # Progress for large files (reduce spam)
                    if bytes_written > 10 * 1024 * 1024 and bytes_written % (20 * 1024 * 1024) == 0:
                        print(f"📦 Progress: {bytes_written // 1024 // 1024}MB")
                        
                        # OPTIMIZED: Strategic memory management - only GC for very large files
                        if should_run_gc():
                            universal_optimizer.memory_cleanup(force=False)
                            await asyncio.sleep(0.01)  # Brief pause for GC
            
            # File handle is now closed, add extra delay for Windows
            print(f"✅ Upload to temp file completed: {temp_destination.name} ({bytes_written:,} bytes)")
            if is_windows:
                await asyncio.sleep(0.2)  # Extra delay for Windows to release file handle
                
            # 🎯 ATOMIC MOVE: Move from .tmp to final destination to prevent race conditions
            import shutil
            import time
            max_retries = 3 if is_windows else 1
            retry_delay = 0.3 if is_windows else 0.1
            
            for attempt in range(max_retries):
                try:
                    print(f"🔄 Moving {temp_destination.name} → {destination.name} (attempt {attempt + 1})")
                    
                    if is_windows:
                        # Use shutil.move for better Windows compatibility
                        await asyncio.to_thread(shutil.move, str(temp_destination), str(destination))
                    else:
                        temp_destination.rename(destination)
                    
                    print(f"✅ File atomically moved to final destination: {destination.name}")
                    break
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️ Move attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                    else:
                        # Final attempt failed, clean up and raise
                        if temp_destination.exists():
                            try:
                                temp_destination.unlink()
                            except:
                                pass
                        print(f"❌ Failed to move temp file after {max_retries} attempts: {e}")
                        raise Exception(f"Failed to finalize upload after {max_retries} attempts: {e}")
        
        except Exception as e:
            # Clean up partial temp file
            if temp_destination.exists():
                temp_destination.unlink()
            print(f"❌ ASYNC Upload error: {e}")
            raise
        finally:
            # 🧹 Universal cleanup (applies to ALL platforms)
            if hasattr(universal_optimizer, 'upload_active'):
                universal_optimizer.upload_active = False
            universal_optimizer.memory_cleanup(force=True)
            print(f"🔄 Universal async cleanup completed")

async def scan_file_async(path: Path):
    """
    🚀 Truly non-blocking async file scanning with frequent yielding
    """
    print(f"🧪 Scanning file in background: {path}")
    
    # OPTIMIZED: Yield control with better interval
    await asyncio.sleep(0.01)  # 10ms instead of 1ms
    
    try:
        # Simulate processing with frequent yielding for responsiveness
        # In real implementation, this would do virus scanning, checksums, etc.
        file_size = path.stat().st_size
        
        # For large files, break processing into smaller chunks with yielding
        if file_size > 100 * 1024 * 1024:  # >100MB
            print(f"🔍 Large file processing with yielding: {path.name} ({file_size // 1024 // 1024}MB)")
            
            # Simulate chunked processing with frequent yielding
            chunk_count = max(1, file_size // (50 * 1024 * 1024))  # 50MB chunks
            for i in range(chunk_count):
                # Yield every processing chunk to keep server responsive
                await asyncio.sleep(0.01)  # 10ms yield per chunk
                
                # Simulate some processing work
                if i % 10 == 0:  # Progress every 10 chunks
                    progress = (i + 1) / chunk_count * 100
                    print(f"🔄 Processing {path.name}: {progress:.1f}% complete")
        else:
            # Small files process quickly with minimal yielding - OPTIMIZED
            await asyncio.sleep(0.01)  # 10ms instead of 1ms
            
        print(f"✅ File scan completed: {path.name}")
        
    except Exception as e:
        print(f"❌ File scan error: {path.name} - {e}")
        # Don't let scanning errors affect the main upload flow
    
    # Final yield to ensure responsiveness
    await asyncio.sleep(0.001)

def scan_file(path: Path):
    """
    🔄 Legacy sync wrapper - creates async task for background processing
    """
    try:
        # Check if we have a running event loop before creating task
        try:
            loop = asyncio.get_running_loop()
            # Create async task with proper error handling for background processing
            task = asyncio.create_task(scan_file_async(path))
            # Add done callback to handle any exceptions
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        except RuntimeError:
            # No event loop running - skip background scan
            pass
    except Exception as e:
        # Suppress error messages during testing
        pass

# === Routes ===

# 🛡️ HTTP-Safe AES Routes
@router.post("/encrypt_http_safe", name="encrypt_http_safe")
async def encrypt_http_safe(
    request: Request,
    file: UploadFile = File(...),
    http_safe: bool = Form(True)
):
    """Encrypt a file with HTTP-Safe AES protection"""
    temp_input_path = None
    encrypted_path = None
    
    try:
        # Save uploaded file temporarily
        temp_input_path = UPLOAD_FOLDER / f"temp_input_{int(time.time())}_{file.filename}"
        
        with open(temp_input_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        # Encrypt with HTTP-Safe protection
        encrypted_path, metadata = encrypt_file_http_safe(
            input_path=str(temp_input_path),
            original_filename=file.filename or "unknown_file"
        )
        
        # Read encrypted content
        with open(encrypted_path, 'rb') as f:
            encrypted_content = f.read()
        
        # Clean up input file
        temp_input_path.unlink(missing_ok=True)
        
        # Extract obfuscated filename from path
        obfuscated_filename = os.path.basename(encrypted_path)
        
        # Save encrypted file temporarily for download
        temp_filename = f"temp_encrypted_{int(time.time())}_{obfuscated_filename}"
        temp_path = UPLOAD_FOLDER / temp_filename
        
        with open(temp_path, 'wb') as f:
            f.write(encrypted_content)
        
        # Clean up original encrypted file
        os.unlink(encrypted_path)
        
        return JSONResponse({
            "status": "success",
            "temp_filename": temp_filename,
            "obfuscated_filename": obfuscated_filename,
            "metadata": metadata,
            "encrypted_size": len(encrypted_content)
        })
        
    except Exception as e:
        # Clean up any temporary files - safe cleanup
        try:
            if temp_input_path and temp_input_path.exists():
                temp_input_path.unlink(missing_ok=True)
        except:
            pass
        try:
            if encrypted_path and os.path.exists(encrypted_path):
                os.unlink(encrypted_path)
        except:
            pass
        
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.get("/download_temp/{filename}", name="download_temp")
async def download_temp_file(filename: str):
    """Download temporary encrypted file"""
    try:
        file_path = UPLOAD_FOLDER / filename
        if not file_path.exists():
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "File not found"}
            )
        
        def iter_file():
            with open(file_path, 'rb') as f:
                yield from f
        
        # Delete temp file after download
        background_tasks = BackgroundTasks()
        background_tasks.add_task(lambda: file_path.unlink(missing_ok=True))
        
        return StreamingResponse(
            iter_file(),
            media_type='application/octet-stream',
            headers={"Content-Disposition": f"attachment; filename={filename}"},
            background=background_tasks
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.post("/generate_decoy", name="generate_decoy")
async def generate_decoy_traffic(request: Request):
    """Generate decoy traffic for HTTP-Safe mode"""
    try:
        data = await request.json()
        size = data.get('size', 10000)
        
        # Generate random decoy data
        decoy_data = os.urandom(size)
        
        # Simulate processing time
        await asyncio.sleep(0.1)
        
        return JSONResponse({
            "status": "success",
            "decoy_size": len(decoy_data)
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@router.get("/loading", response_class=HTMLResponse, name="loading")
async def loading_page(request: Request, redirect: str = "/"):
    """Loading page shown while resources are being prepared"""
    # 🏠 Direct loading page access - no redirects
    return templates.TemplateResponse("loading.html", {
        "request": request,
        "redirect_url": redirect
    })

@router.get("/api/files", name="api_files")
async def api_files():
    """API endpoint to get current file list as JSON"""
    try:
        files = get_file_list()
        return JSONResponse(content={
            "status": "success",
            "files": [f["name"] for f in files],
            "count": len(files)
        })
    except Exception as e:
        print(f"❌ Error getting file list: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to get file list: {str(e)}"}
        )

@router.get("/api/platform-status", name="platform_status")
async def platform_status():
    """API endpoint to get universal platform optimization status"""
    try:
        from .android_optimizer import UniversalOptimizer
        
        optimizer = UniversalOptimizer()
        info = optimizer.get_platform_info()
        
        return JSONResponse(content={
            "status": "success",
            "platform_info": info
        })
    except Exception as e:
        return JSONResponse(content={
            "status": "error",
            "msg": str(e),
            "platform_info": {"platform": "unknown"}
        })

@router.post("/upload", name="upload_files")
async def upload_files(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    encrypt: bool = Query(False, description="Encrypt files with AES-256 if true")
):
    """Main file upload endpoint - handles multiple files with optional encryption"""
    if not files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No files uploaded"
        })

    # Protocol detection
    is_https = request.url.scheme == "https"
    protocol = "HTTPS" if is_https else "HTTP"
    
    try:
        # Use concurrent upload manager for multiple files
        try:
            from .concurrent_upload_manager import ConcurrentUploadManager
        except ImportError:
            from concurrent_upload_manager import ConcurrentUploadManager
        upload_manager = ConcurrentUploadManager()
        
        # Create destinations for uploaded files
        destinations = []
        for file in files:
            if file.filename:
                file_path = UPLOAD_FOLDER / file.filename
                # Ensure unique filename
                counter = 1
                original_path = file_path
                while file_path.exists():
                    stem = original_path.stem
                    suffix = original_path.suffix
                    file_path = UPLOAD_FOLDER / f"{stem}_{counter}{suffix}"
                    counter += 1
                destinations.append(file_path)
            else:
                destinations.append(UPLOAD_FOLDER / "unnamed_file")
        
        # Process uploads
        results = await upload_manager.upload_files_concurrently(
            files=files,
            destinations=destinations,
            encrypt=encrypt
        )
        
        # Process results (concurrent manager returns list of results)
        successful_uploads = []
        failed_uploads = []
        
        for result in results:
            if result.get("success", False):
                successful_uploads.append(result.get("filename", "unknown"))
            else:
                failed_uploads.append(result.get("error", "Unknown error"))
        
        if successful_uploads:
            return JSONResponse(content={
                "status": "success",
                "msg": f"{len(successful_uploads)} file(s) uploaded via {protocol}",
                "files": successful_uploads,
                "protocol": protocol,
                "total_files_processed": len(files),
                "files_uploaded": len(successful_uploads),
                "files_skipped": len(failed_uploads)
            })
        else:
            return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content={
                "status": "error",
                "msg": f"All uploads failed: {'; '.join(failed_uploads[:3])}",
                "protocol": protocol
            })
            
    except ImportError:
        # Fallback to basic upload if concurrent manager fails
        uploaded_files = []
        
        for file in files:
            if file.filename:
                # Basic file save
                file_path = UPLOAD_FOLDER / file.filename
                
                # Ensure unique filename
                counter = 1
                original_path = file_path
                while file_path.exists():
                    stem = original_path.stem
                    suffix = original_path.suffix
                    file_path = UPLOAD_FOLDER / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                # Save file
                content = await file.read()
                file_path.write_bytes(content)
                uploaded_files.append(file_path.name)
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"{len(uploaded_files)} file(s) uploaded via {protocol} (basic mode)",
            "files": uploaded_files,
            "protocol": protocol,
            "total_files_processed": len(files),
            "files_uploaded": len(uploaded_files),
            "files_skipped": 0
        })
        
    except Exception as e:
        return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content={
            "status": "error",
            "msg": f"Upload failed: {str(e)}",
            "protocol": protocol
        })

@router.post("/upload-auto", name="upload_auto_file")
async def upload_auto_file(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    encrypt: bool = Query(False, description="Encrypt files with AES-256 if true")
):
    if not files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No files uploaded"
        })

    # 🔐 Protocol detection
    is_https = request.url.scheme == "https"
    
    # � ULTRA-FAST VALIDATION: Start uploads immediately with lightweight validation
    is_valid, error_messages, validated_files, security_warnings = await validate_upload_files_enhanced_fast(files, encrypt, is_https)
    if not is_valid:
        # 🚨 LOG VALIDATION FAILURES for debugging
        print(f"🚫 File validation failed:")
        for i, file in enumerate(files):
            file_ext = Path(file.filename or "unknown").suffix.lower()
            print(f"   File {i+1}: {file.filename} ({file_ext}) - Size: {getattr(file, 'size', 'unknown')}")
        for error in error_messages:
            print(f"   ❌ {error}")
        
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error", 
            "msg": "; ".join(error_messages),
            "security_blocked": True
        })
    
    # ✅ LOG SUCCESSFUL VALIDATION with file details
    print(f"✅ File validation passed for {len(files)} files:")
    for i, file in enumerate(files):
        file_ext = Path(file.filename or "unknown").suffix.lower()
        validated_file = validated_files[i] if i < len(validated_files) else {}
        print(f"   File {i+1}: {file.filename} ({file_ext}) -> {validated_file.get('sanitized_name', 'unknown')}")
        if file_ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
            print(f"   🎥 Video file detected and approved!")
    
    # 🚨 Log security warnings if any
    if security_warnings:
        print(f"⚠️ Security warnings for upload: {'; '.join(security_warnings)}")

    # 🚫 Enforce encryption restrictions using centralized config
    if encrypt:
        validation = AESConfig.validate_file_for_aes(0, is_https)  # Size will be checked per file
        if not validation['valid'] and 'HTTPS' in validation['error']:
            return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
                "status": "error",
                "msg": validation['error']
            })

    # 🚀 CONCURRENT PROCESSING: Upload all files simultaneously with adaptive optimization
    from .concurrent_upload_manager import upload_multiple_files_concurrent
    
    uploaded = []
    
    print(f"🔍 Processing {len(files)} files for concurrent upload...")

    # 🚀 CONCURRENT PREPARATION: Prepare all file destinations simultaneously
    async def prepare_file_for_upload(i: int, file: UploadFile) -> Dict[str, Any]:
        """Prepare a single file for upload concurrently"""
        try:
            print(f"📁 Preparing file {i+1}/{len(files)}: {file.filename}")
            
            if not file.filename:
                return {"error": f"File {i+1}: No filename"}

            # Use validated filename
            validated_file = validated_files[i] if i < len(validated_files) else None
            if not validated_file:
                return {"error": f"File {i+1}: Validation failed"}
                
            filename = validated_file['sanitized_name']
            file_size = validated_file['size']
            print(f"📋 File {i+1} details: {filename} ({file_size} bytes)")

            # Double-check with existing validation (defense in depth)
            if not is_allowed_file(filename):
                return {"error": f"File {i+1}: File type not allowed"}

            # Check size using centralized AES config
            if encrypt:
                validation = AESConfig.validate_file_for_aes(file_size, is_https)
                if not validation['valid']:
                    return {"error": f"File {i+1} failed AES validation: {validation['error']}"}

            save_name = filename + ".enc" if encrypt else filename
            filepath = UPLOAD_FOLDER / get_unique_filename(UPLOAD_FOLDER, save_name)

            print(f"💾 Will save file {i+1} as: {filepath.name}")
            
            return {
                "success": True,
                "file": file,
                "destination": filepath,
                "file_info": {
                    'original_name': file.filename,
                    'save_name': save_name,
                    'filepath': filepath,
                    'size': file_size
                }
            }
            
        except Exception as e:
            return {"error": f"File {i+1}: Preparation failed - {str(e)}"}
    
    # 🚀 PREPARE ALL FILES CONCURRENTLY
    print(f"� Starting concurrent preparation of {len(files)} files...")
    preparation_tasks = [prepare_file_for_upload(i, file) for i, file in enumerate(files)]
    preparation_results = await asyncio.gather(*preparation_tasks, return_exceptions=True)
    
    # Process preparation results
    destinations = []
    valid_files = []
    file_info = []
    
    for i, result in enumerate(preparation_results):
        if isinstance(result, Exception):
            print(f"❌ File {i+1} preparation exception: {str(result)}")
        elif isinstance(result, dict) and "error" in result:
            print(f"❌ {result['error']}")
        elif isinstance(result, dict) and "success" in result:
            destinations.append(result["destination"])
            valid_files.append(result["file"])
            file_info.append(result["file_info"])
            print(f"✅ File {i+1} prepared successfully")
    
    if not valid_files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No valid files to process"
        })
    
    # 🚀 Execute direct uploads with proper file handling
    print(f"🚀 Starting direct upload of {len(valid_files)} files...")
    
    upload_results = []
    
    # Process each file directly
    for i, file in enumerate(valid_files):
        try:
            # Get the prepared destination and info
            destination = destinations[i]
            info = file_info[i]
            
            print(f"📤 Processing file {i+1}/{len(valid_files)}: {info['original_name']}")
            
            # Read file content
            content = await file.read()
            await file.seek(0)  # Reset file pointer for any subsequent operations
            
            # Write file to destination first
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, 'wb') as f:
                f.write(content)
            
            # Handle encryption if needed (encrypt in place)
            if encrypt:
                try:
                    from .http_safe_aes import encrypt_file_http_safe
                    encrypted_path, metadata = encrypt_file_http_safe(str(destination), info['original_name'])
                    print(f"🔐 File {i+1} encrypted successfully")
                    # Update destination to the encrypted file
                    destination = Path(encrypted_path)
                except Exception as e:
                    print(f"❌ Encryption failed for file {i+1}: {e}")
                    # Clean up original file if encryption failed
                    if destination.exists():
                        destination.unlink()
                    upload_results.append({
                        'success': False,
                        'error': f"Encryption failed: {str(e)}",
                        'filename': info['original_name']
                    })
                    continue
            
            # Add to results
            upload_results.append({
                'success': True,
                'destination': str(destination),
                'filename': info['original_name']
            })
            
            print(f"✅ File {i+1} uploaded successfully: {destination.name}")
            
        except Exception as e:
            print(f"❌ File {i+1} upload failed: {str(e)}")
            upload_results.append({
                'success': False,
                'error': str(e),
                'filename': file.filename or f"file_{i+1}"
            })
    
    uploaded = []
    
    # Process results and add background tasks
    for i, result in enumerate(upload_results):
        if result.get('success'):
            filepath = Path(result['destination'])
            background_tasks.add_task(scan_file, filepath)
            uploaded.append(filepath.name)
            print(f"✅ File {i+1} uploaded successfully: {filepath.name}")
        else:
            print(f"❌ File {i+1} failed: {result.get('error', 'Unknown error')}")

    print(f"🎉 Concurrent upload complete! {len(uploaded)} files uploaded: {uploaded}")

    if not uploaded:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No valid files processed"
        })

    protocol_info = "HTTPS" if is_https else "HTTP"
    response_data = {
        "status": "success",
        "msg": f"{len(uploaded)} file(s) uploaded via {protocol_info}",
        "files": uploaded,
        "protocol": protocol_info,
        "total_files_processed": len(files),
        "files_uploaded": len(uploaded),
        "files_skipped": len(files) - len(uploaded)
    }
    
    print(f"🎯 Upload response: {response_data}")
    return JSONResponse(content=response_data)

@router.get("/download/{filename}", name="download_file")
@router.head("/download/{filename}")
async def download_file(filename: str, request: Request):
    print(f"📥 Download request for: {filename}")
    
    safe_name = secure_filename(filename)
    file_path = UPLOAD_FOLDER / safe_name
    
    print(f"📂 Looking for file at: {file_path}")

    if not file_path.is_file():
        print(f"❌ File not found: {file_path}")
        return Response("File not found", status_code=404)

    mime_type, _ = guess_type(str(file_path))
    file_size = file_path.stat().st_size
    
    print(f"📊 File info - Size: {file_size} bytes, MIME: {mime_type}")
    
    # OK: Handle HEAD requests - return headers only for file info
    if request.method == "HEAD":
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": mime_type or "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Accept-Ranges": "bytes",  # Indicate support for range requests
            "Cache-Control": "public, max-age=86400"
        }
        return Response(content="", headers=headers, status_code=200)
    
    # OK: Determine protocol (HTTP vs HTTPS)
    is_https = request.url.scheme == "https"
    
    # 🔐 Enforcement Rules:
    # 1. .enc files: Always use full download (no chunking)
    # 2. Files ≥250MB: Use chunked download if not .enc
    # 3. Files <250MB: Always use full download
    
    is_enc_file = safe_name.endswith(".enc")
    is_large_file = file_size >= 250 * 1024 * 1024  # 250MB threshold
    
    print(f"🔍 Download strategy - Encrypted: {is_enc_file}, Large: {is_large_file}")
    
    # 📦 Chunked download logic
    if is_large_file and not is_enc_file:
        print("📦 Using chunked download")
        return await chunked_download_file(file_path, safe_name, mime_type, file_size, request)
    else:
        print("📄 Using full download")
        return await full_download_file(file_path, safe_name, mime_type, file_size)

async def full_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int):
    """Ultra-optimized full file download - for small files and .enc files"""
    print(f"📤 Starting full download for: {safe_name}")
    
    # 🚀 Much larger buffer for maximum speed - 32MB buffer (4x improvement)
    STREAM_BUFFER_SIZE = 32 * 1024 * 1024  # 32MB buffer (was 8MB)
    
    def stream_file_ultra_optimized(path: Path):
        print(f"🔄 Streaming file: {path}")
        file_handle = None  # Track file handle for proper cleanup
        
        try:
            if path.suffix == ".enc":
                print("🔐 Processing encrypted file")
                # 🔐 Enhanced .enc file handling with streaming decryption and metadata validation
                try:
                    # Check for metadata file first
                    metadata_path = path.with_suffix('.enc.meta')
                    metadata = None
                    
                    if metadata_path.exists():
                        with open(metadata_path, "r") as meta_file:
                            import json
                            metadata = json.load(meta_file)
                            print(f"🔒 Found metadata for encrypted file: {metadata.get('encryption_method', 'legacy')}")
                    
                    with open(path, "rb") as file:
                        encrypted_data = file.read()
                        print(f"📊 Read {len(encrypted_data)} bytes of encrypted data")
                        
                        # Use appropriate decryption method based on metadata
                        if metadata and metadata.get('encryption_method') == 'streaming':
                            from .aes_utils import decrypt_file_stream
                            decrypted_data = decrypt_file_stream(encrypted_data, metadata, chunk_size=1024 * 1024)
                            print(f"🔒 Used streaming decryption for {path.name}")
                        else:
                            # Note: Legacy encryption not supported - file may be corrupted
                            print(f"⚠️ Cannot decrypt {path.name} - legacy encryption no longer supported")
                            yield f"Error: File {path.name} uses unsupported legacy encryption".encode('utf-8')
                            return
                        
                        print(f"OK: Decrypted to {len(decrypted_data)} bytes")
                        
                        # Validate integrity if metadata available
                        if metadata and 'original_hash' in metadata:
                            import hashlib
                            actual_hash = hashlib.sha256(decrypted_data).hexdigest()
                            expected_hash = metadata['original_hash']
                            if actual_hash != expected_hash:
                                raise Exception(f"File integrity check failed! Expected: {expected_hash}, Got: {actual_hash}")
                            print(f"OK: File integrity validated successfully")
                        
                        # 🚀 Stream in very large chunks for maximum speed
                        data_length = len(decrypted_data)
                        chunks_sent = 0
                        for i in range(0, data_length, STREAM_BUFFER_SIZE):
                            chunk_end = min(i + STREAM_BUFFER_SIZE, data_length)
                            chunk = decrypted_data[i:chunk_end]
                            chunks_sent += 1
                            print(f"📤 Sending chunk {chunks_sent}, size: {len(chunk)} bytes")
                            yield chunk
                            
                except Exception as e:
                    print(f"🚨 AES decryption failed for {path}: {e}")
                    # Return error content instead of crashing
                    error_message = f"Error: Failed to decrypt file {path.name}. {str(e)}"
                    yield error_message.encode('utf-8')
            else:
                print("📄 Processing regular file")
                # 🚀 Ultra-fast regular file streaming with optimized buffer and proper cleanup
                try:
                    file_handle = open(path, "rb")
                    chunks_sent = 0
                    while True:
                        chunk = file_handle.read(STREAM_BUFFER_SIZE)
                        if not chunk:
                            break
                        chunks_sent += 1
                        print(f"📤 Sending chunk {chunks_sent}, size: {len(chunk)} bytes")
                        yield chunk
                    print(f"OK: Completed streaming {chunks_sent} chunks")
                except Exception as e:
                    print(f"🚨 File streaming failed for {path}: {e}")
                    error_message = f"Error: Failed to read file {path.name}. {str(e)}"
                    yield error_message.encode('utf-8')
        finally:
            # Ensure file handle is always closed
            if file_handle is not None:
                try:
                    file_handle.close()
                    print(f"✅ File handle closed for: {path.name}")
                except Exception as e:
                    print(f"⚠️ Error closing file handle: {e}")
            
            # Force garbage collection to release any remaining handles
            import gc
            gc.collect()

    # For encrypted files, we need to adjust the Content-Length after decryption
    final_file_size = file_size
    if file_path.suffix == ".enc":
        # Try to get the original size from metadata
        metadata_path = file_path.with_suffix('.enc.meta')
        if metadata_path.exists():
            try:
                with open(metadata_path, "r") as meta_file:
                    import json
                    metadata = json.load(meta_file)
                    if 'original_size' in metadata:
                        final_file_size = int(metadata['original_size'])
                        print(f"🔒 Using original size from metadata: {final_file_size}")
            except Exception as e:
                print(f"⚠️ Could not read metadata for size: {e}")
    
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "Content-Type": mime_type or "application/octet-stream",
        "Cache-Control": "public, max-age=86400",
        "X-Accel-Buffering": "no",
        "X-Download-Type": "ultra-optimized-full",
        "X-Buffer-Size": "32MB"
    }
    
    # Only add Content-Length for non-encrypted files to avoid mismatch
    if not file_path.suffix == ".enc":
        headers["Content-Length"] = str(final_file_size)
    
    print(f"📋 Response headers: {headers}")
    
    return StreamingResponse(
        stream_file_ultra_optimized(file_path),
        media_type=mime_type or "application/octet-stream",
        headers=headers
    )

async def chunked_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int, request: Request | None = None):
    """High-performance chunked file download - for large files (≥250MB) that are not .enc"""
    # 🚀 Much larger chunk size for faster downloads - 16MB chunks (16x improvement)
    CHUNK_SIZE = 16 * 1024 * 1024  # 16MB chunks (was 1MB)
    
    # Check for Range header (for proper chunked downloads)
    range_header = request.headers.get('Range') if request else None
    start = 0
    end = file_size - 1
    
    if range_header:
        # Parse Range header: "bytes=start-end"
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            if len(range_match) == 2:
                if range_match[0]:
                    start = int(range_match[0])
                if range_match[1]:
                    end = int(range_match[1])
                end = min(end, file_size - 1)
        except ValueError:
            pass  # Ignore invalid range headers
    
    content_length = end - start + 1
    
    def stream_chunks_optimized():
        """Optimized streaming with larger buffers and better memory management"""
        with open(file_path, "rb") as file:
            file.seek(start)
            remaining = content_length
            
            # 🚀 Use larger buffer reads for maximum speed
            while remaining > 0:
                # Dynamic chunk sizing - use full CHUNK_SIZE unless near end
                chunk_size = min(CHUNK_SIZE, remaining)
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"',
        "Content-Length": str(content_length),
        "Cache-Control": "public, max-age=86400",
        "X-Accel-Buffering": "no",
        "X-Download-Type": "high-performance-chunked",  # Updated indicator
        "Accept-Ranges": "bytes",
        "X-Chunk-Size": "16MB"  # Performance indicator
    }
    
    # Add Content-Range header for partial content
    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status_code = 206  # Partial Content
    else:
        status_code = 200

    return StreamingResponse(
        stream_chunks_optimized(),
        media_type=mime_type or "application/octet-stream",
        headers=headers,
        status_code=status_code
    )

@router.get("/download-all", name="download_all")
async def download_all_files():
    """Download all files as a ZIP archive with proper streaming"""
    
    # Check if there are any files to download
    files_to_download = [file for file in UPLOAD_FOLDER.iterdir() if file.is_file()]
    if not files_to_download:
        return JSONResponse(
            status_code=404,
            content={"error": "No files available for download"}
        )
    
    # Create ZIP in memory with proper error handling
    try:
        zip_buffer = io.BytesIO()
        with ZipFile(zip_buffer, "w") as zip_file:
            for file in files_to_download:
                try:
                    if file.suffix == ".enc":
                        # Note: Legacy .enc files no longer supported for security reasons
                        print(f"⚠️ Skipping legacy encrypted file: {file.name}")
                        error_content = f"File {file.name} uses legacy encryption which is no longer supported for security reasons."
                        zip_file.writestr(f"{file.stem}_LEGACY_ENCRYPTION_WARNING.txt", error_content.encode('utf-8'))
                    else:
                        # Add regular files directly
                        zip_file.write(file, arcname=file.name)
                except Exception as e:
                    print(f"⚠️ Error adding {file.name} to ZIP: {e}")
                    # Continue with other files even if one fails
                    continue
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()
        zip_buffer.close()
        
        # Create a proper generator for streaming
        def generate_zip():
            chunk_size = 8192  # 8KB chunks
            for i in range(0, len(zip_data), chunk_size):
                chunk = zip_data[i:i + chunk_size]
                if chunk:  # Only yield non-empty chunks
                    yield chunk
        
        return StreamingResponse(
            generate_zip(),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=all_files.zip",
                "Content-Length": str(len(zip_data))
            }
        )
        
    except Exception as e:
        print(f"❌ Error creating ZIP archive: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to create ZIP archive: {str(e)}"}
        )

@router.post("/clear", name="clear_files")
async def clear_files():
    """Clear all uploaded files and temporary chunks with enhanced Windows compatibility"""
    from .windows_file_manager import WindowsFileManager
    
    try:
        print("🧹 Starting enhanced file cleanup with Windows diagnostics...")
        
        # Use enhanced cleanup with diagnostics
        results = await WindowsFileManager.enhanced_cleanup_with_diagnostics(
            upload_folder=UPLOAD_FOLDER,
            temp_folder=TEMP_CHUNKS_FOLDER
        )
        
        files_deleted = results['files_deleted']
        chunks_deleted = results['chunks_deleted']
        files_locked = results['files_locked']
        locked_files = results['locked_files']
        processes_using_files = results['processes_using_files']
        
        # Create detailed response
        if files_locked > 0:
            # Provide helpful information about locked files
            lock_details = []
            for locked_file in locked_files:
                detail = f"📄 {locked_file}"
                # Find processes using this file
                file_processes = [p for p in processes_using_files if locked_file in p.get('file_path', '')]
                if file_processes:
                    process_names = [p['name'] for p in file_processes]
                    detail += f" (used by: {', '.join(set(process_names))})"
                else:
                    detail += " (likely being downloaded/streamed)"
                lock_details.append(detail)
            
            message = f"Cleared {files_deleted} files and {chunks_deleted} chunks. {files_locked} files still in use:"
            full_message = message + "\n" + "\n".join(lock_details)
            
            print(f"WARNING: {message}")
            for detail in lock_details:
                print(f"  {detail}")
            
            return JSONResponse(content={
                "status": "warning",
                "msg": message,
                "files_deleted": files_deleted,
                "chunks_deleted": chunks_deleted,
                "files_locked": files_locked,
                "locked_files": locked_files,
                "lock_details": lock_details,
                "tip": "Files that are being downloaded or streamed cannot be deleted until the download completes."
            })
        else:
            message = f"Cleared {files_deleted} files and {chunks_deleted} chunks"
            print(f"✅ {message}")
            return JSONResponse(content={
                "status": "success",
                "msg": message,
                "files_deleted": files_deleted,
                "chunks_deleted": chunks_deleted,
                "files_locked": 0
            })
    except Exception as e:
        print(f"❌ Error during file clearing: {e}")
        # Return a JSON error response instead of crashing
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to clear files: {str(e)}"}
        )

@router.post("/delete/{filename}", name="delete_file")
async def delete_file(filename: str):
    """Delete a specific file with proper error handling"""
    try:
        safe_name = secure_filename(filename)
        if not safe_name:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Invalid filename"}
            )
            
        file_path = UPLOAD_FOLDER / safe_name
        
        if not file_path.exists():
            return JSONResponse(
                status_code=404,
                content={"status": "error", "msg": "File not found"}
            )
            
        if file_path.is_file():
            file_path.unlink()
            print(f"OK: Deleted file: {safe_name}")
            return RedirectResponse(url="/", status_code=HTTP_302_FOUND)
        else:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Not a valid file"}
            )
            
    except Exception as e:
        print(f"❌ Error deleting file {filename}: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to delete file: {str(e)}"}
        )

@router.get("/api/upload/chunk-size/{file_size}", name="get_optimal_chunk_size")
async def get_optimal_chunk_size(file_size: int):
    """Get optimal chunk size for a file upload based on system capabilities"""
    from .android_optimizer import universal_optimizer
    
    try:
        # Get adaptive chunk size
        optimal_chunk_size = universal_optimizer.get_adaptive_chunk_size(file_size)
        
        # Get system info for client optimization
        system_info = universal_optimizer.get_system_info()
        
        return JSONResponse({
            "status": "success",
            "optimal_chunk_size": optimal_chunk_size,
            "chunk_size_kb": optimal_chunk_size // 1024,
            "chunk_size_mb": round(optimal_chunk_size / (1024 * 1024), 2),
            "system_info": {
                "platform": system_info["platform"],
                "available_memory_mb": system_info["available_memory_mb"],
                "is_low_memory": system_info["is_low_memory"],
                "cpu_usage": system_info["cpu_usage"]
            },
            "recommendations": {
                "use_concurrent_uploads": file_size > 100 * 1024 * 1024,  # >100MB
                "enable_progress_reporting": file_size > 50 * 1024 * 1024,  # >50MB
                "estimated_chunks": max(1, file_size // optimal_chunk_size)
            }
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to calculate chunk size: {str(e)}"}
        )

# === CONCURRENT UPLOAD STATUS ===

@router.get("/api/upload/status", name="upload_status")
async def get_upload_status():
    """Get current upload status for all concurrent uploads"""
    from .concurrent_upload_manager import concurrent_upload_manager
    
    status = concurrent_upload_manager.get_system_status()
    detailed_status = concurrent_upload_manager.get_upload_status()
    
    return JSONResponse({
        "status": "success",
        "system": status,
        "uploads": detailed_status
    })

# === CHUNKED UPLOAD ENDPOINTS ===

@router.post("/upload_chunk", name="upload_chunk")
async def upload_chunk(
    request: Request,
    chunk: UploadFile = File(...),
    filename: str = Form(...),
    part_number: int = Form(...),
    total_parts: int = Form(None)  # Make optional since adaptive chunking may not know final count
):
    """Handle individual chunk uploads for large files - supports both HTTP and HTTPS with adaptive chunking"""
    try:
        # 🔐 Protocol detection
        is_https = request.url.scheme == "https"
        
        # 🔍 COMPREHENSIVE VALIDATION: Validate upload request using centralized validation
        validation_result = FileValidator.validate_filename(filename)
        if not validation_result['valid']:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": f"Validation failed: {validation_result['error']}"}
            )
        
        # 🛡️ PRELIMINARY SECURITY: Basic extension check (full validation at finalization)
        extension = os.path.splitext(filename)[1].lower()
        if extension in AdvancedFileValidator.BLOCKED_EXTENSIONS:
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN,
                content={
                    "status": "security_blocked",
                    "msg": f"🛡️ Blocked file type: {extension} files are not allowed for security reasons"
                }
            )
        
        # 🔍 Enhanced validation: Check part number validity
        if part_number < 1:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": f"Invalid part number: {part_number}. Must be >= 1."}
            )
        
        if total_parts and part_number > total_parts:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": f"Part number {part_number} exceeds total parts {total_parts}."}
            )
        
        # Secure the filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Invalid filename"}
            )
        
        # 🚫 Enforce .enc file restrictions on HTTPS
        if is_https and safe_filename.endswith(".enc"):
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={
                    "status": "error", 
                    "msg": "Chunked upload is disabled for .enc files to preserve encryption integrity. Please use full upload."
                }
            )
        
        # 📊 Check available disk space before writing
        import shutil
        total, used, free = shutil.disk_usage(TEMP_CHUNKS_FOLDER)
        
        # Read chunk data first to check size
        chunk_data = await chunk.read()
        if not chunk_data:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": f"Chunk {part_number} is empty"}
            )
        
        chunk_size = len(chunk_data)
        
        # Check if we have enough space (with 10% safety margin)
        required_space = chunk_size * 1.1  # 10% safety margin
        if free < required_space:
            return JSONResponse(
                status_code=507,  # Insufficient Storage
                content={
                    "status": "error", 
                    "msg": f"Insufficient disk space. Required: {chunk_size / (1024*1024):.1f}MB, Available: {free / (1024*1024):.1f}MB"
                }
            )
        
        # Create chunk filename
        chunk_filename = f"{safe_filename}.part{part_number}"
        chunk_path = TEMP_CHUNKS_FOLDER / chunk_filename
        
        # 🔍 Check for duplicate chunks (prevent overwrites)
        if chunk_path.exists():
            # Log potential issue but allow overwrite (might be a retry)
            print(f"⚠️ Warning: Chunk {chunk_filename} already exists, overwriting (possible retry)")
        
        # 🌊 Ensure streaming assembly is initialized and register file if this is the first chunk
        ensure_streaming_initialized()
        
        if part_number == 1 and total_parts:
            assembler = get_streaming_assembler()
            if assembler:
                final_path = UPLOAD_FOLDER / safe_filename
                # Estimate total size as chunk size * total parts (approximation)
                estimated_size = len(chunk_data) * total_parts
                assembler.register_file(safe_filename, total_parts, filename, estimated_size)
                print(f"🌊 Registered {safe_filename} for streaming assembly")
        
        # Save the chunk with error handling
        try:
            with open(chunk_path, "wb") as f:
                f.write(chunk_data)
            
            # Verify the file was written correctly
            if not chunk_path.exists():
                raise OSError(f"Failed to create chunk file {chunk_filename}")
            
            written_size = chunk_path.stat().st_size
            if written_size != chunk_size:
                raise OSError(f"Chunk size mismatch: expected {chunk_size}, written {written_size}")
                
        except OSError as e:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error", 
                    "msg": f"Failed to save chunk {part_number}: {str(e)}"
                }
            )
        
        # Prepare response message
        chunk_size_mb = chunk_size / (1024 * 1024)
        total_parts_msg = f"/{total_parts}" if total_parts else ""
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"Chunk {part_number}{total_parts_msg} uploaded ({chunk_size_mb:.1f}MB)",
            "part_number": part_number,
            "total_parts": total_parts,
            "chunk_size_mb": round(chunk_size_mb, 1),
            "chunk_written_size": written_size,
            "free_space_mb": round(free / (1024*1024), 1),
            "protocol": "HTTPS" if is_https else "HTTP"
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"status": "error", "msg": f"Chunk upload failed: {str(e)}"}
        )

@router.post("/finalize_upload", name="finalize_upload")
async def finalize_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    filename: str = Form(...),
    total_parts: int = Form(...),
    encrypt: bool = Form(False)
):
    """Combine all chunks into final file - supports streaming assembly with failsafe fallback"""
    try:
        # 🔐 Protocol detection  
        is_https = request.url.scheme == "https"
        
        # Secure the filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Invalid filename"}
            )
        
        # 🚫 Enforce encryption restrictions
        if encrypt and not is_https:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "msg": "AES encryption is only available over HTTPS connections for security."
                }
            )

        # 🌊 Check if streaming assembly is available and completed
        ensure_streaming_initialized()
        assembler = get_streaming_assembler()
        streaming_completed = False
        final_path = None
        background_processing_done = False
        validation_from_background = None
        
        # First, check if streaming-assembled file already exists
        potential_streaming_file = UPLOAD_FOLDER / safe_filename
        print(f"🔍 Checking for streaming file: {potential_streaming_file}")
        print(f"🔍 File exists: {potential_streaming_file.exists()}")
        
        if potential_streaming_file.exists():
            print(f"🌊 Found streaming-assembled file: {safe_filename}")
            streaming_completed = True
            final_path = potential_streaming_file
            
            # 🚀 Check if background processing was completed during streaming
            if assembler:
                status = assembler.check_status(safe_filename)
                if status and status.get('validation_result'):
                    validation_from_background = status['validation_result']
                    background_processing_done = True
                    print(f"⚡ Background processing completed during upload - no additional processing needed!")
                    
        elif assembler:
            # Check streaming status if file doesn't exist yet
            status = assembler.check_status(safe_filename)
            print(f"🔍 Streaming status: {status}")
            if status and status.get('status') == 'ready':
                streaming_completed = True
                final_path = UPLOAD_FOLDER / safe_filename
                
                # Check for background processing results
                if status.get('validation_result'):
                    validation_from_background = status['validation_result']
                    background_processing_done = True
                    
                print(f"✅ Streaming assembly completed for {safe_filename}")
        
        print(f"🔍 Streaming completed: {streaming_completed}")
        print(f"🔍 Background processing done: {background_processing_done}")
        print(f"🔍 Final path: {final_path}")
        
        # 🔄 Failsafe: Use traditional chunk combination if streaming didn't complete
        if not streaming_completed:
            print(f"🔄 Using traditional chunk assembly for {safe_filename}")
            
            # 🚀 Auto-detect actual chunks (adaptive chunked upload support)
            chunk_files = []
            part_num = 1
            while True:
                chunk_path = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{part_num}"
                if chunk_path.exists():
                    chunk_files.append((part_num, chunk_path))
                    part_num += 1
                else:
                    break
            
            actual_chunks = len(chunk_files)
            
            # If no chunks found but streaming was expected, assume streaming completed successfully
            if actual_chunks == 0 and assembler:
                # Check if streaming file was created
                potential_file = UPLOAD_FOLDER / safe_filename
                if potential_file.exists():
                    print(f"🌊 Found streaming-assembled file: {safe_filename}")
                    streaming_completed = True
                    final_path = potential_file
                else:
                    return JSONResponse(
                        status_code=HTTP_400_BAD_REQUEST,
                        content={"status": "error", "msg": "No chunks found and no streaming file exists"}
                    )
            
            if not streaming_completed:
                if actual_chunks == 0:
                    return JSONResponse(
                        status_code=HTTP_400_BAD_REQUEST,
                        content={"status": "error", "msg": "No chunks found for this file"}
                    )
                
                # Determine final filename
                final_filename = safe_filename + ".enc" if encrypt else safe_filename
                final_path = UPLOAD_FOLDER / get_unique_filename(UPLOAD_FOLDER, final_filename)
                
                # 🚀 Fast chunk combination with proper error handling
                with open(final_path, "wb") as final_file:
                    for part_num, chunk_path in chunk_files:
                        if not chunk_path.exists():
                            # Clean up partial chunks and final file
                            if final_path.exists():
                                final_path.unlink()
                            for _, clean_chunk_path in chunk_files:
                                if clean_chunk_path.exists():
                                    clean_chunk_path.unlink()
                            
                            return JSONResponse(
                                status_code=HTTP_400_BAD_REQUEST,
                                content={"status": "error", "msg": f"Missing chunk {part_num}"}
                            )
                        
                        # Read chunk data
                        chunk_data = chunk_path.read_bytes()
                        
                        # Encrypt if requested with error handling
                        if encrypt:
                            try:
                                # Use secure session-based encryption for temporary chunks
                                chunk_data, session_key, session_iv = encrypt_session_data(chunk_data)
                                # Note: For production use, you'd want to store session_key and session_iv securely
                                # For now, this is just for demonstration - chunks are temporary
                            except Exception as encrypt_error:
                                print(f"🚨 AES encryption failed for chunk {part_num}: {encrypt_error}")
                                # Clean up and return error
                                if final_path.exists():
                                    final_path.unlink()
                                for _, clean_chunk_path in chunk_files:
                                    if clean_chunk_path.exists():
                                        clean_chunk_path.unlink()
                                
                                return JSONResponse(
                                    status_code=HTTP_400_BAD_REQUEST,
                                    content={"status": "error", "msg": f"AES encryption failed: {encrypt_error}"}
                                )
                        
                        # Write to final file
                        final_file.write(chunk_data)
                
                # Clean up temporary chunks using actual chunks found
                for _, chunk_path in chunk_files:
                    if chunk_path.exists():
                        chunk_path.unlink()
        
        else:
            # Streaming assembly completed - just verify the file exists
            if not final_path or not final_path.exists():
                return JSONResponse(
                    status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"status": "error", "msg": "Streaming assembly completed but file not found"}
                )
            
            # Apply encryption if requested for streaming-assembled file
            if encrypt:
                try:
                    # Read the streaming-assembled file
                    file_data = final_path.read_bytes()
                    
                    # Encrypt the data
                    encrypted_data, session_key, session_iv = encrypt_session_data(file_data)
                    
                    # Write back encrypted data
                    final_path.write_bytes(encrypted_data)
                    
                    # Rename to .enc extension
                    encrypted_path = final_path.parent / (final_path.name + ".enc")
                    final_path.rename(encrypted_path)
                    final_path = encrypted_path
                    
                except Exception as encrypt_error:
                    print(f"🚨 AES encryption failed for streaming file: {encrypt_error}")
                    if final_path.exists():
                        final_path.unlink()
                    
                    return JSONResponse(
                        status_code=HTTP_400_BAD_REQUEST,
                        content={"status": "error", "msg": f"AES encryption failed: {encrypt_error}"}
                    )

        # Check if encryption is requested and validate using centralized config
        if encrypt and final_path and final_path.exists():
            # Get file size after processing
            total_size = final_path.stat().st_size
            
            validation = AESConfig.validate_file_for_aes(total_size, is_https)
            if not validation['valid']:
                # Clean up file
                if final_path.exists():
                    final_path.unlink()
                        
                return JSONResponse(
                    status_code=HTTP_400_BAD_REQUEST,
                    content={
                        "status": "error",
                        "msg": validation['error']
                    }
                )
        
        # 🛡️ ENHANCED SECURITY: Validate the assembled file (skip if already done in background)
        try:
            if background_processing_done and validation_from_background:
                # 🚀 Use validation results from background processing - massive time savings!
                print(f"⚡ Using background validation results - skipping duplicate processing!")
                security_check = validation_from_background
            elif final_path:
                # 🐌 Traditional validation (slower)
                print(f"🔄 Performing security validation (no background processing available)")
                security_check = FileValidator.validate_uploaded_file(final_path, filename)
            else:
                # No final_path available
                security_check = {'valid': False, 'errors': ['File path not available']}
            
            # Handle case where security_check might be a string (error message)
            if isinstance(security_check, str):
                security_check = {'valid': False, 'errors': [security_check]}
                
            if not security_check.get('valid', False):
                # File failed security validation - delete it immediately
                if final_path and final_path.exists():
                    final_path.unlink()
                    
                errors = security_check.get('errors', ['Security validation failed'])
                return JSONResponse(
                    status_code=HTTP_403_FORBIDDEN,
                    content={
                        "status": "security_blocked",
                        "msg": f"🛡️ Security Check Failed: {errors[0] if errors else 'Unknown error'}",
                        "security_details": {
                            "blocked_reason": errors[0] if errors else 'Unknown security violation',
                            "detected_type": security_check.get('actual_type'),
                            "claimed_extension": security_check.get('claimed_extension'),
                            "file_deleted": True
                        }
                    }
                )
                
        except Exception as validation_error:
            print(f"⚠️ Security validation error for {final_path.name if final_path else 'unknown file'}: {validation_error}")
            # If validation fails, delete the file as a precaution
            if final_path and final_path.exists():
                final_path.unlink()
                
            return JSONResponse(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error", 
                    "msg": f"Security validation failed: {str(validation_error)}",
                    "file_deleted": True
                }
            )
        
        # Add background scan task
        if final_path:
            background_tasks.add_task(scan_file, final_path)
        
        # Clean up streaming registration if applicable
        if assembler:
            try:
                status = assembler.check_status(safe_filename)
                if status.get("status") != "not_found":
                    assembler.cleanup(safe_filename)
            except AttributeError:
                # Assembler doesn't have these methods, skip cleanup
                pass
        
        # Success response with security confirmation
        assembly_method = "streaming assembly" if streaming_completed else "traditional chunk combination"
        success_msg = f"File '{final_path.name if final_path else 'unknown'}' uploaded successfully via {'HTTPS' if is_https else 'HTTP'} ({assembly_method})"
        
        # Handle warnings safely
        warnings = security_check.get('warnings', []) if isinstance(security_check, dict) else []
        if warnings:
            success_msg += f" ⚠️ Security Notes: {'; '.join(warnings)}"
        
        return JSONResponse(content={
            "status": "success",
            "msg": success_msg,
            "filename": final_path.name if final_path else "unknown",
            "streaming_assembly": streaming_completed,
            "assembly_method": assembly_method,
            "protocol": "HTTPS" if is_https else "HTTP",
            "security_validated": True
        })
        
    except Exception as e:
        # Clean up on error using dynamic chunk detection
        try:
            safe_filename = secure_filename(filename)
            part_num = 1
            while True:
                chunk_path = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{part_num}"
                if chunk_path.exists():
                    chunk_path.unlink()
                    part_num += 1
                else:
                    break
        except:
            pass
            
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"status": "error", "msg": f"File assembly failed: {str(e)}"}
        )

# 🚨 EMERGENCY SHUTDOWN ENDPOINT
@router.post("/api/shutdown")
async def emergency_shutdown():
    """
    Emergency server shutdown endpoint - immediately terminates server
    and notifies all connected clients.
    """
    import asyncio
    from app.main import shutdown_event, connection_manager
    
    print("🚨 EMERGENCY SHUTDOWN REQUESTED!")
    print("⚠️ Notifying all connected clients...")
    
    # Set the shutdown flag immediately
    shutdown_event.set()
    
    # Send shutdown notifications to all active clients
    async def notify_clients():
        await connection_manager.disconnect_all()
        print("✅ All clients notified and disconnected")
    
    # Schedule client notification in background
    asyncio.create_task(notify_clients())
    
    # Force server shutdown after brief delay for response
    async def force_shutdown():
        await asyncio.sleep(0.5)  # Allow response to be sent
        print("🔥 FORCING SERVER SHUTDOWN...")
        import os
        os._exit(0)  # Force immediate shutdown
    
    asyncio.create_task(force_shutdown())
    
    return JSONResponse({
        "status": "shutdown",
        "message": "🚨 Server is shutting down immediately. All operations halted.",
        "warning": "⚠️ All active uploads and downloads have been terminated.",
        "action": "Server will restart automatically if using a process manager."
    })

# 🔍 SERVER STATUS ENDPOINT
@router.get("/api/server-status")
async def server_status():
    """Check if server is shutting down"""
    from app.main import shutdown_event, graceful_shutdown_initiated, shutdown_countdown
    
    # Check for graceful shutdown state
    if graceful_shutdown_initiated:
        return JSONResponse({
            "status": "shutting_down",
            "message": f"⚠️ Server shutdown initiated. {shutdown_countdown} seconds remaining.",
            "shutdown": False,
            "shutdownWarning": True,
            "warningMessage": "Server is shutting down gracefully",
            "countdown": shutdown_countdown
        })
    
    if shutdown_event.is_set():
        return JSONResponse(
            status_code=503,
            content={
                "status": "shutdown",
                "message": "🚨 Server is now inactive. Please restart the server.",
                "shutdown": True,
                "timeRemaining": 0
            }
        )
    
    return JSONResponse({
        "status": "online",
        "message": "✅ Server is running normally",
        "shutdown": False,
        "resources_ready": True  # If we can respond to this request, resources are ready
    })

@router.get("/api/network-info", name="network_info")
async def get_network_info():
    """Get network information including LAN IP and mDNS info"""
    try:
        import socket
        import os
        
        # Check if we're on Android/Termux
        is_android = ("ANDROID_STORAGE" in os.environ or 
                     os.path.exists("/data/data/com.termux") or 
                     "TERMUX_VERSION" in os.environ)
        
        # Get current mDNS manager
        current_mdns = get_current_mdns_manager()
        
        if current_mdns and UNIVERSAL_MDNS_AVAILABLE:
            # Universal mDNS manager
            status = current_mdns.get_status()
            lan_ip = status.get('local_ip', '127.0.0.1')
            mdns_info = {
                'status': 'active' if status['active'] else 'inactive',
                'active': status['active'],
                'domain': status['domain'],
                'url': status['url'],
                'port': status['port']
            }
            protocol = "http"  # Universal mDNS uses HTTP by default
            port = status['port']
            hybrid_url = status['url'] if status['active'] else f"http://{lan_ip}:{port}"
        elif current_mdns:
            # Legacy mDNS manager
            lan_ip = current_mdns.get_lan_ip()
            mdns_info = current_mdns.get_mdns_info()
            hybrid_url = current_mdns.get_hybrid_url()
            protocol = "https" if current_mdns.use_https else "http"
            port = current_mdns.port
        else:
            # No mDNS manager available
            lan_ip = socket.gethostbyname(socket.gethostname())
            mdns_info = {'active': False, 'domain': None, 'url': None}
            protocol = "http"
            port = int(os.environ.get('PORT', 5000))
            hybrid_url = f"http://{lan_ip}:{port}"
        
        # Format LAN IP URL using the same logic as mDNS URLs
        if (port == 80 and protocol == "http") or (port == 443 and protocol == "https"):
            lan_ip_url = f"{protocol}://{lan_ip}"
        else:
            lan_ip_url = f"{protocol}://{lan_ip}:{port}"
        
        response_data = {
            "status": "success",
            "lan_ip": lan_ip,
            "lan_ip_url": lan_ip_url,
            "hostname": socket.gethostname(),
            "mdns": mdns_info,
            "hybrid_url": hybrid_url,
            "protocol": protocol,
            "port": port,
            "platform": "android" if is_android else "desktop"
        }
        
        # Add Android/Termux specific recommendations
        if is_android and current_mdns and hasattr(current_mdns, 'get_android_optimized_info'):
            response_data["android_info"] = current_mdns.get_android_optimized_info()
            response_data["recommendations"] = [
                f"Use IP address: {lan_ip_url}",
                "Avoid .local domains on Android/Termux",
                "Share QR code for easy mobile access",
                "Bookmark the IP address for future use"
            ]
        
        return JSONResponse(content=response_data)
    except Exception as e:
        # Create fallback URL using the same format logic
        current_mdns = get_current_mdns_manager()
        if current_mdns and hasattr(current_mdns, 'use_https'):
            protocol = "https" if current_mdns.use_https else "http"
            port = current_mdns.port
        else:
            # Fallback values
            protocol = "http"
            port = int(os.environ.get('PORT', 5000))
        if (port == 80 and protocol == "http") or (port == 443 and protocol == "https"):
            fallback_url = f"{protocol}://127.0.0.1"
            lan_ip_fallback = f"{protocol}://127.0.0.1"
        else:
            fallback_url = f"{protocol}://127.0.0.1:{port}"
            lan_ip_fallback = f"{protocol}://127.0.0.1:{port}"
        
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "lan_ip": "127.0.0.1",
                "lan_ip_url": lan_ip_fallback,
                "mdns": {"status": "error", "domain": None},
                "hybrid_url": fallback_url,
                "protocol": protocol,
                "port": port
            }
        )

@router.get("/api/qr-code", name="offline_qr")
async def generate_offline_qr(text: str, size: int = 200):
    """Generate QR code locally without internet dependency - Android/Termux optimized"""
    try:
        # Android/Termux detection
        is_android = ("ANDROID_STORAGE" in os.environ or 
                     os.path.exists("/data/data/com.termux") or 
                     "TERMUX_VERSION" in os.environ)
        
        if is_android:
            print("📱 Android/Termux QR generation - using optimized settings")
        
        # Create QR code with Android-optimized settings
        box_size = max(1, size // 25) if not is_android else max(2, size // 20)  # Larger boxes for Android
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=box_size,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)

        # Create image with Android fallbacks
        try:
            qr_img = qr.make_image(fill_color="black", back_color="white")
        except Exception as img_error:
            if is_android:
                print(f"📱 Android QR image creation fallback: {img_error}")
                # Try simpler image creation for Android
                qr_img = qr.make_image()
            else:
                raise img_error
        
        # Convert to bytes with Android-specific handling
        img_buffer = io.BytesIO()
        
        # Enhanced save method with multiple fallbacks
        save_success = False
        
        # Method 1: Standard PNG save
        if not save_success:
            try:
                qr_img.save(img_buffer, 'PNG')
                save_success = True
                if is_android:
                    print("📱 Android QR: PNG save successful")
            except Exception as png_error:
                if is_android:
                    print(f"📱 Android QR PNG save failed: {png_error}")
        
        # Method 2: Format-less save (Android fallback)
        if not save_success:
            try:
                img_buffer = io.BytesIO()  # Reset buffer
                qr_img.save(img_buffer)
                save_success = True
                if is_android:
                    print("📱 Android QR: Fallback save successful")
            except Exception as fallback_error:
                if is_android:
                    print(f"📱 Android QR fallback save failed: {fallback_error}")
        
        # Method 3: Text-based QR for Android (ultimate fallback)
        if not save_success and is_android:
            try:
                # Generate ASCII QR code for Android as last resort
                qr_text = qr.get_matrix()
                ascii_qr = "\n".join(["".join(["██" if cell else "  " for cell in row]) for row in qr_text])
                return JSONResponse({
                    "status": "text_fallback",
                    "qr_text": ascii_qr,
                    "url": text,
                    "message": "QR generated as text for Android compatibility"
                })
            except Exception as text_error:
                print(f"📱 Android QR text fallback failed: {text_error}")
        
        if not save_success:
            raise Exception(f"All QR generation methods failed")
        
        img_buffer.seek(0)

        return StreamingResponse(
            io.BytesIO(img_buffer.getvalue()),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        # Return a simple text-based error response
        return JSONResponse(
            status_code=500,
            content={"error": f"QR generation failed: {str(e)}"}
        )

# === CLIPBOARD SYSTEM ENDPOINTS ===

# Persistent clipboard storage setup
CLIPBOARD_FOLDER = Path("app/clipboard_data")
CLIPBOARD_FOLDER.mkdir(parents=True, exist_ok=True)
CLIPBOARD_HISTORY_FILE = CLIPBOARD_FOLDER / "clipboard_history.json"

# In-memory clipboard storage for current session (loaded from disk)
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
                print(f"📋 Loaded {len(clipboard_history)} clipboard items from persistent storage")
        else:
            print("📋 No persistent clipboard history found, starting fresh")
    except Exception as e:
        print(f"❌ Error loading clipboard history: {e}")
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
        print(f"❌ Error saving clipboard history: {e}")

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
                print(f"❌ Error decoding clipboard item {item.get('id', 'unknown')}: {e}")
                # Remove corrupted item
                continue
    
    return items

# Load clipboard history on server startup
# Note: This will be called after all imports are complete
def initialize_clipboard_persistence():
    """Initialize clipboard persistence after all imports are complete"""
    try:
        load_clipboard_history()
        global clipboard_history
        if clipboard_history:
            clipboard_history = restore_clipboard_data(clipboard_history)
        print(f"📋 Clipboard persistence initialized successfully with {len(clipboard_history)} items")
    except Exception as e:
        print(f"❌ Error initializing clipboard persistence: {e}")
        clipboard_history.clear()
        global clipboard_id_counter
        clipboard_id_counter = 0

@router.get("/clipboard", response_class=HTMLResponse, name="clipboard_page")
async def clipboard_page(request: Request):
    """Full page clipboard route"""
    # 🏠 Direct clipboard access - no redirects
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
            
            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            
            # Limit file size for clipboard (10MB max)
            if file_size > 10 * 1024 * 1024:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "msg": "File too large for clipboard (max 10MB)"}
                )
            
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

def generate_simple_file_preview(filename: str, file_data: bytes, content_type: str) -> str:
    """Generate simple preview text for file content (with base64 image preview)"""
    try:
        if content_type == 'image':
            # Generate base64 preview for images (no Pillow needed!)
            import base64
            try:
                # Limit preview to reasonable size (max 1MB for preview)
                if len(file_data) <= 1024 * 1024:
                    # Detect image format from file extension
                    file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
                    mime_map = {
                        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                        'png': 'image/png', 'gif': 'image/gif',
                        'bmp': 'image/bmp', 'webp': 'image/webp',
                        'svg': 'image/svg+xml'
                    }
                    mime_type = mime_map.get(file_ext, 'image/jpeg')
                    
                    # Create base64 data URL
                    base64_data = base64.b64encode(file_data).decode('utf-8')
                    return f"data:{mime_type};base64,{base64_data}"
                else:
                    return f"Image: {filename} ({format_size(len(file_data))}) - Too large for preview"
            except Exception:
                return f"Image: {filename} ({format_size(len(file_data))}) - Preview failed"
        elif content_type == 'text':
            # Try to decode and show first few lines
            try:
                text_content = file_data.decode('utf-8')
                lines = text_content.split('\n')[:3]  # First 3 lines
                preview = '\n'.join(lines)
                if len(text_content) > 200:
                    preview = preview[:200] + "..."
                return preview
            except:
                return f"Text file: {filename} ({format_size(len(file_data))})"
        elif content_type == 'document':
            return f"Document: {filename} ({format_size(len(file_data))})"
        else:
            return f"File: {filename} ({format_size(len(file_data))})"
    except:
        return f"File: {filename} ({format_size(len(file_data))})"

# === ADDITIONAL API ENDPOINTS FOR TESTING ===

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

@router.get("/api/mdns-info", name="mdns_info")
async def mdns_info():
    """Get mDNS service information"""
    try:
        current_mdns = get_current_mdns_manager()
        
        if current_mdns and UNIVERSAL_MDNS_AVAILABLE:
            # Universal mDNS manager
            status = current_mdns.get_status()
            return JSONResponse(content={
                "status": "success",
                "active": status['active'],
                "domain": status['domain'],
                "url": status['url'],
                "port": status['port'],
                "local_ip": status.get('local_ip'),
                "backend": status.get('backend', 'universal')
            })
        elif current_mdns:
            # Legacy mDNS manager
            info = current_mdns.get_mdns_info()
            return JSONResponse(content=info)
        else:
            # No mDNS available
            return JSONResponse(content={
                "status": "error",
                "active": False,
                "msg": "mDNS not available"
            })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"mDNS info failed: {str(e)}"}
        )

@router.get("/api/aes-config", name="aes_config")
async def aes_config():
    """Get AES encryption configuration"""
    try:
        from aes_config import AES_CONFIG
        return JSONResponse(content={
            "status": "success",
            "aes_enabled": AES_CONFIG.get("ENABLED", False),
            "aes_mode": AES_CONFIG.get("MODE", "disabled"),
            "key_size": AES_CONFIG.get("KEY_SIZE", 0),
            "chunk_size": AES_CONFIG.get("CHUNK_SIZE", 0)
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"AES config failed: {str(e)}"}
        )

@router.get("/api/logs", name="system_logs")
async def system_logs():
    """Get system logs"""
    try:
        # Try to get logs from various sources
        logs = []
        
        # Add responsiveness monitor logs if available
        try:
            from responsiveness_monitor import responsiveness_monitor
            if hasattr(responsiveness_monitor, 'get_recent_logs'):
                monitor_logs = responsiveness_monitor.get_recent_logs()
                logs.extend(monitor_logs)
        except Exception:
            pass
            
        # Add thread manager logs if available
        try:
            from thread_manager import thread_manager
            if hasattr(thread_manager, 'get_logs'):
                thread_logs = thread_manager.get_logs()
                logs.extend(thread_logs)
        except Exception:
            pass
            
        # Add basic system info
        import time
        logs.append({
            "timestamp": time.time(),
            "level": "INFO",
            "message": "System logs endpoint accessed",
            "source": "api"
        })
        
        return JSONResponse(content={
            "status": "success",
            "logs": logs,
            "log_count": len(logs),
            "timestamp": time.time()
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Logs retrieval failed: {str(e)}"}
        )

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

# 📁 FOLDER UPLOAD/DOWNLOAD ROUTES

@router.post("/upload-folder", name="upload_folder")
async def upload_folder(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    folder_name: str = Form(...),
    encrypt: bool = Query(False, description="Encrypt folder contents with AES-256 if true")
):
    """Upload multiple files as a folder structure with real-time progress"""
    if not files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No files uploaded"
        })

    # 🔐 Protocol detection
    is_https = request.url.scheme == "https"
    
    # 📡 Import WebSocket manager for real-time updates
    from .upload_status_ws import upload_status_manager
    
    # 📊 Notify folder upload start
    await upload_status_manager.notify_folder_start(folder_name, len(files))
    
    # Create folder directory
    folder_path = UPLOAD_FOLDER / folder_name
    folder_path.mkdir(exist_ok=True)
    
    # Process each file and maintain folder structure
    uploaded_files = []
    failed_files = []
    start_time = time.time()
    
    for index, file in enumerate(files, 1):
        try:
            # Get relative path from file name (browsers include path in webkitRelativePath)
            if hasattr(file, 'filename') and file.filename:
                # Handle nested folder structure from webkitRelativePath
                relative_path = file.filename
                if '/' in relative_path:
                    # Create nested directories
                    file_folder_path = folder_path / Path(relative_path).parent
                    file_folder_path.mkdir(parents=True, exist_ok=True)
                    final_path = folder_path / relative_path
                else:
                    final_path = folder_path / file.filename
                
                # 📡 Notify file progress start
                await upload_status_manager.notify_file_progress(
                    folder_name, file.filename, index, len(files), 0.0
                )
                
                # Save the file
                await save_upload_file_async(file, final_path, encrypt)
                uploaded_files.append(str(final_path.relative_to(UPLOAD_FOLDER)))
                
                # 📡 Notify file completion
                await upload_status_manager.notify_file_progress(
                    folder_name, file.filename, index, len(files), 100.0
                )
                
        except Exception as e:
            print(f"❌ Failed to upload file {file.filename}: {e}")
            failed_files.append(file.filename)
            # 📡 Notify file error
            await upload_status_manager.notify_folder_error(
                folder_name, f"Failed to upload {file.filename}: {str(e)}"
            )
    
    total_time = time.time() - start_time
    
    # 📡 Notify folder completion
    await upload_status_manager.notify_folder_complete(
        folder_name, uploaded_files, failed_files, total_time
    )
    
    return JSONResponse(content={
        "status": "success" if uploaded_files else "error",
        "msg": f"Folder '{folder_name}' uploaded with {len(uploaded_files)} files",
        "folder_name": folder_name,
        "files_uploaded": uploaded_files,
        "files_failed": failed_files,
        "total_files": len(files),
        "upload_time": round(total_time, 2),
        "protocol": "HTTPS" if is_https else "HTTP"
    })

@router.get("/download-folder/{folder_name}", name="download_folder")
async def download_folder(folder_name: str):
    """Download an entire folder as a ZIP file"""
    folder_path = UPLOAD_FOLDER / folder_name
    
    if not folder_path.exists() or not folder_path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Create ZIP file in memory
    import zipfile
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                # Add file to ZIP with relative path
                arcname = file_path.relative_to(folder_path)
                zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={folder_name}.zip"}
    )

@router.get("/api/folders", name="list_folders")
async def list_folders():
    """Get list of available folders"""
    try:
        folders = []
        for item in UPLOAD_FOLDER.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Count files in folder recursively
                file_count = sum(1 for _ in item.rglob('*') if _.is_file())
                folder_size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                
                folders.append({
                    "name": item.name,
                    "file_count": file_count,
                    "size": folder_size,
                    "size_formatted": format_size(folder_size),
                    "created": item.stat().st_mtime
                })
        
        # Sort by creation time (newest first)
        folders.sort(key=lambda x: x["created"], reverse=True)
        
        return JSONResponse(content={
            "status": "success",
            "folders": folders
        })
        
    except Exception as e:
        print(f"❌ Error listing folders: {e}")
        return JSONResponse(content={
            "status": "error",
            "msg": "Failed to list folders"
        })

@router.post("/delete-folder/{folder_name}", name="delete_folder")
async def delete_folder(folder_name: str):
    """Delete an entire folder"""
    import shutil
    
    folder_path = UPLOAD_FOLDER / folder_name
    
    if not folder_path.exists() or not folder_path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")
    
    try:
        shutil.rmtree(folder_path)
        return JSONResponse(content={
            "status": "success",
            "msg": f"Folder '{folder_name}' deleted successfully"
        })
    except Exception as e:
        print(f"❌ Error deleting folder {folder_name}: {e}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "msg": f"Failed to delete folder: {e}"
        })

# === END OF ROUTES ===
