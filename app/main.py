import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from app.routes import router

# ✅ Initialize FastAPI app with basic metadata and docs disabled
app = FastAPI(
    title="Lanvan File Server",
    version="1.0.0",
    docs_url=None,     # Disable Swagger docs for performance
    redoc_url=None     # Disable ReDoc
)

# ✅ CORS Middleware: Allow all origins for LAN usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for LAN usage
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# ✅ Middleware: Enable GZip compression for responses > 1000 bytes
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ✅ Ensure upload directory exists
UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ Ensure temp chunks directory exists
TEMP_CHUNKS_FOLDER = os.path.join(UPLOAD_FOLDER, "temp_chunks")
os.makedirs(TEMP_CHUNKS_FOLDER, exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ✅ Setup Jinja2 template engine
templates = Jinja2Templates(directory="app/templates")

# ✅ Register app routes
app.include_router(router)
