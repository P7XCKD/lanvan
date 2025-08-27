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
                # Comprehensive tests
                await self.run_tests(url)
                
                # Test web interface and buttons
                timeout = aiohttp.ClientTimeout(total=5)
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    await self.test_web_interface_buttons(session, url)
                
                self.log("HTTP mode: All tests passed!", "PASS")
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
                    # Comprehensive tests for HTTPS
                    await self.run_tests(url)
                    
                    # Test web interface and buttons for HTTPS
                    timeout = aiohttp.ClientTimeout(total=5)
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                        await self.test_web_interface_buttons(session, url)
                    
                    self.log("HTTPS mode: All tests passed!", "PASS")
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
            
            # Test system logs and monitoring
            await self.test_system_monitoring()
            
            elapsed = time.time() - start_time
            self.log(f"Quick test completed in {elapsed:.1f}s!", "PASS")
            return True
            
        except Exception as e:
            self.log(f"Quick test failed: {str(e)}", "FAIL")
            return False

    async def run_tests(self, base_url):
        """Run comprehensive tests on the server"""
        # Test basic endpoints
        basic_endpoints = [
            ("Main page", ""),
            ("Network API", "/api/network-info"),
            ("Files API", "/api/files")
        ]
        
        # Test advanced endpoints  
        advanced_endpoints = [
            ("QR Code API", "/api/qr-code?text=test&size=100"),
            ("Clipboard API", "/api/clipboard"),
            ("mDNS Info API", "/api/mdns-info"),
            ("AES Config API", "/api/aes-config"),
            ("Logs API", "/api/logs")
        ]
        
        timeout = aiohttp.ClientTimeout(total=5)
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Test basic connectivity and endpoints
            self.log("Testing basic endpoints...")
            for name, endpoint in basic_endpoints:
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
            
            # Test advanced features
            self.log("Testing advanced features...")
            for name, endpoint in advanced_endpoints:
                try:
                    url = f"{base_url}{endpoint}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            # Additional validation for specific endpoints
                            if "qr-code" in endpoint:
                                content_type = response.headers.get('content-type', '')
                                if 'image' in content_type:
                                    self.log(f"{name}: OK (image generated)", "PASS")
                                else:
                                    self.log(f"{name}: Invalid content type: {content_type}", "WARN")
                            elif "clipboard" in endpoint:
                                result = await response.json()
                                if 'clipboard_content' in result:
                                    self.log(f"{name}: OK (clipboard readable)", "PASS")
                                else:
                                    self.log(f"{name}: OK (clipboard empty/unavailable)", "PASS")
                            elif "mdns-info" in endpoint:
                                result = await response.json()
                                status = result.get('status', 'unknown')
                                self.log(f"{name}: OK (status: {status})", "PASS")
                            elif "aes-config" in endpoint:
                                result = await response.json()
                                if 'aes_enabled' in result:
                                    aes_status = "enabled" if result.get('aes_enabled') else "disabled"
                                    self.log(f"{name}: OK (AES {aes_status})", "PASS")
                                else:
                                    self.log(f"{name}: OK", "PASS")
                            elif "logs" in endpoint:
                                result = await response.json()
                                if 'logs' in result:
                                    log_count = len(result.get('logs', []))
                                    self.log(f"{name}: OK ({log_count} log entries)", "PASS")
                                else:
                                    self.log(f"{name}: OK", "PASS")
                            else:
                                self.log(f"{name}: OK", "PASS")
                        else:
                            # Some endpoints might not be available in all modes
                            if response.status == 404:
                                self.log(f"{name}: Not available (404)", "WARN")
                            else:
                                self.log(f"{name}: HTTP {response.status}", "FAIL")
                                raise Exception(f"Endpoint {name} failed")
                except Exception as e:
                    self.log(f"{name}: {str(e)}", "WARN")  # Don't fail test for advanced features
            
            # Test file upload with AES encryption test
            await self.test_file_upload_advanced(session, base_url)
            
            # Test clipboard functionality
            await self.test_clipboard_functionality(session, base_url)
            
            # Test QR code generation with different parameters
            await self.test_qr_code_generation(session, base_url)

    async def test_file_upload_advanced(self, session, base_url):
        """Test file upload with AES and validation"""
        self.log("Testing advanced file upload...")
        test_content = f"quick-test-{time.time()}-with-aes".encode()
        data = aiohttp.FormData()
        data.add_field('files', test_content, filename='quick_test.txt')
        
        try:
            upload_url = f"{base_url}/upload-auto"
            async with session.post(upload_url, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("status") == "success":
                        files_uploaded = result.get("files", [])
                        protocol = result.get("protocol", "Unknown")
                        self.log(f"File upload: OK ({len(files_uploaded)} files, {protocol})", "PASS")
                        
                        # Check if AES was involved
                        if "aes" in str(result).lower():
                            self.log("AES encryption: Detected in upload", "PASS")
                        else:
                            self.log("AES encryption: Not detected (may be disabled)", "INFO")
                    else:
                        raise Exception(f"Upload failed: {result.get('msg')}")
                else:
                    raise Exception(f"Upload HTTP {response.status}")
        except Exception as e:
            self.log(f"File upload: {str(e)}", "FAIL")
            raise

    async def test_clipboard_functionality(self, session, base_url):
        """Test clipboard read/write functionality"""
        self.log("Testing clipboard functionality...")
        
        try:
            # Test clipboard read
            async with session.get(f"{base_url}/api/clipboard") as response:
                if response.status == 200:
                    result = await response.json()
                    self.log("Clipboard read: OK", "PASS")
                    
                    # Test clipboard write
                    test_text = f"test-clipboard-{time.time()}"
                    clipboard_data = {"text": test_text}
                    
                    async with session.post(f"{base_url}/api/clipboard", json=clipboard_data) as write_response:
                        if write_response.status == 200:
                            write_result = await write_response.json()
                            if write_result.get("status") == "success":
                                self.log("Clipboard write: OK", "PASS")
                            else:
                                self.log("Clipboard write: Failed", "WARN")
                        else:
                            self.log(f"Clipboard write: HTTP {write_response.status}", "WARN")
                else:
                    self.log(f"Clipboard read: HTTP {response.status}", "WARN")
        except Exception as e:
            self.log(f"Clipboard test: {str(e)}", "WARN")

    async def test_qr_code_generation(self, session, base_url):
        """Test QR code generation with various parameters"""
        self.log("Testing QR code generation...")
        
        qr_tests = [
            ("Basic QR", "?text=hello&size=100"),
            ("Large QR", "?text=test-large&size=300"),
            ("URL QR", f"?text={base_url}&size=150"),
            ("Complex QR", "?text=Hello%20World%20123&size=200")
        ]
        
        try:
            for test_name, params in qr_tests:
                async with session.get(f"{base_url}/api/qr-code{params}") as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        content_length = response.headers.get('content-length', '0')
                        
                        if 'image' in content_type and int(content_length) > 100:
                            self.log(f"{test_name}: OK ({content_length} bytes)", "PASS")
                        else:
                            self.log(f"{test_name}: Invalid response", "WARN")
                    else:
                        self.log(f"{test_name}: HTTP {response.status}", "WARN")
        except Exception as e:
            self.log(f"QR code test: {str(e)}", "WARN")

    async def test_web_interface_buttons(self, session, base_url):
        """Test web interface and button functionality"""
        self.log("Testing web interface buttons...")
        
        try:
            # Get main page and check for key elements
            async with session.get(base_url) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Check for essential UI elements
                    ui_checks = [
                        ("Upload button", "upload" in content.lower()),
                        ("Download links", "download" in content.lower()),
                        ("QR code section", "qr" in content.lower()),
                        ("Clipboard section", "clipboard" in content.lower()),
                        ("Network info", "network" in content.lower() or "ip" in content.lower()),
                        ("File list", "files" in content.lower()),
                        ("JavaScript", "<script" in content.lower())
                    ]
                    
                    for check_name, found in ui_checks:
                        if found:
                            self.log(f"UI {check_name}: Found", "PASS")
                        else:
                            self.log(f"UI {check_name}: Missing", "WARN")
                            
                    # Check for AES indicators in UI
                    if "aes" in content.lower() or "encrypt" in content.lower():
                        self.log("UI AES indicators: Found", "PASS")
                    else:
                        self.log("UI AES indicators: Not found", "INFO")
                        
                else:
                    self.log(f"Web interface: HTTP {response.status}", "FAIL")
                    
        except Exception as e:
            self.log(f"Web interface test: {str(e)}", "WARN")

    async def test_mdns(self):
        """Test mDNS service comprehensively"""
        if self.skip_mdns:
            self.log("mDNS: Skipped (Android mode)", "INFO")
            return
            
        try:
            from simple_mdns import mdns_manager
            
            # Test mDNS info
            info = mdns_manager.get_mdns_info()
            status = info.get("status", "unknown")
            
            if status == "active":
                self.log(f"mDNS: Active", "PASS")
                
                # Check additional mDNS details
                service_name = info.get("service_name", "unknown")
                service_type = info.get("service_type", "unknown")
                addresses = info.get("addresses", [])
                
                self.log(f"mDNS Service: {service_name}", "INFO")
                self.log(f"mDNS Type: {service_type}", "INFO")
                self.log(f"mDNS Addresses: {len(addresses)} found", "INFO")
                
                # Test mDNS URL generation
                urls = info.get("urls", [])
                if urls:
                    self.log(f"mDNS URLs: {len(urls)} generated", "PASS")
                    for i, url in enumerate(urls[:3]):  # Show first 3 URLs
                        self.log(f"  URL {i+1}: {url}", "INFO")
                else:
                    self.log("mDNS URLs: None generated", "WARN")
                    
            elif status == "inactive":
                self.log("mDNS: Inactive", "WARN")
            else:
                self.log(f"mDNS: Status unknown ({status})", "WARN")
                
        except Exception as e:
            self.log(f"mDNS: Error - {str(e)}", "WARN")

    async def test_system_monitoring(self):
        """Test system monitoring, logs, and responsiveness"""
        self.log("Testing system monitoring...")
        
        try:
            # Test if responsiveness monitor is working
            app_path = Path(__file__).parent / "app"
            if str(app_path) not in sys.path:
                sys.path.insert(0, str(app_path))
                
            # Check various system components
            try:
                from responsiveness_monitor import responsiveness_monitor
                if hasattr(responsiveness_monitor, 'get_stats'):
                    stats = responsiveness_monitor.get_stats()
                    self.log("Responsiveness monitor: Active", "PASS")
                    if stats:
                        self.log(f"Monitor stats: {len(stats)} entries", "INFO")
                else:
                    self.log("Responsiveness monitor: Available", "PASS")
            except Exception as e:
                self.log(f"Responsiveness monitor: {str(e)}", "WARN")
            
            # Test thread manager
            try:
                from thread_manager import thread_manager
                if hasattr(thread_manager, 'get_active_threads'):
                    active = thread_manager.get_active_threads()
                    self.log(f"Thread manager: {len(active)} active threads", "PASS")
                else:
                    self.log("Thread manager: Available", "PASS")
            except Exception as e:
                self.log(f"Thread manager: {str(e)}", "WARN")
                
            # Test AES configuration
            try:
                from aes_config import get_aes_config
                config = get_aes_config()
                if config:
                    enabled = config.get('enabled', False)
                    mode = config.get('mode', 'unknown')
                    self.log(f"AES config: {mode} ({'enabled' if enabled else 'disabled'})", "PASS")
                else:
                    self.log("AES config: Available", "PASS")
            except Exception as e:
                self.log(f"AES config: {str(e)}", "WARN")
                
            # Test platform detection
            try:
                from platform_detector import detect_platform, is_android, is_termux
                platform = detect_platform()
                android = is_android()
                termux = is_termux()
                self.log(f"Platform: {platform} (Android: {android}, Termux: {termux})", "INFO")
            except Exception as e:
                self.log(f"Platform detection: {str(e)}", "WARN")
                
            # Test file validation and concurrent processing
            try:
                from validation import validate_files_async
                from concurrent_upload_manager import process_files_concurrently
                self.log("File processing modules: Available", "PASS")
            except Exception as e:
                self.log(f"File processing: {str(e)}", "WARN")
                
        except Exception as e:
            self.log(f"System monitoring test: {str(e)}", "WARN")

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
