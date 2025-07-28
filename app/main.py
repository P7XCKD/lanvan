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

app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ Register app routes
app.include_router(router)
