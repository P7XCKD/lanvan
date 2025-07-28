#!/usr/bin/env python3
"""
🧪 LanVan Automated Testing Suite
Tests all combinations of HTTP/HTTPS, chunked/non-chunked, AES encryption, and host/guest devices
"""

import os
import sys
import asyncio
import json
import time
import hashlib
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import subprocess
import signal
import ssl

# Try to import optional dependencies
try:
    import aiohttp
    import aiofiles
    import psutil
except ImportError as e:
    print(f"❌ Missing required packages for testing: {e}")
    print("Installing test dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "aiohttp", "aiofiles", "psutil"])
    try:
        import aiohttp
        import aiofiles
        import psutil
    except ImportError:
        print("❌ Failed to install test dependencies")
        sys.exit(1)

class LanVanTester:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.upload_dir = self.base_dir / "app" / "uploads"
        self.test_files_dir = self.base_dir / "test_files"
        self.results = []
        self.server_process = None
        self.test_files = {}
        
        # Test configurations
        self.protocols = ["http", "https"]
        self.encryption_modes = [False, True]  # AES on/off
        self.device_types = ["host", "guest"]  # Different upload strategies
        self.file_sizes = {
            "small": 1024 * 100,      # 100KB - no chunking
            "medium": 1024 * 1024 * 5,  # 5MB - no chunking
            "large": 1024 * 1024 * 300   # 300MB - chunked
        }
        
        # Server ports
        self.http_port = 5000
        self.https_port = 5001  # Match run.py configuration
        
    async def setup_test_environment(self):
        """Setup test files and environment"""
        print("🔧 Setting up test environment...")
        
        # Create test files directory
        self.test_files_dir.mkdir(exist_ok=True)
        
        # Generate test files with known content
        for size_name, size_bytes in self.file_sizes.items():
            filename = f"test_{size_name}.txt"
            filepath = self.test_files_dir / filename
            
            # Generate predictable content for hash verification
            content = f"LanVan Test File - {size_name.upper()}\n" * (size_bytes // 50)
            content = content[:size_bytes]  # Trim to exact size
            
            with open(filepath, 'w') as f:
                f.write(content)
            
            # Calculate hash for verification
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            self.test_files[size_name] = {
                "path": filepath,
                "size": size_bytes,
                "hash": file_hash,
                "filename": filename
            }
        
        print(f"✅ Created {len(self.test_files)} test files")
        
    async def start_server(self, protocol: str) -> bool:
        """Start the LanVan server"""
        try:
            port = self.https_port if protocol == "https" else self.http_port
            
            # Kill any existing server on this port
            await self.kill_server_on_port(port)
            
            if protocol == "https":
                cmd = [sys.executable, "run.py", "--https", "--port", str(port)]
            else:
                cmd = [sys.executable, "run.py", "--port", str(port)]
            
            print(f"🚀 Starting {protocol.upper()} server on port {port}...")
            
            self.server_process = subprocess.Popen(
                cmd,
                cwd=self.base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # Wait for server to start
            await asyncio.sleep(3)
            
            # Test if server is responsive
            url = f"{protocol}://localhost:{port}/"
            timeout = aiohttp.ClientTimeout(total=10)
            
            # Create SSL context that ignores self-signed certificates for testing
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context if protocol == "https" else None)
            
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        print(f"✅ {protocol.upper()} server started successfully")
                        return True
                    else:
                        print(f"❌ Server responded with status {response.status}")
                        return False
                        
        except Exception as e:
            print(f"❌ Failed to start {protocol} server: {e}")
            return False
    
    async def kill_server_on_port(self, port: int):
        """Kill any process using the specified port"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'connections']):
                try:
                    for conn in proc.info['connections'] or []:
                        if conn.laddr.port == port:
                            print(f"🔪 Killing process {proc.info['pid']} using port {port}")
                            proc.kill()
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"⚠️ Error killing processes on port {port}: {e}")
    
    async def stop_server(self):
        """Stop the running server"""
        if self.server_process:
            try:
                if os.name == 'nt':
                    # Windows
                    self.server_process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    # Unix/Linux
                    self.server_process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.server_process.kill()
                    self.server_process.wait()
                
                print("🛑 Server stopped")
            except Exception as e:
                print(f"⚠️ Error stopping server: {e}")
            finally:
                self.server_process = None
    
    async def upload_file_full(self, session: aiohttp.ClientSession, url: str, 
                              file_path: Path, encrypt: bool = False) -> Dict:
        """Upload file using full upload method"""
        try:
            data = aiohttp.FormData()
            
            async with aiofiles.open(file_path, 'rb') as f:
                file_content = await f.read()
            
            data.add_field('files', 
                          file_content,
                          filename=file_path.name,
                          content_type='application/octet-stream')
            
            params = {"encrypt": "true" if encrypt else "false"}
            
            async with session.post(f"{url}/upload-auto", data=data, params=params) as response:
                result = await response.json()
                return {
                    "status": response.status,
                    "result": result,
                    "method": "full"
                }
        except Exception as e:
            return {"status": 0, "error": str(e), "method": "full"}
    
    async def upload_file_chunked(self, session: aiohttp.ClientSession, url: str, 
                                 file_path: Path, encrypt: bool = False, 
                                 chunk_size: int = 1024 * 1024) -> Dict:
        """Upload file using chunked upload method"""
        try:
            file_size = file_path.stat().st_size
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            
            # Upload chunks
            async with aiofiles.open(file_path, 'rb') as f:
                for chunk_num in range(1, total_chunks + 1):
                    chunk_data = await f.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    # Create chunk upload data
                    chunk_form = aiohttp.FormData()
                    chunk_form.add_field('chunk', chunk_data, 
                                       filename=f"{file_path.name}.part{chunk_num}")
                    chunk_form.add_field('filename', file_path.name)
                    chunk_form.add_field('part_number', str(chunk_num))
                    chunk_form.add_field('total_parts', str(total_chunks))
                    
                    # Upload chunk
                    async with session.post(f"{url}/upload_chunk", data=chunk_form) as response:
                        if response.status != 200:
                            result = await response.json()
                            return {
                                "status": response.status,
                                "error": f"Chunk {chunk_num} failed: {result}",
                                "method": "chunked"
                            }
            
            # Finalize upload
            finalize_form = aiohttp.FormData()
            finalize_form.add_field('filename', file_path.name)
            finalize_form.add_field('total_parts', str(total_chunks))
            finalize_form.add_field('encrypt', 'true' if encrypt else 'false')
            
            async with session.post(f"{url}/finalize_upload", data=finalize_form) as response:
                result = await response.json()
                return {
                    "status": response.status,
                    "result": result,
                    "method": "chunked",
                    "chunks": total_chunks
                }
                
        except Exception as e:
            return {"status": 0, "error": str(e), "method": "chunked"}
    
    async def download_and_verify(self, session: aiohttp.ClientSession, url: str, 
                                 filename: str, expected_hash: str) -> Dict:
        """Download file and verify its integrity"""
        try:
            async with session.get(f"{url}/download/{filename}") as response:
                if response.status != 200:
                    return {
                        "status": response.status,
                        "error": f"Download failed with status {response.status}"
                    }
                
                content = await response.read()
                
                # For encrypted files, we need to verify the decrypted content
                if filename.endswith('.enc'):
                    # The server should have automatically decrypted it
                    actual_hash = hashlib.sha256(content).hexdigest()
                else:
                    actual_hash = hashlib.sha256(content).hexdigest()
                
                return {
                    "status": response.status,
                    "hash_match": actual_hash == expected_hash,
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                    "size": len(content)
                }
                
        except Exception as e:
            return {"status": 0, "error": str(e)}
    
    async def clear_uploads(self, session: aiohttp.ClientSession, url: str) -> bool:
        """Clear all uploaded files"""
        try:
            async with session.post(f"{url}/clear") as response:
                return response.status in [200, 302]  # 302 is redirect after clear
        except:
            return False
    
    async def run_test_scenario(self, protocol: str, encrypt: bool, 
                               device_type: str, file_size: str) -> Dict:
        """Run a single test scenario"""
        port = self.https_port if protocol == "https" else self.http_port
        url = f"{protocol}://localhost:{port}"
        
        test_info = {
            "protocol": protocol,
            "encrypt": encrypt,
            "device_type": device_type,
            "file_size": file_size
        }
        
        print(f"\n🧪 Testing: {protocol.upper()} | AES: {'ON' if encrypt else 'OFF'} | Device: {device_type.upper()} | Size: {file_size.upper()}")
        
        # Create SSL context for HTTPS
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context if protocol == "https" else None)
        timeout = aiohttp.ClientTimeout(total=60)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                # Get test file info
                file_info = self.test_files[file_size]
                file_path = file_info["path"]
                expected_hash = file_info["hash"]
                
                # Clear any existing uploads
                await self.clear_uploads(session, url)
                
                # Determine upload method based on file size and device type
                is_large = file_size == "large"
                use_chunked = is_large and not encrypt  # No chunking for encrypted files
                
                # Adjust chunk size for guest devices (simulate lower bandwidth)
                chunk_size = 512 * 1024 if device_type == "guest" else 2 * 1024 * 1024
                
                # Upload file
                start_time = time.time()
                
                if use_chunked:
                    upload_result = await self.upload_file_chunked(
                        session, url, file_path, encrypt, chunk_size
                    )
                else:
                    upload_result = await self.upload_file_full(
                        session, url, file_path, encrypt
                    )
                
                upload_time = time.time() - start_time
                
                # Check upload success
                if upload_result["status"] != 200:
                    return {
                        **test_info,
                        "status": "FAILED",
                        "stage": "upload",
                        "error": upload_result.get("error", "Upload failed"),
                        "upload_time": upload_time
                    }
                
                # Determine download filename
                uploaded_filename = upload_result["result"].get("files", [None])[0]
                if not uploaded_filename:
                    uploaded_filename = upload_result["result"].get("filename")
                
                if not uploaded_filename:
                    return {
                        **test_info,
                        "status": "FAILED",
                        "stage": "upload",
                        "error": "No filename in upload response",
                        "upload_time": upload_time
                    }
                
                # Download and verify
                download_start = time.time()
                download_result = await self.download_and_verify(
                    session, url, uploaded_filename, expected_hash
                )
                download_time = time.time() - download_start
                
                if download_result["status"] != 200:
                    return {
                        **test_info,
                        "status": "FAILED",
                        "stage": "download",
                        "error": download_result.get("error", "Download failed"),
                        "upload_time": upload_time,
                        "download_time": download_time
                    }
                
                # Verify file integrity
                if not download_result.get("hash_match", False):
                    return {
                        **test_info,
                        "status": "FAILED",
                        "stage": "verification",
                        "error": "Hash mismatch - file corruption detected",
                        "expected_hash": download_result["expected_hash"],
                        "actual_hash": download_result["actual_hash"],
                        "upload_time": upload_time,
                        "download_time": download_time
                    }
                
                # Calculate speeds
                file_size_mb = file_info["size"] / (1024 * 1024)
                upload_speed = file_size_mb / upload_time if upload_time > 0 else 0
                download_speed = file_size_mb / download_time if download_time > 0 else 0
                
                return {
                    **test_info,
                    "status": "PASSED",
                    "upload_method": upload_result["method"],
                    "chunks": upload_result.get("chunks", 1),
                    "upload_time": round(upload_time, 2),
                    "download_time": round(download_time, 2),
                    "upload_speed_mbps": round(upload_speed, 2),
                    "download_speed_mbps": round(download_speed, 2),
                    "file_size_mb": round(file_size_mb, 2)
                }
                
        except Exception as e:
            return {
                **test_info,
                "status": "FAILED",
                "stage": "connection",
                "error": str(e)
            }
    
    async def run_all_tests(self):
        """Run all test combinations"""
        print("🚀 Starting LanVan Automated Test Suite")
        print("=" * 60)
        
        await self.setup_test_environment()
        
        total_tests = len(self.protocols) * len(self.encryption_modes) * len(self.device_types) * len(self.file_sizes)
        current_test = 0
        
        for protocol in self.protocols:
            # Start server for this protocol
            if not await self.start_server(protocol):
                print(f"❌ Failed to start {protocol} server, skipping tests")
                continue
            
            try:
                for encrypt in self.encryption_modes:
                    for device_type in self.device_types:
                        for file_size in self.file_sizes.keys():
                            current_test += 1
                            
                            # Skip invalid combinations
                            if encrypt and protocol == "http":
                                print(f"⏭️ Skipping AES over HTTP (not allowed)")
                                continue
                            
                            print(f"\n📊 Progress: {current_test}/{total_tests}")
                            
                            result = await self.run_test_scenario(
                                protocol, encrypt, device_type, file_size
                            )
                            self.results.append(result)
                            
                            # Print immediate result
                            status_emoji = "✅" if result["status"] == "PASSED" else "❌"
                            print(f"{status_emoji} {result['status']}")
                            
                            if result["status"] == "FAILED":
                                print(f"   Error: {result.get('error', 'Unknown error')}")
                            else:
                                print(f"   Upload: {result['upload_speed_mbps']} MB/s | Download: {result['download_speed_mbps']} MB/s")
                            
                            # Small delay between tests
                            await asyncio.sleep(1)
            
            finally:
                await self.stop_server()
                await asyncio.sleep(2)  # Allow port to be released
    
    def generate_report(self):
        """Generate detailed test report"""
        print("\n" + "=" * 80)
        print("📊 LANVAN AUTOMATED TEST REPORT")
        print("=" * 80)
        
        passed = len([r for r in self.results if r["status"] == "PASSED"])
        failed = len([r for r in self.results if r["status"] == "FAILED"])
        
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed / len(self.results) * 100):.1f}%")
        
        # Group results by status
        if failed > 0:
            print(f"\n❌ FAILED TESTS ({failed}):")
            print("-" * 40)
            for result in self.results:
                if result["status"] == "FAILED":
                    print(f"  {result['protocol'].upper()} | AES: {'ON' if result['encrypt'] else 'OFF'} | "
                          f"{result['device_type'].upper()} | {result['file_size'].upper()}")
                    print(f"    Error: {result.get('error', 'Unknown')}")
                    print()
        
        if passed > 0:
            print(f"\n✅ PASSED TESTS ({passed}):")
            print("-" * 40)
            
            # Performance summary
            avg_upload_speed = sum(r.get('upload_speed_mbps', 0) for r in self.results if r['status'] == 'PASSED') / passed
            avg_download_speed = sum(r.get('download_speed_mbps', 0) for r in self.results if r['status'] == 'PASSED') / passed
            
            print(f"Average Upload Speed: {avg_upload_speed:.2f} MB/s")
            print(f"Average Download Speed: {avg_download_speed:.2f} MB/s")
            
            # Best performers
            fastest_upload = max((r for r in self.results if r['status'] == 'PASSED'), 
                               key=lambda x: x.get('upload_speed_mbps', 0), default=None)
            fastest_download = max((r for r in self.results if r['status'] == 'PASSED'), 
                                 key=lambda x: x.get('download_speed_mbps', 0), default=None)
            
            if fastest_upload:
                print(f"\nFastest Upload: {fastest_upload['upload_speed_mbps']} MB/s")
                print(f"  {fastest_upload['protocol'].upper()} | AES: {'ON' if fastest_upload['encrypt'] else 'OFF'} | "
                      f"{fastest_upload['device_type'].upper()} | {fastest_upload['file_size'].upper()}")
            
            if fastest_download:
                print(f"\nFastest Download: {fastest_download['download_speed_mbps']} MB/s")
                print(f"  {fastest_download['protocol'].upper()} | AES: {'ON' if fastest_download['encrypt'] else 'OFF'} | "
                      f"{fastest_download['device_type'].upper()} | {fastest_download['file_size'].upper()}")
        
        # Save detailed results
        report_file = self.base_dir / "test_results.json"
        with open(report_file, 'w') as f:
            json.dump({
                "summary": {
                    "total": len(self.results),
                    "passed": passed,
                    "failed": failed,
                    "success_rate": passed / len(self.results) * 100
                },
                "results": self.results
            }, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {report_file}")
        print("=" * 80)
    
    async def cleanup(self):
        """Cleanup test environment"""
        try:
            await self.stop_server()
            
            # Clean upload directory
            if self.upload_dir.exists():
                for file in self.upload_dir.iterdir():
                    if file.is_file():
                        file.unlink()
            
            # Clean test files
            if self.test_files_dir.exists():
                shutil.rmtree(self.test_files_dir)
            
            print("🧹 Test environment cleaned up")
        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

async def main():
    """Main test runner"""
    tester = LanVanTester()
    
    try:
        await tester.run_all_tests()
        tester.generate_report()
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    # Check if required packages are installed
    required_packages = ["aiohttp", "aiofiles", "psutil"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print(f"Install with: pip install {' '.join(missing_packages)}")
        sys.exit(1)
    
    asyncio.run(main())
