import os
import time
import io
from typing import List
from pathlib import Path
from mimetypes import guess_type
from zipfile import ZipFile
from app.aes_utils import encrypt_bytes, decrypt_bytes

from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse,
    JSONResponse, Response
)
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND
from werkzeug.utils import secure_filename

from app.config import is_allowed_file

# === Setup ===
router = APIRouter()
UPLOAD_FOLDER = Path("app/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory="app/templates")

# === Utilities ===
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
            "mtime": f.stat().st_mtime,
            "is_encrypted": f.suffix == ".enc"
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

from app.aes_utils import encrypt_bytes  # Adjust import path

def save_upload_file_sync(upload_file: UploadFile, destination: Path, encrypt=False):
    data = upload_file.file.read()
    if encrypt:
        data = encrypt_bytes(data)
    with destination.open("wb") as f:
        f.write(data)


def scan_file(path: Path):
    print(f"🧪 Scanning file in background: {path}")
    # Placeholder for: virus scan, checksum, or DLP hook
    # Simulated delay or processing logic
    # time.sleep(1)


# === Routes ===

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    files = get_file_list()  # ✅ Must return dicts with name/is_encrypted
    return templates.TemplateResponse("index.html", {
        "request": request,
        "msg": "Lanvan",
        "files": files
    })

from starlette.status import HTTP_400_BAD_REQUEST

from fastapi import Query
from app.aes_utils import encrypt_bytes  # Adjust if needed

@router.post("/upload-auto", name="upload_auto_file")
async def upload_auto_file(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    encrypt: bool = Query(False, description="Encrypt files with AES-256 if true")
):
    if not files:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={"status": "error", "msg": "No files uploaded"})

    uploaded = []
    MAX_AES_SIZE_MB = 200
    MAX_AES_SIZE_BYTES = MAX_AES_SIZE_MB * 1024 * 1024

    for file in files:
        if not file.filename:
            continue

        filename = secure_filename(file.filename)
        if not is_allowed_file(filename):
            continue

        # 🔍 Check file size without breaking upload
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        # 🚫 Block AES encryption if file > 200MB
        if encrypt and file_size > MAX_AES_SIZE_BYTES:
            return JSONResponse(
                status_code=HTTP_400_BAD_REQUEST,
                content={
                    "status": "error",
                    "msg": "AES is blocked for files >200MB to ensure smooth & efficient file transfer."
                }
            )

        # ✅ Proceed with saving
        save_name = filename + ".enc" if encrypt else filename
        filepath = UPLOAD_FOLDER / get_unique_filename(UPLOAD_FOLDER, save_name)

        save_upload_file_sync(file, filepath, encrypt=encrypt)
        background_tasks.add_task(scan_file, filepath)
        uploaded.append(str(filepath.name))

        






        

    if not uploaded:
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content={"status": "error", "msg": "No valid files processed"})

    return JSONResponse(content={
        "status": "success",
        "msg": f"{len(uploaded)} file(s) uploaded",
        "files": uploaded
    })

from app.aes_utils import decrypt_bytes

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

from app.aes_utils import decrypt_bytes

@router.get("/download-all", name="download_all")
async def download_all_files():
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, "w") as zip_file:
        for file in UPLOAD_FOLDER.iterdir():
            if file.is_file():
                if file.suffix == ".enc":
                    encrypted_data = file.read_bytes()
                    decrypted_data = decrypt_bytes(encrypted_data)
                    zip_file.writestr(file.stem, decrypted_data)  # Write decrypted file without .enc extension
                else:
                    zip_file.write(file, arcname=file.name)
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=all_files.zip"
        }
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
