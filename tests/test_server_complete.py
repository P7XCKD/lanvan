#!/usr/bin/env python3
"""
🧪 LANVAN Complete Server Functionality Test Suite
Automated testing for all server components and features.

Tests:
- Server startup (HTTP/HTTPS modes)
- File upload/download functionality
- AES encryption/decryption
- mDNS service discovery
- QR code generation
- Clipboard functionality
- Web app UI components
- API endpoints
- Network connectivity

Usage:
    python test_server_complete.py
    python test_server_complete.py --verbose
    python test_server_complete.py --skip-mdns
"""

import asyncio
import aiohttp
import os
import sys
import time
import json
import subprocess
import tempfile
import hashlib
import base64
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import qrcode
from PIL import Image
import io

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

class Colors:
    """Console colors for better output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class TestResult:
    """Test result container"""
    def __init__(self, name: str, passed: bool, message: str = "", details: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details
        self.duration = 0.0

class LANVANTestSuite:
    """Complete LANVAN server test suite"""
    
    def __init__(self, verbose: bool = False, skip_mdns: bool = False):
        self.verbose = verbose
        self.skip_mdns = skip_mdns
        self.results: List[TestResult] = []
        self.server_process = None
        self.server_url = None
        self.server_port = None
        self.test_files_dir = Path(__file__).parent / "test_files"
        self.test_files_dir.mkdir(exist_ok=True)
        
    def log(self, message: str, color: str = Colors.WHITE):
        """Log message with optional color"""
        print(f"{color}{message}{Colors.END}")
        
    def log_verbose(self, message: str):
        """Log verbose message"""
        if self.verbose:
            self.log(f"  → {message}", Colors.CYAN)
            
    def add_result(self, result: TestResult):
        """Add test result"""
        self.results.append(result)
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result.passed else f"{Colors.RED}❌ FAIL{Colors.END}"
        self.log(f"{status} {result.name}: {result.message}")
        if result.details and self.verbose:
            self.log(f"     {result.details}", Colors.YELLOW)
    
    async def test_server_startup(self, https_mode: bool = False) -> TestResult:
        """Test server startup in HTTP or HTTPS mode"""
        test_name = f"Server Startup ({'HTTPS' if https_mode else 'HTTP'})"
        start_time = time.time()
        
        try:
            # Start server
            cmd = ["python", "run.py"]
            if https_mode:
                cmd.append("https")
                
            self.log_verbose(f"Starting server: {' '.join(cmd)}")
            
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=Path(__file__).parent
            )
            
            # Wait for server to start (check output for startup message)
            timeout = 15  # seconds
            for _ in range(timeout * 10):  # Check every 0.1 seconds
                if self.server_process.poll() is not None:
                    # Process terminated
                    stdout, stderr = self.server_process.communicate()
                    return TestResult(test_name, False, 
                                    "Server failed to start", 
                                    f"stdout: {stdout}\nstderr: {stderr}")
                
                await asyncio.sleep(0.1)
                
                # Try to connect
                try:
                    protocol = "https" if https_mode else "http"
                    port = 443 if https_mode else 80
                    self.server_url = f"{protocol}://127.0.0.1:{port}"
                    self.server_port = port
                    
                    async with aiohttp.ClientSession(
                        connector=aiohttp.TCPConnector(ssl=False)
                    ) as session:
                        async with session.get(self.server_url, timeout=2) as response:
                            if response.status == 200:
                                duration = time.time() - start_time
                                result = TestResult(test_name, True, 
                                                  f"Server started successfully in {duration:.1f}s",
                                                  f"URL: {self.server_url}")
                                result.duration = duration
                                return result
                except:
                    continue
                    
            # Timeout
            return TestResult(test_name, False, "Server startup timeout (15s)")
            
        except Exception as e:
            return TestResult(test_name, False, f"Startup error: {str(e)}")
    
    async def test_basic_connectivity(self) -> TestResult:
        """Test basic HTTP connectivity"""
        test_name = "Basic Connectivity"
        
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                async with session.get(self.server_url, timeout=5) as response:
                    content = await response.text()
                    
                    if response.status == 200 and "Lanvan" in content:
                        return TestResult(test_name, True, 
                                        f"HTTP {response.status} - Main page loaded")
                    else:
                        return TestResult(test_name, False, 
                                        f"HTTP {response.status} - Invalid response")
                        
        except Exception as e:
            return TestResult(test_name, False, f"Connection error: {str(e)}")
    
    async def test_api_endpoints(self) -> TestResult:
        """Test critical API endpoints"""
        test_name = "API Endpoints"
        
        endpoints = [
            "/api/network-info",
            "/api/files",
            "/api/qr-code?text=test&size=100"
        ]
        
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                
                for endpoint in endpoints:
                    url = f"{self.server_url}{endpoint}"
                    self.log_verbose(f"Testing endpoint: {endpoint}")
                    
                    async with session.get(url, timeout=5) as response:
                        if response.status != 200:
                            return TestResult(test_name, False, 
                                            f"Endpoint {endpoint} returned {response.status}")
                
                return TestResult(test_name, True, 
                                f"All {len(endpoints)} API endpoints responding")
                
        except Exception as e:
            return TestResult(test_name, False, f"API test error: {str(e)}")
    
    async def test_file_upload_download(self) -> TestResult:
        """Test file upload and download functionality"""
        test_name = "File Upload/Download"
        
        try:
            # Create test file
            test_content = b"LANVAN Test File Content - " + os.urandom(1024)
            test_filename = "test_upload_file.txt"
            test_file_path = self.test_files_dir / test_filename
            
            with open(test_file_path, "wb") as f:
                f.write(test_content)
            
            self.log_verbose(f"Created test file: {test_file_path}")
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                
                # Test upload
                with open(test_file_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field('files', f, filename=test_filename)
                    
                    upload_url = f"{self.server_url}/upload-auto"
                    self.log_verbose(f"Uploading to: {upload_url}")
                    
                    async with session.post(upload_url, data=data, timeout=10) as response:
                        if response.status != 200:
                            return TestResult(test_name, False, 
                                            f"Upload failed: HTTP {response.status}")
                        
                        upload_result = await response.json()
                        if upload_result.get("status") != "success":
                            return TestResult(test_name, False, 
                                            f"Upload error: {upload_result.get('msg', 'Unknown')}")
                
                # Test download
                download_url = f"{self.server_url}/download/{test_filename}"
                self.log_verbose(f"Downloading from: {download_url}")
                
                async with session.get(download_url, timeout=10) as response:
                    if response.status != 200:
                        return TestResult(test_name, False, 
                                        f"Download failed: HTTP {response.status}")
                    
                    downloaded_content = await response.read()
                    
                    if downloaded_content == test_content:
                        return TestResult(test_name, True, 
                                        f"Upload/download successful ({len(test_content)} bytes)")
                    else:
                        return TestResult(test_name, False, 
                                        "Downloaded content doesn't match uploaded content")
            
        except Exception as e:
            return TestResult(test_name, False, f"File test error: {str(e)}")
        finally:
            # Cleanup
            if test_file_path.exists():
                test_file_path.unlink()
    
    async def test_aes_encryption(self) -> TestResult:
        """Test AES encryption/decryption functionality"""
        test_name = "AES Encryption"
        
        try:
            # Import AES utilities
            from aes_utils import encrypt_file_content, decrypt_file_content
            
            # Test data
            test_data = b"LANVAN AES Test Content - " + os.urandom(512)
            password = "test_password_123"
            
            self.log_verbose("Testing AES encryption/decryption")
            
            # Encrypt
            encrypted_data = encrypt_file_content(test_data, password)
            if not encrypted_data or encrypted_data == test_data:
                return TestResult(test_name, False, "Encryption failed or returned original data")
            
            # Decrypt
            decrypted_data = decrypt_file_content(encrypted_data, password)
            if decrypted_data != test_data:
                return TestResult(test_name, False, "Decryption failed - data mismatch")
            
            # Test wrong password
            try:
                wrong_decrypt = decrypt_file_content(encrypted_data, "wrong_password")
                if wrong_decrypt == test_data:
                    return TestResult(test_name, False, "Encryption security failed - wrong password worked")
            except:
                pass  # Expected to fail
            
            return TestResult(test_name, True, 
                            f"AES encryption/decryption working correctly")
            
        except ImportError:
            return TestResult(test_name, False, "AES utilities not available")
        except Exception as e:
            return TestResult(test_name, False, f"AES test error: {str(e)}")
    
    async def test_qr_code_generation(self) -> TestResult:
        """Test QR code generation and image output"""
        test_name = "QR Code Generation"
        
        try:
            # Test QR code API endpoint
            qr_url = f"{self.server_url}/api/qr-code?text=http://test.example.com&size=150"
            
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                
                self.log_verbose("Testing QR code API endpoint")
                async with session.get(qr_url, timeout=5) as response:
                    if response.status != 200:
                        return TestResult(test_name, False, 
                                        f"QR API failed: HTTP {response.status}")
                    
                    qr_data = await response.read()
                    
                    # Verify it's a valid image
                    try:
                        img = Image.open(io.BytesIO(qr_data))
                        width, height = img.size
                        
                        if width < 50 or height < 50:
                            return TestResult(test_name, False, 
                                            f"QR code too small: {width}x{height}")
                        
                        # Test local QR generation
                        qr = qrcode.QRCode(version=1, box_size=5, border=4)
                        qr.add_data("test_data")
                        qr.make(fit=True)
                        test_img = qr.make_image(fill_color="black", back_color="white")
                        
                        return TestResult(test_name, True, 
                                        f"QR code generation working ({width}x{height} image)")
                        
                    except Exception as img_error:
                        return TestResult(test_name, False, 
                                        f"Invalid QR image data: {str(img_error)}")
            
        except Exception as e:
            return TestResult(test_name, False, f"QR test error: {str(e)}")
    
    async def test_mdns_functionality(self) -> TestResult:
        """Test mDNS service discovery"""
        test_name = "mDNS Service Discovery"
        
        if self.skip_mdns:
            return TestResult(test_name, True, "Skipped (--skip-mdns flag)")
        
        try:
            # Import mDNS manager
            from simple_mdns import mdns_manager
            
            self.log_verbose("Testing mDNS service registration")
            
            # Check if mDNS service is running
            mdns_info = mdns_manager.get_mdns_info()
            
            if mdns_info.get("status") == "active":
                domain = mdns_info.get("domain")
                
                # Try to resolve the domain
                import socket
                try:
                    ip = socket.gethostbyname(domain)
                    return TestResult(test_name, True, 
                                    f"mDNS active: {domain} → {ip}")
                except socket.gaierror:
                    return TestResult(test_name, False, 
                                    f"mDNS registered but {domain} not resolvable")
            else:
                return TestResult(test_name, False, 
                                f"mDNS service not active: {mdns_info.get('status')}")
            
        except ImportError:
            return TestResult(test_name, False, "mDNS utilities not available")
        except Exception as e:
            return TestResult(test_name, False, f"mDNS test error: {str(e)}")
    
    async def test_clipboard_functionality(self) -> TestResult:
        """Test clipboard API endpoints"""
        test_name = "Clipboard Functionality"
        
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                
                # Test clipboard page
                clipboard_url = f"{self.server_url}/clipboard"
                self.log_verbose("Testing clipboard page")
                
                async with session.get(clipboard_url, timeout=5) as response:
                    if response.status != 200:
                        return TestResult(test_name, False, 
                                        f"Clipboard page failed: HTTP {response.status}")
                    
                    page_content = await response.text()
                    if "clipboard" not in page_content.lower():
                        return TestResult(test_name, False, 
                                        "Clipboard page doesn't contain clipboard content")
                
                # Test clipboard add API
                add_url = f"{self.server_url}/api/clipboard/add"
                test_data = {"data": "Test clipboard content from automated test"}
                
                self.log_verbose("Testing clipboard add API")
                async with session.post(add_url, data=test_data, timeout=5) as response:
                    if response.status not in [200, 302]:  # 302 for redirect after add
                        return TestResult(test_name, False, 
                                        f"Clipboard add failed: HTTP {response.status}")
                
                return TestResult(test_name, True, "Clipboard functionality working")
            
        except Exception as e:
            return TestResult(test_name, False, f"Clipboard test error: {str(e)}")
    
    async def test_web_app_components(self) -> TestResult:
        """Test web app UI components and JavaScript functionality"""
        test_name = "Web App Components"
        
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                
                # Get main page
                async with session.get(self.server_url, timeout=5) as response:
                    if response.status != 200:
                        return TestResult(test_name, False, 
                                        f"Main page failed: HTTP {response.status}")
                    
                    content = await response.text()
                    
                    # Check for critical UI components
                    required_elements = [
                        "fileInput",           # File input
                        "enableEncryption",    # Encryption checkbox
                        "enableDarkMode",      # Dark mode toggle
                        "unifiedUploadForm",   # Upload form
                        "clipboard",           # Clipboard section
                        "qr-code",            # QR code functionality
                        "download-btn"         # Download buttons
                    ]
                    
                    missing_elements = []
                    for element in required_elements:
                        if element not in content:
                            missing_elements.append(element)
                    
                    if missing_elements:
                        return TestResult(test_name, False, 
                                        f"Missing UI elements: {', '.join(missing_elements)}")
                    
                    # Check for JavaScript functionality indicators
                    js_features = [
                        "DEBUG_MODE",          # Logging system
                        "uploadFiles",         # Upload function
                        "updateUI",           # UI update function
                        "showSection"         # Section switching
                    ]
                    
                    missing_js = []
                    for feature in js_features:
                        if feature not in content:
                            missing_js.append(feature)
                    
                    if missing_js:
                        return TestResult(test_name, False, 
                                        f"Missing JS features: {', '.join(missing_js)}")
                    
                    return TestResult(test_name, True, 
                                    f"All UI components and JS features present")
            
        except Exception as e:
            return TestResult(test_name, False, f"Web app test error: {str(e)}")
    
    def cleanup_server(self):
        """Clean up server process"""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                self.server_process.wait()
            except:
                pass
    
    async def run_all_tests(self) -> Dict:
        """Run all tests and return summary"""
        self.log(f"{Colors.BOLD}{Colors.BLUE}🧪 LANVAN Server Test Suite Starting...{Colors.END}\n")
        
        total_start_time = time.time()
        
        # Test server startup (HTTP mode)
        result = await self.test_server_startup(https_mode=False)
        self.add_result(result)
        
        if not result.passed:
            self.log(f"\n{Colors.RED}❌ Server startup failed - aborting remaining tests{Colors.END}")
            return self.generate_summary()
        
        # Run all other tests
        tests = [
            self.test_basic_connectivity(),
            self.test_api_endpoints(),
            self.test_file_upload_download(),
            self.test_aes_encryption(),
            self.test_qr_code_generation(),
            self.test_mdns_functionality(),
            self.test_clipboard_functionality(),
            self.test_web_app_components()
        ]
        
        for test_coro in tests:
            result = await test_coro
            self.add_result(result)
        
        # Cleanup and test HTTPS mode
        self.cleanup_server()
        await asyncio.sleep(2)  # Wait for cleanup
        
        # Test HTTPS startup
        self.log(f"\n{Colors.YELLOW}🔒 Testing HTTPS mode...{Colors.END}")
        https_result = await self.test_server_startup(https_mode=True)
        self.add_result(https_result)
        
        total_duration = time.time() - total_start_time
        
        return self.generate_summary(total_duration)
    
    def generate_summary(self, total_duration: float = 0) -> Dict:
        """Generate test summary"""
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        
        summary = {
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "success_rate": (passed / len(self.results) * 100) if self.results else 0,
            "total_duration": total_duration,
            "results": self.results
        }
        
        # Print summary
        self.log(f"\n{Colors.BOLD}📊 TEST SUMMARY{Colors.END}")
        self.log("=" * 50)
        
        status_color = Colors.GREEN if failed == 0 else Colors.RED
        self.log(f"Total Tests: {len(self.results)}")
        self.log(f"Passed: {Colors.GREEN}{passed}{Colors.END}")
        self.log(f"Failed: {Colors.RED}{failed}{Colors.END}")
        self.log(f"Success Rate: {status_color}{summary['success_rate']:.1f}%{Colors.END}")
        if total_duration:
            self.log(f"Total Duration: {total_duration:.1f}s")
        
        if failed > 0:
            self.log(f"\n{Colors.RED}❌ FAILED TESTS:{Colors.END}")
            for result in self.results:
                if not result.passed:
                    self.log(f"  • {result.name}: {result.message}")
        else:
            self.log(f"\n{Colors.GREEN}🎉 ALL TESTS PASSED!{Colors.END}")
            self.log("✅ LANVAN server is fully functional and ready to use!")
        
        return summary

async def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="LANVAN Server Test Suite")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose output")
    parser.add_argument("--skip-mdns", action="store_true", 
                       help="Skip mDNS tests (useful for Android/Termux)")
    
    args = parser.parse_args()
    
    # Create and run test suite
    test_suite = LANVANTestSuite(verbose=args.verbose, skip_mdns=args.skip_mdns)
    
    try:
        summary = await test_suite.run_all_tests()
        
        # Exit with appropriate code
        sys.exit(0 if summary["failed"] == 0 else 1)
        
    except KeyboardInterrupt:
        test_suite.log(f"\n{Colors.YELLOW}⚠️ Tests interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        test_suite.log(f"\n{Colors.RED}❌ Test suite error: {str(e)}{Colors.END}")
        sys.exit(1)
    finally:
        test_suite.cleanup_server()

if __name__ == "__main__":
    asyncio.run(main())
