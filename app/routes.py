import os
import io
import time
import re
from typing import List, Optional, Tuple
from pathlib import Path
from mimetypes import guess_type
from zipfile import ZipFile

from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Query, Form
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse,
    JSONResponse, Response
)
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND, HTTP_400_BAD_REQUEST

from app.aes_utils import encrypt_bytes_legacy, decrypt_bytes_legacy
from app.aes_config import AESConfig
from app.config import is_allowed_file
from app.validation import validate_upload_files, secure_filename

# === Setup ===
router = APIRouter()
UPLOAD_FOLDER = Path("app/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# === Chunked Upload Setup ===
TEMP_CHUNKS_FOLDER = UPLOAD_FOLDER / "temp_chunks"
TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)

# Templates - keep local for routes that need it
templates = Jinja2Templates(directory="app/templates")

# === 🔍 VALIDATION CONSTANTS & FUNCTIONS ===
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB maximum file size
MAX_FILENAME_LENGTH = 255
MAX_CONCURRENT_UPLOADS = 5  # Maximum parallel uploads per session

# Allowed MIME types for security
ALLOWED_MIME_TYPES = {
    'application/pdf', 'application/zip', 'application/x-zip-compressed',
    'application/octet-stream', 'application/msword', 'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain', 'text/csv', 'text/html', 'text/css', 'text/javascript',
    'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp',
    'video/mp4', 'video/avi', 'video/mov', 'video/mkv', 'video/webm',
    'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/m4a', 'audio/flac'
}

# Dangerous file extensions to block
BLOCKED_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js', '.jar',
    '.msi', '.dll', '.sys', '.bin', '.deb', '.rpm', '.dmg', '.pkg'
}

def validate_filename(filename: str) -> Tuple[bool, str]:
    """
    Comprehensive filename validation for security and compatibility.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not filename:
        return False, "Filename cannot be empty"
    
    if len(filename) > MAX_FILENAME_LENGTH:
        return False, f"Filename too long (max {MAX_FILENAME_LENGTH} characters)"
    
    # Check for dangerous characters
    dangerous_chars = r'[<>:"|?*\x00-\x1f]'
    if re.search(dangerous_chars, filename):
        return False, "Filename contains invalid characters"
    
    # Check for dangerous extensions
    file_ext = Path(filename).suffix.lower()
    if file_ext in BLOCKED_EXTENSIONS:
        return False, f"File type {file_ext} is not allowed for security reasons"
    
    # Check for reserved Windows names
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
        'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
        'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in reserved_names:
        return False, f"Filename '{filename}' is reserved by the system"
    
    # Check for hidden files or files starting with dots (except .enc)
    if filename.startswith('.') and not filename.endswith('.enc'):
        return False, "Hidden files are not allowed"
    
    return True, ""

def validate_file_size(file_size: int) -> Tuple[bool, str]:
    """
    Validate file size constraints.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if file_size <= 0:
        return False, "File is empty"
    
    if file_size > MAX_FILE_SIZE:
        size_gb = file_size / (1024 * 1024 * 1024)
        max_gb = MAX_FILE_SIZE / (1024 * 1024 * 1024)
        return False, f"File too large ({size_gb:.1f}GB). Maximum allowed: {max_gb}GB"
    
    return True, ""

def validate_mime_type(filename: str, content_type: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validate MIME type for security.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Get MIME type from filename
    guessed_type, _ = guess_type(filename)
    
    # Use provided content type or guessed type
    mime_type = content_type or guessed_type
    
    if not mime_type:
        # Allow unknown types for now, but log them
        print(f"⚠️ Unknown MIME type for file: {filename}")
        return True, ""
    
    # Check against allowed types
    if mime_type not in ALLOWED_MIME_TYPES:
        return False, f"File type '{mime_type}' is not allowed"
    
    return True, ""

def validate_upload_request(filename: str, file_size: Optional[int] = None, content_type: Optional[str] = None) -> Tuple[bool, str]:
    """
    Comprehensive validation for upload requests.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Validate filename
    is_valid, error_msg = validate_filename(filename)
    if not is_valid:
        return False, f"Invalid filename: {error_msg}"
    
    # Validate file size if provided
    if file_size is not None:
        is_valid, error_msg = validate_file_size(file_size)
        if not is_valid:
            return False, f"Invalid file size: {error_msg}"
    
    # Validate MIME type
    is_valid, error_msg = validate_mime_type(filename, content_type)
    if not is_valid:
        return False, f"Invalid file type: {error_msg}"
    
    return True, ""

# === Utility Functions ===
def format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"

def get_file_list():
    return sorted([
        {
            "name": f.name,
            "size": format_size(f.stat().st_size),
            "mtime": f.stat().st_mtime
        }
        for f in UPLOAD_FOLDER.iterdir() if f.is_file()
    ], key=lambda x: x["mtime"], reverse=True)

def get_unique_filename(directory: Path, filename: str) -> str:
    base = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    new_name = filename
    while (directory / new_name).exists():
        new_name = f"{base}_{counter}{ext}"
        counter += 1
    return new_name

def save_upload_file_sync(upload_file: UploadFile, destination: Path, encrypt=False):
    data = upload_file.file.read()
    if encrypt:
        try:
            # Import streaming encryption functions
            from .aes_utils import encrypt_file_stream
            
            # Add file integrity validation for encrypted files
            import hashlib
            original_hash = hashlib.sha256(data).hexdigest()
            print(f"🔒 Original file hash: {original_hash}")
            
            # Use memory-efficient streaming encryption
            encrypted_data, metadata = encrypt_file_stream(data, chunk_size=1024 * 1024)  # 1MB chunks
            
            # Enhanced metadata with integrity information
            metadata['original_hash'] = original_hash
            metadata['original_size'] = str(len(data))
            metadata['encrypted_size'] = str(len(encrypted_data))
            metadata['encryption_method'] = 'streaming'
            
            # Save metadata to separate file
            metadata_path = destination.with_suffix('.enc.meta')
            with metadata_path.open("w") as meta_file:
                import json
                json.dump(metadata, meta_file, indent=2)
            
            # Write encrypted data
            with destination.open("wb") as f:
                f.write(encrypted_data)
                
            print(f"🔒 File encrypted using streaming AES with {len(encrypted_data)} bytes")
        except Exception as e:
            print(f"🚨 Streaming encryption failed: {e}")
            raise Exception(f"AES encryption failed: {e}")
    else:
        with destination.open("wb") as f:
            f.write(data)

def scan_file(path: Path):
    print(f"🧪 Scanning file in background: {path}")
    # Placeholder for virus scan / checksum / DLP
    # Simulate processing delay
    # time.sleep(1)

# === Routes ===

@router.get("/", response_class=HTMLResponse, name="home")
async def home(request: Request):
    files = get_file_list()
    
    # Add helpful debug info for HTTPS troubleshooting
    protocol = request.url.scheme
    host = request.headers.get("host", "unknown")
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "msg": "Lanvan",
        "files": [f["name"] for f in files],
        "debug_info": {
            "protocol": protocol,
            "host": host,
            "port": "5000" if ":5000" in host else "unknown"
        }
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
    
    # 🔍 Comprehensive input validation
    is_valid, error_messages, validated_files = validate_upload_files(files, encrypt, is_https)
    if not is_valid:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "; ".join(error_messages)
        })

    # 🚫 Enforce encryption restrictions using centralized config
    if encrypt:
        validation = AESConfig.validate_file_for_aes(0, is_https)  # Size will be checked per file
        if not validation['valid'] and 'HTTPS' in validation['error']:
            return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
                "status": "error",
                "msg": validation['error']
            })

    uploaded = []
    
    print(f"🔍 Processing {len(files)} files for upload...")

    for i, file in enumerate(files):
        print(f"📁 Processing file {i+1}/{len(files)}: {file.filename}")
        
        if not file.filename:
            print(f"❌ Skipping file {i+1}: No filename")
            continue

        # Use validated filename
        validated_file = validated_files[i] if i < len(validated_files) else None
        if not validated_file:
            print(f"❌ Skipping file {i+1}: Validation failed")
            continue
            
        filename = validated_file['sanitized_name']
        file_size = validated_file['size']
        print(f"📋 File {i+1} details: {filename} ({file_size} bytes)")

        # Double-check with existing validation (defense in depth)
        if not is_allowed_file(filename):
            print(f"❌ Skipping file {i+1}: File type not allowed")
            continue

        # Check size using centralized AES config
        if encrypt:
            validation = AESConfig.validate_file_for_aes(file_size, is_https)
            if not validation['valid']:
                print(f"❌ File {i+1} failed AES validation: {validation['error']}")
                return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
                    "status": "error",
                    "msg": validation['error']
                })

        save_name = filename + ".enc" if encrypt else filename
        filepath = UPLOAD_FOLDER / get_unique_filename(UPLOAD_FOLDER, save_name)

        print(f"💾 Saving file {i+1} as: {filepath.name}")
        save_upload_file_sync(file, filepath, encrypt=encrypt)
        background_tasks.add_task(scan_file, filepath)
        uploaded.append(filepath.name)
        print(f"✅ File {i+1} uploaded successfully: {filepath.name}")

    print(f"🎉 Upload complete! {len(uploaded)} files uploaded: {uploaded}")

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
                        # Fallback to legacy decryption
                        decrypted_data = decrypt_bytes_legacy(encrypted_data)
                        print(f"🔒 Used legacy decryption for {path.name}")
                    
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
            # 🚀 Ultra-fast regular file streaming with optimized buffer
            try:
                with open(path, "rb") as file:
                    chunks_sent = 0
                    while True:
                        chunk = file.read(STREAM_BUFFER_SIZE)
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
                        # Decrypt .enc files before adding to ZIP with error handling
                        try:
                            decrypted_data = decrypt_bytes_legacy(file.read_bytes())
                            zip_file.writestr(file.stem, decrypted_data)
                        except Exception as decrypt_error:
                            print(f"🚨 AES decryption failed for {file.name}: {decrypt_error}")
                            # Add error file to ZIP instead of crashing
                            error_content = f"Error: Failed to decrypt {file.name}. File may be corrupted or not properly encrypted."
                            zip_file.writestr(f"{file.stem}_DECRYPT_ERROR.txt", error_content.encode('utf-8'))
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
    import gc
    
    try:
        files_deleted = 0
        chunks_deleted = 0
        files_locked = 0
        
        # Force garbage collection to release any file handles
        gc.collect()
        
        # Clear main upload files with retry mechanism for Windows
        for file in UPLOAD_FOLDER.iterdir():
            if file.is_file():
                deleted = False
                for attempt in range(3):  # Try 3 times
                    try:
                        file.unlink()
                        files_deleted += 1
                        deleted = True
                        break
                    except PermissionError as e:
                        if attempt < 2:  # Not the last attempt
                            print(f"🔄 File locked (attempt {attempt + 1}/3): {file.name}")
                            time.sleep(0.5)  # Wait 500ms before retry
                            gc.collect()  # Try to release handles
                        else:
                            files_locked += 1
                            print(f"🔒 File still in use after 3 attempts: {file.name} - {e}")
                    except Exception as e:
                        print(f"❌ Error deleting file {file}: {e}")
                        break
        
        # Clear temporary chunks
        if TEMP_CHUNKS_FOLDER.exists():
            for chunk_file in TEMP_CHUNKS_FOLDER.iterdir():
                if chunk_file.is_file():
                    try:
                        chunk_file.unlink()
                        chunks_deleted += 1
                    except Exception as e:
                        print(f"Error deleting chunk {chunk_file}: {e}")
        
        # Enhanced status message
        if files_locked > 0:
            print(f"WARNING: Cleared {files_deleted} files and {chunks_deleted} chunks ({files_locked} files still in use)")
            return JSONResponse(content={
                "status": "warning",
                "msg": f"Cleared {files_deleted} files and {chunks_deleted} chunks ({files_locked} files still in use)",
                "files_deleted": files_deleted,
                "chunks_deleted": chunks_deleted,
                "files_locked": files_locked
            })
        else:
            print(f"OK: Cleared {files_deleted} files and {chunks_deleted} chunks")
            return JSONResponse(content={
                "status": "success",
                "msg": f"Cleared {files_deleted} files and {chunks_deleted} chunks",
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
        
        # 🔍 COMPREHENSIVE VALIDATION: Validate upload request
        is_valid, error_msg = validate_upload_request(filename, content_type=chunk.content_type)
        if not is_valid:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": f"Validation failed: {error_msg}"}
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
    """Combine all chunks into final file - supports both HTTP and HTTPS with dynamic chunk detection"""
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
        if actual_chunks == 0:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "No chunks found for this file"}
            )

        # Check if encryption is requested and validate using centralized config
        if encrypt:
            # Calculate total size by checking all actual chunks
            total_size = sum(chunk_path.stat().st_size for _, chunk_path in chunk_files)
            
            validation = AESConfig.validate_file_for_aes(total_size, is_https)
            if not validation['valid']:
                # Clean up chunks
                for _, chunk_path in chunk_files:
                    if chunk_path.exists():
                        chunk_path.unlink()
                        
                return JSONResponse(
                    status_code=HTTP_400_BAD_REQUEST,
                    content={
                        "status": "error",
                        "msg": validation['error']
                    }
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
                        chunk_data = encrypt_bytes_legacy(chunk_data)
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
        
        # Add background scan task
        background_tasks.add_task(scan_file, final_path)
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"File '{final_path.name}' uploaded successfully via {'HTTPS' if is_https else 'HTTP'} ({actual_chunks} chunks combined)",
            "filename": final_path.name,
            "actual_chunks": actual_chunks,
            "estimated_chunks": total_parts,
            "protocol": "HTTPS" if is_https else "HTTP"
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
