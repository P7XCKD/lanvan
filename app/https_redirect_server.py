"""
🔀 HTTPS Redirect Server
Minimal HTTP server that redirects all requests to HTTPS when server runs in HTTPS mode.
This enables seamless lanvan.local access regardless of protocol.
"""

import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
import uvicorn

class HTTPSRedirectServer:
    """Minimal HTTP server that redirects all traffic to HTTPS"""
    
    def __init__(self, https_port: int, http_port: int = 80):
        self.https_port = https_port
        self.http_port = http_port
        self.server_task: Optional[asyncio.Task] = None
        self.server = None
        
        # Create minimal FastAPI app
        self.app = FastAPI(
            title="LANVAN HTTPS Redirect",
            description="Redirects HTTP traffic to HTTPS",
            version="1.0.0",
            docs_url=None,  # Disable docs
            redoc_url=None  # Disable redoc
        )
        
        # Add catch-all redirect route
        @self.app.get("/{path:path}")
        async def redirect_to_https(request: Request, path: str = ""):
            """Redirect all HTTP requests to HTTPS"""
            host = request.headers.get("host", "").split(":")[0]  # Remove port if present
            
            # Construct HTTPS URL
            if self.https_port == 443:
                # Standard HTTPS port - don't include in URL
                https_url = f"https://{host}/{path}"
            else:
                # Non-standard port - include in URL
                https_url = f"https://{host}:{self.https_port}/{path}"
            
            # Preserve query parameters
            if request.url.query:
                https_url += f"?{request.url.query}"
            
            return RedirectResponse(url=https_url, status_code=301)
        
        # Add POST redirect for completeness
        @self.app.post("/{path:path}")
        async def redirect_post_to_https(request: Request, path: str = ""):
            """Redirect POST requests to HTTPS"""
            return await redirect_to_https(request, path)
    
    async def start(self):
        """Start the redirect server"""
        try:
            config = uvicorn.Config(
                self.app,
                host="0.0.0.0",
                port=self.http_port,
                log_level="error",  # Minimal logging
                access_log=False,   # No access logs
                timeout_keep_alive=1,
                timeout_graceful_shutdown=1
            )
            
            self.server = uvicorn.Server(config)
            print(f"🔀 Starting HTTPS redirect server on port {self.http_port} → {self.https_port}")
            
            # Start server in background task
            self.server_task = asyncio.create_task(self.server.serve())
            await asyncio.sleep(0.1)  # Give it time to start
            
            print(f"✅ HTTPS redirect server active: http://lanvan.local → https://lanvan.local:{self.https_port}")
            
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"⚠️ Port {self.http_port} already in use - redirect server skipped")
                print(f"   You may need to access HTTPS directly: https://lanvan.local:{self.https_port}")
            else:
                print(f"⚠️ HTTPS redirect server failed to start: {e}")
            print(f"   Direct HTTPS access will still work")
        except Exception as e:
            print(f"⚠️ HTTPS redirect server failed to start: {e}")
            print(f"   HTTP access to lanvan.local may not work")
    
    async def stop(self):
        """Stop the redirect server"""
        if self.server_task and not self.server_task.done():
            print("🔴 Stopping HTTPS redirect server...")
            
            # Cancel the server task
            self.server_task.cancel()
            
            # Wait for graceful shutdown
            try:
                await asyncio.wait_for(self.server_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            
            print("✅ HTTPS redirect server stopped")
    
    def is_running(self) -> bool:
        """Check if the redirect server is running"""
        return self.server_task is not None and not self.server_task.done()

# Global redirect server instance
redirect_server: Optional[HTTPSRedirectServer] = None

async def start_https_redirect_server(https_port: int, http_port: int = 80):
    """Start the HTTPS redirect server"""
    global redirect_server
    
    if redirect_server and redirect_server.is_running():
        print("🔀 HTTPS redirect server already running")
        return
    
    try:
        redirect_server = HTTPSRedirectServer(https_port, http_port)
        await redirect_server.start()
    except Exception as e:
        print(f"❌ Failed to start HTTPS redirect server: {e}")
        redirect_server = None

async def stop_https_redirect_server():
    """Stop the HTTPS redirect server"""
    global redirect_server
    
    if redirect_server:
        await redirect_server.stop()
        redirect_server = None

def is_redirect_server_running() -> bool:
    """Check if redirect server is running"""
    return redirect_server is not None and redirect_server.is_running()
