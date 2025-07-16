import os
import time
from typing import List
from pathlib import Path
from mimetypes import guess_type

from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND
from werkzeug.utils import secure_filename  # filename sanitization
from app.config import is_allowed_file

router = APIRouter()
UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

templates = Jinja2Templates(directory="app/templates")

# ✅ Format bytes into human-readable form
def format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"

# ✅ List files sorted by modification time (newest first)
def get_file_list():
    files = []
    for fname in os.listdir(UPLOAD_FOLDER):
        fpath = os.path.join(UPLOAD_FOLDER, fname)
        if os.path.isfile(fpath):
            size = os.path.getsize(fpath)
            mtime = os.path.getmtime(fpath)
            files.append({
                "name": fname,
                "size": format_size(size),
                "mtime": mtime
            })
    return sorted(files, key=lambda f: f["mtime"], reverse=True)

# ✅ Generate unique filename to avoid overwrite
def get_unique_filename(directory: str, filename: str):
    base = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    new_name = filename
    while os.path.exists(os.path.join(directory, new_name)):
        new_name = f"{base}_{counter}{ext}"
        counter += 1
    return new_name

# ✅ Optimized SYNC file save with chunked writing (PC-hosted performance)
def save_upload_file_sync(upload_file: UploadFile, destination: str):
    start = time.time()
    with open(destination, "wb") as f:
        while chunk := upload_file.file.read(4 * 1024 * 1024):  # 4MB chunks
            f.write(chunk)
    print(f"[UPLOAD DONE] {destination} in {time.time() - start:.2f}s")

# ❌ Async version no longer used, kept for fallback or Android-specific later
# import aiofiles
# async def save_upload_file(upload_file: UploadFile, destination: str):
#     async with aiofiles.open(destination, "wb") as buffer:
#         while chunk := await upload_file.read(1024 * 1024):  # 1MB chunks
#             await buffer.write(chunk)

# ✅ Dummy background task placeholder
def scan_file(path: str):
    print(f"🧪 Background scanning file: {path}")
    # Optional: Add logging, integrity checks, virus scan, etc.

# ✅ Home page (lists sorted files)
@router.get("/", response_class=HTMLResponse, name="home")
async def home(request: Request):
    files = get_file_list()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "msg": "Lanvan",
        "files": [f["name"] for f in files]
    })

# ✅ Single file upload (SYNC) with background task
@router.post("/upload", name="upload_file")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename:
        return {"error": "No selected file"}

    filename = secure_filename(file.filename)
    if not is_allowed_file(filename):
        return {"error": "File type not allowed"}

    unique_name = get_unique_filename(UPLOAD_FOLDER, filename)
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    save_upload_file_sync(file, filepath)  # ⬅️ Fast sync upload

    background_tasks.add_task(scan_file, filepath)
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# ✅ Multi file upload (SYNC) with background tasks
@router.post("/upload-multiple", name="upload_multiple_files")
async def upload_multiple_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    if len(files) > 10:
        return {"error": "Max 10 files allowed"}

    for file in files:
        if not file.filename:
            continue
        filename = secure_filename(file.filename)
        if not is_allowed_file(filename):
            continue
        unique_name = get_unique_filename(UPLOAD_FOLDER, filename)
        filepath = os.path.join(UPLOAD_FOLDER, unique_name)
        save_upload_file_sync(file, filepath)  # ⬅️ Fast sync upload
        background_tasks.add_task(scan_file, filepath)

    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# ✅ File download (streamed with headers and cache)
@router.get("/download/{filename}", name="download_file")
async def download_file(filename: str):
    safe_name = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_name)

    if not os.path.isfile(file_path):
        return Response("File not found", status_code=404)

    file_size = os.stat(file_path).st_size

    def file_stream(path):
        with open(path, "rb") as f:
            while chunk := f.read(2 * 1024 * 1024):  # 2MB
                yield chunk

    mime_type, _ = guess_type(file_path)
    return StreamingResponse(
        file_stream(file_path),
        media_type=mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400"
        }
    )

# ✅ Clear all uploaded files
@router.post("/clear", name="clear_files")
async def clear_files():
    for filename in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(path):
            os.remove(path)
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# ✅ Delete specific file
@router.post("/delete/{filename}", name="delete_file")
async def delete_file(filename: str):
    safe_name = secure_filename(filename)
    path = os.path.join(UPLOAD_FOLDER, safe_name)
    if os.path.isfile(path):
        os.remove(path)
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)
