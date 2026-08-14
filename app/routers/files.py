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
import threading
import uuid
from pathlib import Path
from mimetypes import guess_type
from typing import List, Optional, Dict, Any, Tuple, Set
from app.core.logger import logger

from pydantic import BaseModel

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
from app.ws_manager.file_events import broadcast_file_event_sync
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
from app.utils.termux_compat import is_android, is_termux, is_android_environment
from app.core.concurrent_upload_manager import concurrent_upload_manager, ConcurrentUploadManager
from app.core.windows_file_manager import WindowsFileManager
from app.core.streaming_assembly import get_streaming_assembler, add_streaming_chunk, check_streaming_status, get_assembled_file, initialize_streaming_assembly

from app.core.stream_manager import get_stream_manager, StreamSession

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")
try:
    from app.utils.android_compat import get_base_data_dir
    DATA_DIR = get_base_data_dir() / "data"
except ImportError:
    DATA_DIR = Path("data")

UPLOAD_FOLDER = DATA_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
TEMP_CHUNKS_FOLDER = Path("data/temp_chunks")
TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)

# Upload history file - cleared on every server startup
UPLOAD_HISTORY_FILE = DATA_DIR / "upload_history.json"
# Clear history on startup so it resets with every server restart
try:
    UPLOAD_HISTORY_FILE.write_text("[]", encoding="utf-8")
except Exception:
    pass


def _clean_parent_path(parent_path: Optional[str]) -> str:
    """Normalize a parent path to Lanvan's internal relative-folder representation."""
    if not parent_path:
        return ""
    clean_parent = urllib.parse.unquote(parent_path).replace('\\', '/').strip('/')
    if clean_parent.startswith("Home (Root)/"):
        clean_parent = clean_parent[12:].lstrip('/')
    elif clean_parent.startswith("Home/"):
        clean_parent = clean_parent[5:].lstrip('/')
    if clean_parent in ("Home", "Home (Root)", "Home/"):
        return ""
    return clean_parent


def _resolve_target_dir(parent_path: Optional[str]) -> Path:
    """Resolve an exact upload subdirectory without any basename fallback."""
    target_dir = UPLOAD_FOLDER
    clean_parent = _clean_parent_path(parent_path)
    if clean_parent:
        parts = [secure_filename(p) for p in clean_parent.split('/') if p and p != ".." and p != "Home" and secure_filename(p)]
        if parts:
            target_dir = UPLOAD_FOLDER.joinpath(*parts)
    return target_dir


# Startup cleanup of orphan .tmp files in upload folder.
# Only scans top-level (non-recursive) for performance — orphaned .tmp files
# in deep subdirectories are cleaned up lazily on access.
try:
    for orphan_tmp in UPLOAD_FOLDER.glob("*.tmp"):
        if orphan_tmp.is_file():
            try:
                orphan_tmp.unlink()
                logger.info("STORAGE", "Removed orphan temporary file")
            except Exception:
                pass
    # Also clean temp_chunks
    for orphan_tmp in TEMP_CHUNKS_FOLDER.glob("*.tmp"):
        if orphan_tmp.is_file():
            try:
                orphan_tmp.unlink()
            except Exception:
                pass
except Exception:
    pass

def cleanup_temp_file_for_filename(filename: str, parent_path: Optional[str] = None, upload_id: Optional[str] = None, relative_path: Optional[str] = None) -> int:
    """Delete exact upload-scoped file artifacts for a cancelled upload or finalized delete.

    Identity is derived once via UploadPathResolver so that ROOT/A and Inside/A
    never share the same cleanup target, matching how upload_chunk names chunks.
    """
    deleted_count = 0
    if not filename:
        return 0
    safe_name = secure_filename(filename)
    if not safe_name:
        return 0

    resolved_parent = parent_path
    if not resolved_parent and relative_path:
        rel_clean = urllib.parse.unquote(relative_path).replace('\\', '/').strip('/')
        if rel_clean:
            rel_parent = Path(rel_clean).parent.as_posix()
            resolved_parent = "" if rel_parent in (".", "Home", "Home (Root)") else rel_parent

    try:
        resolved = UploadPathResolver.resolve(resolved_parent, safe_name, UPLOAD_FOLDER)
        target_dir = resolved.target_directory
        exact_target = resolved.full_path
        chunk_prefix = resolved.relative_path.as_posix().replace("/", "__")
    except Exception:
        target_dir = _resolve_target_dir(resolved_parent)
        exact_target = target_dir / safe_name
        chunk_prefix = safe_name

    logger.log_upload("Cancelled file cleanup", op_id=upload_id, file_ext=logger.extract_safe_ext(filename))

    if exact_target.exists() and exact_target.is_file():
        try:
            exact_target.unlink()
            deleted_count += 1
            logger.info("STORAGE", "Deleted cancelled target file")
        except Exception as e:
            logger.warn("STORAGE", "Failed to delete cancelled target file", details={"Reason": str(e)})

    for p in target_dir.glob(f"{safe_name}.tmp"):
        if p.is_file():
            try:
                p.unlink()
                deleted_count += 1
                logger.info("STORAGE", "Deleted temporary file")
            except Exception as e:
                logger.warn("STORAGE", "Failed to delete temp file", details={"Reason": str(e)})
    for p in target_dir.glob(f"{safe_name}.chunk.tmp"):
        if p.is_file():
            try:
                p.unlink()
                deleted_count += 1
                logger.info("STORAGE", "Deleted chunk temp file")
            except Exception as e:
                logger.warn("STORAGE", "Failed to delete chunk temp file", details={"Reason": str(e)})

    # Use the scoped chunk_prefix (e.g. "Inside__A") to match exactly the temp
    # chunk files created by upload_chunk, which names them as chunk_prefix.partN.
    if TEMP_CHUNKS_FOLDER.exists():
        for chunk in TEMP_CHUNKS_FOLDER.glob(f"{chunk_prefix}.part*"):
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
    """Check if file is in pending locked deletion list.

    The set stores absolute filesystem paths only. Comparison uses resolved
    absolute paths on both sides so that 'A' and 'Inside/A' are always distinct.
    """
    global LOCKED_DELETIONS_SET
    if not filename_or_path:
        return False
    p = Path(filename_or_path)
    # Resolve to absolute path; relative inputs are anchored under UPLOAD_FOLDER.
    if not p.is_absolute():
        p = UPLOAD_FOLDER / filename_or_path
    try:
        resolved_check = str(p.resolve()).lower()
    except Exception:
        resolved_check = str(p).lower()
    for item in list(LOCKED_DELETIONS_SET):
        try:
            resolved_item = str(Path(item).resolve()).lower()
        except Exception:
            resolved_item = item.lower()
        if resolved_check == resolved_item:
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
    items = []
    from app.core.version_manager import VersionManager
    for f in UPLOAD_FOLDER.iterdir():
        if f.name.startswith('.') or f.name.endswith('.tmp') or should_ignore_file(f.name):
            continue
        if f.is_dir():
            items.append({
                "name": f.name,
                "size": "--",
                "mtime": f.stat().st_mtime,
                "isFolder": True
            })
        elif f.is_file():
            lf = VersionManager.get_logical_file_by_path("", f.name)
            v_count = lf.get("versionCount", 1) if lf else 1
            lf_id = lf.get("id") if lf else f"lf_{f.name}"
            latest_v_id = lf.get("latestVersionId") if lf else None
            items.append({
                "name": f.name,
                "identity": f.name,
                "size": format_size(f.stat().st_size),
                "mtime": f.stat().st_mtime,
                "isFolder": False,
                "logicalFileId": lf_id,
                "versionCount": v_count,
                "hasVersions": (v_count > 1),
                "latestVersionId": latest_v_id
            })
    return sorted(items, key=lambda x: x["mtime"], reverse=True)

async def get_file_list_async():
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    retry_pending_deletions()
    items = []
    file_count = 0
    from app.core.version_manager import VersionManager
    
    for f in UPLOAD_FOLDER.iterdir():
        if f.name.startswith('.') or f.name.endswith('.tmp') or should_ignore_file(f.name):
            continue
        if f.is_dir():
            items.append({
                "name": f.name,
                "size": "--",
                "mtime": f.stat().st_mtime,
                "isFolder": True
            })
            file_count += 1
        elif f.is_file():
            lf = VersionManager.get_logical_file_by_path("", f.name)
            v_count = lf.get("versionCount", 1) if lf else 1
            lf_id = lf.get("id") if lf else f"lf_{f.name}"
            latest_v_id = lf.get("latestVersionId") if lf else None
            items.append({
                "name": f.name,
                "size": format_size(f.stat().st_size),
                "mtime": f.stat().st_mtime,
                "isFolder": False,
                "logicalFileId": lf_id,
                "versionCount": v_count,
                "hasVersions": (v_count > 1),
                "latestVersionId": latest_v_id
            })
            file_count += 1
            
        if file_count % 50 == 0:
            await asyncio.sleep(0.01)
    
    return sorted(items, key=lambda x: x["mtime"], reverse=True)

def get_unique_filename(directory: Path, filename: str) -> str:
    """Return original filename directly — VersionManager manages version history for identical names."""
    return filename

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
    safe_ext = logger.extract_safe_ext(upload_file.filename or destination.name)
    start_time = time.time()
    
    # Platform Detection
    is_android = is_android_environment()
    is_windows = os.name == 'nt'
    is_linux = os.name == 'posix' and not is_android
    platform_name = "Android/Termux" if is_android else "Windows" if is_windows else "Linux/Unix"
    
    # ASYNC File size estimation for progress tracking
    await asyncio.to_thread(upload_file.file.seek, 0, 2)
    file_size = await asyncio.to_thread(upload_file.file.tell)
    await asyncio.to_thread(upload_file.file.seek, 0)
    
    logger.log_upload("Async Upload Started", file_ext=safe_ext, size_bytes=file_size, status="STARTED")
    
    # Universal adaptive chunk sizing
    CHUNK_SIZE = universal_optimizer.get_adaptive_chunk_size(file_size)
    
    # ACQUIRE FILE LOCK: Prevent race conditions during upload
    async with lock_manager.upload_lock(destination.name, timeout=60.0):
        if encrypt:
            try:
                data = await asyncio.to_thread(upload_file.file.read)
                from app.core.aes_utils import encrypt_file_stream
                original_hash = hashlib.sha256(data).hexdigest()
                
                encrypted_data, metadata = encrypt_file_stream(data, chunk_size=CHUNK_SIZE)
                metadata['original_hash'] = original_hash
                metadata['original_size'] = str(len(data))
                metadata['encrypted_size'] = str(len(encrypted_data))
                
                import aiofiles
                async with aiofiles.open(temp_destination, 'wb') as f:
                    await f.write(encrypted_data)
                
                import shutil
                max_retries = 3 if is_windows else 1
                retry_delay = 0.3 if is_windows else 0.1
                
                for attempt in range(max_retries):
                    try:
                        if is_windows:
                            await asyncio.to_thread(shutil.move, str(temp_destination), str(destination))
                        else:
                            temp_destination.rename(destination)
                        
                        duration = time.time() - start_time
                        logger.log_upload("Encrypted Upload Completed", file_ext=safe_ext, size_bytes=file_size, duration=duration, status="SUCCESS")
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 1.5
                        else:
                            if temp_destination.exists():
                                try:
                                    temp_destination.unlink()
                                except:
                                    pass
                            logger.log_upload("Encrypted Finalization Failed", file_ext=safe_ext, size_bytes=file_size, status="FAILED", reason="STORAGE_WRITE_FAILED")
                            raise Exception(f"Failed to finalize encrypted upload: {e}")
                
                await asyncio.sleep(0.01)
            except Exception as e:
                if temp_destination.exists():
                    temp_destination.unlink()
                logger.log_upload("Encryption Upload Failed", file_ext=safe_ext, size_bytes=file_size, status="FAILED", reason="ENCRYPTION_ERROR")
                raise
        else:
            try:
                import aiofiles
                bytes_written = 0
                hash_calculator = hashlib.sha256()
                processed_chunks = 0
                
                async with aiofiles.open(temp_destination, 'wb') as f:
                    while True:
                        chunk = await asyncio.to_thread(upload_file.file.read, CHUNK_SIZE)
                        if not chunk:
                            break
                        
                        await f.write(chunk)
                        await f.flush()
                        
                        bytes_written += len(chunk)
                        hash_calculator.update(chunk)
                        processed_chunks += 1
                        
                        if processed_chunks % 5 == 0:
                            await asyncio.sleep(0.01)
                
                if is_windows:
                    await asyncio.sleep(0.2)
                    
                import shutil
                max_retries = 3 if is_windows else 1
                retry_delay = 0.3 if is_windows else 0.1
                
                for attempt in range(max_retries):
                    try:
                        if is_windows:
                            await asyncio.to_thread(shutil.move, str(temp_destination), str(destination))
                        else:
                            temp_destination.rename(destination)
                        
                        duration = time.time() - start_time
                        logger.log_upload("Upload Completed", file_ext=safe_ext, size_bytes=bytes_written, duration=duration, status="SUCCESS")
                        break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 1.5
                        else:
                            if temp_destination.exists():
                                try:
                                    temp_destination.unlink()
                                except:
                                    pass
                            logger.log_upload("Finalization Failed", file_ext=safe_ext, size_bytes=bytes_written, status="FAILED", reason="STORAGE_WRITE_FAILED")
                            raise Exception(f"Failed to finalize upload: {e}")
                
            except Exception as e:
                if temp_destination.exists():
                    temp_destination.unlink()
                logger.log_upload("Upload Transfer Failed", file_ext=safe_ext, size_bytes=file_size, status="FAILED", reason="UPLOAD_TRANSFER_FAILED")
                raise
            finally:
                if hasattr(universal_optimizer, 'upload_active'):
                    universal_optimizer.upload_active = False
                universal_optimizer.memory_cleanup(force=True)

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
        TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)
        # Save uploaded file temporarily using chunked streaming in TEMP_CHUNKS_FOLDER
        temp_input_path = TEMP_CHUNKS_FOLDER / f"temp_input_{int(time.time())}_{secure_filename(file.filename or 'file')}"
        
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
        
        # Save encrypted file temporarily in TEMP_CHUNKS_FOLDER for download
        temp_filename = f"temp_encrypted_{int(time.time())}_{obfuscated_filename}"
        temp_path = TEMP_CHUNKS_FOLDER / temp_filename
        
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
        file_path = TEMP_CHUNKS_FOLDER / safe_name
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
        file_names = [f["name"] for f in files]
        return JSONResponse(content={
            "status": "success",
            "files": file_names,
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
                
                file_path = target_dir / resolved.filename
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
        
        from app.core.version_manager import VersionManager
        for result in results:
            if result.get("success", False):
                fn = result.get("filename", "unknown")
                successful_uploads.append(fn)
                dest_p = result.get("destination")
                if dest_p and Path(dest_p).exists():
                    try:
                        VersionManager.create_version_transaction(
                            target_dir=parent_path,
                            filename=fn,
                            incoming_file_path=Path(dest_p),
                            uploaded_by=request.client.host if request and request.client else "upload",
                            change_type="uploaded"
                        )
                    except Exception as ve:
                        print(f"[VERSION] Version creation log: {ve}")
            else:
                failed_uploads.append(result.get("error", "Unknown error"))
        
        if successful_uploads:
            # Broadcast real-time WebSocket event to all connected devices
            try:
                from app.ws_manager.upload_status import upload_status_manager
                asyncio.create_task(upload_status_manager.notify_file_list_updated(successful_uploads))
            except Exception:
                pass
            # Broadcast via file_events WebSocket for instant cross-device sync
            try:
                broadcast_file_event_sync("upload", parent_path or "", ", ".join(successful_uploads))
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
        # Fallback to basic upload when ConcurrentUploadManager cannot be imported.
        # Must still honour parent_path so files land in the correct subfolder.
        uploaded_files = []
        from app.utils.universal_optimizer import get_adaptive_chunk_size
        CHUNK_SIZE = get_adaptive_chunk_size(1024 * 1024)

        for file in files:
            if not file.filename:
                continue
            try:
                # Use the same resolver as the main path so identity is consistent.
                resolved_fb = UploadPathResolver.resolve(parent_path, file.filename, UPLOAD_FOLDER)
                resolved_fb.target_directory.mkdir(parents=True, exist_ok=True)
                file_path = resolved_fb.full_path

                # Ensure unique filename
                counter = 1
                base_path = file_path
                while file_path.exists():
                    file_path = base_path.parent / f"{base_path.stem}_{counter}{base_path.suffix}"
                    counter += 1

                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                uploaded_files.append(file_path.name)
            except Exception as fb_err:
                print(f"[ERR] ImportError fallback upload failed for '{file.filename}': {fb_err}")

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

    # [TRACE VERIFY] Log raw UploadFile.filename BEFORE any processing
    for i, file in enumerate(files):
        print(f"[TRACE VERIFY] Raw UploadFile.filename: file[{i}].filename='{file.filename}' | parent_path='{parent_path}'")

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

            # [TRACE STEP 1] Log destination before saving
            print(f"[TRACE STEP 1] resolve: parent_path='{parent_path}' | file.filename='{file.filename}' | target_dir='{target_dir}' | full_path='{resolved.full_path}'")
            print(f"[TRACE STEP 1] Destination: {resolved.relative_path}")
            print(f"[TRACE STEP 1] Absolute: {resolved.full_path.resolve()}")

            save_name = resolved.filename + ".enc" if encrypt else resolved.filename
            filepath = target_dir / save_name

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
    from app.core.version_manager import VersionManager
    
    # Process results and add background tasks
    for i, result in enumerate(upload_results):
        if result.get('success'):
            filepath = Path(result['destination'])
            rel_dir = parent_path or ""
            VersionManager.create_version_transaction(rel_dir, filepath.name, filepath)
            background_tasks.add_task(scan_file, filepath)
            uploaded.append(filepath.name)
            print(f"[OK] File {i+1} uploaded successfully via VersionManager: {filepath.name}")
        else:
            print(f"[ERR] File {i+1} failed: {result.get('error', 'Unknown error')}")

    print(f"[DONE] Concurrent upload complete! {len(uploaded)} files uploaded: {uploaded}")

    # [TRACE STEP 2] Verify filesystem after upload
    for i, result in enumerate(upload_results):
        if result.get('success'):
            filepath = Path(result['destination'])
            parent_dir = filepath.parent
            print(f"[TRACE STEP 2] Verify filesystem | File saved at: '{filepath}' | os.path.exists={filepath.exists()}")
            print(f"[TRACE STEP 2] Verify filesystem | Parent dir: '{parent_dir}' | os.path.exists={parent_dir.exists()} | os.listdir={sorted([p.name for p in parent_dir.iterdir()]) if parent_dir.exists() else 'N/A'}")

    if not uploaded:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No valid files processed"
        })

    # Broadcast via file_events WebSocket for instant cross-device sync
    try:
        broadcast_file_event_sync("upload", parent_path or "", ", ".join(uploaded))
    except Exception:
        pass

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

@router.get("/download/{filename:path}", name="download_file")
@router.head("/download/{filename:path}")
async def download_file(filename: str, request: Request):
    print(f"[IN] Download request for: {filename}")
    
    clean_filename = urllib.parse.unquote(filename).strip("/\\")
    safe_name = secure_filename(clean_filename)
    file_path = _resolve_target_dir(None) / clean_filename

    if file_path.exists() and file_path.is_dir():
        print(f"[DIR] Directory requested via /download/{clean_filename}. Redirecting to /download-folder/{clean_filename}...")
        return RedirectResponse(url=f"/download-folder/{urllib.parse.quote(clean_filename)}", status_code=307)

    if not file_path.is_file():
        file_path = _resolve_target_dir(None) / safe_name
        if not file_path.is_file():
            print(f"[ERR] File not found: {clean_filename}")
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
            
    from app.core.download_engine import download_engine_v2
    stat_info = download_engine_v2.stat_cache.get_stat(file_path, mime_type_hint=mime_type)
    if not stat_info:
        return Response("File not found", status_code=404)

    file_size = stat_info["file_size"]
    etag = stat_info["etag"]
    
    print(f"[STATS] File info (cached) - Size: {file_size} bytes, MIME: {mime_type}, ETag: {etag}")
    
    is_download_requested = request.query_params.get("download") == "1"
    disposition_type = "attachment" if is_download_requested else "inline"

    # OK: Handle HEAD requests - return headers only for file info
    if request.method == "HEAD":
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": mime_type or "application/octet-stream",
            "Content-Disposition": f'{disposition_type}; filename="{safe_name}"',
            "Accept-Ranges": "bytes",  # Indicate support for range requests
            "ETag": etag,
            "Cache-Control": "public, max-age=86400"
        }
        return Response(content="", headers=headers, status_code=200)
    
    # Classify client capabilities and transfer strategy via DownloadEngine
    plan = download_engine_v2.classify_request(request, safe_name, file_size)

    # Deficit Round Robin (DRR) Fair-Share Concurrency Scheduler
    wait_time = await download_engine_v2.scheduler.acquire_slot(plan["client_ip"])
    session_id = uuid.uuid4().hex[:12]
    download_engine_v2.analytics.record_start(session_id, wait_time_sec=wait_time)

    client_ip = plan["client_ip"]
    slot_acquired = True

    def _release_scheduler_slot(bytes_transferred: int = 0, interrupted: bool = False):
        nonlocal slot_acquired
        if slot_acquired:
            slot_acquired = False
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(download_engine_v2.scheduler.release_slot(client_ip))
            except RuntimeError:
                pass
            download_engine_v2.analytics.record_completion(session_id, bytes_sent=bytes_transferred, interrupted=interrupted)

    try:
        if plan["strategy"] == "range":
            return await range_download_file(file_path, safe_name, mime_type, file_size, plan["range_header"], disposition_type=disposition_type, request=request, release_slot_cb=_release_scheduler_slot)
        elif plan["strategy"] == "chunked":
            print("[PKG] Using chunked download strategy via DownloadEngine")
            return await chunked_download_file(file_path, safe_name, mime_type, file_size, request, disposition_type=disposition_type, release_slot_cb=_release_scheduler_slot)
        else:
            print("[FILE] Using full download strategy via DownloadEngine")
            return await full_download_file(file_path, safe_name, mime_type, file_size, disposition_type=disposition_type, etag=etag, release_slot_cb=_release_scheduler_slot)
    except Exception:
        _release_scheduler_slot(bytes_transferred=0, interrupted=True)
        raise

async def range_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int, range_header: str, disposition_type: str = "inline", request: Optional[Request] = None, release_slot_cb: Any = None):
    """Serve HTTP Range Requests (206 Partial Content) with ETag caching & dynamic buffer scaling."""
    try:
        # Generate stable ETag based on file modification time & size
        st = file_path.stat()
        mtime_ns = getattr(st, 'st_mtime_ns', int(st.st_mtime * 1e9))
        etag = f'"{mtime_ns:x}-{file_size:x}"'

        # Check If-None-Match header for 304 Not Modified validation
        if request:
            if_none_match = request.headers.get("if-none-match") or request.headers.get("If-None-Match")
            if if_none_match and if_none_match.strip() == etag:
                if release_slot_cb:
                    if asyncio.iscoroutinefunction(release_slot_cb):
                        await release_slot_cb(bytes_transferred=0, interrupted=False)
                    else:
                        release_slot_cb(bytes_transferred=0, interrupted=False)
                return Response(status_code=304, headers={"ETag": etag, "Accept-Ranges": "bytes"})

            # Handle If-Range validation for download managers (IDM/1DM+/curl/ADM)
            if_range = request.headers.get("if-range") or request.headers.get("If-Range")
            if if_range:
                if_range_clean = if_range.strip()
                # If ETag doesn't match, serve full file (200 OK) instead of 206 Range
                if if_range_clean.startswith('"') and if_range_clean != etag:
                    return await full_download_file(file_path, safe_name, mime_type, file_size, disposition_type=disposition_type, etag=etag, release_slot_cb=release_slot_cb)

        if "=" not in range_header:
            return await full_download_file(file_path, safe_name, mime_type, file_size, disposition_type=disposition_type, release_slot_cb=release_slot_cb)
            
        unit, bytes_range = range_header.strip().split("=", 1)
        if unit.lower() != "bytes":
            if release_slot_cb:
                if asyncio.iscoroutinefunction(release_slot_cb):
                    await release_slot_cb(bytes_transferred=0, interrupted=True)
                else:
                    release_slot_cb(bytes_transferred=0, interrupted=True)
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
            if release_slot_cb:
                if asyncio.iscoroutinefunction(release_slot_cb):
                    await release_slot_cb(bytes_transferred=0, interrupted=True)
                else:
                    release_slot_cb(bytes_transferred=0, interrupted=True)
            headers = {"Content-Range": f"bytes */{file_size}"}
            return Response("Requested range not satisfiable", status_code=416, headers=headers)
        
        chunk_size = (end - start) + 1
        
        # Dynamic Range Buffer Scaling:
        if chunk_size >= 10 * 1024 * 1024:
            buffer_size = 1024 * 1024  # 1MB buffer
        elif chunk_size >= 1024 * 1024:
            buffer_size = 512 * 1024   # 512KB buffer
        else:
            buffer_size = 256 * 1024   # 256KB buffer

        session = get_stream_manager().register_stream(file_path, "http-client")

        def iterfile():
            sent = 0
            interrupted = False
            try:
                with open(file_path, "rb") as f:
                    session.file_handle = f
                    f.seek(start)
                    bytes_left = chunk_size
                    while bytes_left > 0:
                        if session.cancel_event.is_set():
                            print(f"[STREAM] Range stream session {session.session_id} canceled for '{safe_name}'")
                            interrupted = True
                            break
                        read_len = min(buffer_size, bytes_left)
                        data = f.read(read_len)
                        if not data:
                            break
                        bytes_left -= len(data)
                        sent += len(data)
                        yield data
            except (ValueError, OSError) as e:
                interrupted = True
                print(f"[STREAM] Range stream session {session.session_id} closed during read: {e}")
            finally:
                get_stream_manager().unregister_stream(session)
                if release_slot_cb:
                    try:
                        release_slot_cb(bytes_transferred=sent, interrupted=interrupted or (sent < chunk_size))
                    except Exception:
                        pass

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": mime_type or "application/octet-stream",
            "ETag": etag,
            "Cache-Control": "public, max-age=3600",
            "X-Accel-Buffering": "no"
        }
        if disposition_type == "attachment":
            headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        
        print(f"[STREAM] Serving Range 206 ({disposition_type}): bytes {start}-{end}/{file_size} (buffer {buffer_size // 1024}KB) for {safe_name}")
        return StreamingResponse(iterfile(), status_code=206, headers=headers)
    except Exception as e:
        print(f"[ERR] Range request failed ({e}), falling back to full download")
        return await full_download_file(file_path, safe_name, mime_type, file_size, disposition_type=disposition_type, release_slot_cb=release_slot_cb)

async def full_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int, disposition_type: str = "inline", etag: str | None = None, release_slot_cb: Any = None):
    """Ultra-optimized full file download - for small files and .enc files"""
    print(f"[OUT] Starting full download ({disposition_type}) for: {safe_name}")
    session = get_stream_manager().register_stream(file_path, "http-client")
    
    STREAM_BUFFER_SIZE = max(65536, min(file_size, 32 * 1024 * 1024, max(65536, file_size // 4)))
    
    def stream_file_ultra_optimized(path: Path):
        print(f"[RETRY] Streaming file: {path}")
        file_handle = None  # Track file handle for proper cleanup
        sent = 0
        interrupted = False
        
        try:
            if path.suffix == ".enc":
                print("[AUTH] Processing encrypted file")
                try:
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
                        
                        if metadata and metadata.get('encryption_method') == 'streaming':
                            from app.core.aes_utils import decrypt_file_stream
                            decrypted_data = decrypt_file_stream(encrypted_data, metadata, chunk_size=1024 * 1024)
                            print(f"[LOCK] Used streaming decryption for {path.name}")
                        else:
                            print(f"[WARN] Cannot decrypt {path.name} - legacy encryption no longer supported")
                            interrupted = True
                            yield f"Error: File {path.name} uses unsupported legacy encryption".encode('utf-8')
                            return
                        
                        print(f"OK: Decrypted to {len(decrypted_data)} bytes")
                        
                        if metadata and 'original_hash' in metadata:
                            import hashlib
                            actual_hash = hashlib.sha256(decrypted_data).hexdigest()
                            expected_hash = metadata['original_hash']
                            if actual_hash != expected_hash:
                                raise Exception(f"File integrity check failed! Expected: {expected_hash}, Got: {actual_hash}")
                            print(f"OK: File integrity validated successfully")
                        
                        data_length = len(decrypted_data)
                        chunks_sent = 0
                        for i in range(0, data_length, STREAM_BUFFER_SIZE):
                            if session.cancel_event.is_set():
                                interrupted = True
                                break
                            chunk_end = min(i + STREAM_BUFFER_SIZE, data_length)
                            chunk = decrypted_data[i:chunk_end]
                            chunks_sent += 1
                            sent += len(chunk)
                            print(f"[OUT] Sending chunk {chunks_sent}, size: {len(chunk)} bytes")
                            yield chunk
                            
                except Exception as e:
                    interrupted = True
                    print(f"[!] AES decryption failed for {path}: {e}")
                    error_message = f"Error: Failed to decrypt file {path.name}. {str(e)}"
                    yield error_message.encode('utf-8')
            else:
                print("[FILE] Processing regular file")
                try:
                    file_handle = open(path, "rb")
                    session.file_handle = file_handle
                    chunks_sent = 0
                    while True:
                        if session.cancel_event.is_set():
                            interrupted = True
                            break
                        chunk = file_handle.read(STREAM_BUFFER_SIZE)
                        if not chunk:
                            break
                        chunks_sent += 1
                        sent += len(chunk)
                        print(f"[OUT] Sending chunk {chunks_sent}, size: {len(chunk)} bytes")
                        yield chunk
                    print(f"OK: Completed streaming {chunks_sent} chunks")
                except Exception as e:
                    interrupted = True
                    print(f"[!] File streaming failed for {path}: {e}")
                    error_message = f"Error: Failed to read file {path.name}. {str(e)}"
                    yield error_message.encode('utf-8')
        finally:
            get_stream_manager().unregister_stream(session)
            if file_handle is not None:
                try:
                    file_handle.close()
                    print(f"[OK] File handle closed for: {path.name}")
                except Exception as e:
                    print(f"[WARN] Error closing file handle: {e}")
            if release_slot_cb:
                try:
                    release_slot_cb(bytes_transferred=sent, interrupted=interrupted or (file_size > 0 and sent < file_size))
                except Exception:
                    pass

    final_file_size = file_size
    if file_path.suffix == ".enc":
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
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=86400",
        "X-Accel-Buffering": "no",
        "X-Download-Type": "ultra-optimized-full",
        "X-Buffer-Size": "32MB"
    }
    if etag:
        headers["ETag"] = etag
    
    if not file_path.suffix == ".enc":
        headers["Content-Length"] = str(final_file_size)
    
    print(f"[INFO] Response headers: {headers}")
    
    return StreamingResponse(
        stream_file_ultra_optimized(file_path),
        media_type=mime_type or "application/octet-stream",
        headers=headers
    )

async def chunked_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int, request: Request | None = None, disposition_type: str = "inline", release_slot_cb: Any = None):
    """High-performance chunked file download - for large files (≥250MB) that are not .enc"""
    CHUNK_SIZE = 16 * 1024 * 1024  # 16MB chunks
    
    range_header = request.headers.get('Range') if request else None
    start = 0
    end = file_size - 1
    
    if range_header:
        try:
            range_match = range_header.replace('bytes=', '').split('-')
            if len(range_match) == 2:
                if range_match[0]:
                    start = int(range_match[0])
                if range_match[1]:
                    end = int(range_match[1])
                end = min(end, file_size - 1)
        except ValueError:
            pass
    
    content_length = end - start + 1
    session = get_stream_manager().register_stream(file_path, "http-client")
    
    def stream_chunks_optimized():
        """Optimized streaming with larger buffers, StreamManager registration, and proper lifecycle hooks"""
        sent = 0
        interrupted = False
        file_handle = None
        try:
            file_handle = open(file_path, "rb")
            session.file_handle = file_handle
            file_handle.seek(start)
            remaining = content_length
            
            while remaining > 0:
                if session.cancel_event.is_set():
                    interrupted = True
                    break
                chunk_size = min(CHUNK_SIZE, remaining)
                chunk = file_handle.read(chunk_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                sent += len(chunk)
                yield chunk
        except Exception as e:
            interrupted = True
            print(f"[STREAM] Chunked download session {session.session_id} error for '{safe_name}': {e}")
        finally:
            get_stream_manager().unregister_stream(session)
            if file_handle is not None:
                try:
                    file_handle.close()
                except Exception:
                    pass
            if release_slot_cb:
                try:
                    release_slot_cb(bytes_transferred=sent, interrupted=interrupted or (sent < content_length))
                except Exception:
                    pass

    headers = {
        "Content-Disposition": f'{disposition_type}; filename="{safe_name}"',
        "Content-Length": str(content_length),
        "Cache-Control": "public, max-age=86400",
        "X-Accel-Buffering": "no",
        "X-Download-Type": "high-performance-chunked",
        "Accept-Ranges": "bytes",
        "X-Chunk-Size": "16MB"
    }
    
    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status_code = 206
    else:
        status_code = 200

    return StreamingResponse(
        stream_chunks_optimized(),
        media_type=mime_type or "application/octet-stream",
        headers=headers,
        status_code=status_code
    )

def create_fast_zip_response(files_to_download: list, zip_filename: str = "archive.zip"):
    """
    High-performance ZIP generator & streaming response.
    Uses ZIP_STORED for pre-compressed media/binaries to eliminate CPU compression delay,
    and streams with 512KB chunks for maximum throughput.
    """
    import zipfile
    from urllib.parse import quote

    PRECOMPRESSED_EXTS = {
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.3gp', '.m4v', '.mp3', '.aac',
        '.flac', '.ogg', '.wav', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.zip', '.rar',
        '.7z', '.gz', '.tar', '.bz2', '.iso', '.pdf', '.docx', '.xlsx', '.pptx'
    }

    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for file_path, arcname in files_to_download:
                try:
                    if not file_path.exists():
                        continue
                    ext = file_path.suffix.lower()
                    compress_type = zipfile.ZIP_STORED if ext in PRECOMPRESSED_EXTS else zipfile.ZIP_DEFLATED
                    zip_file.write(file_path, arcname=arcname, compress_type=compress_type)
                except Exception as e:
                    print(f"[WARN] Error adding {arcname} to ZIP: {e}")
                    continue

        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()
        zip_buffer.close()

        def generate_zip():
            chunk_size = 524288  # 512KB chunks for high throughput LAN transfers
            for i in range(0, len(zip_data), chunk_size):
                chunk = zip_data[i:i + chunk_size]
                if chunk:
                    yield chunk

        encoded_name = quote(zip_filename)
        return StreamingResponse(
            generate_zip(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{zip_filename}"; filename*=UTF-8\'\'{encoded_name}',
                "Content-Length": str(len(zip_data))
            }
        )
    except Exception as e:
        print(f"[ERR] Error creating fast ZIP: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to create ZIP archive: {str(e)}"}
        )

class BatchDownloadZipRequest(BaseModel):
    files: List[str]
    # Parent folder the user was viewing when they selected items.
    # Required to correctly resolve filenames in subfolders (e.g. Inside/A vs ROOT/A).
    parent_path: Optional[str] = None

@router.post("/api/files/download-zip", name="download_files_zip")
@router.post("/download-zip", name="download_files_zip_alias")
async def download_files_zip(req: BatchDownloadZipRequest):
    """Download arbitrary selected list of files as a high-speed ZIP archive.

    Files are resolved against req.parent_path so that ROOT/A, Inside/A, and
    Inside/Nested/A are always distinct — even when they share the same basename.
    """
    # Resolve the base folder once; falls back to UPLOAD_FOLDER root.
    base_dir = _resolve_target_dir(req.parent_path)

    files_to_download = []
    last_safe_fn = "files"
    for fn in req.files:
        safe_fn = secure_filename(fn)
        if not safe_fn:
            continue
        last_safe_fn = safe_fn
        fp = base_dir / safe_fn
        if fp.exists() and fp.is_file():
            files_to_download.append((fp, fp.name))
        elif fp.exists() and fp.is_dir():
            for child in fp.rglob('*'):
                if child.is_file():
                    rel = child.relative_to(fp.parent)
                    files_to_download.append((child, str(rel)))

    if not files_to_download:
        return JSONResponse(status_code=404, content={"error": "No valid files found for ZIP download"})

    zip_name = "selected_files.zip" if len(req.files) > 1 else f"{last_safe_fn}.zip"
    return create_fast_zip_response(files_to_download, zip_name)

@router.get("/download-all", name="download_all")
async def download_all_files():
    """Download all files as a ZIP archive with proper high-speed streaming"""
    files_to_download = [(file, file.name) for file in UPLOAD_FOLDER.iterdir() if file.is_file() and not file.name.endswith('.tmp')]
    if not files_to_download:
        return JSONResponse(
            status_code=404,
            content={"error": "No files available for download"}
        )
    return create_fast_zip_response(files_to_download, "all_files.zip")

@router.get("/selection-demo")
async def selection_demo():
    """Serve interactive selection style showcase & demo page"""
    demo_path = TEMPLATE_DIR / "selection_demo.html"
    if demo_path.is_file():
        return FileResponse(demo_path)
    return Response("Demo page not found", status_code=404)

@router.post("/clear", name="clear_files")
@router.post("/api/files/clear", name="clear_files_api_alias")
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
        
        # Reset version metadata to clean slate when all files are cleared
        try:
            from app.core.version_manager import VersionManager
            VersionManager.reset_all_metadata()
            print("[CLEAN] Version metadata reset to clean slate.")
        except Exception as v_err:
            print(f"[WARN] Failed to reset version metadata during clear: {v_err}")

        # Clear clipboard history from memory and persistent disk store
        try:
            from app.routers.clipboard import clear_clipboard_data_sync
            clear_clipboard_data_sync()
            print("[CLEAN] Clipboard history cleared successfully.")
        except Exception as c_err:
            print(f"[WARN] Failed to clear clipboard history during clear: {c_err}")

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
            # Broadcast via file_events WebSocket for instant cross-device sync
            try:
                broadcast_file_event_sync("clear", "", "")
            except Exception:
                pass
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
async def cancel_upload_api(filename: Optional[str] = Form(None), parent_path: Optional[str] = Form(None), upload_id: Optional[str] = Form(None), relative_path: Optional[str] = Form(None), request: Request = None):
    """Cancel an upload and purge any temporary .tmp files or chunks on disk."""
    try:
        target_file = filename
        target_parent = parent_path
        if not target_file and request:
            try:
                form = await request.form()
                target_file = form.get("filename")
                target_parent = form.get("parent_path")
                upload_id = upload_id or form.get("upload_id")
                relative_path = relative_path or form.get("relative_path")
            except Exception:
                pass
        deleted = cleanup_temp_file_for_filename(target_file or "", target_parent, upload_id=upload_id, relative_path=relative_path)
        print(f"[CANCEL] Purged {deleted} temporary file(s) for '{target_file}' upload_id='{upload_id or ''}'")
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

        print("[REAL DELETE BACKEND]")
        print(f"timestamp={time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime())}")
        print(f"filename={filename}")
        print(f"parent_path={target_parent or ''}")

        target_dir = _resolve_target_dir(target_parent)
        print(f"resolved target_dir={target_dir}")

        file_path = target_dir / safe_name
        print(f"resolved absolute file_path={file_path.resolve()}")
        exists_before_unlink = file_path.exists()
        print(f"exists_before={exists_before_unlink}")
        
        if not file_path.exists():
            # Check target_dir with unescaped filename or alternate safe_name representations (strictly scoped to target_dir)
            found = False
            for target_name in set([safe_name, filename, secure_filename(filename)]):
                if not target_name: continue
                candidate = target_dir / target_name
                if candidate.exists():
                    file_path = candidate
                    found = True
                    break

            if not found:
                # Idempotent delete: file is already unlinked from disk! Purge any leftover temp artifacts
                cleanup_temp_file_for_filename(filename, target_parent, relative_path=target_parent + "/" + safe_name if target_parent else safe_name)
                return JSONResponse(content={"status": "success", "msg": "File deleted successfully"})

        if file_path.is_dir():
            await get_stream_manager().cancel_and_await_cleanup(file_path)
            gc.collect()
            def handle_remove_readonly(func, p, exc):
                import stat
                try:
                    os.chmod(p, stat.S_IWRITE)
                    func(p)
                except Exception:
                    pass
            shutil.rmtree(file_path, onerror=handle_remove_readonly)
            print("unlink_result=directory_deleted")
            print(f"exists_after={file_path.exists()}")
            return JSONResponse(content={"status": "success", "msg": "Folder deleted successfully"})
        elif file_path.is_file():
            await get_stream_manager().cancel_and_await_cleanup(file_path)
            retry_delays = [0.0, 0.05, 0.1, 0.2]
            deleted = False
            for attempt, delay in enumerate(retry_delays):
                if delay > 0:
                    gc.collect()
                    await asyncio.sleep(delay)
                try:
                    file_path.unlink()
                    print(f"OK: Deleted file: {file_path.name}")
                    deleted = True
                    print("unlink_result=success")
                    break
                except (PermissionError, OSError) as pe:
                    await get_stream_manager().cancel_and_await_cleanup(file_path)
                    continue

            if not deleted and file_path.exists():
                try:
                    trash_name = file_path.parent / f".trash_{uuid.uuid4().hex[:8]}_{file_path.name}"
                    file_path.rename(trash_name)
                    try:
                        trash_name.unlink()
                    except Exception:
                        pass
                except Exception as e2:
                    print(f"[WARN] Scheduled background deletion for locked file: {e2}")
                    # Store only the absolute path so is_pending_deletion() can
                    # perform exact comparison without substring collision.
                    LOCKED_DELETIONS_SET.add(str(file_path))

            if not deleted:
                print("unlink_result=failed_or_deferred")
            print(f"exists_after={file_path.exists()}")

            root_a = (UPLOAD_FOLDER / 'A').exists()
            root_b = (UPLOAD_FOLDER / 'B').exists()
            root_c = (UPLOAD_FOLDER / 'C').exists()
            inside_a = (UPLOAD_FOLDER / 'Inside' / 'A').exists()
            inside_b = (UPLOAD_FOLDER / 'Inside' / 'B').exists()
            inside_c = (UPLOAD_FOLDER / 'Inside' / 'C').exists()
            print(f"ROOT/A exists = {root_a}")
            print(f"ROOT/B exists = {root_b}")
            print(f"ROOT/C exists = {root_c}")
            print(f"Inside/A exists = {inside_a}")
            print(f"Inside/B exists = {inside_b}")
            print(f"Inside/C exists = {inside_c}")
            
        # Clean up version history and metadata for logical file
        try:
            from app.core.version_manager import VersionManager
            lf = VersionManager.get_logical_file_by_path(target_parent, safe_name) or VersionManager.get_logical_file_by_path(target_parent, filename)
            if lf:
                VersionManager.delete_logical_file(lf["id"])
        except Exception as ve:
            print(f"[VERSION_MANAGER] Delete cleanup warning: {ve}")

        cleanup_temp_file_for_filename(filename, target_parent, relative_path=target_parent + "/" + safe_name if target_parent else safe_name)
        # Broadcast via file_events WebSocket for instant cross-device sync
        try:
            broadcast_file_event_sync("delete", target_parent or "", safe_name)
        except Exception:
            pass
        return JSONResponse(content={"status": "success", "msg": "File deleted successfully"})
    except Exception as e:
        print(f"[ERR] Error in delete_file: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to delete file: {str(e)}"}
        )


@router.post("/api/forensic/export-trace", name="forensic_export_trace")
async def forensic_export_trace(request: Request):
    """Persist browser-captured forensic trace to artifacts for offline analysis."""
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    trace = payload.get("trace") if isinstance(payload, dict) else None
    if not isinstance(trace, list) or len(trace) == 0:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "RUNTIME TRACE NOT CAPTURED"})

    artifacts_dir = Path("testing") / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifacts_dir / "identity_delete_trace.json"
    txt_path = artifacts_dir / "identity_delete_trace.txt"

    with json_path.open("w", encoding="utf-8") as jf:
        json.dump(trace, jf, ensure_ascii=False, indent=2)

    with txt_path.open("w", encoding="utf-8") as tf:
        for row in trace:
            if not isinstance(row, dict):
                continue
            tf.write("timestamp=" + str(row.get("timestamp", "")) + "\n")
            tf.write("stage=" + str(row.get("stage", "")) + "\n")
            tf.write("event=" + str(row.get("event", "")) + "\n")
            tf.write("folder=" + str(row.get("folder", "")) + "\n")
            tf.write("name=" + str(row.get("name", "")) + "\n")
            tf.write("identity=" + str(row.get("identity", "")) + "\n")
            tf.write("details=" + json.dumps(row.get("details", {}), ensure_ascii=False) + "\n")
            tf.write("\n")

    return {
        "status": "success",
        "json": str(json_path),
        "txt": str(txt_path),
        "count": len(trace)
    }

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
        if FileValidator.is_dangerous_blocking_enabled(is_https) and extension in AdvancedFileValidator.BLOCKED_EXTENSIONS:
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
        
        # Resolve the upload path once so chunk storage stays folder-scoped.
        resolved = UploadPathResolver.resolve(parent_path, filename, UPLOAD_FOLDER)
        safe_filename = resolved.filename
        scoped_key = resolved.relative_path.as_posix()
        chunk_prefix = scoped_key.replace("/", "__")
        
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
        chunk_filename = f"{chunk_prefix}.part{part_number}"
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
                # Estimate total size as chunk size * total parts (approximation)
                estimated_size = len(chunk_data) * total_parts
                assembler.register_file(scoped_key, total_parts, scoped_key, estimated_size)
                print(f"[STREAM] Registered {scoped_key} for streaming assembly")
        
        # [START] ADD CHUNK TO STREAMING ASSEMBLY SYSTEM
        assembler = get_streaming_assembler()
        streaming_result = None
        if assembler:
            # Add chunk to streaming assembly for real-time processing
            streaming_result = add_streaming_chunk(scoped_key, part_number, chunk_data)
            if part_number == 1 or part_number == total_parts or (total_parts and part_number % max(1, total_parts // 10) == 0):
                print(f"[STREAM] Added chunk {part_number}/{total_parts or '?'} to streaming assembly: {streaming_result.get('status', 'unknown')}")
            
            # Check if file completed via streaming assembly
            if streaming_result and streaming_result.get("status") == "completed":
                print(f"[OK] File completed via streaming assembly: {scoped_key}")
                
                # Clean up temp chunks since file is completed via streaming
                try:
                    pattern = f"{chunk_prefix}.part*"
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
    # Initialise identity variables before the try block so that every exception
    # handler — including the outermost one — can use the scoped values rather
    # than re-deriving a basename-only fallback.
    scoped_key: Optional[str] = None
    chunk_prefix: Optional[str] = None
    safe_filename: str = secure_filename(filename) or "unknown"

    try:
        # [AUTH] Protocol detection
        is_https = request.url.scheme == "https"

        # Resolve the upload path once so finalization stays folder-scoped.
        resolved = UploadPathResolver.resolve(parent_path, filename, UPLOAD_FOLDER)
        safe_filename = resolved.filename
        scoped_key = resolved.relative_path.as_posix()
        chunk_prefix = scoped_key.replace("/", "__")
        
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
            streaming_status = check_streaming_status(scoped_key)
            print(f"[SEARCH] Streaming assembly status: {streaming_status}")
            
            if streaming_status and streaming_status.get('status') == 'ready':
                # File completed via streaming assembly
                file_info = get_assembled_file(scoped_key)
                if file_info and file_info.get('status') == 'ready':
                    streaming_completed = True
                    final_path = Path(file_info['path'])
                    print(f"[OK] File completed via streaming assembly: {scoped_key}")
                    print(f"   [DIR] Path: {final_path}")
                    print(f"   [STATS] Size: {final_path.stat().st_size:,} bytes")
        
        # Second, check if streaming-assembled file already exists (legacy check)
        potential_streaming_file = resolved.full_path
        if not streaming_completed and potential_streaming_file.exists():
            print(f"[STREAM] Found legacy streaming-assembled file: {scoped_key}")
            streaming_completed = True
            final_path = potential_streaming_file
            
            # [START] Check if background processing was completed during streaming
            if assembler:
                status = assembler.check_status(scoped_key)
                if status and status.get('validation_result'):
                    validation_from_background = status['validation_result']
                    background_processing_done = True
                    print(f"[FAST] Background processing completed during upload - no additional processing needed!")
        
        print(f"[SEARCH] Streaming completed: {streaming_completed}")
        print(f"[SEARCH] Background processing done: {background_processing_done}")
        print(f"[SEARCH] Final path: {final_path}")
        
        # [RETRY] Failsafe: Use traditional chunk combination if streaming didn't complete
        if not streaming_completed:
            print(f"[RETRY] Using traditional chunk assembly for {scoped_key}")
            
            # [START] Auto-detect actual chunks (adaptive chunked upload support)
            chunk_files = []
            part_num = 1
            while True:
                chunk_path = TEMP_CHUNKS_FOLDER / f"{chunk_prefix}.part{part_num}"
                if chunk_path.exists():
                    chunk_files.append((part_num, chunk_path))
                    part_num += 1
                else:
                    break
            
            actual_chunks = len(chunk_files)
            
            # If no chunks found but streaming was expected, assume streaming completed successfully
            if actual_chunks == 0 and assembler:
                # Check if streaming file was created
                potential_file = resolved.full_path
                if potential_file.exists():
                    print(f"[STREAM] Found streaming-assembled file: {scoped_key}")
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
                
                # Ensure target directory exists BEFORE attempting to open temporary assembly file
                resolved.target_directory.mkdir(parents=True, exist_ok=True)

                # Determine final filename
                final_filename = safe_filename + ".enc" if encrypt else safe_filename
                final_path = resolved.target_directory / f"{final_filename}.chunk.tmp"
                
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
                
                # Atomically move .chunk.tmp to the actual final destination
                actual_final_path = resolved.target_directory / final_filename
                if final_path != actual_final_path and final_path.exists():
                    import shutil
                    if actual_final_path.exists():
                        try:
                            actual_final_path.unlink()
                        except Exception:
                            pass
                    try:
                        final_path.replace(actual_final_path)
                    except Exception:
                        shutil.move(str(final_path), str(actual_final_path))
                
                final_path = actual_final_path
                
                if not final_path.exists():
                    return JSONResponse(
                        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                        content={"status": "error", "msg": "Final file assembly failed: Destination file missing after assembly"}
                    )
                
                # Register completed file with VersionManager
                from pathlib import PurePosixPath
                from app.core.version_manager import VersionManager
                clean_target_dir = str(resolved.relative_path.parent) if resolved.relative_path.parent != PurePosixPath(".") else ""
                VersionManager.create_version_transaction(
                    target_dir=clean_target_dir,
                    filename=final_filename,
                    incoming_file_path=final_path,
                    uploaded_by="chunk_assembly",
                    change_type="uploaded"
                )
        
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

        # Resolve target directory based on the resolved upload identity.
        target_dir = resolved.target_directory
        target_dir.mkdir(parents=True, exist_ok=True)

        if final_path and final_path.exists() and final_path.parent != target_dir:
            import shutil
            new_final_path = target_dir / final_path.name
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
                security_check = FileValidator.validate_uploaded_file(final_path, filename, is_https=is_https)
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
        
        # Clean up streaming registration if applicable.
        # Use scoped_key (e.g. "Inside/A") and chunk_prefix (e.g. "Inside__A")
        # — the same identifiers used during registration and chunk storage.
        if assembler and scoped_key:
            try:
                status = assembler.check_status(scoped_key)
                if status.get("status") != "not_found":
                    assembler.cleanup(scoped_key)

                    # Clean up temp chunk files using the scoped prefix so that
                    # ROOT/A chunks ("A.part*") and Inside/A chunks ("Inside__A.part*")
                    # are never confused.
                    if streaming_completed and chunk_prefix:
                        try:
                            pattern = f"{chunk_prefix}.part*"
                            temp_chunks_cleaned = 0
                            for chunk_file in TEMP_CHUNKS_FOLDER.glob(pattern):
                                chunk_file.unlink()
                                temp_chunks_cleaned += 1
                            if temp_chunks_cleaned > 0:
                                print(f"[CLEAN] Cleaned up {temp_chunks_cleaned} temp chunk files for {scoped_key}")
                        except Exception as cleanup_error:
                            print(f"[WARN] Could not clean up temp chunks for {scoped_key}: {cleanup_error}")

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
        
        # Broadcast via file_events WebSocket for instant cross-device sync
        try:
            broadcast_file_event_sync("upload", parent_path or "", final_path.name if final_path else "unknown")
        except Exception:
            pass

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
        # Clean up on error using the scoped chunk_prefix computed at the top of
        # this function.  chunk_prefix is None only when UploadPathResolver itself
        # raised before we could compute the scoped identity — fall back to the
        # pre-initialised safe_filename only in that degenerate case.
        try:
            _cleanup_prefix = chunk_prefix if chunk_prefix else safe_filename
            part_num = 1
            while True:
                chunk_path = TEMP_CHUNKS_FOLDER / f"{_cleanup_prefix}.part{part_num}"
                if chunk_path.exists():
                    chunk_path.unlink()
                    part_num += 1
                else:
                    break
        except Exception:
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
                # Sanitize every component of the browser-supplied relative path.
                # This prevents path traversal via crafted filenames such as
                # "nested/../../../etc/passwd" escaping folder_path.
                raw_parts = file.filename.replace('\\', '/').split('/')
                safe_parts = [secure_filename(p) for p in raw_parts if p and p != '..']
                safe_parts = [p for p in safe_parts if p]  # remove empty after sanitization

                if not safe_parts:
                    print(f"[WARN] upload_folder: skipping file with unresolvable path: {file.filename}")
                    failed_files.append(file.filename or '')
                    continue

                final_path = folder_path.joinpath(*safe_parts)

                # Traversal guard: final_path must remain inside folder_path.
                try:
                    final_path.resolve().relative_to(folder_path.resolve())
                except ValueError:
                    print(f"[ERR] upload_folder: path traversal blocked for: {file.filename}")
                    failed_files.append(file.filename or '')
                    continue

                final_path.parent.mkdir(parents=True, exist_ok=True)

                # Save the file
                await save_upload_file_async(file, final_path, encrypt)
                uploaded_files.append(str(final_path.relative_to(UPLOAD_FOLDER)))
                
        except Exception as e:
            print(f"[ERR] Failed to upload file {file.filename}: {e}")
            failed_files.append(file.filename)
    
    # Broadcast via file_events WebSocket for instant cross-device sync
    if uploaded_files:
        try:
            broadcast_file_event_sync("upload_folder", parent_path or "", folder_name)
        except Exception:
            pass

    return JSONResponse(content={
        "status": "success" if uploaded_files else "error",
        "msg": f"Folder '{folder_name}' uploaded with {len(uploaded_files)} files",
        "folder_name": folder_name,
        "files_uploaded": uploaded_files,
        "files_failed": failed_files,
        "total_files": len(files),
        "protocol": "HTTPS" if is_https else "HTTP"
    })

@router.get("/download-folder/{folder_name:path}", name="download_folder")
async def download_folder(folder_name: str):
    """Download an entire folder (including subfolders) as a high-speed ZIP file"""
    clean_name = urllib.parse.unquote(folder_name).replace('\\', '/').strip('/')
    parts = [secure_filename(p) for p in clean_name.split('/') if p and p != '..']
    parts = [p for p in parts if p]
    if not parts:
        raise HTTPException(status_code=400, detail="Invalid folder name")

    folder_path = UPLOAD_FOLDER.joinpath(*parts)
    try:
        folder_path.resolve().relative_to(UPLOAD_FOLDER.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not folder_path.exists() or not folder_path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    files_to_download = [
        (file_path, str(file_path.relative_to(folder_path)))
        for file_path in folder_path.rglob('*')
        if file_path.is_file()
    ]

    zip_name = f"{parts[-1]}.zip"
    return create_fast_zip_response(files_to_download, zip_name)

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
    parts = [p for p in clean_path.split("/") if p and p != ".." and p != "Home"]
    if not parts:
        # Fallback to root files listing if path resolved to root
        return await list_files()
    
    folder_path_obj = UPLOAD_FOLDER
    for part in parts:
        target_sub = folder_path_obj / part
        if target_sub.exists() or target_sub.is_dir():
            folder_path_obj = target_sub
        else:
            safe_part = secure_filename(part)
            if safe_part and (folder_path_obj / safe_part).is_dir():
                folder_path_obj = folder_path_obj / safe_part
            else:
                folder_path_obj = target_sub
    
    # Path traversal check
    try:
        folder_path_obj.resolve().relative_to(UPLOAD_FOLDER.resolve())
    except ValueError:
        return JSONResponse(status_code=403, content={"status": "error", "msg": "Access denied"})
    
    if not folder_path_obj.exists() or not folder_path_obj.is_dir():
        # Return clean empty files response rather than 404 so subfolder views never break
        return JSONResponse(content={
            "status": "success",
            "files": [],
            "count": 0,
            "folder": folder_path
        })
    
    try:
        # [TRACE DIAGNOSTIC] Log raw directory listing before filtering
        raw_items = list(folder_path_obj.iterdir())
        print(f"[TRACE] list_folder_contents: '{folder_path}' -> Raw items on disk: {[f.name for f in raw_items]}")

        files = []
        from app.core.version_manager import VersionManager
        clean_rel_folder = str(folder_path_obj.relative_to(UPLOAD_FOLDER)).replace("\\", "/") if folder_path_obj != UPLOAD_FOLDER else ""
        for f in folder_path_obj.iterdir():
            if f.is_file() and not f.name.endswith('.tmp') and not should_ignore_file(f.name):
                lf = VersionManager.get_logical_file_by_path(clean_rel_folder, f.name)
                v_count = lf.get("versionCount", 1) if lf else 1
                lf_id = lf.get("id") if lf else f"lf_{f.name}"
                latest_v_id = lf.get("latestVersionId") if lf else None
                files.append({
                    "name": f.name,
                    "identity": f"{clean_rel_folder}/{f.name}" if clean_rel_folder else f.name,
                    "size": format_size(f.stat().st_size),
                    "mtime": f.stat().st_mtime,
                    "isFolder": False,
                    "logicalFileId": lf_id,
                    "versionCount": v_count,
                    "hasVersions": (v_count > 1),
                    "latestVersionId": latest_v_id
                })
            elif f.is_dir() and not f.name.startswith('.'):
                files.append({
                    "name": f.name,
                    "identity": f"{clean_rel_folder}/{f.name}" if clean_rel_folder else f.name,
                    "size": format_size(sum(f2.stat().st_size for f2 in f.rglob('*') if f2.is_file())),
                    "mtime": f.stat().st_mtime,
                    "isFolder": True
                })
        # [TRACE DIAGNOSTIC] Log what the API is returning
        print(f"[TRACE] list_folder_contents: '{folder_path}' -> Filtered response: {[(f['name'], f.get('isFolder', False)) for f in files]}")
        # Folders first, then by mtime descending
        folders_list = sorted([f for f in files if f.get("isFolder")], key=lambda x: x["mtime"], reverse=True)
        regulars_list = sorted([f for f in files if not f.get("isFolder")], key=lambda x: x["mtime"], reverse=True)
        all_res = folders_list + regulars_list

        return JSONResponse(content={
            "status": "success",
            "files": all_res,
            "files_data": all_res,
            "count": len(all_res),
            "folder": folder_path
        })
    except Exception as e:
        print(f"[ERR] Error listing folder contents: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "msg": f"Failed to list folder contents: {e}"})


@router.post("/api/files/rename", name="rename_file")
@router.post("/rename", name="rename_file_alias")
@router.post("/files/rename", name="rename_file_alias2")
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
        # The resolved folder is the sole authority. Never fall back to a
        # filesystem-wide search: ROOT/A and Inside/A are independent objects.
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
    
    # 1. Deterministically cancel and await any active stream cleanup (file or folder contents)
    await get_stream_manager().cancel_and_await_cleanup(src_path)

    # 2. Execute operation with 4-attempt exponential backoff for OS kernel handle release latency
    retry_delays = [0.0, 0.05, 0.1, 0.2]
    last_err = None
    for attempt, delay in enumerate(retry_delays):
        if delay > 0:
            gc.collect()
            await asyncio.sleep(delay)
        try:
            os.rename(src_path, dst_path)
            # Update VersionManager metadata for renamed file
            try:
                from app.core.version_manager import VersionManager
                VersionManager.rename_logical_file(parent_path, safe_filename, safe_new)
            except Exception as ve:
                print(f"[VERSION_MANAGER] Rename sync warning: {ve}")
            # Rename .enc.meta sidecar if present
            meta_src = src_path.with_name(src_path.name + ".meta") if src_path.name.endswith(".enc") else src_path.with_suffix('.enc.meta')
            if meta_src.exists():
                meta_dst = dst_path.with_name(dst_path.name + ".meta") if dst_path.name.endswith(".enc") else dst_path.with_suffix('.enc.meta')
                try:
                    os.rename(meta_src, meta_dst)
                except Exception:
                    pass
            print(f"[RENAME] Renamed '{safe_filename}' to '{safe_new}' in '{src_path.parent}' (attempt {attempt + 1})")
            broadcast_file_event_sync("rename", parent_path or "", safe_new)
            return JSONResponse(content={
                "status": "success",
                "msg": f"Renamed to '{safe_new}'",
                "old_name": safe_filename,
                "new_name": safe_new
            })
        except (PermissionError, OSError) as e:
            last_err = e
            winerr = getattr(e, 'winerror', None)
            if winerr == 32 or 'being used by another process' in str(e):
                print(f"[WARN] Rename attempt {attempt + 1} blocked for '{safe_filename}' (file locked). Re-canceling streams...")
                await get_stream_manager().cancel_and_await_cleanup(src_path)
                continue
            break

    print(f"[ERR] Rename failed for '{safe_filename}': {last_err}")
    return JSONResponse(status_code=409 if (getattr(last_err, 'winerror', None) == 32 or 'being used by another process' in str(last_err)) else 500, content={
        "status": "error",
        "msg": f"Cannot rename '{safe_filename}': {last_err}"
    })


@router.post("/api/files/move", name="move_file")
@router.post("/move", name="move_file_alias")
@router.post("/files/move", name="move_file_alias2")
async def move_file(filename: str = Form(...), destination: str = Form(...), source_path: Optional[str] = Form(None), parent_path: Optional[str] = Form(None)):
    """Move a file or folder to a different directory"""
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid source filename"})
    
    source_parent = _clean_parent_path(source_path or parent_path)
    source_dir = _resolve_target_dir(source_parent)
    src_path = source_dir / safe_filename
    if not src_path.exists():
        # The resolved source path is the sole authority.
        return JSONResponse(status_code=404, content={"status": "error", "msg": "Source file or directory not found"})
    
    # Validate and clean destination directory path
    clean_dest = _clean_parent_path(destination)
    
    # Prevent path traversal
    if '..' in destination or '//' in destination:
        return JSONResponse(status_code=400, content={"status": "error", "msg": "Invalid path"})
    
    # Ensure destination directory exists
    dest_dir = _resolve_target_dir(clean_dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dst_path = dest_dir / safe_filename

    # Prevent moving a folder into itself or its own subfolder
    if src_path.is_dir():
        try:
            dst_path.resolve().relative_to(src_path.resolve())
            return JSONResponse(status_code=400, content={"status": "error", "msg": "Cannot move a folder into itself or its subfolder"})
        except ValueError:
            pass

    # Prevent overwrites
    if dst_path.exists():
        return JSONResponse(status_code=409, content={"status": "error", "msg": f"'{safe_filename}' already exists in destination"})
    
    await get_stream_manager().cancel_and_await_cleanup(src_path)

    try:
        shutil.move(str(src_path), str(dst_path))
        # Update VersionManager metadata for moved item
        try:
            from app.core.version_manager import VersionManager
            VersionManager.move_logical_file(source_parent, clean_dest, safe_filename)
        except Exception as ve:
            print(f"[VERSION_MANAGER] Move sync warning: {ve}")
        print(f"[MOVE] Moved '{safe_filename}' from '{source_parent}' to '{clean_dest}'")
        broadcast_file_event_sync("move", clean_dest, safe_filename)
        if source_parent != clean_dest:
            broadcast_file_event_sync("delete", source_parent, safe_filename)
        return JSONResponse(content={
            "status": "success",
            "msg": f"Item moved to '{clean_dest}'",
            "filename": safe_filename,
            "destination": clean_dest
        })
    except (PermissionError, OSError) as e:
        # WinError 32: file locked by another process (e.g. currently being streamed/previewed)
        winerr = getattr(e, 'winerror', None)
        if winerr == 32 or 'being used by another process' in str(e):
            print(f"[WARN] Move blocked: '{safe_filename}' is locked (streaming/open). Retrying after gc...")
            gc.collect()
            time.sleep(0.1)
            try:
                shutil.move(str(src_path), str(dst_path))
                print(f"[MOVE] Moved '{safe_filename}' to '{destination}' on retry")
                broadcast_file_event_sync("move", destination or "", safe_filename)
                return JSONResponse(content={
                    "status": "success",
                    "msg": f"File moved to '{destination}'",
                    "filename": safe_filename,
                    "destination": destination
                })
            except Exception:
                pass
            return JSONResponse(status_code=409, content={
                "status": "error",
                "msg": f"Cannot move '{safe_filename}' — it is currently open or being streamed. Close the preview and try again.",
                "file_locked": True
            })
        print(f"[ERR] Move error: {e}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "msg": f"Failed to move file: {e}"
        })
    except Exception as e:
        print(f"[ERR] Move error: {e}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "msg": f"Failed to move file: {e}"
        })


@router.post("/api/files/mkdir", name="create_folder")
@router.post("/mkdir", name="create_folder_alias")
@router.post("/files/mkdir", name="create_folder_alias2")
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
        broadcast_file_event_sync("mkdir", parent_path or "", safe_name)
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
            if (folder_path_obj / part).is_dir():
                folder_path_obj = folder_path_obj / part
            elif safe_part and (folder_path_obj / safe_part).is_dir():
                folder_path_obj = folder_path_obj / safe_part
            elif safe_part:
                folder_path_obj = folder_path_obj / safe_part
            else:
                folder_path_obj = folder_path_obj / part
        
        # Path traversal check
        try:
            folder_path_obj.resolve().relative_to(UPLOAD_FOLDER.resolve())
        except ValueError:
            return JSONResponse(status_code=403, content={"status": "error", "msg": "Access denied"})
        
        if not folder_path_obj.exists() or not folder_path_obj.is_dir():
            return JSONResponse(content={"status": "success", "msg": "Folder deleted successfully"})
        
        # Cancel any active streams for files inside this folder hierarchy
        await get_stream_manager().cancel_and_await_cleanup(folder_path_obj)
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
        broadcast_file_event_sync("delete_folder", folder_path, folder_path)
        return JSONResponse(content={
            "status": "success",
            "msg": f"Folder '{folder_path}' deleted successfully"
        })
    except Exception as e:
        print(f"[ERR] Failed to delete folder {folder_path}: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "msg": f"Failed to delete folder: {str(e)}"})
