import os
import io
import time
from typing import List, Optional
from pathlib import Path
from mimetypes import guess_type
from zipfile import ZipFile
import base64

import qrcode
from PIL import Image

from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, Query, Form
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse,
    JSONResponse, Response
)
from fastapi.templating import Jinja2Templates
from app.clipboard_ws import clipboard_ws_manager
from starlette.status import HTTP_302_FOUND, HTTP_400_BAD_REQUEST, HTTP_403_FORBIDDEN, HTTP_500_INTERNAL_SERVER_ERROR

from app.aes_utils import encrypt_session_data, decrypt_session_data
from app.aes_config import AESConfig
from app.validation import (
    validate_upload_files, 
    validate_upload_files_enhanced,
    secure_filename,
    is_allowed_file,
    FileValidator,
    AdvancedFileValidator
)
from app.simple_mdns import mdns_manager

# === Setup ===
router = APIRouter()
UPLOAD_FOLDER = Path("app/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# === Chunked Upload Setup ===
TEMP_CHUNKS_FOLDER = UPLOAD_FOLDER / "temp_chunks"
TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)

# Templates - keep local for routes that need it
templates = Jinja2Templates(directory="app/templates")

# === 🔍 CONSTANTS ===
MAX_CONCURRENT_UPLOADS = 5  # Maximum parallel uploads per session

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

@router.get("/loading", response_class=HTMLResponse, name="loading")
async def loading_page(request: Request, redirect: str = "/"):
    """Loading page shown while resources are being prepared"""
    return templates.TemplateResponse("loading.html", {
        "request": request,
        "redirect_url": redirect
    })

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
        },
        "show_both_sections": True,  # Show both file transfer and clipboard
        "default_view": "file"       # Default to file transfer view
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
    
    # 🔍 ENHANCED SECURITY: Comprehensive input validation with content analysis
    is_valid, error_messages, validated_files, security_warnings = validate_upload_files_enhanced(files, encrypt, is_https)
    if not is_valid:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error", 
            "msg": "; ".join(error_messages),
            "security_blocked": True
        })
    
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
                        # Note: Legacy encryption not supported - file may be corrupted
                        print(f"⚠️ Cannot decrypt {path.name} - legacy encryption no longer supported")
                        return Response(
                            content=f"Error: File {path.name} uses unsupported legacy encryption",
                            status_code=400
                        )
                    
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
    import gc
    
    try:
        files_deleted = 0
        chunks_deleted = 0
        files_locked = 0
        
        # OPTIMIZED: Remove forced GC - let Python handle naturally
        
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
                            # OPTIMIZED: Removed excessive gc.collect() from retry loop
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
        
        # 🛡️ ENHANCED SECURITY: Validate the assembled file before finalizing
        try:
            # Perform comprehensive security validation on the assembled file
            security_check = AdvancedFileValidator.validate_uploaded_file(final_path)
            
            if not security_check['valid']:
                # File failed security validation - delete it immediately
                if final_path.exists():
                    final_path.unlink()
                    
                return JSONResponse(
                    status_code=HTTP_403_FORBIDDEN,
                    content={
                        "status": "security_blocked",
                        "msg": f"🛡️ Security Check Failed: {security_check['error']}",
                        "security_details": {
                            "blocked_reason": security_check.get('error', 'Unknown security violation'),
                            "detected_type": security_check.get('detected_type'),
                            "claimed_extension": security_check.get('claimed_extension'),
                            "file_deleted": True
                        }
                    }
                )
                
        except Exception as validation_error:
            print(f"⚠️ Security validation error for {final_path.name}: {validation_error}")
            # If validation fails, delete the file as a precaution
            if final_path.exists():
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
        background_tasks.add_task(scan_file, final_path)
        
        # Success response with security confirmation
        success_msg = f"File '{final_path.name}' uploaded successfully via {'HTTPS' if is_https else 'HTTP'} ({actual_chunks} chunks combined)"
        if security_check.get('warnings'):
            success_msg += f" ⚠️ Security Notes: {'; '.join(security_check['warnings'])}"
        
        return JSONResponse(content={
            "status": "success",
            "msg": success_msg,
            "filename": final_path.name,
            "actual_chunks": actual_chunks,
            "estimated_chunks": total_parts,
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
        
        # Use mDNS manager's offline-capable method to get LAN IP
        lan_ip = mdns_manager.get_lan_ip()
        
        # Get mDNS info
        mdns_info = mdns_manager.get_mdns_info()
        
        # Get hybrid URL (mDNS first, fallback to IP)
        hybrid_url = mdns_manager.get_hybrid_url()
        
        # Also provide separate URL components for QR code generation
        protocol = "https" if mdns_manager.use_https else "http"
        port = mdns_manager.port
        
        # Format LAN IP URL using the same logic as mDNS URLs
        if (port == 80 and protocol == "http") or (port == 443 and protocol == "https"):
            lan_ip_url = f"{protocol}://{lan_ip}"
        else:
            lan_ip_url = f"{protocol}://{lan_ip}:{port}"
        
        return JSONResponse(content={
            "status": "success",
            "lan_ip": lan_ip,
            "lan_ip_url": lan_ip_url,
            "hostname": socket.gethostname(),
            "mdns": mdns_info,
            "hybrid_url": hybrid_url,
            "protocol": protocol,
            "port": port
        })
    except Exception as e:
        # Create fallback URL using the same format logic as mdns_manager
        protocol = "https" if mdns_manager.use_https else "http"
        port = mdns_manager.port
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
    """Generate QR code locally without internet dependency"""
    try:
        # Create QR code with dynamic sizing
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=max(1, size // 25),  # Dynamic box size based on requested size
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)

        # Create image - let qrcode handle the sizing
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        img_buffer = io.BytesIO()
        
        # Save using the qrcode image's save method
        try:
            qr_img.save(img_buffer, 'PNG')
        except Exception:
            # Fallback: try without format specification
            try:
                qr_img.save(img_buffer)
            except Exception as e:
                # If all else fails, let it raise to be caught by outer handler
                raise Exception(f"QR image save failed: {e}")
        
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

# === FULL PAGE CLIPBOARD ROUTE ===
@router.get("/clipboard", response_class=HTMLResponse, name="clipboard_page")
async def clipboard_page(request: Request):
    files = get_file_list()  # Include files for seamless switching
    
    # Render the same template, but with clipboard as default view
    return templates.TemplateResponse("index.html", {
        "request": request,
        "msg": "Lanvan",
        "files": [f["name"] for f in files],
        "show_both_sections": True,  # Show both sections
        "default_view": "clipboard"  # Default to clipboard view
    })

# === CLIPBOARD SYSTEM ENDPOINTS ===

# In-memory clipboard storage for current session
clipboard_history = []
clipboard_id_counter = 0

@router.post("/api/clipboard/add", name="clipboard_add")
async def add_to_clipboard(
    request: Request,
    data: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """Add content to clipboard - supports text, images, and files"""
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
            
            # Create clipboard item for file
            clipboard_item = {
                "id": clipboard_id_counter,
                "type": "file",
                "content_type": content_type,
                "filename": file.filename,
                "size": file_size,
                "data": file_content,
                "timestamp": timestamp,
                "formatted_time": time.strftime("%I:%M:%S %p", time.localtime(timestamp)),
                "preview": generate_file_preview(file.filename, file_content, content_type)
            }
            
        elif data:
            # Handle text/data content
            content_size = len(data.encode('utf-8'))
            
            # Detect content type
            if data.startswith('data:image/'):
                content_type = 'image_base64'
                preview = "Base64 image data"
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
                "preview": clipboard_item["preview"]
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
        # Return sanitized clipboard history (without large data)
        history = []
        for item in clipboard_history:
            sanitized_item = {
                "id": item["id"],
                "type": item["type"],
                "content_type": item["content_type"],
                "size": item["size"],
                "timestamp": item["formatted_time"],
                "preview": item["preview"]
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

@router.post("/api/clipboard/upload/{item_id}", name="clipboard_upload")
async def upload_from_clipboard(
    item_id: int,
    background_tasks: BackgroundTasks,
    encrypt: bool = Query(False, description="Encrypt file with AES-256 if true")
):
    """Upload clipboard item to main file storage"""
    try:
        # Find clipboard item
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
        
        if item["type"] != "file":
            return JSONResponse(
                status_code=400,
                content={"status": "error", "msg": "Only file items can be uploaded"}
            )
        
        # Validate file for upload
        filename = item["filename"]
        file_data = item["data"]
        file_size = len(file_data)
        
        # Check if file type is allowed
        if not is_allowed_file(filename):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "msg": "File type not allowed"}
            )
        
        # Check AES encryption requirements
        if encrypt:
            # Determine if HTTPS (can't determine from clipboard context, assume HTTP for safety)
            is_https = False  # Conservative assumption
            validation = AESConfig.validate_file_for_aes(file_size, is_https)
            if not validation['valid']:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "msg": validation['error']}
                )
        
        # Create unique filename
        save_name = filename + ".enc" if encrypt else filename
        filepath = UPLOAD_FOLDER / get_unique_filename(UPLOAD_FOLDER, save_name)
        
        # Save file
        if encrypt:
            try:
                from .aes_utils import encrypt_file_stream
                import hashlib
                
                # Calculate original hash
                original_hash = hashlib.sha256(file_data).hexdigest()
                
                # Encrypt the data
                encrypted_data, metadata = encrypt_file_stream(file_data, chunk_size=1024 * 1024)
                
                # Enhanced metadata
                metadata['original_hash'] = original_hash
                metadata['original_size'] = str(len(file_data))
                metadata['encrypted_size'] = str(len(encrypted_data))
                metadata['encryption_method'] = 'streaming'
                metadata['source'] = 'clipboard'
                
                # Save metadata
                metadata_path = filepath.with_suffix('.enc.meta')
                with metadata_path.open("w") as meta_file:
                    import json
                    json.dump(metadata, meta_file, indent=2)
                
                # Write encrypted data
                with filepath.open("wb") as f:
                    f.write(encrypted_data)
                    
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "msg": f"AES encryption failed: {str(e)}"}
                )
        else:
            # Save as regular file
            with filepath.open("wb") as f:
                f.write(file_data)
        
        # Add background scan task
        background_tasks.add_task(scan_file, filepath)
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"Uploaded from clipboard: {filepath.name}",
            "filename": filepath.name,
            "size": format_size(file_size),
            "encrypted": encrypt
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "msg": f"Failed to upload from clipboard: {str(e)}"}
        )

@router.delete("/api/clipboard/clear", name="clipboard_clear")
async def clear_clipboard():
    """Clear all clipboard history"""
    global clipboard_history
    try:
        count = len(clipboard_history)
        clipboard_history.clear()
        
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

def generate_file_preview(filename: str, file_data: bytes, content_type: str) -> str:
    """Generate preview text for file content"""
    try:
        if content_type == 'image':
            return f"Image: {filename} ({format_size(len(file_data))})"
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
