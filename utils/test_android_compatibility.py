#!/usr/bin/env python3
"""
Android/Termux Compatibility Test Script
Tests the enhanced Android features and network detection
"""

import os
import sys
import socket
import subprocess
import platform
from pathlib import Path

def test_android_environment():
    """Test if we're running in Android/Termux environment"""
    print("🤖 Testing Android/Termux Environment")
    print("=" * 40)
    
    # Check for Termux
    is_termux = os.path.exists('/data/data/com.termux')
    print(f"Termux detected: {'✅ Yes' if is_termux else '❌ No'}")
    
    # Check Python version
    print(f"Python version: {sys.version}")
    
    # Check platform
    print(f"Platform: {platform.system()} {platform.release()}")
    print()
    
    return is_termux

def test_network_detection():
    """Test network IP detection methods"""
    print("🌐 Testing Network Detection")
    print("=" * 30)
    
    # Test basic socket method
    try:
        hostname = socket.gethostname()
        basic_ip = socket.gethostbyname(hostname)
        print(f"Basic IP detection: {basic_ip}")
    except Exception as e:
        print(f"Basic IP detection failed: {e}")
    
    # Test enhanced Android detection (like in our updated code)
    try:
        # Method 1: ip route command
        try:
            result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'src' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'src' and i + 1 < len(parts):
                                route_ip = parts[i + 1]
                                print(f"Route command IP: {route_ip}")
                                break
        except Exception as e:
            print(f"Route command failed: {e}")
        
        # Method 2: Socket connection method
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(('8.8.8.8', 80))
                socket_ip = s.getsockname()[0]
                print(f"Socket connection IP: {socket_ip}")
        except Exception as e:
            print(f"Socket connection failed: {e}")
            
        # Method 3: Network interfaces
        try:
            import subprocess
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("Network interfaces detected:")
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'inet ' in line and '127.0.0.1' not in line:
                        parts = line.strip().split()
                        for part in parts:
                            if part.startswith('inet '):
                                ip = part.split('/')[0].replace('inet ', '')
                                print(f"  Interface IP: {ip}")
        except Exception as e:
            print(f"Interface detection failed: {e}")
    
    except Exception as e:
        print(f"Network detection error: {e}")
    
    print()

def test_qr_support():
    """Test QR code generation support"""
    print("📱 Testing QR Code Support")
    print("=" * 25)
    
    # Test qrcode library
    try:
        import qrcode
        print("✅ qrcode library available")
        
        # Test basic QR generation
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data("http://192.168.1.100:8000")
        qr.make(fit=True)
        print("✅ Basic QR generation works")
        
    except ImportError:
        print("❌ qrcode library not available")
    except Exception as e:
        print(f"⚠️ QR generation error: {e}")
    
    # Test PIL/Pillow
    try:
        from PIL import Image
        print("✅ PIL/Pillow available for image QR codes")
    except ImportError:
        print("⚠️ PIL/Pillow not available (text QR codes will be used)")
    
    print()

def test_websocket_support():
    """Test WebSocket library support"""
    print("🔌 Testing WebSocket Support")
    print("=" * 25)
    
    # Test websockets library
    try:
        import websockets
        print("✅ websockets library available")
    except ImportError:
        print("❌ websockets library not available")
        print("   Install with: pip install websockets")
    
    # Test uvicorn WebSocket support
    try:
        import uvicorn
        print("✅ uvicorn available")
        
        # Check if standard extras are available
        try:
            import uvloop
            print("✅ uvloop (performance enhancement) available")
        except ImportError:
            print("⚠️ uvloop not available (install uvicorn[standard] for better performance)")
            
    except ImportError:
        print("❌ uvicorn not available")
    
    print()

def test_dependencies():
    """Test all required dependencies"""
    print("📦 Testing Dependencies")
    print("=" * 20)
    
    required_packages = [
        'fastapi',
        'jinja2',
        'python_multipart',
        'aiofiles',
        'cryptography',
        'zeroconf',
        'psutil'
    ]
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Install with: pip install {package}")
    
    print()

def test_file_permissions():
    """Test file system permissions"""
    print("📁 Testing File Permissions")
    print("=" * 25)
    
    # Test current directory write
    try:
        test_file = Path("test_write.tmp")
        test_file.write_text("test")
        test_file.unlink()
        print("✅ Current directory writable")
    except Exception as e:
        print(f"❌ Current directory not writable: {e}")
    
    # Test home directory
    try:
        home_test = Path.home() / "test_write.tmp"
        home_test.write_text("test")
        home_test.unlink()
        print("✅ Home directory writable")
    except Exception as e:
        print(f"❌ Home directory not writable: {e}")
    
    # Check for Android storage
    if os.path.exists('/data/data/com.termux'):
        storage_paths = [
            Path.home() / "storage" / "shared",
            Path.home() / "storage" / "downloads",
            Path("/sdcard")
        ]
        
        for path in storage_paths:
            if path.exists():
                try:
                    test_file = path / "test_write.tmp"
                    test_file.write_text("test")
                    test_file.unlink()
                    print(f"✅ {path} writable")
                except Exception as e:
                    print(f"⚠️ {path} not writable: {e}")
    
    print()

def main():
    """Run all tests"""
    print("🧪 LANVAN Android/Termux Compatibility Test")
    print("=" * 45)
    print()
    
    is_android = test_android_environment()
    test_network_detection()
    test_qr_support()
    test_websocket_support()
    test_dependencies()
    test_file_permissions()
    
    print("🏁 Test Summary")
    print("=" * 15)
    if is_android:
        print("✅ Running on Android/Termux")
        print("💡 Check individual test results above")
        print("📚 See docs/ANDROID_TROUBLESHOOTING.md for solutions")
    else:
        print("ℹ️ Not running on Android/Termux")
        print("   This test is designed for Android environments")
    
    print()
    print("🚀 If all tests pass, you can run: python run.py")

if __name__ == "__main__":
    main()