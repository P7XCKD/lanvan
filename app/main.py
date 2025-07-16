import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware
from app.routes import router

# ✅ Initialize FastAPI app with basic metadata and docs disabled
app = FastAPI(
    title="LanVan File Server",
    version="1.0.0",
    docs_url=None,     # Disable Swagger docs for performance
    redoc_url=None     # Disable ReDoc
)

# ✅ Middleware: Enable GZip compression for responses > 1000 bytes
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ✅ Ensure upload directory exists
UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ✅ Setup Jinja2 template engine
templates = Jinja2Templates(directory="app/templates")

# ✅ Register app routes
app.include_router(router)
