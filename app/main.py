import os
import signal
import asyncio
import threading
import time
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from app.routes import router

# Import mDNS manager for service discovery
from app.simple_mdns import mdns_manager

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
    
    # Start mDNS service
    # Get the actual port being used (80/443 or fallback ports)
    port = int(os.environ.get('PORT', 80))  # Default to HTTP port 80
    # Get HTTPS mode from environment variable set by run.py
    use_https = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
    mdns_manager.port = port
    mdns_manager.use_https = use_https  # Configure HTTPS mode
    
    print(f"🔍 Starting mDNS service discovery ({'HTTPS' if use_https else 'HTTP'} mode)...")
    
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
            else:
                print("⚠️  mDNS service failed to start - using IP access only")
        except Exception as e:
            print(f"⚠️  mDNS service error: {e} - using IP access only")
    
    # Start mDNS in background thread
    mdns_thread = threading.Thread(target=start_mdns_background, daemon=True)
    mdns_thread.start()
    
    # Store shutdown state in app for access from routes
    app.state.graceful_shutdown_initiated = False
    app.state.shutdown_countdown = 0
    
    yield
    print("🚨 Server shutting down immediately...")
    
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
