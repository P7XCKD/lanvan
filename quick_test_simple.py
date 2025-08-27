#!/usr/bin/env python3
"""
LANVAN Simple Quick Test
Super fast test that directly uses server logic without subprocess overhead.

Usage:
    python quick_test_simple.py
    python quick_test_simple.py --android  # Skip mDNS for Android/Termux
"""

import asyncio
import aiohttp
import sys
import argparse
import socket
import os
import time
from pathlib import Path

# Add app directory to path for imports
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

# Import server components directly
from main import app
from config import get_safe_port, DEFAULT_HTTP_PORT, FALLBACK_HTTP_PORT, DEFAULT_HTTPS_PORT, FALLBACK_HTTPS_PORT
import uvicorn

class QuickTest:
    """Super simple and fast test"""
    
    def __init__(self, skip_mdns=False):
        self.skip_mdns = skip_mdns
        self.server = None
        self.server_task = None
        
    def log(self, message, status="INFO"):
        """Simple logging"""
        symbols = {"PASS": "[+]", "FAIL": "[-]", "INFO": "[*]", "WARN": "[!]"}
        print(f"{symbols.get(status, '[*]')} {message}")

    async def start_server_direct(self, mode="http"):
        """Start server directly using uvicorn (no subprocess)"""
        try:
            # Determine port using same logic as run.py
            if mode == "http":
                port = get_safe_port(DEFAULT_HTTP_PORT, FALLBACK_HTTP_PORT)
                ssl_keyfile = None
                ssl_certfile = None
            else:  # https
                port = get_safe_port(DEFAULT_HTTPS_PORT, FALLBACK_HTTPS_PORT)
                cert_path = Path(__file__).parent / "certs"
                ssl_keyfile = str(cert_path / "key.pem")
                ssl_certfile = str(cert_path / "cert.pem")
                
                # Check if certificates exist
                if not Path(ssl_certfile).exists() or not Path(ssl_keyfile).exists():
                    self.log("SSL certificates not found", "WARN")
                    return None, None
            
            self.log(f"Starting {mode.upper()} server on port {port}...")
            
            # Create uvicorn config
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=port,
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile,
                log_level="critical"  # Suppress uvicorn logs
            )
            
            # Start server in background task
            server = uvicorn.Server(config)
            self.server_task = asyncio.create_task(server.serve())
            
            # Give server a moment to start
            await asyncio.sleep(0.5)
            
            # Build URL
            protocol = "https" if mode == "https" else "http"
            default_port = 443 if mode == "https" else 80
            if port == default_port:
                url = f"{protocol}://127.0.0.1"
            else:
                url = f"{protocol}://127.0.0.1:{port}"
                
            return server, url
            
        except Exception as e:
            self.log(f"Failed to start {mode} server: {str(e)}", "FAIL")
            return None, None

    async def test_endpoints_fast(self, base_url):
        """Fast endpoint testing"""
        endpoints = [
            ("Main page", ""),
            ("API Info", "/api/network-info"),
            ("File API", "/api/files")
        ]
        
        # Use single session for all tests
        timeout = aiohttp.ClientTimeout(total=3)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for name, endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            self.log(f"{name}: OK", "PASS")
                        else:
                            self.log(f"{name}: HTTP {response.status}", "FAIL")
                            return False
                except Exception as e:
                    self.log(f"{name}: {str(e)}", "FAIL")
                    return False
        return True

    async def test_upload_fast(self, base_url):
        """Fast upload test"""
        try:
            test_content = f"test-{time.time()}".encode()
            
            timeout = aiohttp.ClientTimeout(total=5)
            connector = aiohttp.TCPConnector(ssl=False)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                data = aiohttp.FormData()
                data.add_field('files', test_content, filename='test.txt')
                
                url = f"{base_url}/upload-auto"
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("status") == "success":
                            self.log("Upload: OK", "PASS")
                            return True
                        else:
                            self.log(f"Upload failed: {result.get('msg')}", "FAIL")
                            return False
                    else:
                        self.log(f"Upload: HTTP {response.status}", "FAIL")
                        return False
        except Exception as e:
            self.log(f"Upload error: {str(e)}", "FAIL")
            return False

    async def test_mode(self, mode="http"):
        """Test a server mode quickly"""
        self.log(f"=== Testing {mode.upper()} ===")
        
        # Start server
        server, url = await self.start_server_direct(mode)
        if not server or not url:
            if mode == "https":
                self.log("HTTPS test skipped (no certificates)", "WARN")
                return True  # Not a failure for HTTPS
            return False
        
        try:
            # Quick connectivity check
            try:
                timeout = aiohttp.ClientTimeout(total=2)
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            self.log(f"{mode.upper()} server: Connected", "PASS")
                        else:
                            self.log(f"{mode.upper()} server: HTTP {response.status}", "FAIL")
                            return False
            except Exception as e:
                self.log(f"{mode.upper()} server: Connection failed - {str(e)}", "FAIL")
                return False
            
            # Test endpoints
            if not await self.test_endpoints_fast(url):
                return False
                
            # Test upload
            if not await self.test_upload_fast(url):
                return False
                
            self.log(f"{mode.upper()} mode: All tests passed!", "PASS")
            return True
            
        finally:
            # Cleanup server
            if self.server_task:
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
                self.server_task = None
            # Give it a moment to cleanup
            await asyncio.sleep(0.2)

    async def test_mdns_fast(self):
        """Quick mDNS test"""
        if self.skip_mdns:
            self.log("mDNS: Skipped (Android mode)", "INFO")
            return True
            
        try:
            from simple_mdns import mdns_manager
            info = mdns_manager.get_mdns_info()
            if info.get("status") == "active":
                self.log("mDNS: Active", "PASS")
            else:
                self.log("mDNS: Inactive", "WARN")
            return True
        except Exception as e:
            self.log(f"mDNS: Error - {str(e)}", "WARN")
            return True

    async def run_quick_test(self):
        """Run the complete quick test"""
        self.log("LANVAN Quick Test - Starting...")
        start_time = time.time()
        
        try:
            # Test HTTP mode
            if not await self.test_mode("http"):
                self.log("HTTP test failed", "FAIL")
                return False
            
            # Small delay between modes
            await asyncio.sleep(0.1)
            
            # Test HTTPS mode (optional)
            if not await self.test_mode("https"):
                self.log("HTTPS test issues (non-critical)", "WARN")
            
            # Test mDNS
            await self.test_mdns_fast()
            
            elapsed = time.time() - start_time
            self.log(f"All tests completed in {elapsed:.1f}s", "PASS")
            return True
            
        except Exception as e:
            self.log(f"Test failed: {str(e)}", "FAIL")
            return False

async def main():
    """Main runner"""
    parser = argparse.ArgumentParser(description="LANVAN Quick Test")
    parser.add_argument("--android", action="store_true", 
                       help="Skip mDNS tests (for Android/Termux)")
    
    args = parser.parse_args()
    
    print("LANVAN Simple Quick Test")
    print("=" * 25)
    
    tester = QuickTest(skip_mdns=args.android)
    success = await tester.run_quick_test()
    
    print("=" * 25)
    if success:
        print("[+] Quick test passed! Server is ready.")
        sys.exit(0)
    else:
        print("[-] Quick test failed. Check issues above.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
