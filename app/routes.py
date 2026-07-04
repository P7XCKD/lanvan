"""
[NET] Router Aggregator Module
Combines individual page, file, clipboard, and system routers under a single APIRouter.
Exposes sub-router symbols dynamically to retain full compatibility with test scripts.
"""

from fastapi import APIRouter

# Import sub-routers
from app.routers.pages import router as pages_router
from app.routers.files import router as files_router
from app.routers.clipboard import router as clipboard_router
from app.routers.system import router as system_router

# Expose all symbols from sub-routers for full compatibility with qt.py and external scripts
from app.routers.pages import *
from app.routers.files import *
from app.routers.clipboard import *
from app.routers.system import *

# Unified router wrapper
router = APIRouter()
router.include_router(pages_router)
router.include_router(files_router)
router.include_router(clipboard_router)
router.include_router(system_router)
