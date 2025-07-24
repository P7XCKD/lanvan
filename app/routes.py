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
    return templates.TemplateResponse("index.html", {
        "request": request,
        "msg": "Lanvan",
        "files": [f["name"] for f in files]
    })

@router.post("/upload-auto", name="upload_auto_file")
async def upload_auto_file(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    encrypt: bool = Query(False, description="Encrypt files with AES-256 if true")
):
    if not files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={
            "status": "error",
            "msg": "No files uploaded"
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

    return JSONResponse(content={
        "status": "success",
        "msg": f"{len(uploaded)} file(s) uploaded",
        "files": uploaded
    })

@router.get("/download/{filename}", name="download_file")
async def download_file(filename: str):
    safe_name = secure_filename(filename)
    file_path = UPLOAD_FOLDER / safe_name

    if not file_path.is_file():
        return Response("File not found", status_code=404)

    mime_type, _ = guess_type(str(file_path))
    file_size = file_path.stat().st_size

    def stream_file(path: Path):
        data = path.read_bytes()
        if path.suffix == ".enc":
            data = decrypt_bytes(data)
        yield data

    return StreamingResponse(
        stream_file(file_path),
        media_type=mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400",
            "X-Accel-Buffering": "no"
        }
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
    for file in UPLOAD_FOLDER.iterdir():
        if file.is_file():
            file.unlink()
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

@router.post("/delete/{filename}", name="delete_file")
async def delete_file(filename: str):
    safe_name = secure_filename(filename)
    file_path = UPLOAD_FOLDER / safe_name
    if file_path.is_file():
        file_path.unlink()
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# === CHUNKED UPLOAD ENDPOINTS ===

@router.post("/upload_chunk", name="upload_chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    filename: str = Form(...),
    part_number: int = Form(...),
    total_parts: int = Form(...)
):
    """Handle individual chunk uploads for large files"""
    try:
        # Secure the filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Invalid filename"}
            )
        
        # Create chunk filename
        chunk_filename = f"{safe_filename}.part{part_number}"
        chunk_path = TEMP_CHUNKS_FOLDER / chunk_filename
        
        # Save the chunk
        chunk_data = await chunk.read()
        with open(chunk_path, "wb") as f:
            f.write(chunk_data)
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"Chunk {part_number}/{total_parts} uploaded",
            "part_number": part_number,
            "total_parts": total_parts
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"status": "error", "msg": f"Chunk upload failed: {str(e)}"}
        )

@router.post("/finalize_upload", name="finalize_upload")
async def finalize_upload(
    background_tasks: BackgroundTasks,
    filename: str = Form(...),
    total_parts: int = Form(...),
    encrypt: bool = Form(False)
):
    """Combine all chunks into final file"""
    try:
        # Secure the filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={"status": "error", "msg": "Invalid filename"}
            )
        
        # Check if encryption is requested and file would be too large
        if encrypt:
            # Calculate total size by checking all chunks
            total_size = 0
            for part_num in range(1, total_parts + 1):
                chunk_path = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{part_num}"
                if chunk_path.exists():
                    total_size += chunk_path.stat().st_size
            
            MAX_AES_SIZE_BYTES = 200 * 1024 * 1024  # 200MB
            if total_size > MAX_AES_SIZE_BYTES:
                # Clean up chunks
                for part_num in range(1, total_parts + 1):
                    chunk_path = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{part_num}"
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
        
        # Combine all chunks
        with open(final_path, "wb") as final_file:
            for part_num in range(1, total_parts + 1):
                chunk_path = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{part_num}"
                if not chunk_path.exists():
                    # Clean up partial chunks and final file
                    if final_path.exists():
                        final_path.unlink()
                    for clean_part in range(1, total_parts + 1):
                        clean_chunk = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{clean_part}"
                        if clean_chunk.exists():
                            clean_chunk.unlink()
                    
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
        
        # Clean up temporary chunks
        for part_num in range(1, total_parts + 1):
            chunk_path = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{part_num}"
            if chunk_path.exists():
                chunk_path.unlink()
        
        # Add background scan task
        background_tasks.add_task(scan_file, final_path)
        
        return JSONResponse(content={
            "status": "success",
            "msg": f"File '{final_path.name}' uploaded successfully",
            "filename": final_path.name
        })
        
    except Exception as e:
        # Clean up on error
        try:
            safe_filename = secure_filename(filename)
            for part_num in range(1, total_parts + 1):
                chunk_path = TEMP_CHUNKS_FOLDER / f"{safe_filename}.part{part_num}"
                if chunk_path.exists():
                    chunk_path.unlink()
        except:
            pass
            
        return JSONResponse(
            status_code=HTTP_400_BAD_REQUEST,
            content={"status": "error", "msg": f"File assembly failed: {str(e)}"}
        )
