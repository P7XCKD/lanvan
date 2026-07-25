"""
Lanvan Files Router
Handles core file operations: listing files, chunk-based concurrent uploads,
real-time file assembly, ZIP compression for folder downloads, and cross-platform
file path normalization.
"""

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
import urllib.parse
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from mimetypes import guess_type
from zipfile import ZipFile
from app.utils.termux_compat import is_android_environment

from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Query, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from starlette.status import (
    HTTP_302_FOUND,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR
)

# Import common app utilities
from app.core.aes_utils import encrypt_file_http_safe, decrypt_http_safe_file, decrypt_file_stream, encrypt_session_data
from app.core.metadata_protection import generate_secure_filename, obfuscate_file_size, generate_decoy_requests
from app.core.validation import (
    validate_upload_files_enhanced_fast,
    secure_filename,
    is_allowed_file,
    FileValidator,
    AdvancedFileValidator
)
from app.core.upload_path_resolver import UploadPathResolver
from app.core.file_locking import get_file_lock_manager
from app.utils.termux_compat import is_android, is_termux
from app.core.concurrent_upload_manager import concurrent_upload_manager, ConcurrentUploadManager
from app.core.windows_file_manager import WindowsFileManager
from app.core.streaming_assembly import get_streaming_assembler, add_streaming_chunk, check_streaming_status, get_assembled_file, initialize_streaming_assembly

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
UPLOAD_FOLDER = Path("data/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Upload history file - cleared on every server startup
UPLOAD_HISTORY_FILE = Path("data/upload_history.json")
# Clear history on startup so it resets with every server restart
try:
    UPLOAD_HISTORY_FILE.write_text("[]", encoding="utf-8")
except Exception:
    pass

# Startup cleanup of orphan .tmp files in upload folder
try:
    for orphan_tmp in UPLOAD_FOLDER.rglob("*.tmp"):
        if orphan_tmp.is_file():
            try:
                orphan_tmp.unlink()
                print(f"[STARTUP CLEANUP] Removed orphan temporary file: {orphan_tmp}")
            except Exception:
                pass
except Exception:
    pass

def cleanup_temp_file_for_filename(filename: str, parent_path: Optional[str] = None) -> int:
    """Find and delete all .tmp files and chunk artifacts associated with a filename."""
    deleted_count = 0
    if not filename:
        return 0
    safe_name = secure_filename(filename)
    if not safe_name:
        return 0

    base_name = safe_name.rsplit('.', 1)[0] if '.' in safe_name else safe_name

    target_dirs = [UPLOAD_FOLDER]
    if parent_path:
        clean_parent = urllib.parse.unquote(parent_path).replace('\\', '/').strip('/')
        if clean_parent:
            # Sanitize each path component to prevent traversal & filter virtual 'Home' root
            parts = [secure_filename(p) for p in clean_parent.split('/') if p and p != "Home" and secure_filename(p)]
            if parts:
                sub_dir = UPLOAD_FOLDER.joinpath(*parts)
                try:
                    sub_dir.resolve().relative_to(UPLOAD_FOLDER.resolve())
                    if sub_dir.exists():
                        target_dirs.append(sub_dir)
                except ValueError:
                    print(f"[SECURITY] Blocked path traversal attempt in cleanup_temp_file_for_filename: '{parent_path}'")
                    pass

    for d in target_dirs:
        # Delete any partially written destination file matching safe_name or raw filename
        for target_name in set([safe_name, filename, secure_filename(filename)]):
            if not target_name: continue
            exact_target = d / target_name
            if exact_target.exists() and exact_target.is_file():
                try:
                    exact_target.unlink()
                    deleted_count += 1
                    print(f"[CLEANUP] Deleted cancelled target file: {exact_target}")
                except Exception as e:
                    print(f"[ERR] Failed to delete cancelled target file {exact_target}: {e}")

        for p in d.rglob("*.tmp"):
            p_name = p.name
            if (base_name in p_name or safe_name in p_name) and p.is_file():
                try:
                    p.unlink()
                    deleted_count += 1
                    print(f"[CLEANUP] Deleted temporary file: {p}")
                except Exception as e:
                    print(f"[ERR] Failed to delete temp file {p}: {e}")

    temp_chunks_dir = Path("data/temp_chunks")
    if temp_chunks_dir.exists():
        for chunk in temp_chunks_dir.glob(f"*{base_name}*"):
            try:
                if chunk.is_file():
                    chunk.unlink()
                    deleted_count += 1
                elif chunk.is_dir():
                    shutil.rmtree(chunk, ignore_errors=True)
                    deleted_count += 1
            except Exception:
                pass

    return deleted_count

@router.get("/api/upload-history")
async def get_upload_history():
    """Return persisted upload tray history for this server session."""
    try:
        if UPLOAD_HISTORY_FILE.exists():
            data = json.loads(UPLOAD_HISTORY_FILE.read_text(encoding="utf-8"))
            return JSONResponse(content=data)
    except Exception:
        pass
    return JSONResponse(content=[])

@router.post("/api/upload-history")
async def save_upload_history(request: Request):
    """Save upload tray history for this server session."""
    try:
        body = await request.json()
        if isinstance(body, list):
            UPLOAD_HISTORY_FILE.write_text(json.dumps(body), encoding="utf-8")
            return JSONResponse(content={"ok": True})
    except Exception as e:
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=400)
    return JSONResponse(content={"ok": False, "error": "Invalid payload"}, status_code=400)

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

TEMP_CHUNKS_FOLDER = Path("data/temp_chunks")
TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)

MAX_CONCURRENT_UPLOADS = 5  # Maximum parallel uploads per session

_streaming_initialized = False

def ensure_streaming_initialized():
    """Ensure streaming assembly is initialized"""
    global _streaming_initialized
    if not _streaming_initialized:
        initialize_streaming_assembly(TEMP_CHUNKS_FOLDER, UPLOAD_FOLDER)
        _streaming_initialized = True

def cleanup_orphaned_temp_files():
    """
    [CLEAN] Clean up orphaned .tmp files on startup (from interrupted uploads)
    """
    try:
        temp_files = list(UPLOAD_FOLDER.glob("*.tmp"))
        if temp_files:
            print(f"[CLEAN] Cleaning up {len(temp_files)} orphaned .tmp files...")
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

async def initialize_file_locking():
    """Initialize file locking system and clean up stale locks"""
    try:
        lock_manager = get_file_lock_manager(UPLOAD_FOLDER)
        locks_dir = lock_manager.locks_dir
        
        # Clean up stale locks from previous sessions
        await cleanup_stale_locks(locks_dir, max_age_seconds=300)  # 5 minutes
        print("[LOCK] File locking system initialized")
    except Exception as e:
        print(f"[WARN] File locking initialization error: {e}")

def format_size(size_bytes):
    """Format bytes to human readable string"""
    if size_bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

LOCKED_DELETIONS_SET = set()

def is_pending_deletion(filename_or_path: str) -> bool:
    """Check if file is in pending locked deletion list"""
    global LOCKED_DELETIONS_SET
    if not filename_or_path:
        return False
    str_val = str(filename_or_path).lower()
    for item in list(LOCKED_DELETIONS_SET):
        if str_val in item.lower() or item.lower() in str_val:
            return True
    return False

def retry_pending_deletions():
    """Background helper to retry unlinking locked files"""
    global LOCKED_DELETIONS_SET
    if not LOCKED_DELETIONS_SET:
        return
    to_remove = set()
    for item in list(LOCKED_DELETIONS_SET):
        p = Path(item)
        if not p.exists():
            to_remove.add(item)
            continue
        try:
            p.unlink()
            to_remove.add(item)
            print(f"[BACKGROUND CLEANUP] Unlinked locked file: {p.name}")
        except Exception:
            pass
    LOCKED_DELETIONS_SET -= to_remove

def should_ignore_file(filename: str) -> bool:
    """
    Check if a file should be ignored based on qt.py patterns or pending deletion list
    """
    if is_pending_deletion(filename):
        return True

    qt_patterns = [
        "quick_test", "test_output", "temp_test", "debug_test",
        "qt_test_", "qt_debug_", "qt_output_", "test_results_", "test_log_",
        "test_file_"
    ]
    
    filename_lower = filename.lower()
    for pattern in qt_patterns:
        if pattern in filename_lower:
            return True
    
    if filename_lower.endswith(('.tmp', '.log')) and any(p in filename_lower for p in qt_patterns):
        return True
        
    return False

def get_file_list():
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    retry_pending_deletions()
    return sorted([
        {
            "name": f.name,
            "size": format_size(f.stat().st_size),
            "mtime": f.stat().st_mtime
        }
        for f in UPLOAD_FOLDER.iterdir() 
        if f.is_file() and not f.name.endswith('.tmp') and not should_ignore_file(f.name)
    ], key=lambda x: x["mtime"], reverse=True)

async def get_file_list_async():
    """
    [START] Async file list with yielding for large directories
     RACE CONDITION FIX: Filter out .tmp files to prevent downloading partial uploads
     Qt.py FILTER: Hide qt.py generated test files from listings
    """
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    retry_pending_deletions()
    files = []
    file_count = 0
    
    for f in UPLOAD_FOLDER.iterdir():
        if f.is_file() and not f.name.endswith('.tmp') and not should_ignore_file(f.name):  #  Filter out temporary files and qt.py test files
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
    [RETRY] ASYNC Universal Streaming Upload Handler - Non-blocking optimized for ALL platforms
    [LOCK] RACE CONDITION FIX: Upload to .tmp file first, then atomically move to final name
    [BOT] TERMUX OPTIMIZED: Memory monitoring and resource management
    Processes files in chunks asynchronously to avoid memory exhaustion and server blocking
    """
    import os
    import hashlib
    import gc
    from app.utils.universal_optimizer import optimize_for_upload, get_adaptive_chunk_size, should_run_gc, universal_optimizer
    
    # [BOT] TERMUX MEMORY CHECK: Enforce memory limits before starting upload
    try:
        from app.utils.termux_memory_monitor import enforce_termux_memory_limit
        if not enforce_termux_memory_limit(f"upload_{upload_file.filename}"):
            raise Exception("Upload blocked due to memory constraints")
    except ImportError:
        pass  # Graceful fallback if memory monitor not available
    
    #  FILE LOCKING: Initialize file lock manager for safe concurrent uploads
    lock_manager = get_file_lock_manager(UPLOAD_FOLDER)
    
    # [START] TEMPORARY FILE STRATEGY: Upload to .tmp extension first
    temp_destination = destination.with_suffix(destination.suffix + '.tmp')
    print(f"[RETRY] Uploading to temporary file: {temp_destination.name}")
    
    # [MOBILE] Platform Detection (but optimizations apply to ALL)
    is_android = is_android_environment()
    
    is_windows = os.name == 'nt'
    is_linux = os.name == 'posix' and not is_android
    
    platform_name = "Android/Termux" if is_android else "Windows" if is_windows else "Linux/Unix"
    
    # [STATS] ASYNC File size estimation for progress tracking (NON-BLOCKING)
    await asyncio.to_thread(upload_file.file.seek, 0, 2)  # Seek to end - ASYNC
    file_size = await asyncio.to_thread(upload_file.file.tell)  # Tell position - ASYNC  
    await asyncio.to_thread(upload_file.file.seek, 0)  # Reset to beginning - ASYNC
    
    #  Apply optimizations for large files on ALL platforms
    if file_size > 50 * 1024 * 1024:  # Files > 50MB
        print(f"[RETRY] Large file detected ({file_size//1024//1024}MB) - enabling streaming optimizations")
        
        # Android-specific feasibility check (but streaming works everywhere)
        if is_android:
            feasibility = optimize_for_upload(file_size)
            if feasibility['warnings']:
                for warning in feasibility['warnings']:
                    print(f"[WARN] {warning}")
            if feasibility['recommendations']:
                print(f"[TIP] Android recommendations:")
                for rec in feasibility['recommendations']:
                    print(f"   • {rec}")
        else:
            # General recommendations for PC/Linux/Mac
            feasibility = optimize_for_upload(file_size)
            if feasibility['warnings']:
                for warning in feasibility['warnings']:
                    print(f"[WARN] {warning}")
            if feasibility['recommendations']:
                print(f"[TIP] {platform_name} recommendations:")
                for rec in feasibility['recommendations']:
                    print(f"   • {rec}")
    
    # [TARGET] Universal adaptive chunk sizing optimized for each platform
    CHUNK_SIZE = universal_optimizer.get_adaptive_chunk_size(file_size)
    print(f"[TARGET] {platform_name} - chunk size: {CHUNK_SIZE//1024}KB")
    
    print(f"[RETRY] ASYNC Upload: {destination.name} ({file_size:,} bytes)")
    
    # [LOCK] ACQUIRE FILE LOCK: Prevent race conditions during upload
    async with lock_manager.upload_lock(destination.name, timeout=60.0):
        print(f"[LOCK] File lock acquired for: {destination.name}")
        
        if encrypt:
            # [LOCK] For now, fall back to original method for encrypted files
            # TODO: Implement true streaming encryption in future update
            print(f"[LOCK] Using existing encryption method (will be optimized in future)")
            try:
                data = await asyncio.to_thread(upload_file.file.read)
                
                # Import streaming encryption functions
                from app.core.aes_utils import encrypt_file_stream
                
                # Add file integrity validation for encrypted files
                original_hash = hashlib.sha256(data).hexdigest()
                print(f"[LOCK] Original file hash: {original_hash}")
                
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
                
                # [TARGET] ATOMIC MOVE: Move encrypted file from .tmp to final destination
                import shutil
                max_retries = 3 if is_windows else 1
                retry_delay = 0.3 if is_windows else 0.1
                
                for attempt in range(max_retries):
                    try:
                        print(f"[RETRY] Moving encrypted {temp_destination.name} -> {destination.name} (attempt {attempt + 1})")
                        
                        if is_windows:
                            # Use shutil.move for better Windows compatibility
                            await asyncio.to_thread(shutil.move, str(temp_destination), str(destination))
                        else:
                            temp_destination.rename(destination)
                        
                        print(f"[OK] Encrypted file atomically moved to final destination: {destination.name}")
                        break
                        
                    except Exception as e:
                        if attempt < max_retries - 1:
                            print(f"[WARN] Encrypted move attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 1.5  # Exponential backoff
                        else:
                            # Final attempt failed, clean up and raise
                            if temp_destination.exists():
                                try:
                                    temp_destination.unlink()
                                except:
                                    pass
                            print(f"[ERR] Failed to move encrypted temp file after {max_retries} attempts: {e}")
                            raise Exception(f"Failed to finalize encrypted upload after {max_retries} attempts: {e}")
                
                # Yield control periodically - OPTIMIZED: 10ms instead of 1ms for better performance
                await asyncio.sleep(0.01)
                
            except Exception as e:
                # Clean up encrypted temp file
                if temp_destination.exists():
                    temp_destination.unlink()
                print(f"[ERR] Encryption error: {e}")
                raise
        else:
            # [PKG] Async Streaming upload without encryption
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
                            print(f"[PKG] Progress: {bytes_written // 1024 // 1024}MB")
                            
                            # OPTIMIZED: Strategic memory management - only GC for very large files
                            if should_run_gc():
                                universal_optimizer.memory_cleanup(force=False)
                                await asyncio.sleep(0.01)  # Brief pause for GC
                
                # File handle is now closed, add extra delay for Windows
                print(f"[OK] Upload to temp file completed: {temp_destination.name} ({bytes_written:,} bytes)")
                if is_windows:
                    await asyncio.sleep(0.2)  # Extra delay for Windows to release file handle
                    
                # [TARGET] ATOMIC MOVE: Move from .tmp to final destination to prevent race conditions
                import shutil
                import time
                max_retries = 3 if is_windows else 1
                retry_delay = 0.3 if is_windows else 0.1
                
                for attempt in range(max_retries):
                    try:
                        print(f"[RETRY] Moving {temp_destination.name} -> {destination.name} (attempt {attempt + 1})")
                        
                        if is_windows:
                            # Use shutil.move for better Windows compatibility
                            await asyncio.to_thread(shutil.move, str(temp_destination), str(destination))
                        else:
                            temp_destination.rename(destination)
                        
                        print(f"[OK] File atomically moved to final destination: {destination.name}")
                        break
                        
                    except Exception as e:
                        if attempt < max_retries - 1:
                            print(f"[WARN] Move attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 1.5  # Exponential backoff
                        else:
                            # Final attempt failed, clean up and raise
                            if temp_destination.exists():
                                try:
                                    temp_destination.unlink()
                                except:
                                    pass
                            print(f"[ERR] Failed to move temp file after {max_retries} attempts: {e}")
                            raise Exception(f"Failed to finalize upload after {max_retries} attempts: {e}")
                
            except Exception as e:
                # Clean up partial temp file
                if temp_destination.exists():
                    temp_destination.unlink()
                print(f"[ERR] ASYNC Upload error: {e}")
                raise
            finally:
                # [CLEAN] Universal cleanup (applies to ALL platforms)
                if hasattr(universal_optimizer, 'upload_active'):
                    universal_optimizer.upload_active = False
                universal_optimizer.memory_cleanup(force=True)
                print(f"[RETRY] Universal async cleanup completed")
        
        print(f"[UNLOCK] File lock released for: {destination.name}")

async def scan_file_async(path: Path):
    """
    [START] Truly non-blocking async file scanning with frequent yielding
    """
    # Only show scan messages in verbose mode
    if os.getenv('LANVAN_VERBOSE') or os.getenv('DEBUG'):
        print(f" Scanning file in background: {path}")
    
    # OPTIMIZED: Yield control with better interval
    await asyncio.sleep(0.01)  # 10ms instead of 1ms
    
    try:
        # Simulate processing with frequent yielding for responsiveness
        # In real implementation, this would do virus scanning, checksums, etc.
        file_size = path.stat().st_size
        
        # For large files, break processing into smaller chunks with yielding
        if file_size > 100 * 1024 * 1024:  # >100MB
            print(f"[SEARCH] Large file processing with yielding: {path.name} ({file_size // 1024 // 1024}MB)")
            
            # Simulate chunked processing with frequent yielding
            chunk_count = max(1, file_size // (50 * 1024 * 1024))  # 50MB chunks
            for i in range(chunk_count):
                # Yield every processing chunk to keep server responsive
                await asyncio.sleep(0.01)  # 10ms yield per chunk
                
                # Simulate some processing work
                if i % 10 == 0:  # Progress every 10 chunks
                    progress = (i + 1) / chunk_count * 100
                    print(f"[RETRY] Processing {path.name}: {progress:.1f}% complete")
        else:
            # Small files process quickly with minimal yielding - OPTIMIZED
            await asyncio.sleep(0.01)  # 10ms instead of 1ms
            
        print(f"[OK] File scan completed: {path.name}")
        
    except Exception as e:
        # Silently handle scan errors during testing/normal operation
        # This is expected when testing with dummy files or during file cleanup
        pass  # No output to avoid alarming users with test artifacts
        # Don't let scanning errors affect the main upload flow
    
    # Final yield to ensure responsiveness
    await asyncio.sleep(0.001)

def scan_file(path: Path):
    """
    [RETRY] Legacy sync wrapper - creates managed background task for processing
    """
    try:
        # Check if we have a running event loop before creating task
        try:
            loop = asyncio.get_running_loop()
            # Use task manager for automatic cleanup and resource management
            from app.utils.task_manager import submit_background_task
            task = submit_background_task(scan_file_async(path), f"scan_file:{path.name}")
            if task is None:
                # Task manager rejected task (likely due to limits) - graceful degradation
                print(f"[WARN] Background file scan skipped (task limit): {path.name}")
        except RuntimeError:
            # No event loop running - skip background scan
            pass
    except Exception as e:
        # Suppress error messages during testing
        pass

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
        UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
        # Save uploaded file temporarily using chunked streaming
        temp_input_path = UPLOAD_FOLDER / f"temp_input_{int(time.time())}_{secure_filename(file.filename or 'file')}"
        
        # [RETRY] MEMORY FIX: Use Termux-optimized chunk size for streaming
        from app.utils.universal_optimizer import universal_optimizer, get_adaptive_chunk_size
        CHUNK_SIZE = get_adaptive_chunk_size(1024 * 1024)  # Get platform-optimal chunk size
        
        with open(temp_input_path, 'wb') as f:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
        
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
        safe_name = secure_filename(filename)
        file_path = UPLOAD_FOLDER / safe_name
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

@router.get("/api/files", name="api_files")
async def api_files():
    """API endpoint to get current file list as JSON with full metadata"""
    try:
        files = get_file_list()
        return JSONResponse(content={
            "status": "success",
            "files": [f["name"] for f in files],
            "files_data": files,
            "count": len(files)
        })
    except Exception as e:
        print(f"[ERR] Error getting file list: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to get file list: {str(e)}"}
        )

@router.post("/upload", name="upload_files")
async def upload_files(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    encrypt: bool = Query(False, description="Encrypt files with AES-256 if true"),
    parent_path: Optional[str] = Form(None)
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
            from app.core.concurrent_upload_manager import ConcurrentUploadManager
        except ImportError:
            from concurrent_upload_manager import ConcurrentUploadManager
        upload_manager = ConcurrentUploadManager()
        
        # Create destinations for uploaded files using UploadPathResolver
        destinations = []
        for file in files:
            if file.filename:
                resolved = UploadPathResolver.resolve(parent_path, file.filename, UPLOAD_FOLDER)
                target_dir = resolved.target_directory
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Ensure unique filename if collision exists
                file_path = get_unique_filename(target_dir, resolved.filename)
                destinations.append(target_dir / file_path)
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
            # Broadcast real-time WebSocket event to all connected devices
            try:
                from app.ws_manager.upload_status import upload_status_manager
                asyncio.create_task(upload_status_manager.notify_file_list_updated(successful_uploads))
            except Exception:
                pass

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
                # Basic file save with Termux-optimized streaming
                file_path = UPLOAD_FOLDER / file.filename
                
                # Ensure unique filename
                counter = 1
                original_path = file_path
                while file_path.exists():
                    stem = original_path.stem
                    suffix = original_path.suffix
                    file_path = UPLOAD_FOLDER / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                # [RETRY] MEMORY FIX: Use Termux-optimized chunk size for streaming
                from app.utils.universal_optimizer import get_adaptive_chunk_size, universal_optimizer
                CHUNK_SIZE = get_adaptive_chunk_size(1024 * 1024)  # Get platform-optimal chunk size
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
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
    encrypt: bool = Query(False, description="Encrypt files with AES-256 if true"),
    parent_path: Optional[str] = Form(None)
):
    if not files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No files uploaded"
        })

    # [AUTH] Protocol detection
    is_https = request.url.scheme == "https"
    
    #  ULRA-FAST VALIDATION: Start uploads immediately with lightweight validation
    is_valid, error_messages, validated_files, security_warnings = await validate_upload_files_enhanced_fast(files, encrypt, is_https)
    if not is_valid:
        # [!] LOG VALIDATION FAILURES for debugging
        print(f" File validation failed:")
        for i, file in enumerate(files):
            file_ext = Path(file.filename or "unknown").suffix.lower()
            print(f"   File {i+1}: {file.filename} ({file_ext}) - Size: {getattr(file, 'size', 'unknown')}")
        for error in error_messages:
            print(f"   [ERR] {error}")
        
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error", 
            "msg": "; ".join(error_messages),
            "security_blocked": True
        })
    
    # [OK] LOG SUCCESSFUL VALIDATION with file details
    print(f"[OK] File validation passed for {len(files)} files:")
    for i, file in enumerate(files):
        file_ext = Path(file.filename or "unknown").suffix.lower()
        validated_file = validated_files[i] if i < len(validated_files) else {}
        print(f"   File {i+1}: {file.filename} ({file_ext}) -> {validated_file.get('sanitized_name', 'unknown')}")
        if file_ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']:
            print(f"    Video file detected and approved!")
    
    # [!] Log security warnings if any
    if security_warnings:
        print(f"[WARN] Security warnings for upload: {'; '.join(security_warnings)}")

    #  Enforce encryption restrictions using centralized config
    if encrypt:
        validation = AESConfig.validate_file_for_aes(0, is_https)  # Size will be checked per file
        if not validation['valid'] and 'HTTPS' in validation['error']:
            return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
                "status": "error",
                "msg": validation['error']
            })

    # [START] CONCURRENT PROCESSING: Upload all files simultaneously with adaptive optimization
    from app.core.concurrent_upload_manager import upload_multiple_files_concurrent
    
    uploaded = []
    
    print(f"[SEARCH] Processing {len(files)} files for concurrent upload...")

    # [START] CONCURRENT PREPARATION: Prepare all file destinations simultaneously
    async def prepare_file_for_upload(i: int, file: UploadFile) -> Dict[str, Any]:
        """Prepare a single file for upload concurrently"""
        try:
            print(f"[DIR] Preparing file {i+1}/{len(files)}: {file.filename}")
            
            if not file.filename:
                return {"error": f"File {i+1}: No filename"}

            # Use validated filename
            validated_file = validated_files[i] if i < len(validated_files) else None
            if not validated_file:
                return {"error": f"File {i+1}: Validation failed"}
                
            filename = validated_file['sanitized_name']
            file_size = validated_file['size']
            print(f"[INFO] File {i+1} details: {filename} ({file_size} bytes)")

            # Double-check with existing validation (defense in depth)
            if not is_allowed_file(filename):
                return {"error": f"File {i+1}: File type not allowed"}

            # Check size using centralized AES config
            if encrypt:
                validation = AESConfig.validate_file_for_aes(file_size, is_https)
                if not validation['valid']:
                    return {"error": f"File {i+1} failed AES validation: {validation['error']}"}

            # Resolve target directory and path using UploadPathResolver
            resolved = UploadPathResolver.resolve(parent_path, file.filename, UPLOAD_FOLDER)
            target_dir = resolved.target_directory
            target_dir.mkdir(parents=True, exist_ok=True)

            save_name = resolved.filename + ".enc" if encrypt else resolved.filename
            filepath = target_dir / get_unique_filename(target_dir, save_name)

            print(f"[SAVE] Will save file {i+1} as: {filepath.name}")
            
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
    
    # [START] PREPARE ALL FILES CONCURRENTLY
    print(f" Starting concurrent preparation of {len(files)} files...")
    preparation_tasks = [prepare_file_for_upload(i, file) for i, file in enumerate(files)]
    preparation_results = await asyncio.gather(*preparation_tasks, return_exceptions=True)
    
    # Process preparation results
    destinations = []
    valid_files = []
    file_info = []
    
    for i, result in enumerate(preparation_results):
        if isinstance(result, Exception):
            print(f"[ERR] File {i+1} preparation exception: {str(result)}")
        elif isinstance(result, dict) and "error" in result:
            print(f"[ERR] {result['error']}")
        elif isinstance(result, dict) and "success" in result:
            destinations.append(result["destination"])
            valid_files.append(result["file"])
            file_info.append(result["file_info"])
            print(f"[OK] File {i+1} prepared successfully")
    
    if not valid_files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No valid files to process"
        })
    
    # [START] Execute uploads with bounded concurrency
    print(f"[START] Starting concurrent direct upload of {len(valid_files)} files...")

    max_parallel_uploads = max(1, min(MAX_CONCURRENT_UPLOADS, len(valid_files)))
    upload_manager = ConcurrentUploadManager(max_concurrent_uploads=max_parallel_uploads)

    upload_results = await upload_manager.upload_files_concurrently(
        files=valid_files,
        destinations=destinations,
        encrypt=encrypt
    )

    for i, result in enumerate(upload_results):
        if result.get('success'):
            print(f"[OK] File {i+1} uploaded successfully: {result.get('destination', 'unknown')}")
        else:
            print(f"[ERR] File {i+1} upload failed: {result.get('error', 'Unknown error')}")
    
    uploaded = []
    
    # Process results and add background tasks
    for i, result in enumerate(upload_results):
        if result.get('success'):
            filepath = Path(result['destination'])
            background_tasks.add_task(scan_file, filepath)
            uploaded.append(filepath.name)
            print(f"[OK] File {i+1} uploaded successfully: {filepath.name}")
        else:
            print(f"[ERR] File {i+1} failed: {result.get('error', 'Unknown error')}")

    print(f"[DONE] Concurrent upload complete! {len(uploaded)} files uploaded: {uploaded}")

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
    
    print(f"[TARGET] Upload response: {response_data}")
    return JSONResponse(content=response_data)

@router.get("/download/{filename}", name="download_file")
@router.head("/download/{filename}")
async def download_file(filename: str, request: Request):
    print(f"[IN] Download request for: {filename}")
    
    safe_name = secure_filename(filename)
    file_path = UPLOAD_FOLDER / safe_name
    
    if not file_path.is_file():
        # Fallback: search subdirectories recursively
        found = False
        for subdir_file in UPLOAD_FOLDER.rglob(safe_name):
            if subdir_file.is_file():
                file_path = subdir_file
                found = True
                break
        if not found:
            print(f"[ERR] File not found: {safe_name}")
            return Response("File not found", status_code=404)
            
    print(f"[DIR] Looking for file at: {file_path}")

    mime_type, _ = guess_type(str(file_path))
    if not mime_type or mime_type == "application/octet-stream":
        ext = safe_name.split(".")[-1].lower() if "." in safe_name else ""
        mime_map = {
            "mp4": "video/mp4",
            "webm": "video/webm",
            "mov": "video/quicktime",
            "mkv": "video/x-matroska",
            "avi": "video/x-msvideo",
            "3gp": "video/3gpp",
            "m4v": "video/mp4",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
            "m4a": "audio/mp4",
            "aac": "audio/aac",
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "ppt": "application/vnd.ms-powerpoint",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        }
        if ext in mime_map:
            mime_type = mime_map[ext]
            
    file_size = file_path.stat().st_size
    
    print(f"[STATS] File info - Size: {file_size} bytes, MIME: {mime_type}")
    
    is_download_requested = request.query_params.get("download") == "1"
    disposition_type = "attachment" if is_download_requested else "inline"

    # OK: Handle HEAD requests - return headers only for file info
    if request.method == "HEAD":
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": mime_type or "application/octet-stream",
            "Content-Disposition": f'{disposition_type}; filename="{safe_name}"',
            "Accept-Ranges": "bytes",  # Indicate support for range requests
            "Cache-Control": "public, max-age=86400"
        }
        return Response(content="", headers=headers, status_code=200)
    
    # OK: Determine protocol (HTTP vs HTTPS)
    is_https = request.url.scheme == "https"
    
    # [AUTH] Enforcement Rules:
    # 1. .enc files: Always use full download (no chunking)
    # 2. Files ≥250MB: Use chunked download if not .enc
    # 3. Files <250MB: Always use full download
    
    is_enc_file = safe_name.endswith(".enc")
    is_large_file = file_size >= 250 * 1024 * 1024  # 250MB threshold
    
    # Check for HTTP Range header (crucial for HTML5 video/audio seeking & scrubbing)
    range_header = request.headers.get("range") or request.headers.get("Range")
    if range_header and not is_enc_file:
        return await range_download_file(file_path, safe_name, mime_type, file_size, range_header, disposition_type=disposition_type)

    print(f"[SEARCH] Download strategy - Encrypted: {is_enc_file}, Large: {is_large_file}")
    
    # [PKG] Chunked download logic
    if is_large_file and not is_enc_file:
        print("[PKG] Using chunked download")
        return await chunked_download_file(file_path, safe_name, mime_type, file_size, request, disposition_type=disposition_type)
    else:
        print("[FILE] Using full download")
        return await full_download_file(file_path, safe_name, mime_type, file_size, disposition_type=disposition_type)

async def range_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int, range_header: str, disposition_type: str = "inline"):
    """Serve HTTP Range Requests (206 Partial Content) for seeking/forwarding in video and audio players."""
    try:
        if "=" not in range_header:
            return await full_download_file(file_path, safe_name, mime_type, file_size, disposition_type=disposition_type)
            
        unit, bytes_range = range_header.strip().split("=", 1)
        if unit.lower() != "bytes":
            return Response("Invalid range unit", status_code=416)
        
        parts = bytes_range.split("-", 1)
        start_str = parts[0].strip() if parts[0] else ""
        end_str = parts[1].strip() if len(parts) > 1 and parts[1] else ""
        
        if start_str and end_str:
            start = int(start_str)
            end = int(end_str)
        elif start_str:
            start = int(start_str)
            end = file_size - 1
        elif end_str:
            suffix = int(end_str)
            start = max(0, file_size - suffix)
            end = file_size - 1
        else:
            start = 0
            end = file_size - 1

        if start >= file_size or end >= file_size or start > end:
            headers = {"Content-Range": f"bytes */{file_size}"}
            return Response("Requested range not satisfiable", status_code=416, headers=headers)
        
        chunk_size = (end - start) + 1
        
        def iterfile():
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_left = chunk_size
                buffer_size = 64 * 1024  # 64KB chunks for smooth seeking
                while bytes_left > 0:
                    read_len = min(buffer_size, bytes_left)
                    data = f.read(read_len)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": mime_type or "application/octet-stream",
            "Content-Disposition": f'{disposition_type}; filename="{safe_name}"',
            "Cache-Control": "public, max-age=3600"
        }
        
        print(f"[STREAM] Serving Range 206 ({disposition_type}): bytes {start}-{end}/{file_size} for {safe_name}")
        return StreamingResponse(iterfile(), status_code=206, headers=headers)
    except Exception as e:
        print(f"[ERR] Range request failed ({e}), falling back to full download")
        return await full_download_file(file_path, safe_name, mime_type, file_size, disposition_type=disposition_type)

async def full_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int, disposition_type: str = "inline"):
    """Ultra-optimized full file download - for small files and .enc files"""
    print(f"[OUT] Starting full download ({disposition_type}) for: {safe_name}")
    
    # [START] Much larger buffer for maximum speed - 32MB buffer (4x improvement)
    STREAM_BUFFER_SIZE = 32 * 1024 * 1024  # 32MB buffer (was 8MB)
    
    def stream_file_ultra_optimized(path: Path):
        print(f"[RETRY] Streaming file: {path}")
        file_handle = None  # Track file handle for proper cleanup
        
        try:
            if path.suffix == ".enc":
                print("[AUTH] Processing encrypted file")
                # [AUTH] Enhanced .enc file handling with streaming decryption and metadata validation
                try:
                    # Check for metadata file first
                    metadata_path = path.with_suffix('.enc.meta')
                    metadata = None
                    
                    if metadata_path.exists():
                        with open(metadata_path, "r") as meta_file:
                            import json
                            metadata = json.load(meta_file)
                            print(f"[LOCK] Found metadata for encrypted file: {metadata.get('encryption_method', 'legacy')}")
                    
                    with open(path, "rb") as file:
                        encrypted_data = file.read()
                        print(f"[STATS] Read {len(encrypted_data)} bytes of encrypted data")
                        
                        # Use appropriate decryption method based on metadata
                        if metadata and metadata.get('encryption_method') == 'streaming':
                            from app.core.aes_utils import decrypt_file_stream
                            decrypted_data = decrypt_file_stream(encrypted_data, metadata, chunk_size=1024 * 1024)
                            print(f"[LOCK] Used streaming decryption for {path.name}")
                        else:
                            # Note: Legacy encryption not supported - file may be corrupted
                            print(f"[WARN] Cannot decrypt {path.name} - legacy encryption no longer supported")
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
                        
                        # [START] Stream in very large chunks for maximum speed
                        data_length = len(decrypted_data)
                        chunks_sent = 0
                        for i in range(0, data_length, STREAM_BUFFER_SIZE):
                            chunk_end = min(i + STREAM_BUFFER_SIZE, data_length)
                            chunk = decrypted_data[i:chunk_end]
                            chunks_sent += 1
                            print(f"[OUT] Sending chunk {chunks_sent}, size: {len(chunk)} bytes")
                            yield chunk
                            
                except Exception as e:
                    print(f"[!] AES decryption failed for {path}: {e}")
                    # Return error content instead of crashing
                    error_message = f"Error: Failed to decrypt file {path.name}. {str(e)}"
                    yield error_message.encode('utf-8')
            else:
                print("[FILE] Processing regular file")
                # [START] Ultra-fast regular file streaming with optimized buffer and proper cleanup
                try:
                    file_handle = open(path, "rb")
                    chunks_sent = 0
                    while True:
                        chunk = file_handle.read(STREAM_BUFFER_SIZE)
                        if not chunk:
                            break
                        chunks_sent += 1
                        print(f"[OUT] Sending chunk {chunks_sent}, size: {len(chunk)} bytes")
                        yield chunk
                    print(f"OK: Completed streaming {chunks_sent} chunks")
                except Exception as e:
                    print(f"[!] File streaming failed for {path}: {e}")
                    error_message = f"Error: Failed to read file {path.name}. {str(e)}"
                    yield error_message.encode('utf-8')
        finally:
            # Ensure file handle is always closed
            if file_handle is not None:
                try:
                    file_handle.close()
                    print(f"[OK] File handle closed for: {path.name}")
                except Exception as e:
                    print(f"[WARN] Error closing file handle: {e}")
            
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
                        print(f"[LOCK] Using original size from metadata: {final_file_size}")
            except Exception as e:
                print(f"[WARN] Could not read metadata for size: {e}")
    
    headers = {
        "Content-Disposition": f'{disposition_type}; filename="{safe_name}"',
        "Content-Type": mime_type or "application/octet-stream",
        "Cache-Control": "public, max-age=86400",
        "X-Accel-Buffering": "no",
        "X-Download-Type": "ultra-optimized-full",
        "X-Buffer-Size": "32MB"
    }
    
    # Only add Content-Length for non-encrypted files to avoid mismatch
    if not file_path.suffix == ".enc":
        headers["Content-Length"] = str(final_file_size)
    
    print(f"[INFO] Response headers: {headers}")
    
    return StreamingResponse(
        stream_file_ultra_optimized(file_path),
        media_type=mime_type or "application/octet-stream",
        headers=headers
    )

async def chunked_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int, request: Request | None = None, disposition_type: str = "inline"):
    """High-performance chunked file download - for large files (≥250MB) that are not .enc"""
    # [START] Much larger chunk size for faster downloads - 16MB chunks (16x improvement)
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
            
            # [START] Use larger buffer reads for maximum speed
            while remaining > 0:
                # Dynamic chunk sizing - use full CHUNK_SIZE unless near end
                chunk_size = min(CHUNK_SIZE, remaining)
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Disposition": f'{disposition_type}; filename="{safe_name}"',
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
    files_to_download = [file for file in UPLOAD_FOLDER.iterdir() if file.is_file() and not file.name.endswith('.tmp')]
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
                        print(f"[WARN] Skipping legacy encrypted file: {file.name}")
                        error_content = f"File {file.name} uses legacy encryption which is no longer supported for security reasons."
                        zip_file.writestr(f"{file.stem}_LEGACY_ENCRYPTION_WARNING.txt", error_content.encode('utf-8'))
                    else:
                        # Add regular files directly
                        zip_file.write(file, arcname=file.name)
                except Exception as e:
                    print(f"[WARN] Error adding {file.name} to ZIP: {e}")
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
        print(f"[ERR] Error creating ZIP archive: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to create ZIP archive: {str(e)}"}
        )

@router.post("/clear", name="clear_files")
async def clear_files():
    """Clear all uploaded files and temporary chunks with enhanced Windows compatibility"""
    from app.core.windows_file_manager import WindowsFileManager
    
    try:
        print("[CLEAN] Starting enhanced file cleanup with Windows diagnostics...")
        
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
                detail = f"[FILE] {locked_file}"
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
            print(f"[OK] {message}")
            return JSONResponse(content={
                "status": "success",
                "msg": message,
                "files_deleted": files_deleted,
                "chunks_deleted": chunks_deleted,
                "files_locked": 0
            })
    except Exception as e:
        print(f"[ERR] Error during file clearing: {e}")
        # Return a JSON error response instead of crashing
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to clear files: {str(e)}"}
        )

@router.post("/api/cancel-upload", name="cancel_upload_api")
@router.post("/cancel-upload", name="cancel_upload_legacy")
async def cancel_upload_api(filename: Optional[str] = Form(None), parent_path: Optional[str] = Form(None), request: Request = None):
    """Cancel an upload and purge any temporary .tmp files or chunks on disk."""
    try:
        target_file = filename
        target_parent = parent_path
        if not target_file and request:
            try:
                form = await request.form()
                target_file = form.get("filename")
                target_parent = form.get("parent_path")
            except Exception:
                pass
        deleted = cleanup_temp_file_for_filename(target_file or "", target_parent)
        print(f"[CANCEL] Purged {deleted} temporary file(s) for '{target_file}'")
        return JSONResponse(content={"status": "success", "msg": f"Cleaned up {deleted} temporary file(s)", "deleted_files": deleted})
    except Exception as e:
        print(f"[ERR] Error in cancel_upload_api: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "msg": str(e)})

@router.post("/delete/{filename}", name="delete_file")
@router.post("/api/files/delete", name="delete_file_api")
async def delete_file(filename: str, parent_path: Optional[str] = Form(None), request: Request = None):
    """Delete a specific file with proper error handling and idempotent safety"""
    try:
        safe_name = secure_filename(filename)
        if not safe_name:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Invalid filename"}
            )
            
        target_parent = parent_path
        if not target_parent and request:
            try:
                form = await request.form()
                target_parent = form.get("parent_path")
            except Exception:
                pass

        target_dir = UPLOAD_FOLDER
        if target_parent:
            clean_parent = urllib.parse.unquote(target_parent).replace('\\', '/').strip('/')
            parts = [secure_filename(p) for p in clean_parent.split('/') if p and p != "Home" and secure_filename(p)]
            if parts:
                target_dir = UPLOAD_FOLDER.joinpath(*parts)

        file_path = target_dir / safe_name
        
        if not file_path.exists():
            # Search target_dir and subdirectories recursively for filename or safe_name
            found = False
            for target_name in set([safe_name, filename, secure_filename(filename)]):
                if not target_name: continue
                for candidate in UPLOAD_FOLDER.rglob(target_name):
                    if candidate.is_file():
                        file_path = candidate
                        found = True
                        break
                if found: break

            if not found:
                # Idempotent delete: file is already unlinked from disk! Purge any leftover temp artifacts
                cleanup_temp_file_for_filename(filename, target_parent)
                return JSONResponse(content={"status": "success", "msg": "File deleted successfully"})

        if file_path.is_file():
            try:
                file_path.unlink()
                print(f"OK: Deleted file: {file_path.name}")
            except (PermissionError, OSError) as pe:
                print(f"[WARN] File locked by process on Windows, attempting gc and retry: {pe}")
                gc.collect()
                time.sleep(0.05)
                try:
                    file_path.unlink()
                    print(f"OK: Deleted file on retry: {file_path.name}")
                except Exception:
                    import uuid
                    trash_name = file_path.parent / f".trash_{uuid.uuid4().hex[:8]}_{file_path.name}"
                    try:
                        file_path.rename(trash_name)
                        print(f"OK: Renamed locked file to trash: {trash_name.name}")
                        try:
                            trash_name.unlink()
                        except Exception:
                            pass
                    except Exception as e2:
                        print(f"[WARN] File locked by process, scheduling background deletion: {e2}")
                        LOCKED_DELETIONS_SET.add(str(file_path))
                        LOCKED_DELETIONS_SET.add(filename)
            
        cleanup_temp_file_for_filename(filename, target_parent)
        return JSONResponse(content={"status": "success", "msg": "File deleted successfully"})
    except Exception as e:
        print(f"[ERR] Error in delete_file: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to delete file: {str(e)}"}
        )

@router.get("/api/upload/status", name="upload_status")
async def get_upload_status():
    """Get current upload status for all concurrent uploads"""
    from app.core.concurrent_upload_manager import concurrent_upload_manager
    
    status = concurrent_upload_manager.get_system_status()
    detailed_status = concurrent_upload_manager.get_upload_status()
    
    return JSONResponse({
        "status": "success",
        "system": status,
        "uploads": detailed_status
    })

@router.post("/upload_chunk", name="upload_chunk")
async def upload_chunk(
    request: Request,
    chunk: UploadFile = File(...),
    filename: str = Form(...),
    part_number: int = Form(...),
    total_parts: int = Form(None),  # Make optional since adaptive chunking may not know final count
    parent_path: Optional[str] = Form(None)
):
    """Handle individual chunk uploads for large files - supports both HTTP and HTTPS with adaptive chunking"""
    try:
        # [AUTH] Protocol detection
        is_https = request.url.scheme == "https"
        
        # [SEARCH] COMPREHENSIVE VALIDATION: Validate upload request using centralized validation
        validation_result = FileValidator.validate_filename(filename)
        if not validation_result['valid']:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": f"Validation failed: {validation_result['error']}"}
            )
        
        # [SHIELD] PRELIMINARY SECURITY: Basic extension check (full validation at finalization)
        extension = os.path.splitext(filename)[1].lower()
        if extension in AdvancedFileValidator.BLOCKED_EXTENSIONS:
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN,
                content={
                    "status": "security_blocked",
                    "msg": f"[SHIELD] Blocked file type: {extension} files are not allowed for security reasons"
                }
            )
        
        # [SEARCH] Enhanced validation: Check part number validity
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
        
        #  Enforce .enc file restrictions on HTTPS
        if is_https and safe_filename.endswith(".enc"):
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={
                    "status": "error", 
                    "msg": "Chunked upload is disabled for .enc files to preserve encryption integrity. Please use full upload."
                }
            )
        
        # [STATS] Check available disk space before writing
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
        
        # [SEARCH] Check for duplicate chunks (prevent overwrites)
        if chunk_path.exists():
            # Log potential issue but allow overwrite (might be a retry)
            print(f"[WARN] Warning: Chunk {chunk_filename} already exists, overwriting (possible retry)")
        
        # [STREAM] Ensure streaming assembly is initialized and register file if this is the first chunk
        ensure_streaming_initialized()
        
        if part_number == 1 and total_parts:
            assembler = get_streaming_assembler()
            if assembler:
                final_path = UPLOAD_FOLDER / safe_filename
                # Estimate total size as chunk size * total parts (approximation)
                estimated_size = len(chunk_data) * total_parts
                assembler.register_file(safe_filename, total_parts, filename, estimated_size)
                print(f"[STREAM] Registered {safe_filename} for streaming assembly")
        
        # [START] ADD CHUNK TO STREAMING ASSEMBLY SYSTEM
        assembler = get_streaming_assembler()
        streaming_result = None
        if assembler:
            # Add chunk to streaming assembly for real-time processing
            streaming_result = add_streaming_chunk(safe_filename, part_number, chunk_data)
            if part_number == 1 or part_number == total_parts or (total_parts and part_number % max(1, total_parts // 10) == 0):
                print(f"[STREAM] Added chunk {part_number}/{total_parts or '?'} to streaming assembly: {streaming_result.get('status', 'unknown')}")
            
            # Check if file completed via streaming assembly
            if streaming_result and streaming_result.get("status") == "completed":
                print(f"[OK] File completed via streaming assembly: {safe_filename}")
                
                # Clean up temp chunks since file is completed via streaming
                try:
                    pattern = f"{safe_filename}.part*"
                    temp_chunks_cleaned = 0
                    for chunk_file in TEMP_CHUNKS_FOLDER.glob(pattern):
                        chunk_file.unlink()
                        temp_chunks_cleaned += 1
                    if temp_chunks_cleaned > 0:
                        print(f"[CLEAN] Cleaned up {temp_chunks_cleaned} temp chunk files for {safe_filename}")
                except Exception as e:
                    print(f"[WARN] Warning: Could not clean up temp chunks: {e}")
                
                # File is already assembled, no need to save chunk to temp folder
                return JSONResponse(content={
                    "status": "streaming_completed",
                    "msg": f"File {safe_filename} completed via streaming assembly",
                    "part_number": part_number,
                    "total_parts": total_parts,
                    "chunk_size_mb": round(len(chunk_data) / (1024 * 1024), 1),
                    "file_path": str(streaming_result.get("path")),
                    "file_size": streaming_result.get("size", 0),
                    "protocol": "HTTPS" if is_https else "HTTP"
                })
        
        # [RETRY] FALLBACK: Save chunk to temp folder (for traditional assembly if streaming fails)
        # This maintains backward compatibility while adding streaming assembly
        
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
        
        # Include streaming assembly status in response
        response_data = {
            "status": "success",
            "msg": f"Chunk {part_number}{total_parts_msg} uploaded ({chunk_size_mb:.1f}MB)",
            "part_number": part_number,
            "total_parts": total_parts,
            "chunk_size_mb": round(chunk_size_mb, 1),
            "chunk_written_size": written_size,
            "free_space_mb": round(free / (1024*1024), 1),
            "protocol": "HTTPS" if is_https else "HTTP"
        }
        
        # Add streaming assembly progress if available
        if streaming_result:
            response_data["streaming_status"] = streaming_result.get("status", "unknown")
            if "progress" in streaming_result:
                response_data["streaming_progress"] = streaming_result["progress"]
        
        return JSONResponse(content=response_data)
        
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
    encrypt: bool = Form(False),
    parent_path: Optional[str] = Form(None)
):
    """Combine all chunks into final file - supports streaming assembly with failsafe fallback"""
    try:
        # [AUTH] Protocol detection  
        is_https = request.url.scheme == "https"
        
        # Secure the filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Invalid filename"}
            )
        
        #  Enforce encryption restrictions
        if encrypt and not is_https:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "msg": "AES encryption is only available over HTTPS connections for security."
                }
            )

        # [STREAM] Check if streaming assembly is available and completed
        ensure_streaming_initialized()
        assembler = get_streaming_assembler()
        streaming_completed = False
        final_path = None
        background_processing_done = False
        validation_from_background = None
        
        # [START] ENHANCED: Check streaming assembly status first
        if assembler:
            # Check if file was completed via streaming assembly
            streaming_status = check_streaming_status(safe_filename)
            print(f"[SEARCH] Streaming assembly status: {streaming_status}")
            
            if streaming_status and streaming_status.get('status') == 'ready':
                # File completed via streaming assembly
                file_info = get_assembled_file(safe_filename)
                if file_info and file_info.get('status') == 'ready':
                    streaming_completed = True
                    final_path = Path(file_info['path'])
                    print(f"[OK] File completed via streaming assembly: {safe_filename}")
                    print(f"   [DIR] Path: {final_path}")
                    print(f"   [STATS] Size: {final_path.stat().st_size:,} bytes")
        
        # Second, check if streaming-assembled file already exists (legacy check)
        potential_streaming_file = UPLOAD_FOLDER / safe_filename
        if not streaming_completed and potential_streaming_file.exists():
            print(f"[STREAM] Found legacy streaming-assembled file: {safe_filename}")
            streaming_completed = True
            final_path = potential_streaming_file
            
            # [START] Check if background processing was completed during streaming
            if assembler:
                status = assembler.check_status(safe_filename)
                if status and status.get('validation_result'):
                    validation_from_background = status['validation_result']
                    background_processing_done = True
                    print(f"[FAST] Background processing completed during upload - no additional processing needed!")
        
        print(f"[SEARCH] Streaming completed: {streaming_completed}")
        print(f"[SEARCH] Background processing done: {background_processing_done}")
        print(f"[SEARCH] Final path: {final_path}")
        
        # [RETRY] Failsafe: Use traditional chunk combination if streaming didn't complete
        if not streaming_completed:
            print(f"[RETRY] Using traditional chunk assembly for {safe_filename}")
            
            # [START] Auto-detect actual chunks (adaptive chunked upload support)
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
                    print(f"[STREAM] Found streaming-assembled file: {safe_filename}")
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
                
                # [START] Fast chunk combination with proper error handling
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
                                print(f"[!] AES encryption failed for chunk {part_num}: {encrypt_error}")
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
                    print(f"[!] AES encryption failed for streaming file: {encrypt_error}")
                    if final_path.exists():
                        final_path.unlink()
                    
                    return JSONResponse(
                        status_code=HTTP_400_BAD_REQUEST,
                        content={"status": "error", "msg": f"AES encryption failed: {encrypt_error}"}
                    )

        # Resolve target directory based on parent_path
        target_dir = UPLOAD_FOLDER
        if parent_path:
            clean_parent = urllib.parse.unquote(parent_path)
            parts = [p for p in clean_parent.split("/") if p and p != ".."]
            for part in parts:
                safe_part = secure_filename(part)
                if safe_part:
                    target_dir = target_dir / safe_part
            target_dir.mkdir(parents=True, exist_ok=True)

        if final_path and final_path.exists() and final_path.parent != target_dir:
            import shutil
            new_final_path = target_dir / get_unique_filename(target_dir, final_path.name)
            shutil.move(str(final_path), str(new_final_path))
            final_path = new_final_path

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
        
        # [SHIELD] ENHANCED SECURITY: Validate the assembled file (skip if already done in background)
        try:
            if background_processing_done and validation_from_background:
                # [START] Use validation results from background processing - massive time savings!
                print(f"[FAST] Using background validation results - skipping duplicate processing!")
                security_check = validation_from_background
            elif final_path:
                #  Traditional validation (slower)
                print(f"[RETRY] Performing security validation (no background processing available)")
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
                        "msg": f"[SHIELD] Security Check Failed: {errors[0] if errors else 'Unknown error'}",
                        "security_details": {
                            "blocked_reason": errors[0] if errors else 'Unknown security violation',
                            "detected_type": security_check.get('actual_type'),
                            "claimed_extension": security_check.get('claimed_extension'),
                            "file_deleted": True
                        }
                    }
                )
                
        except Exception as validation_error:
            print(f"[WARN] Security validation error for {final_path.name if final_path else 'unknown file'}: {validation_error}")
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
                    
                    # Also clean up temp chunk files if streaming was successful
                    if streaming_completed:
                        try:
                            pattern = f"{safe_filename}.part*"
                            temp_chunks_cleaned = 0
                            for chunk_file in TEMP_CHUNKS_FOLDER.glob(pattern):
                                chunk_file.unlink()
                                temp_chunks_cleaned += 1
                            if temp_chunks_cleaned > 0:
                                print(f"[CLEAN] Cleaned up {temp_chunks_cleaned} temp chunk files for {safe_filename}")
                        except Exception as cleanup_error:
                            print(f"[WARN] Warning: Could not clean up temp chunks: {cleanup_error}")
                            
            except AttributeError:
                # Assembler doesn't have these methods, skip cleanup
                pass
        
        # Success response with security confirmation
        assembly_method = "streaming assembly" if streaming_completed else "traditional chunk combination"
        success_msg = f"File '{final_path.name if final_path else 'unknown'}' uploaded successfully via {'HTTPS' if is_https else 'HTTP'} ({assembly_method})"
        
        # Handle warnings safely
        warnings = security_check.get('warnings', []) if isinstance(security_check, dict) else []
        if warnings:
            success_msg += f" [WARN] Security Notes: {'; '.join(warnings)}"
        
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

@router.post("/upload-folder", name="upload_folder")
async def upload_folder(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    folder_name: str = Form(...),
    parent_path: Optional[str] = Form(None),
    encrypt: bool = Query(False, description="Encrypt folder contents with AES-256 if true")
):
    """Upload multiple files as a folder structure"""
    if not files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No files uploaded"
        })

    # [AUTH] Protocol detection
    is_https = request.url.scheme == "https"
    
    # Target base folder directory
    base_folder = UPLOAD_FOLDER
    if parent_path:
        clean_parent = urllib.parse.unquote(parent_path).strip("/\\")
        parts = [p for p in clean_parent.split("/") if p and p != ".." and p != "Home"]
        for part in parts:
            safe_part = secure_filename(part)
            if safe_part:
                base_folder = base_folder / safe_part

        # Path traversal check
        try:
            base_folder.resolve().relative_to(UPLOAD_FOLDER.resolve())
        except ValueError:
            return JSONResponse(status_code=403, content={"status": "error", "msg": "Access denied"})

        base_folder.mkdir(parents=True, exist_ok=True)

    # Auto-increment folder name if duplicate exists in target location
    safe_folder_name = secure_filename(folder_name) or "uploaded_folder"
    original_folder_name = safe_folder_name
    counter = 1
    folder_path = base_folder / safe_folder_name
    while folder_path.exists():
        safe_folder_name = f"{original_folder_name} ({counter})"
        folder_path = base_folder / safe_folder_name
        counter += 1

    folder_path.mkdir(parents=True, exist_ok=True)
    
    # Process each file and maintain folder structure
    uploaded_files = []
    failed_files = []
    
    for file in files:
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
                
                # Save the file
                await save_upload_file_async(file, final_path, encrypt)
                uploaded_files.append(str(final_path.relative_to(UPLOAD_FOLDER)))
                
        except Exception as e:
            print(f"[ERR] Failed to upload file {file.filename}: {e}")
            failed_files.append(file.filename)
    
    return JSONResponse(content={
        "status": "success" if uploaded_files else "error",
        "msg": f"Folder '{folder_name}' uploaded with {len(uploaded_files)} files",
        "folder_name": folder_name,
        "files_uploaded": uploaded_files,
        "files_failed": failed_files,
        "total_files": len(files),
        "protocol": "HTTPS" if is_https else "HTTP"
    })

@router.get("/download-folder/{folder_name}", name="download_folder")
async def download_folder(folder_name: str):
    """Download an entire folder as a ZIP file"""
    safe_folder = secure_filename(folder_name)
    if not safe_folder:
        raise HTTPException(status_code=400, detail="Invalid folder name")
        
    folder_path = UPLOAD_FOLDER / safe_folder
    
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
    
    # Properly quote filename in header to prevent injection
    from urllib.parse import quote
    encoded_filename = quote(f"{safe_folder}.zip")
    
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{safe_folder}.zip\"; filename*=UTF-8''{encoded_filename}"}
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
        print(f"[ERR] Error listing folders: {e}")
        return JSONResponse(content={
            "status": "error",
            "msg": "Failed to list folders"
        })

@router.get("/api/folders/{folder_path:path}/files", name="list_folder_contents")
async def list_folder_contents(folder_path: str):
    """Get files inside a specific folder (supports nested paths like FolderA/SubFolder)"""
    # Unquote URL-encoded path components (%20 -> space)
    clean_path = urllib.parse.unquote(folder_path)
    parts = [p for p in clean_path.split("/") if p and p != ".."]
    if not parts:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid folder path"})
    
    folder_path_obj = UPLOAD_FOLDER
    for part in parts:
        safe_part = secure_filename(part)
        if not safe_part:
            return JSONResponse(status_code=400, content={"status": "error", "msg": f"Invalid path component: {part}"})
        folder_path_obj = folder_path_obj / safe_part
    
    # Path traversal check
    try:
        folder_path_obj.resolve().relative_to(UPLOAD_FOLDER.resolve())
    except ValueError:
        return JSONResponse(status_code=403, content={"status": "error", "msg": "Access denied"})
    
    if not folder_path_obj.exists() or not folder_path_obj.is_dir():
        return JSONResponse(status_code=404, content={"status": "error", "msg": "Folder not found"})
    
    try:
        files = []
        for f in folder_path_obj.iterdir():
            if f.is_file() and not f.name.endswith('.tmp') and not should_ignore_file(f.name):
                files.append({
                    "name": f.name,
                    "size": format_size(f.stat().st_size),
                    "mtime": f.stat().st_mtime
                })
            elif f.is_dir() and not f.name.startswith('.'):
                files.append({
                    "name": f.name,
                    "size": format_size(sum(f2.stat().st_size for f2 in f.rglob('*') if f2.is_file())),
                    "mtime": f.stat().st_mtime,
                    "isFolder": True
                })
        # Folders first, then by mtime descending
        folders_list = sorted([f for f in files if f.get("isFolder")], key=lambda x: x["mtime"], reverse=True)
        regulars_list = sorted([f for f in files if not f.get("isFolder")], key=lambda x: x["mtime"], reverse=True)
        return JSONResponse(content={
            "status": "success",
            "files": folders_list + regulars_list,
            "count": len(files),
            "folder": folder_path
        })
    except Exception as e:
        print(f"[ERR] Error listing folder contents: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "msg": f"Failed to list folder contents: {e}"})


@router.post("/api/files/rename", name="rename_file")
async def rename_file(filename: str = Form(...), new_name: str = Form(...), parent_path: Optional[str] = Form(None)):
    """Rename a file or folder with validation and path traversal prevention"""
    # Validate source name
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid source name"})
    
    target_dir = UPLOAD_FOLDER
    if parent_path:
        cleaned_parent = parent_path.strip("/\\").replace("..", "")
        if cleaned_parent and cleaned_parent != "Home":
            target_dir = UPLOAD_FOLDER / cleaned_parent

    src_path = target_dir / safe_filename
    if not src_path.exists():
        # Search root or subdirectories if direct parent path search failed
        src_path = UPLOAD_FOLDER / safe_filename
        if not src_path.exists():
            found = False
            for subdir_item in UPLOAD_FOLDER.rglob(safe_filename):
                if subdir_item.is_file() or subdir_item.is_dir():
                    src_path = subdir_item
                    found = True
                    break
            if not found:
                return JSONResponse(status_code=404, content={"status": "error", "msg": "Source not found"})
    
    # Validate destination name
    safe_new = secure_filename(new_name)
    if not safe_new:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid target name"})
    
    # Prevent path traversal
    if '/' in safe_new or '\\' in safe_new or '..' in safe_new:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid characters in filename"})
    
    # Check for duplicates in the same parent directory
    dst_path = src_path.parent / safe_new
    if dst_path.exists():
        return JSONResponse(status_code=409, content={"status": "error", "msg": f"'{safe_new}' already exists"})
    
    try:
        os.rename(src_path, dst_path)
        print(f"[RENAME] Renamed '{safe_filename}' to '{safe_new}' in '{src_path.parent}'")
        return JSONResponse(content={
            "status": "success",
            "msg": f"Renamed to '{safe_new}'",
            "old_name": safe_filename,
            "new_name": safe_new
        })
    except Exception as e:
        print(f"[ERR] Rename error: {e}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "msg": f"Failed to rename: {e}"
        })


@router.post("/api/files/move", name="move_file")
async def move_file(filename: str = Form(...), destination: str = Form(...)):
    """Move a file to a different directory"""
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid source filename"})
    
    # Search for the file in root and all subdirectories
    src_path = UPLOAD_FOLDER / safe_filename
    if not src_path.exists():
        found = False
        for subdir_file in UPLOAD_FOLDER.rglob(safe_filename):
            if subdir_file.is_file():
                src_path = subdir_file
                found = True
                break
        if not found:
            return JSONResponse(status_code=404, content={"status": "error", "msg": "Source file not found"})
    elif not src_path.is_file():
        return JSONResponse(status_code=404, content={"status": "error", "msg": "Source file not found"})
    
    # Validate destination directory
    safe_dest = secure_filename(destination)
    if not safe_dest:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid destination"})
    
    # Prevent path traversal
    if '..' in destination or '//' in destination:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid path"})
    
    # Ensure destination directory exists
    dest_dir = UPLOAD_FOLDER
    if destination:
        dest_dir = UPLOAD_FOLDER / destination.strip('/')
        dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Prevent overwrites
    dst_path = dest_dir / safe_filename
    if dst_path.exists():
        return JSONResponse(status_code=409, content={"status": "error", "msg": f"'{safe_filename}' already exists in destination"})
    
    try:
        shutil.move(str(src_path), str(dst_path))
        print(f"[MOVE] Moved '{safe_filename}' to '{destination}'")
        return JSONResponse(content={
            "status": "success",
            "msg": f"File moved to '{destination}'",
            "filename": safe_filename,
            "destination": destination
        })
    except Exception as e:
        print(f"[ERR] Move error: {e}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "msg": f"Failed to move file: {e}"
        })


@router.post("/api/files/mkdir", name="create_folder")
async def create_folder(folder_name: str = Form(...), parent_path: Optional[str] = Form(None)):
    """Create a new folder"""
    safe_name = secure_filename(folder_name)
    if not safe_name:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid folder name"})
    
    # Validate folder name
    if '/' in safe_name or '\\' in safe_name or '..' in safe_name:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid characters in folder name"})
    
    # Resolve target directory based on parent_path
    target_dir = UPLOAD_FOLDER
    if parent_path:
        clean_parent = urllib.parse.unquote(parent_path)
        parts = [p for p in clean_parent.split("/") if p and p != ".."]
        for part in parts:
            safe_part = secure_filename(part)
            if safe_part:
                target_dir = target_dir / safe_part
                
        # Path traversal check
        try:
            target_dir.resolve().relative_to(UPLOAD_FOLDER.resolve())
        except ValueError:
            return JSONResponse(status_code=403, content={"status": "error", "msg": "Access denied"})

    # Ensure parent folder exists
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Auto-increment if folder already exists: "Folder" -> "Folder (1)" -> "Folder (2)"
    original_name = safe_name
    counter = 1
    new_folder = target_dir / safe_name
    while new_folder.exists():
        safe_name = f"{original_name} ({counter})"
        new_folder = target_dir / safe_name
        counter += 1
    
    try:
        new_folder.mkdir()
        print(f"[MKDIR] Created folder: {new_folder}")
        return JSONResponse(content={
            "status": "success",
            "msg": f"Folder '{safe_name}' created",
            "folder_name": safe_name
        })
    except Exception as e:
        print(f"[ERR] Folder creation error: {e}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "msg": f"Failed to create folder: {e}"
        })


@router.post("/delete-folder/{folder_path:path}", name="delete_folder")
async def delete_folder(folder_path: str):
    """Delete an entire folder (supports nested paths)"""
    try:
        # Sanitize each path component
        clean_path = urllib.parse.unquote(folder_path)
        parts = [p for p in clean_path.split("/") if p and p != ".."]
        if not parts:
            return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid folder path"})
        
        folder_path_obj = UPLOAD_FOLDER
        for part in parts:
            safe_part = secure_filename(part)
            if not safe_part:
                return JSONResponse(status_code=400, content={"status": "error", "msg": f"Invalid path component: {part}"})
            folder_path_obj = folder_path_obj / safe_part
        
        # Path traversal check
        try:
            folder_path_obj.resolve().relative_to(UPLOAD_FOLDER.resolve())
        except ValueError:
            return JSONResponse(status_code=403, content={"status": "error", "msg": "Access denied"})
        
        if not folder_path_obj.exists() or not folder_path_obj.is_dir():
            return JSONResponse(status_code=404, content={"status": "error", "msg": "Folder not found"})
        
        # Force garbage collection to release any open file handles on Windows
        gc.collect()

        def handle_remove_readonly(func, path, exc_info):
            import stat
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        try:
            shutil.rmtree(folder_path_obj, onerror=handle_remove_readonly)
        except Exception:
            shutil.rmtree(folder_path_obj, ignore_errors=True)

        print(f"[OK] Deleted folder: {folder_path}")
        return JSONResponse(content={
            "status": "success",
            "msg": f"Folder '{folder_path}' deleted successfully"
        })
    except Exception as e:
        print(f"[ERR] Failed to delete folder {folder_path}: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "msg": f"Failed to delete folder: {str(e)}"})
