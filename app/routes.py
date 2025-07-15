import os
import aiofiles
from typing import List
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, Response, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from mimetypes import guess_type
from starlette.status import HTTP_302_FOUND
from app.config import is_allowed_file

router = APIRouter()
UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

templates = Jinja2Templates(directory="app/templates")

# ✅ Async helper to save upload file in chunks using aiofiles
async def save_upload_file(upload_file: UploadFile, destination: str):
    async with aiofiles.open(destination, "wb") as buffer:
        while True:
            chunk = await upload_file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            await buffer.write(chunk)

# ✅ Home Page
@router.get("/", response_class=HTMLResponse, name="home")
async def home(request: Request):
    files = os.listdir(UPLOAD_FOLDER)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "msg": "Lanvan",
        "files": files
    })

# ✅ Single File Upload
@router.post("/upload", name="upload_file")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        return {"error": "No selected file"}

    if not is_allowed_file(file.filename):
        return {"error": "File type not allowed"}

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    await save_upload_file(file, filepath)

    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# ✅ Multi-file Upload
@router.post("/upload-multiple", name="upload_multiple_files")
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    saved_files = []
    for file in files:
        if not file.filename:
            continue
        if not is_allowed_file(file.filename):
            continue
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        await save_upload_file(file, filepath)
        saved_files.append(file.filename)
    return {"message": f"Successfully uploaded {len(saved_files)} files", "files": saved_files}

# ✅ Download File (streamed)
@router.get("/download/{filename}", name="download_file")
async def download_file(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.isfile(file_path):
        return Response("File not found", status_code=404)

    def file_stream(path):
        with open(path, "rb") as f:
            while chunk := f.read(65536):  # 64 KB
                yield chunk

    mime_type, _ = guess_type(file_path)

    return StreamingResponse(
        file_stream(file_path),
        media_type=mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "public, max-age=86400"
        }
    )

# ✅ Clear All Files
@router.post("/clear", name="clear_files")
async def clear_files():
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# ✅ Delete Specific File
@router.post("/delete/{filename}", name="delete_file")
async def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.isfile(file_path):
        os.remove(file_path)
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)
