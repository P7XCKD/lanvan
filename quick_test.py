#!/usr/bin/env python3
"""
LANVAN Quick Server Test
Fast test using direct server import (no subprocess overhead).

Usage:
    python quick_test.py
    python quick_test.py --android  # Skip mDNS for Android/Termux
"""

import asyncio
import aiohttp
import sys
import socket
import os
import argparse
import time
from pathlib import Path

# Add app directory to path for imports
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

# Import server components directly
from main import app
import uvicorn

# Port constants (same as run.py)
DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
FALLBACK_HTTP_PORT = 5000
FALLBACK_HTTPS_PORT = 5001

HTTP_PORT = int(os.getenv("HTTP_PORT", DEFAULT_HTTP_PORT))
HTTPS_PORT = int(os.getenv("HTTPS_PORT", DEFAULT_HTTPS_PORT))

def can_bind_privileged_port(port):
    """Check if we can bind to a privileged port (< 1024) - from run.py"""
    if port >= 1024:
        return True
    
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind(('0.0.0.0', port))
        test_socket.close()
        return True
    except (OSError, PermissionError):
        return False

def get_safe_port(preferred_port, fallback_port):
    """Get a safe port to use, falling back if privileged port can't be bound - from run.py"""
    if can_bind_privileged_port(preferred_port):
        return preferred_port
    else:
        if preferred_port < 1024:
            print(f"[WARNING] Cannot bind to privileged port {preferred_port} (requires admin/root)")
            print(f"[INFO] Using fallback port {fallback_port}")
        return fallback_port

class QuickTest:
    """Quick smoke test for LANVAN server using direct imports"""
    
    def __init__(self, skip_mdns=False):
        self.skip_mdns = skip_mdns
        self.server_task = None
        
    def log(self, message, status="INFO"):
        """Simple logging"""
        symbols = {"PASS": "[+]", "FAIL": "[-]", "INFO": "[*]", "WARN": "[!]"}
        print(f"{symbols.get(status, '[*]')} {message}")

    async def start_server_fast(self, mode="http"):
        """Start server directly using uvicorn (no subprocess overhead)"""
        try:
            # Use same port logic as run.py
            if mode == "http":
                port = get_safe_port(HTTP_PORT, FALLBACK_HTTP_PORT)
                ssl_keyfile = None
                ssl_certfile = None
            else:  # https
                port = get_safe_port(HTTPS_PORT, FALLBACK_HTTPS_PORT)
                cert_path = Path(__file__).parent / "certs"
                ssl_keyfile = str(cert_path / "key.pem")
                ssl_certfile = str(cert_path / "cert.pem")
                
                if not Path(ssl_certfile).exists() or not Path(ssl_keyfile).exists():
                    return None, None  # No certificates
            
            self.log(f"Starting {mode.upper()} server on port {port}...")
            
            # Create and start uvicorn server
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0", 
                port=port,
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile,
                log_level="critical"  # Suppress logs for clean output
            )
            
            server = uvicorn.Server(config)
            self.server_task = asyncio.create_task(server.serve())
            
            # Brief startup delay
            await asyncio.sleep(0.3)
            
            # Build URL
            protocol = "https" if mode == "https" else "http"
            default_port = 443 if mode == "https" else 80
            url = f"{protocol}://127.0.0.1" if port == default_port else f"{protocol}://127.0.0.1:{port}"
                
            return server, url
            
        except Exception as e:
            self.log(f"Failed to start {mode} server: {str(e)}", "FAIL")
            return None, None

    async def test_server_quick(self):
        """Quick server functionality test"""
        self.log("Starting LANVAN quick test...")
        start_time = time.time()
        
        try:
            # Test HTTP mode
            self.log("=== Testing HTTP Mode ===")
            server, url = await self.start_server_fast("http")
            if not server or not url:
                self.log("HTTP server startup failed", "FAIL")
                return False
            
            try:
                # Quick tests
                await self.run_tests(url)
                self.log("HTTP mode: OK", "PASS")
            finally:
                # Cleanup HTTP server
                if self.server_task:
                    self.server_task.cancel()
                    try:
                        await self.server_task
                    except asyncio.CancelledError:
                        pass
                    self.server_task = None
                await asyncio.sleep(0.1)
            
            # Test HTTPS mode if certificates exist
            self.log("=== Testing HTTPS Mode ===")
            server, url = await self.start_server_fast("https")
            if server and url:
                try:
                    await self.run_tests(url)
                    self.log("HTTPS mode: OK", "PASS")
                finally:
                    # Cleanup HTTPS server
                    if self.server_task:
                        self.server_task.cancel()
                        try:
                            await self.server_task
                        except asyncio.CancelledError:
                            pass
                        self.server_task = None
            else:
                self.log("HTTPS mode: Skipped (no certificates)", "INFO")
            
            # Test mDNS
            await self.test_mdns()
            
            elapsed = time.time() - start_time
            self.log(f"Quick test completed in {elapsed:.1f}s!", "PASS")
            return True
            
        except Exception as e:
            self.log(f"Quick test failed: {str(e)}", "FAIL")
            return False

    async def run_tests(self, base_url):
        """Run essential tests on the server"""
        # Test basic endpoints
        endpoints = [
            ("Main page", ""),
            ("Network API", "/api/network-info"),
            ("Files API", "/api/files")
        ]
        
        timeout = aiohttp.ClientTimeout(total=3)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Test connectivity and endpoints
            for name, endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            self.log(f"{name}: OK", "PASS")
                        else:
                            self.log(f"{name}: HTTP {response.status}", "FAIL")
                            raise Exception(f"Endpoint {name} failed")
                except Exception as e:
                    self.log(f"{name}: {str(e)}", "FAIL")
                    raise
            
            # Test file upload
            self.log("Testing file upload...")
            test_content = f"quick-test-{time.time()}".encode()
            data = aiohttp.FormData()
            data.add_field('files', test_content, filename='quick_test.txt')
            
            try:
                upload_url = f"{base_url}/upload-auto"
                async with session.post(upload_url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("status") == "success":
                            self.log("File upload: OK", "PASS")
                        else:
                            raise Exception(f"Upload failed: {result.get('msg')}")
                    else:
                        raise Exception(f"Upload HTTP {response.status}")
            except Exception as e:
                self.log(f"File upload: {str(e)}", "FAIL")
                raise

    async def test_mdns(self):
        """Test mDNS service"""
        if self.skip_mdns:
            self.log("mDNS: Skipped (Android mode)", "INFO")
            return
            
        try:
            from simple_mdns import mdns_manager
            info = mdns_manager.get_mdns_info()
            if info.get("status") == "active":
                self.log("mDNS: Active", "PASS")
            else:
                self.log("mDNS: Inactive", "WARN")
        except Exception as e:
            self.log(f"mDNS: {str(e)}", "WARN")

async def main():
    """Main runner"""
    parser = argparse.ArgumentParser(description="LANVAN Quick Test")
    parser.add_argument("--android", action="store_true", 
                       help="Skip mDNS tests (for Android/Termux)")
    
    args = parser.parse_args()
    
    print("LANVAN Quick Server Test")
    print("=" * 30)
    
    test = QuickTest(skip_mdns=args.android)
    success = await test.test_server_quick()
    
    print("\n" + "=" * 30)
    if success:
        print("[+] All tests passed! Server is ready for use.")
        sys.exit(0)
    else:
        print("[-] Some tests failed. Check the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
