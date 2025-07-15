# app/main.py

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes import router  # ✅ YOUR router is named `router`, not `main`

app = FastAPI(title="LanVan File Server")

# Ensure uploads folder exists
UPLOAD_FOLDER = "app/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 👇 Correctly mount static assets for CSS/JS/images
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Optional: Set up templates (only needed once)
templates = Jinja2Templates(directory="app/templates")

# ✅ Register router with all your endpoints
app.include_router(router)
