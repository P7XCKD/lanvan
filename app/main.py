# app/main.py

import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from app.routes import router

MAX_SIZE_BYTES = 15 * 1024 * 1024 * 1024  # 15 GB

app = FastAPI(title="LanVan File Server")

# Ensure the uploads folder exists
UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Middleware to limit upload size
class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get('content-length')
        if content_length:
            size = int(content_length)
            if size > MAX_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="Upload too large. Max 15 GB allowed.")
        return await call_next(request)

app.add_middleware(LimitUploadSizeMiddleware)

# Mount static assets (CSS/JS)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup Jinja2 templates (in case needed elsewhere)
templates = Jinja2Templates(directory="app/templates")

# Register all route handlers
app.include_router(router)
