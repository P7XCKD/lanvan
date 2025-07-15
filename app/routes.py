import os
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, Response, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from mimetypes import guess_type
from starlette.status import HTTP_302_FOUND

from app.config import is_allowed_file

router = APIRouter()
UPLOAD_FOLDER = "app/uploads"
templates = Jinja2Templates(directory="app/templates")

# Home Page
@router.get("/", response_class=HTMLResponse, name="home")
async def home(request: Request):
    files = os.listdir(UPLOAD_FOLDER)
    return templates.TemplateResponse("index.html", {"request": request, "msg": "Lanvan", "files": files})

# Upload File
@router.post("/upload", name="upload_file")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        return {"error": "No selected file"}

    if not is_allowed_file(file.filename):
        return {"error": "File type not allowed"}

    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())

    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# Download File
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

# Clear All Files
@router.post("/clear", name="clear_files")
async def clear_files():
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)

# Delete Specific File (optional)
@router.post("/delete/{filename}", name="delete_file")
async def delete_file(filename: str):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.isfile(file_path):
        os.remove(file_path)
    return RedirectResponse(url="/", status_code=HTTP_302_FOUND)
