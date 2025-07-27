import os
import io
import time
from typing import List
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
from werkzeug.utils import secure_filename

from app.aes_utils import encrypt_bytes, decrypt_bytes
from app.config import is_allowed_file

# === Setup ===
router = APIRouter()
UPLOAD_FOLDER = Path("app/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# === Chunked Upload Setup ===
TEMP_CHUNKS_FOLDER = UPLOAD_FOLDER / "temp_chunks"
TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory="app/templates")

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
        data = encrypt_bytes(data)
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
    
    # 🚫 Enforce encryption restrictions (re-enabled for testing)
    if encrypt and not is_https:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "AES encryption is only available over HTTPS connections for security."
        })

    uploaded = []
    MAX_AES_SIZE_MB = 200
    MAX_AES_SIZE_BYTES = MAX_AES_SIZE_MB * 1024 * 1024

    for file in files:
        if not file.filename:
            continue

        filename = secure_filename(file.filename)
        if not is_allowed_file(filename):
            continue

        # Check size
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        if encrypt and file_size > MAX_AES_SIZE_BYTES:
            return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
                "status": "error",
                "msg": "AES is blocked for files >200MB to ensure smooth & efficient file transfer."
            })

        save_name = filename + ".enc" if encrypt else filename
        filepath = UPLOAD_FOLDER / get_unique_filename(UPLOAD_FOLDER, save_name)

        save_upload_file_sync(file, filepath, encrypt=encrypt)
        background_tasks.add_task(scan_file, filepath)
        uploaded.append(filepath.name)

    if not uploaded:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No valid files processed"
        })

    protocol_info = "HTTPS" if is_https else "HTTP"
    return JSONResponse(content={
        "status": "success",
        "msg": f"{len(uploaded)} file(s) uploaded via {protocol_info}",
        "files": uploaded,
        "protocol": protocol_info
    })

@router.get("/download/{filename}", name="download_file")
@router.head("/download/{filename}")
async def download_file(filename: str, request: Request):
    safe_name = secure_filename(filename)
    file_path = UPLOAD_FOLDER / safe_name

    if not file_path.is_file():
        return Response("File not found", status_code=404)

    mime_type, _ = guess_type(str(file_path))
    file_size = file_path.stat().st_size
    
    # ✅ Handle HEAD requests - return headers only for file info
    if request.method == "HEAD":
        headers = {
            "Content-Length": str(file_size),
            "Content-Type": mime_type or "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Accept-Ranges": "bytes",  # Indicate support for range requests
            "Cache-Control": "public, max-age=86400"
        }
        return Response(content="", headers=headers, status_code=200)
    
    # ✅ Determine protocol (HTTP vs HTTPS)
    is_https = request.url.scheme == "https"
    
    # 🔐 Enforcement Rules:
    # 1. .enc files: Always use full download (no chunking)
    # 2. Files ≥250MB: Use chunked download if not .enc
    # 3. Files <250MB: Always use full download
    
    is_enc_file = safe_name.endswith(".enc")
    is_large_file = file_size >= 250 * 1024 * 1024  # 250MB threshold
    
    # 📦 Chunked download logic
    if is_large_file and not is_enc_file:
        return await chunked_download_file(file_path, safe_name, mime_type, file_size, request)
    else:
        return await full_download_file(file_path, safe_name, mime_type, file_size)

async def full_download_file(file_path: Path, safe_name: str, mime_type: str | None, file_size: int):
    """Ultra-optimized full file download - for small files and .enc files"""
    # 🚀 Much larger buffer for maximum speed - 32MB buffer (4x improvement)
    STREAM_BUFFER_SIZE = 32 * 1024 * 1024  # 32MB buffer (was 8MB)
    
    def stream_file_ultra_optimized(path: Path):
        if path.suffix == ".enc":
            # 🔐 Optimized .enc file handling with streaming decryption
            with open(path, "rb") as file:
                encrypted_data = file.read()
                decrypted_data = decrypt_bytes(encrypted_data)
                
                # 🚀 Stream in very large chunks for maximum speed
                data_length = len(decrypted_data)
                for i in range(0, data_length, STREAM_BUFFER_SIZE):
                    chunk_end = min(i + STREAM_BUFFER_SIZE, data_length)
                    yield decrypted_data[i:chunk_end]
        else:
            # 🚀 Ultra-fast regular file streaming with optimized buffer
            with open(path, "rb") as file:
                while True:
                    chunk = file.read(STREAM_BUFFER_SIZE)
                    if not chunk:
                        break
                    yield chunk

    return StreamingResponse(
        stream_file_ultra_optimized(file_path),
        media_type=mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400",
            "X-Accel-Buffering": "no",
            "X-Download-Type": "ultra-optimized-full",  # Updated indicator
            "X-Buffer-Size": "32MB"  # Performance indicator
        }
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
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        for file in UPLOAD_FOLDER.iterdir():
            if file.is_file():
                if file.suffix == ".enc":
                    decrypted_data = decrypt_bytes(file.read_bytes())
                    zip_file.writestr(file.stem, decrypted_data)
                else:
                    zip_file.write(file, arcname=file.name)
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=all_files.zip"}
    )

@router.post("/clear", name="clear_files")
async def clear_files():
    """Clear all uploaded files and temporary chunks with enhanced Windows compatibility"""
    import time
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
            print(f"⚠️  Cleared {files_deleted} files and {chunks_deleted} chunks ({files_locked} files still in use)")
        else:
            print(f"✅ Cleared {files_deleted} files and {chunks_deleted} chunks")
            
        return RedirectResponse(url="/", status_code=HTTP_302_FOUND)
        
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
            print(f"✅ Deleted file: {safe_name}")
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
        
        # Create chunk filename
        chunk_filename = f"{safe_filename}.part{part_number}"
        chunk_path = TEMP_CHUNKS_FOLDER / chunk_filename
        
        # Save the chunk
        chunk_data = await chunk.read()
        if not chunk_data:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": f"Chunk {part_number} is empty"}
            )
            
        with open(chunk_path, "wb") as f:
            f.write(chunk_data)
        
        # Prepare response message
        chunk_size_mb = len(chunk_data) / (1024 * 1024)
        total_parts_msg = f"/{total_parts}" if total_parts else ""
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"Chunk {part_number}{total_parts_msg} uploaded ({chunk_size_mb:.1f}MB)",
            "part_number": part_number,
            "total_parts": total_parts,
            "chunk_size_mb": round(chunk_size_mb, 1),
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
        
        # 🚫 Enforce encryption restrictions (re-enabled for testing)
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

        # Check if encryption is requested and file would be too large
        if encrypt:
            # Calculate total size by checking all actual chunks
            total_size = sum(chunk_path.stat().st_size for _, chunk_path in chunk_files)
            
            MAX_AES_SIZE_BYTES = 200 * 1024 * 1024  # 200MB
            if total_size > MAX_AES_SIZE_BYTES:
                # Clean up chunks
                for _, chunk_path in chunk_files:
                    if chunk_path.exists():
                        chunk_path.unlink()
                        
                return JSONResponse(
                    status_code=HTTP_400_BAD_REQUEST,
                    content={
                        "status": "error",
                        "msg": "AES is blocked for files >200MB to ensure smooth & efficient file transfer."
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
                
                # Encrypt if requested
                if encrypt:
                    chunk_data = encrypt_bytes(chunk_data)
                
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
