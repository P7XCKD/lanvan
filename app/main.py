import os
import signal
import asyncio
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from app.routes import router

# 🚨 Global shutdown event for immediate server termination
shutdown_event = asyncio.Event()
active_connections = set()

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app startup and shutdown"""
    print("🚀 Server starting up...")
    yield
    print("🚨 Server shutting down immediately...")
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

app.mount("/static", StaticFiles(directory="static"), name="static")

# ✅ Register app routes
app.include_router(router)
