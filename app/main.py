"""
[CORE] Lanvan FastAPI Application Entry Point
Initializes the FastAPI application, registers middleware (CORS, network filters),
binds WebSocket sub-routers, and handles server lifespan events (mDNS, thread lifecycle).
"""

import os
import re
import signal
import asyncio
import threading
import time
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import ClientDisconnect
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers.pages import router as pages_router
from app.routers.files import router as files_router
from app.routers.clipboard import router as clipboard_router
from app.routers.system import router as system_router

from app.utils.simple_mdns import mdns_manager
from app.core.logger import logger

class ClientDisconnectFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'exc_info') and record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            if isinstance(exc_value, ClientDisconnect):
                return False
            if isinstance(exc_value, HTTPException) and "parsing the body" in str(exc_value.detail):
                return False
            if isinstance(exc_value, HTTPException) and exc_value.status_code == 404:
                return False
        if hasattr(record, 'getMessage'):
            msg = record.getMessage()
            if any(path in msg for path in [
                "GET /api/network-info",
                "GET /api/server-status",
                "GET /api/files",
                "GET /api/folders",
                "POST /upload_chunk"
            ]):
                return False
            if any(phrase in msg for phrase in [
                "ClientDisconnect",
                "parsing the body", 
                "There was an error parsing the body",
                "'NoneType' object is not callable",
                "404: Not Found",
                "Exception in ASGI application",
                "ExceptionGroup: unhandled errors in a TaskGroup",
                "HTTPException: 404",
                "HTTPException: 400: There was an error parsing the body"
            ]):
                return False
        return True

for _logger_name in ("uvicorn.error", "uvicorn", "uvicorn.access", "starlette", "fastapi", ""):
    _target_logger = logging.getLogger(_logger_name)
    if not any(isinstance(f, ClientDisconnectFilter) for f in _target_logger.filters):
        _target_logger.addFilter(ClientDisconnectFilter())

shutdown_event = asyncio.Event()
active_connections = set()
graceful_shutdown_initiated = False
shutdown_countdown = 0

class ConnectionManager:
    """Manage active connections for graceful shutdown"""
    def __init__(self):
        self.active_connections = set()
    
    async def add_connection(self, connection):
        self.active_connections.add(connection)
    
    async def remove_connection(self, connection):
        if connection in self.active_connections:
            self.active_connections.remove(connection)
    
    async def disconnect_all(self):
        """Force disconnect all active connections"""
        for connection in list(self.active_connections):
            try:
                await connection.close()
            except Exception as e:
                pass
        self.active_connections.clear()

connection_manager = ConnectionManager()

from app.ws_manager import clipboard_ws_router, upload_status_ws_router
from app.core.shutdown import shutdown_manager

def console_command_monitor():
    """Monitor console for 'close' command"""
    while not shutdown_event.is_set():
        try:
            command = input().strip().lower()
            if command in ['close', 'quit', 'exit', 'shutdown']:
                logger.info("SERVER", "Console shutdown command detected")
                initiate_graceful_shutdown_process()
                break
        except (EOFError, KeyboardInterrupt):
            break
        except Exception:
            pass

def initiate_graceful_shutdown_process():
    """Initiate graceful shutdown process"""
    global graceful_shutdown_initiated
    if graceful_shutdown_initiated:
        return
    
    graceful_shutdown_initiated = True
    logger.info("SERVER", "Shutdown initiated")
    
    try:
        from app.ws_manager import ui_events_manager
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                ui_events_manager.broadcast("server_shutdown", {"reason": "Console command shutdown", "graceful_time": 3.0}),
                loop
            )
    except Exception as e:
        logger.warn("WEBSOCKET", "Could not broadcast shutdown to UI clients", details={"Reason": str(e)})
    
    def force_exit():
        time.sleep(3.0)
        os._exit(0)
        
    threading.Thread(target=force_exit, daemon=True).start()

def setup_signal_handlers():
    """Setup graceful signal handling for CTRL+C and SIGTERM on the main thread."""
    def handle_signal(sig, frame):
        logger.info("SERVER", "Shutdown signal received")
        initiate_graceful_shutdown_process()
    
    # Signal handlers can only be set from the main thread in Python
    if threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except (ValueError, AttributeError):
            pass
    else:
        # Expected and normal when running as an embedded background service (e.g. Android JVM)
        logger.debug("SERVER", "Skipping signal handlers (running in background thread)")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    [LIFESPAN] Lifespan context manager for resource initialization and clean shutdown.
    """
    logger.info("SERVER", "Server starting up")
    
    setup_signal_handlers()
    
    if sys.stdin.isatty():
        command_thread = threading.Thread(target=console_command_monitor, daemon=True)
        command_thread.start()
    
    try:
        from app.utils.simple_mdns import mdns_manager
        mdns_mode = "HTTPS" if os.environ.get("USE_HTTPS", "false").lower() == "true" else "HTTP"
        logger.info("MDNS", "Starting mDNS service discovery", details={"Mode": mdns_mode})
        mdns_manager.start_service()
    except Exception as mdns_err:
        logger.warn("MDNS", "mDNS startup warning", details={"Reason": str(mdns_err)})
    
    try:
        from app.utils.termux_memory_monitor import termux_memory_monitor
        termux_memory_monitor.start_monitoring()
    except Exception as mem_err:
        logger.warn("STORAGE", "Memory monitor warning", details={"Reason": str(mem_err)})
    
    try:
        from app.utils.responsiveness_manager import responsiveness_monitor
        await responsiveness_monitor.start_monitoring()
    except Exception as resp_err:
        logger.warn("STORAGE", "Responsiveness monitor warning", details={"Reason": str(resp_err)})
    
    try:
        from app.core.streaming_assembly import initialize_streaming_assembly
        initialize_streaming_assembly("data/temp_chunks", "data/uploads")
    except Exception as stream_err:
        logger.warn("STORAGE", "Streaming assembly init warning", details={"Reason": str(stream_err)})

    try:
        from app.routers.clipboard import initialize_clipboard_persistence
        initialize_clipboard_persistence()
    except Exception as clip_err:
        logger.warn("CLIPBOARD", "Clipboard persistence warning", details={"Reason": str(clip_err)})
    
    logger.info("SERVER", "Startup completed", details={"Status": "READY"})
    
    yield
    
    logger.info("SERVER", "Shutdown initiated")
    
    try:
        from app.utils.responsiveness_manager import responsiveness_monitor
        await responsiveness_monitor.stop_monitoring()
    except Exception as resp_err:
        pass
    
    try:
        from app.utils.termux_memory_monitor import termux_memory_monitor
        termux_memory_monitor.stop_monitoring()
    except Exception as mem_err:
        pass
    
    try:
        import gc
        gc.collect()
        logger.debug("STORAGE", "Garbage collection completed during shutdown")
    except Exception as e:
        logger.warn("STORAGE", "Garbage collection warning", details={"Reason": str(e)})
    
    logger.info("STORAGE", "Stopping streaming assembly system")
    from app.core.streaming_assembly import shutdown_streaming_assembly
    shutdown_streaming_assembly()
    
    logger.info("WEBSOCKET", "Stopping WebSocket managers")
    try:
        from app.ws_manager import clipboard_ws_manager, upload_status_manager, file_events_manager, ui_events_manager
        await clipboard_ws_manager.shutdown()
        await upload_status_manager.shutdown()
        await file_events_manager.shutdown()
        await ui_events_manager.shutdown()
        logger.info("WEBSOCKET", "WebSocket managers stopped successfully")
    except Exception as ws_err:
        logger.warn("WEBSOCKET", "WebSocket manager shutdown warning", details={"Reason": str(ws_err)})
    
    logger.info("MDNS", "Stopping mDNS service")
    mdns_manager.stop_service()
    
    await connection_manager.disconnect_all()
    shutdown_event.set()
    logger.info("SERVER", "Shutdown completed", details={"Status": "STOPPED"})


app = FastAPI(
    title="Lanvan File Server",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecureCORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware with pattern matching for local network security"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.allow_credentials = kwargs.get('allow_credentials', True)
        self.allow_methods = kwargs.get('allow_methods', ["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
        self.allow_headers = kwargs.get('allow_headers', ["*"])
        self.expose_headers = kwargs.get('expose_headers', ["*"])
        self.max_age = kwargs.get('max_age', 3600)
        
        self.allowed_patterns = [
            r'^https?://localhost(:\d+)?$',
            r'^https?://127\.0\.0\.1(:\d+)?$',
            r'^https?://10\.\d+\.\d+\.\d+(:\d+)?$',
            r'^https?://172\.(1[6-9]|2\d|3[01])\.\d+\.\d+(:\d+)?$',
            r'^https?://192\.168\.\d+\.\d+(:\d+)?$',
            r'^https?://169\.254\.\d+\.\d+(:\d+)?$',
            r'^https?://[^\.]+\.local(:\d+)?$',
            r'^https?://lanvan\.local(:\d+)?$',
        ]
    
    def is_origin_allowed(self, origin: str) -> bool:
        if not origin:
            return False
        for pattern in self.allowed_patterns:
            if re.match(pattern, origin):
                return True
        return False
    
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        
        if request.method == "OPTIONS":
            response = Response(status_code=200)
            if origin and self.is_origin_allowed(origin):
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = "*"
            
            response.headers["Access-Control-Allow-Credentials"] = str(self.allow_credentials).lower()
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            response.headers["Access-Control-Max-Age"] = str(self.max_age)
            return response
        
        response = await call_next(request)
        
        if origin and self.is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
            
        response.headers["Access-Control-Allow-Credentials"] = str(self.allow_credentials).lower()
        if self.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
            
        return response

app.add_middleware(SecureCORSMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/images", StaticFiles(directory="app/static/images"), name="images")

app.include_router(pages_router)
app.include_router(files_router)
app.include_router(clipboard_router)
app.include_router(system_router)
app.include_router(clipboard_ws_router)
app.include_router(upload_status_ws_router)

from app.ws_manager import file_events_ws_router, ui_events_ws_router
app.include_router(file_events_ws_router)
app.include_router(ui_events_ws_router)

from app.routers.version_routes import router as version_router
app.include_router(version_router)

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "msg": "Resource not found"}
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "msg": str(exc.detail)}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"status": "error", "msg": "Validation error", "errors": exc.errors()}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("SERVER", "Unhandled request exception", details={"Reason": str(exc)})
    return JSONResponse(
        status_code=500,
        content={"status": "error", "msg": "Internal Server Error"}
    )
