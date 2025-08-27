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
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import ClientDisconnect
from app.routes import router

# Import mDNS manager for service discovery
from app.simple_mdns import mdns_manager

# Import HTTPS redirect server for dual-protocol support
# Removed: HTTPS redirect server import (no longer needed)

# 🔇 Suppress noisy ClientDisconnect errors in logs
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
logging.getLogger("starlette").addFilter(ClientDisconnectFilter())
logging.getLogger("fastapi").addFilter(ClientDisconnectFilter())
logging.getLogger().addFilter(ClientDisconnectFilter())

# 🚨 Global shutdown event for immediate server termination
shutdown_event = asyncio.Event()
active_connections = set()

# 🎯 Global graceful shutdown state
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


# 🎯 Console command monitor for "close" command
from app.clipboard_ws import clipboard_ws_router

def console_command_monitor():
    """Monitor console for 'close' command"""
    while not shutdown_event.is_set():
        try:
            command = input().strip().lower()
            if command in ['close', 'quit', 'exit', 'shutdown']:
                print(f"🚨 Console command '{command}' detected - initiating graceful shutdown...")
                initiate_graceful_shutdown_process()
                break
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C in input - this will also trigger signal handler
            break
        except Exception as e:
            # Ignore input errors and continue monitoring
            pass

# 🎯 Graceful shutdown process
def initiate_graceful_shutdown_process():
    """Start graceful shutdown with client notifications"""
    global graceful_shutdown_initiated, shutdown_countdown
    
    if graceful_shutdown_initiated:
        return  # Already shutting down
    
    graceful_shutdown_initiated = True
    shutdown_countdown = 5  # 5 second countdown
    
    print("🚨 Graceful shutdown initiated - notifying all connected clients...")
    
    def countdown_and_shutdown():
        global shutdown_countdown
        for i in range(5, 0, -1):
            shutdown_countdown = i
            print(f"🕒 Shutdown in {i} seconds...")
            threading.Event().wait(1)  # Non-blocking sleep
        
        print("🚨 Server is now inactive...")
        shutdown_event.set()
        
        # Force exit to ensure immediate shutdown
        os._exit(0)
    
    # Start countdown in background thread
    shutdown_thread = threading.Thread(target=countdown_and_shutdown, daemon=True)
    shutdown_thread.start()

# 🎯 Signal handlers for Ctrl+C and other termination signals
def signal_handler(signum, frame):
    """Handle Ctrl+C and other termination signals"""
    signal_name = signal.Signals(signum).name
    print(f"\n🚨 {signal_name} signal received - initiating graceful shutdown...")
    initiate_graceful_shutdown_process()

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

# Start console command monitor in background thread (disabled to prevent unexpected shutdowns)
# console_thread = threading.Thread(target=console_command_monitor, daemon=True)
# console_thread.start()
print("💡 Console command monitor disabled - use Ctrl+C to shutdown")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown"""
    print("🚀 Server starting up with enhanced shutdown handling...")
    print("💡 Use Ctrl+C to shutdown gracefully (console commands disabled)")
    
    # Start responsiveness monitor
    from app.responsiveness_monitor import responsiveness_monitor
    await responsiveness_monitor.start_monitoring()
    
    # Start mDNS service
    # Get the actual port being used (80/443 or fallback ports)
    port = int(os.environ.get('PORT', 80))  # Default to HTTP port 80
    # Get HTTPS mode from environment variable set by run.py
    use_https = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
    mdns_manager.port = port
    mdns_manager.use_https = use_https  # Configure HTTPS mode
    
    print(f"🔍 Starting mDNS service discovery ({'HTTPS' if use_https else 'HTTP'} mode)...")
    
    # 🔀 HTTPS redirect server DISABLED for flexible access
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
    #         print(f"⚠️ HTTPS redirect server failed: {e}")
    
    print(f"🌐 Flexible access enabled: Both HTTP and HTTPS protocols supported")
    
    # Start mDNS in background thread to not block server startup
    def start_mdns_background():
        try:
            time.sleep(1)  # Give server time to start
            if mdns_manager.start_service():
                mdns_info = mdns_manager.get_mdns_info()
                print(f"✅ mDNS service active: {mdns_info['domain']}")
                print(f"   Access via: {mdns_info['url']}")
                if mdns_info['conflict_resolved']:
                    print(f"   🔧 Conflict resolved (attempt #{mdns_info['conflict_count'] + 1})")
                
                # Show redirect info for HTTPS mode
                if use_https and mdns_info['domain'] != "lanvan.local":
                    print(f"🔀 Redirect available: http://lanvan.local → https://lanvan.local:{port}")
            else:
                print("⚠️  mDNS service failed to start - using IP access only")
        except Exception as e:
            print(f"⚠️  mDNS service error: {e} - using IP access only")
    
    # Start mDNS in background thread
    mdns_thread = threading.Thread(target=start_mdns_background, daemon=True)
    mdns_thread.start()
    
    # Mark resources as ready after startup
    def mark_resources_ready():
        global resources_ready
        time.sleep(2)  # Give time for initial setup
        resources_ready = True
        print("✅ Server resources are ready")
    
    ready_thread = threading.Thread(target=mark_resources_ready, daemon=True)
    ready_thread.start()
    
    # Store shutdown state in app for access from routes
    app.state.graceful_shutdown_initiated = False
    app.state.shutdown_countdown = 0
    
    yield
    print("🚨 Server shutting down immediately...")
    
    # Stop responsiveness monitor
    await responsiveness_monitor.stop_monitoring()
    
    # Stop universal optimizations if active
    try:
        import gc
        gc.collect()  # Simple cleanup without specific function
        print("🔄 Universal optimizer resources cleaned")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")
    
    # HTTPS redirect server removed - no longer needed
    
    # Stop streaming assembly system
    print("🌊 Stopping streaming assembly system...")
    from app.streaming_assembly import shutdown_streaming_assembly
    shutdown_streaming_assembly()
    
    # Stop mDNS service
    print("🔴 Stopping mDNS service...")
    mdns_manager.stop_service()
    
    # Force close all active connections
    await connection_manager.disconnect_all()
    # Set shutdown event
    shutdown_event.set()
    print("✅ All connections closed. Server stopped.")

# ✅ Initialize FastAPI app with lifespan management
app = FastAPI(
    title="Lanvan File Server",
    version="1.0.0",
    docs_url=None,     # Disable Swagger docs for performance
    redoc_url=None,    # Disable ReDoc
    lifespan=lifespan  # Enable graceful shutdown handling
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

# 🚨 Custom middleware to track connections and handle immediate shutdown
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import asyncio

class ShutdownMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if shutdown is requested
        if shutdown_event.is_set():
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Server is shutting down",
                    "message": "⚠️ Server has been shut down. Please refresh the page or restart the server.",
                    "shutdown": True
                }
            )
        
        # Track this request connection
        request_id = id(request)
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
                        "message": "⚠️ Server was shut down while processing your request. Please restart the server.",
                        "shutdown": True
                    }
                )
            raise
        finally:
            await connection_manager.remove_connection(request)

app.add_middleware(ShutdownMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ✅ Register app routes
app.include_router(router)
app.include_router(clipboard_ws_router)

# ✅ Exception handlers for smart loading page system
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time

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
        # Check if templates directory exists and is accessible
        template_dir = "app/templates"
        static_dir = "app/static"
        if os.path.exists(template_dir) and os.path.exists(static_dir):
            resources_ready = True
            return True
    except:
        pass
    
    return False

@app.exception_handler(404)
@app.exception_handler(StarletteHTTPException)
async def smart_404_handler(request: Request, exc):
    """Redirect 404s to loading page only if resources aren't ready"""
    if hasattr(exc, 'status_code') and exc.status_code == 404:
        # Get the original path
        original_path = str(request.url.path)
        
        # Never redirect loading page to itself
        if original_path == '/loading':
            raise exc
        
        # Don't redirect API calls or static resources
        if (original_path.startswith('/api/') or 
            original_path.startswith('/static/') or
            original_path.startswith('/_')):
            raise exc
        
        # Only redirect to loading page if resources aren't ready
        if not are_resources_ready():
            return RedirectResponse(
                url=f"/loading?redirect={original_path}",
                status_code=302
            )
    
    # For everything else, let the normal 404 happen
    raise exc

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors - only use loading page if resources not ready"""
    if not are_resources_ready():
        return RedirectResponse(url="/loading?redirect=/", status_code=302)
    # Otherwise, let the validation error be handled normally
    raise exc

@app.exception_handler(500)
async def smart_internal_error_handler(request: Request, exc):
    """Handle server errors smartly"""
    # Check if this is a ClientDisconnect wrapped in other exceptions
    if _is_client_disconnect_error(exc):
        print(f"ℹ️ Client disconnected during request to {request.url.path} (wrapped)")
        from starlette.responses import PlainTextResponse
        return PlainTextResponse("Client disconnected", status_code=400)
    
    # Only redirect to loading page during startup period
    if not are_resources_ready():
        return RedirectResponse(url="/loading?redirect=/", status_code=302)
    # Otherwise, let the error be handled normally
    raise exc

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
