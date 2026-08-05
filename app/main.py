"""
[CORE] Lanvan FastAPI Application Entry Point
Initializes the FastAPI application, registers middleware (CORS, network filters),
binds WebSocket sub-routers, and handles server lifespan events (mDNS, thread lifecycle).

Key Features:
- Lifespan context manager controlling resource initialization and prioritized shutdowns
- Secure CORSMiddleware with local network restriction filtering
- Global client disconnect log silencer filters
- Custom error pages redirection and loading phase states
"""

import os
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

# Import mDNS manager for service discovery
from app.utils.simple_mdns import mdns_manager

# Import HTTPS redirect server for dual-protocol support
# Removed: HTTPS redirect server import (no longer needed)

#  Suppress noisy ClientDisconnect errors in logs
class ClientDisconnectFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'exc_info') and record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            if isinstance(exc_value, ClientDisconnect):
                return False
            # Also filter HTTPException with "parsing the body" message
            if isinstance(exc_value, HTTPException) and "parsing the body" in str(exc_value.detail):
                return False
            # Filter out static file 404s and other noise
            if isinstance(exc_value, HTTPException) and exc_value.status_code == 404:
                return False
        # Filter out the string-based error messages too
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

# Apply filter to uvicorn and starlette loggers
logging.getLogger("uvicorn.error").addFilter(ClientDisconnectFilter())
logging.getLogger("uvicorn").addFilter(ClientDisconnectFilter())
logging.getLogger("uvicorn.access").addFilter(ClientDisconnectFilter())
logging.getLogger("starlette").addFilter(ClientDisconnectFilter())
logging.getLogger("fastapi").addFilter(ClientDisconnectFilter())
logging.getLogger().addFilter(ClientDisconnectFilter())

# [!] Global shutdown event for immediate server termination
shutdown_event = asyncio.Event()
active_connections = set()

# [TARGET] Global graceful shutdown state
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
                print(f"Error closing connection: {e}")
        self.active_connections.clear()

connection_manager = ConnectionManager()


# [TARGET] Console command monitor for "close" command
from app.ws_manager import clipboard_ws_router, upload_status_ws_router

def console_command_monitor():
    """Monitor console for 'close' command"""
    while not shutdown_event.is_set():
        try:
            command = input().strip().lower()
            if command in ['close', 'quit', 'exit', 'shutdown']:
                print(f"[!] Console command '{command}' detected - initiating graceful shutdown...")
                initiate_graceful_shutdown_process()
                break
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C in input - this will also trigger signal handler
            break
        except Exception as e:
            # Ignore input errors and continue monitoring
            pass

# [TARGET] Graceful shutdown process
def initiate_graceful_shutdown_process():
    """Start graceful shutdown with client notifications"""
    global graceful_shutdown_initiated, shutdown_countdown
    
    if graceful_shutdown_initiated:
        return  # Already shutting down
    
    graceful_shutdown_initiated = True
    shutdown_countdown = 5  # 5 second countdown
    
    print("[!] Graceful shutdown initiated - notifying all connected clients...")
    
    def countdown_and_shutdown():
        global shutdown_countdown
        for i in range(5, 0, -1):
            shutdown_countdown = i
            print(f"[TIME] Shutdown in {i} seconds...")
            time.sleep(1)  # sleep 1 second between countdown steps
        
        print("[!] Server is now inactive...")
        shutdown_event.set()
        
        # On Android, exit the thread cleanly instead of killing the JVM process
        # This keeps the host APK running while stopping the FastAPI server
        import sys
        if "ANDROID_STORAGE" in os.environ:
            sys.exit(0)
        else:
            os._exit(0)
    
    # Start countdown in background thread
    shutdown_thread = threading.Thread(target=countdown_and_shutdown, daemon=True)
    shutdown_thread.start()

# NOTE: stdin command monitor ('close'/'quit') is handled in run.py, not here,
# because with a single-process uvicorn (reload=False) stdin belongs to run.py.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown"""
    print("[START] Server starting up with enhanced shutdown handling...")
    print("[TIP] Use Ctrl+C to shutdown gracefully (console commands disabled)")
    
    # Start responsiveness monitor
    from app.utils.responsiveness_manager import responsiveness_monitor
    await responsiveness_monitor.start_monitoring()
    
    # Start mDNS service
    # Get the actual port being used (80/443 or fallback ports)
    port = int(os.environ.get('PORT', 80))  # Default to HTTP port 80
    # Get HTTPS mode from environment variable set by run.py
    use_https = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
    mdns_manager.port = port
    mdns_manager.use_https = use_https  # Configure HTTPS mode
    
    print(f"[SEARCH] Starting mDNS service discovery ({'HTTPS' if use_https else 'HTTP'} mode)...")
    
    #  HTTPS redirect server DISABLED for flexible access
    # This allows both HTTP and HTTPS access without forced redirects:
    # - Users can access http://lanvan.local for HTTP
    # - Users can access https://lanvan.local for HTTPS  
    # - Both LAN IP and localhost work with both protocols
    #
    # Original redirect server logic preserved but disabled:
    # if use_https:
    #     try:
    #         # Determine HTTP redirect port logic...
    #         await start_https_redirect_server(port, http_redirect_port)
    #     except Exception as e:
    #         print(f"[WARN] HTTPS redirect server failed: {e}")
    
    print(f"[NET] Flexible access enabled: Both HTTP and HTTPS protocols supported")
    
    # Start mDNS in background thread to not block server startup
    def start_mdns_background():
        try:
            time.sleep(1)  # Give server time to start
            if mdns_manager.start_service():
                mdns_info = mdns_manager.get_mdns_info()
                print(f"[OK] mDNS service active: {mdns_info['domain']}")
                print(f"   Access via: {mdns_info['url']}")
                if mdns_info['conflict_resolved']:
                    print(f"   [CFG] Conflict resolved (attempt #{mdns_info['conflict_count'] + 1})")
                
                # Show redirect info for HTTPS mode
                if use_https and mdns_info['domain'] != "lanvan.local":
                    print(f" Redirect available: http://lanvan.local -> https://lanvan.local:{port}")
            else:
                print("[WARN]  mDNS service failed to start - using IP access only")
        except Exception as e:
            print(f"[WARN]  mDNS service error: {e} - using IP access only")
    
    # Start mDNS in background thread
    mdns_thread = threading.Thread(target=start_mdns_background, daemon=True)
    mdns_thread.start()
    
    # Mark resources as ready after startup
    def mark_resources_ready():
        global resources_ready
        time.sleep(2)  # Give time for initial setup
        
        # Initialize clipboard persistence after everything is ready
        try:
            from app.routers.clipboard import initialize_clipboard_persistence
            initialize_clipboard_persistence()
        except Exception as e:
            print(f"[WARN] Clipboard persistence initialization failed: {e}")
        
        resources_ready = True
        print("[OK] Server resources are ready")
    
    ready_thread = threading.Thread(target=mark_resources_ready, daemon=True)
    ready_thread.start()
    
    # Store shutdown state in app for access from routes
    app.state.graceful_shutdown_initiated = False
    app.state.shutdown_countdown = 0
    
    yield
    print("[!] Server shutting down immediately...")
    
    # Stop responsiveness monitor
    await responsiveness_monitor.stop_monitoring()
    
    # Stop universal optimizations if active
    try:
        import gc
        gc.collect()  # Simple cleanup without specific function
        print("[RETRY] Universal optimizer resources cleaned")
    except Exception as e:
        print(f"[WARN] Cleanup warning: {e}")
    
    # HTTPS redirect server removed - no longer needed
    
    # Stop streaming assembly system
    print("[STREAM] Stopping streaming assembly system...")
    from app.core.streaming_assembly import shutdown_streaming_assembly
    shutdown_streaming_assembly()
    
    # Stop WebSocket managers
    print("[WS] Stopping WebSocket connection managers...")
    try:
        from app.ws_manager import clipboard_ws_manager, upload_status_manager
        await clipboard_ws_manager.shutdown()
        await upload_status_manager.shutdown()
        print("[OK] WebSocket managers shutdown successfully")
    except Exception as ws_err:
        print(f"[WARN] WebSocket managers shutdown warning: {ws_err}")
    
    # Stop mDNS service
    print(" Stopping mDNS service...")
    mdns_manager.stop_service()
    
    # Force close all active connections
    await connection_manager.disconnect_all()
    # Set shutdown event
    shutdown_event.set()
    print("[OK] All connections closed. Server stopped.")

# [OK] Initialize FastAPI app with lifespan management
app = FastAPI(
    title="Lanvan File Server",
    version="1.0.0",
    docs_url=None,     # Disable Swagger docs for performance
    redoc_url=None,    # Disable ReDoc
    lifespan=lifespan  # Enable graceful shutdown handling
)

# [OK] CORS Middleware: Enhanced security with local network restriction
import re
from typing import List
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
        
        # Define allowed origin patterns for local network
        self.allowed_patterns = [
            r'^https?://localhost(:\d+)?$',
            r'^https?://127\.0\.0\.1(:\d+)?$',
            r'^https?://10\.\d+\.\d+\.\d+(:\d+)?$',                    # 10.0.0.0/8
            r'^https?://172\.(1[6-9]|2\d|3[01])\.\d+\.\d+(:\d+)?$',   # 172.16.0.0/12
            r'^https?://192\.168\.\d+\.\d+(:\d+)?$',                   # 192.168.0.0/16
            r'^https?://169\.254\.\d+\.\d+(:\d+)?$',                   # 169.254.0.0/16 (link-local)
            r'^https?://[^\.]+\.local(:\d+)?$',                        # .local domains (mDNS)
            r'^https?://lanvan\.local(:\d+)?$',                        # Lanvan mDNS domain
        ]
    
    def is_origin_allowed(self, origin: str) -> bool:
        """Check if origin matches any allowed patterns"""
        if not origin:
            return False
        
        # Check against all patterns
        for pattern in self.allowed_patterns:
            if re.match(pattern, origin):
                return True
        
        return False
    
    async def dispatch(self, request, call_next):
        origin = request.headers.get('origin')
        
        # Handle preflight requests
        if request.method == 'OPTIONS':
            if origin and self.is_origin_allowed(origin):
                response = Response()
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
                response.headers['Access-Control-Allow-Methods'] = ', '.join(self.allow_methods)
                response.headers['Access-Control-Allow-Headers'] = ', '.join(self.allow_headers)
                response.headers['Access-Control-Max-Age'] = str(self.max_age)
                return response
            else:
                # Reject preflight for non-allowed origins
                return Response(status_code=403)
        
        # Process the request
        response = await call_next(request)
        
        # Add CORS headers to actual requests
        if origin and self.is_origin_allowed(origin):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Expose-Headers'] = ', '.join(self.expose_headers)
        
        return response

# Apply custom secure CORS middleware
app.add_middleware(
    SecureCORSMiddleware,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=[
        "*",
        "Content-Type",
        "Authorization", 
        "X-Requested-With",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Mx-ReqToken",
        "Keep-Alive",
        "If-Modified-Since",
        "X-File-Name"
    ],
    expose_headers=["*"],
    max_age=3600,
)


# [!] Custom middleware to track connections and handle immediate shutdown
import asyncio


class IOSSafariMiddleware(BaseHTTPMiddleware):
    """Middleware to handle iOS Safari specific compatibility issues"""
    
    def detect_ios_safari(self, user_agent: str) -> bool:
        """Detect iOS Safari browser"""
        user_agent_lower = user_agent.lower()
        is_ios = any(ios_indicator in user_agent_lower for ios_indicator in [
            'iphone', 'ipad', 'ipod'
        ])
        is_safari = 'safari' in user_agent_lower and 'chrome' not in user_agent_lower
        return is_ios and is_safari
    
    async def dispatch(self, request: Request, call_next):
        user_agent = request.headers.get("user-agent", "")
        is_ios_safari = self.detect_ios_safari(user_agent)
        
        # Add iOS Safari detection to request state
        request.state.is_ios_safari = is_ios_safari
        
        try:
            response = await call_next(request)
            
            # Add iOS Safari-specific headers
            if is_ios_safari:
                # Prevent iOS Safari caching issues
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                
                # iOS Safari WebSocket compatibility
                response.headers["Connection"] = "keep-alive"
                
                # Prevent iOS Safari from auto-optimizing resources
                response.headers["X-Content-Type-Options"] = "nosniff"
                
                # iOS Safari viewport handling
                response.headers["X-UA-Compatible"] = "IE=edge"
            
            return response
            
        except Exception as e:
            # Log iOS-specific errors for debugging
            if is_ios_safari:
                print(f" iOS Safari error: {str(e)} - User-Agent: {user_agent[:100]}...")
            raise

class ShutdownMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if shutdown is requested
        if shutdown_event.is_set():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Server is shutting down",
                    "message": "[WARN] Server has been shut down. Please refresh the page or restart the server.",
                    "shutdown": True
                }
            )
        
        # Track this request connection
        await connection_manager.add_connection(request)
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # If shutdown occurred during request, return shutdown message
            if shutdown_event.is_set():
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Server shutdown during request",
                        "message": "[WARN] Server was shut down while processing your request. Please restart the server.",
                        "shutdown": True
                    }
                )
            raise
        finally:
            await connection_manager.remove_connection(request)

class EnsureDataDirMiddleware(BaseHTTPMiddleware):
    """Automatically recreate data & data/uploads folders on demand if deleted during runtime"""
    async def dispatch(self, request: Request, call_next):
        try:
            from app.routers.files import UPLOAD_FOLDER, TEMP_CHUNKS_FOLDER, UPLOAD_HISTORY_FILE
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            TEMP_CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)
            if not UPLOAD_HISTORY_FILE.parent.exists():
                UPLOAD_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return await call_next(request)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Production Security Headers Middleware"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:;"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Lightweight in-memory rate limiting middleware.
    Uses a sliding-window counter per client IP with automatic TTL eviction.
    No external dependencies required.
    
    Limits (per second, per IP):
      - Upload endpoints:     30 req/s  (/upload, /upload-auto, /encrypt_http_safe)
      - Chunk endpoints:      60 req/s  (/upload_chunk)
      - Clipboard writes:     20 req/s  (/api/clipboard/add, /api/clipboard, /api/clipboard/download-zip)
      - API reads:           100 req/s  (/api/* GET endpoints)
      - Default:             200 req/s  (everything else — static files, pages, WebSocket upgrades)
    
    These limits are generous for LAN usage and only protect against
    accidental or malicious flooding from a single client.
    
    To disable rate limiting entirely, set env: LANVAN_RATE_LIMIT=off
    """
    def __init__(self, app, **kwargs):
        super().__init__(app)
        # Check if rate limiting is disabled via environment variable
        self._enabled = os.environ.get("LANVAN_RATE_LIMIT", "").lower() not in ("off", "0", "false", "no")
        # Structure: { "ip:window_key": (count, expiry) }
        self._windows: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 60  # seconds between stale entry sweeps
        self._last_cleanup = time.time()

    def _get_limit(self, path: str) -> int:
        """Return the per-second rate limit for a given request path."""
        if path in ("/upload", "/upload-auto", "/encrypt_http_safe"):
            return 30
        if path == "/upload_chunk":
            return 60
        if path in ("/api/clipboard/add", "/api/clipboard", "/api/clipboard/download-zip"):
            return 20
        if path.startswith("/api/") or path.startswith("/api"):
            return 100
        return 200  # default for static files, pages, WebSocket upgrades

    def _get_key(self, request: Request) -> str:
        """Derive a rate-limit key from the client IP and current second window."""
        client_ip = request.client.host if request.client else "unknown"
        # Use 1-second windows for per-second limiting
        window = int(time.time())
        return f"{client_ip}:{window}"

    def _maybe_cleanup(self, now: float):
        """Periodically evict stale window entries to prevent unbounded growth."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        with self._lock:
            stale = [k for k, (_, expiry) in self._windows.items() if now > expiry]
            for k in stale:
                del self._windows[k]
            self._last_cleanup = now

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        limit = self._get_limit(path)
        
        # WebSocket upgrade requests bypass rate limiting
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)
        
        key = self._get_key(request)
        now = time.time()
        
        with self._lock:
            self._maybe_cleanup(now)
            
            current = self._windows.get(key)
            if current is None:
                # First request in this second window
                self._windows[key] = (1, now + 10)  # expiry in 10 seconds
                count = 1
            else:
                count, expiry = current
                count += 1
                self._windows[key] = (count, expiry)
        
        if count > limit:
            # Rate limit exceeded — return 429 Too Many Requests
            # Note: We've already incremented the counter, which is correct —
            # the first request over the limit triggers the 429.
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "msg": "Too many requests. Please slow down."
                }
            )
        
        return await call_next(request)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(EnsureDataDirMiddleware)
app.add_middleware(IOSSafariMiddleware)
app.add_middleware(ShutdownMiddleware)

def is_production_mode() -> bool:
    return os.environ.get("LANVAN_ENV", "").lower() in ("production", "prod", "1") or os.environ.get("PRODUCTION", "").lower() in ("1", "true")

class ProductionStaticFiles(StaticFiles):
    """
    Transparently resolves static assets:
    - In Production mode: Serves minified .min.js assets from dist/static/js if available.
    - In Development mode: Serves original unminified .js source files directly from app/static/js.
    - Adds Cache-Control headers: 1 year for versioned assets, 1 hour for unversioned.
    """
    async def get_response(self, path: str, scope):
        if is_production_mode() and path.endswith(".js") and not path.endswith(".min.js"):
            min_path = path[:-3] + ".min.js"
            full_min_path = os.path.join(self.directory, min_path)
            if os.path.exists(full_min_path):
                response = await super().get_response(min_path, scope)
                # Versioned/minified assets get long-lived cache (1 year)
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                return response
        response = await super().get_response(path, scope)
        # Set appropriate cache headers based on file type
        if path.endswith((".min.js", ".min.css", ".woff2", ".woff", ".ttf")):
            # Versioned/hashed assets: 1 year
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")):
            # Images: 1 week
            response.headers["Cache-Control"] = "public, max-age=604800"
        elif path.endswith((".html", ".htm")):
            # HTML templates: no cache
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        else:
            # Other assets (CSS, JS, fonts): 1 hour
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

static_dir = os.path.abspath("dist/static") if (is_production_mode() and os.path.exists("dist/static")) else os.path.abspath("app/static")
app.mount("/static", ProductionStaticFiles(directory=static_dir), name="static")

from app.ws_manager import clipboard_ws_router, upload_status_ws_router, file_events_ws_router, ui_events_ws_router
from app.routers.version_routes import router as version_router

# [OK] Register app routes
app.include_router(pages_router)
app.include_router(files_router)
app.include_router(version_router)
app.include_router(clipboard_router)
app.include_router(system_router)
app.include_router(clipboard_ws_router)
app.include_router(upload_status_ws_router)
app.include_router(file_events_ws_router)
app.include_router(ui_events_ws_router)

# [OK] Exception handlers for smart loading page system
# Track when the server started and if resources are ready
server_start_time = time.time()
resources_ready = False
startup_grace_period = 5  # seconds

def are_resources_ready():
    """Check if server resources are ready"""
    global resources_ready, server_start_time
    
    # If we've explicitly marked resources as ready, return True
    if resources_ready:
        return True
    
    # If it's been more than grace period since startup, consider ready
    if time.time() - server_start_time > startup_grace_period:
        resources_ready = True
        return True
    
    # During startup grace period, check if essential services are available
    try:
        template_dir = "app/templates"
        static_dir = "app/static"
        if os.path.exists(template_dir) and os.path.exists(static_dir):
            resources_ready = True
            return True
    except Exception:
        pass
    
    return False

@app.exception_handler(404)
@app.exception_handler(StarletteHTTPException)
async def smart_404_handler(request: Request, exc):
    from fastapi.responses import PlainTextResponse
    status_code = getattr(exc, 'status_code', 404)
    return PlainTextResponse("Not Found" if status_code == 404 else str(exc), status_code=status_code)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"status": "error", "msg": "Validation Error", "details": str(exc)})

@app.exception_handler(500)
@app.exception_handler(Exception)
async def smart_internal_error_handler(request: Request, exc: Exception):
    from fastapi.responses import PlainTextResponse, JSONResponse
    if _is_client_disconnect_error(exc):
        print(f"[INFO] Client disconnected during request to {request.url.path} (wrapped)")
        return PlainTextResponse("Client disconnected", status_code=400)
    
    # Log the full traceback internally via the logger (not to stdout)
    # but NEVER leak stack traces, paths, or exception types to clients.
    import logging
    logger = logging.getLogger("lanvan")
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    
    # In production mode, return a generic message. In dev mode, include details.
    if is_production_mode():
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "msg": "Internal Server Error"
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "msg": str(exc) or "Internal Server Error",
                "path": str(request.url.path),
                "error_type": type(exc).__name__
            }
        )


def _is_client_disconnect_error(exc) -> bool:
    """Check if exception is caused by client disconnect"""
    # Check the exception chain for ClientDisconnect
    current = exc
    while current:
        if isinstance(current, ClientDisconnect):
            return True
        # Check if it's an HTTPException with ClientDisconnect as cause
        if hasattr(current, '__cause__') and isinstance(current.__cause__, ClientDisconnect):
            return True
        # Check if error message indicates client disconnect
        if hasattr(current, 'detail') and 'parsing the body' in str(current.detail):
            return True
        current = getattr(current, '__cause__', None)
    return False
