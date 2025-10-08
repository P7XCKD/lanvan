#!/usr/bin/env python3
"""
🌍 LANVAN Universal Launcher
Final comprehensive solution for Windows + Termux with full mDNS support
Automatically detects platform and uses optimized settings for each environment
"""

import os
import sys
import platform
import subprocess
import signal
import socket
import time
from pathlib import Path

class UniversalLauncher:
    def __init__(self):
        self.platform_info = self._detect_platform()
        self.is_termux = self._is_termux()
        self.is_windows = platform.system() == "Windows"
        self.is_android = self._is_android()
        
        print(f"🌍 LANVAN Universal Launcher")
        print(f"📱 Platform: {self.platform_info['system']}")
        print(f"🤖 Termux: {'Yes' if self.is_termux else 'No'}")
        print(f"🪟 Windows: {'Yes' if self.is_windows else 'No'}")
        print(f"📋 Architecture: {self.platform_info['machine']}")
        
    def _detect_platform(self):
        """Comprehensive platform detection"""
        return {
            'system': platform.system(),
            'machine': platform.machine(),
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'home': str(Path.home())
        }
    
    def _is_termux(self):
        """Reliable Termux detection"""
        return any([
            "TERMUX_VERSION" in os.environ,
            "ANDROID_STORAGE" in os.environ,
            os.path.exists("/data/data/com.termux"),
            "com.termux" in os.environ.get("PREFIX", ""),
            "/data/data/com.termux" in sys.executable,
            os.path.exists("/system/bin/termux-setup-storage")
        ])
    
    def _is_android(self):
        """Broader Android detection"""
        return any([
            self.is_termux,
            "ANDROID_ROOT" in os.environ,
            os.path.exists("/system/build.prop"),
            "android" in platform.platform().lower()
        ])
    
    def setup_termux_environment(self):
        """Setup Termux-specific optimizations"""
        if not self.is_termux:
            return
        
        print("🤖 Setting up Termux environment...")
        
        # Set environment variables for better performance
        os.environ['PYTHONUNBUFFERED'] = '1'
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        
        # Acquire wake lock
        try:
            result = subprocess.run(['termux-wake-lock'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ Wake lock acquired - preventing sleep")
            else:
                print("⚠️ Wake lock not available - keep app in foreground")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("⚠️ Wake lock command not found - install termux-api if needed")
        
        # Create keepalive file
        try:
            keepalive_file = "/tmp/lanvan_keepalive"
            with open(keepalive_file, 'w') as f:
                f.write(f"LANVAN_KEEPALIVE_{int(time.time())}")
            print(f"✅ Keepalive created: {keepalive_file}")
        except Exception as e:
            print(f"⚠️ Keepalive creation failed: {e}")
    
    def ensure_dependencies(self):
        """Ensure required dependencies are installed"""
        print("📦 Checking dependencies...")
        
        # Platform-specific requirements
        if self.is_termux:
            requirements_file = "requirements-android.txt"
            if not os.path.exists(requirements_file):
                print("📋 Creating Android requirements...")
                self._create_android_requirements()
        else:
            requirements_file = "requirements.txt"
        
        # Check if key packages are available
        missing_packages = []
        try:
            import fastapi
            import uvicorn
        except ImportError:
            missing_packages.extend(['fastapi', 'uvicorn[standard]'])
        
        try:
            import qrcode
        except ImportError:
            missing_packages.append('qrcode[pil]')
        
        if missing_packages:
            print(f"📥 Installing missing packages: {missing_packages}")
            try:
                subprocess.run([
                    sys.executable, "-m", "pip", "install"
                ] + missing_packages, check=True)
                print("✅ Dependencies installed successfully")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install dependencies: {e}")
                print("💡 Try running: pip install -r requirements-android.txt" if self.is_termux else "pip install -r requirements.txt")
        else:
            print("✅ All dependencies available")
    
    def _create_android_requirements(self):
        """Create Android-optimized requirements file"""
        android_requirements = """# Android/Termux Optimized Requirements
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
jinja2>=3.1.2
python-multipart>=0.0.6
qrcode[pil]>=7.4.2
pillow>=10.0.0
aiofiles>=23.2.0
zeroconf>=0.132.2
psutil>=5.9.6
cryptography>=41.0.7
websockets>=11.0.2
wsproto>=1.2.0
"""
        with open("requirements-android.txt", 'w') as f:
            f.write(android_requirements)
        print("✅ Android requirements file created")
    
    def get_platform_config(self):
        """Get platform-specific configuration"""
        if self.is_termux:
            return {
                'default_port': 8000,  # Non-privileged port
                'fallback_port': 8080,
                'host': '0.0.0.0',
                'use_https': False,  # HTTPS can be problematic on Android
                'enable_mdns': True,  # We'll make this work!
                'chunk_size_limit': 2 * 1024 * 1024,  # 2MB max
                'max_concurrent_uploads': 3,
                'memory_limit_mb': 1024,
                'venv_path': None,  # No venv in Termux typically
                'python_executable': sys.executable
            }
        else:  # Windows or other desktop platforms
            return {
                'default_port': 80,
                'fallback_port': 5000,
                'host': '0.0.0.0',
                'use_https': True,
                'enable_mdns': True,
                'chunk_size_limit': 32 * 1024 * 1024,  # 32MB max
                'max_concurrent_uploads': 8,
                'memory_limit_mb': 4096,
                'venv_path': self._get_windows_venv_path(),
                'python_executable': sys.executable
            }
    
    def _get_windows_venv_path(self):
        """Get Windows virtual environment path"""
        venv_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".venv", "Scripts", "python.exe"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe"),
            os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe")
        ]
        
        for venv_path in venv_paths:
            if os.path.exists(venv_path):
                return venv_path
        return None
    
    def setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        def signal_handler(signum, frame):
            print(f"\n🛑 Shutting down LANVAN server...")
            
            if self.is_termux:
                try:
                    subprocess.run(['termux-wake-unlock'], timeout=5)
                    print("✅ Wake lock released")
                except:
                    pass
            
            print("👋 Goodbye!")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def launch_server(self):
        """Launch the appropriate server based on platform"""
        config = self.get_platform_config()
        
        print(f"\n🚀 Launching LANVAN server...")
        print(f"⚙️ Configuration:")
        print(f"   📡 Port: {config['default_port']} (fallback: {config['fallback_port']})")
        print(f"   🌐 Host: {config['host']}")
        print(f"   🔒 HTTPS: {'Yes' if config['use_https'] else 'No'}")
        print(f"   📡 mDNS: {'Yes' if config['enable_mdns'] else 'No'}")
        
        if self.is_termux:
            self._launch_termux_server(config)
        else:
            self._launch_windows_server(config)
    
    def _launch_termux_server(self, config):
        """Launch server optimized for Termux"""
        print("🤖 Starting Termux-optimized server...")
        
        # Import and patch for Termux compatibility
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
        
        try:
            # Apply Termux compatibility patches
            self._apply_termux_patches()
            
            # Start the server with Termux settings
            os.environ['LANVAN_PLATFORM'] = 'termux'
            os.environ['LANVAN_PORT'] = str(config['default_port'])
            os.environ['LANVAN_HOST'] = config['host']
            os.environ['LANVAN_ENABLE_MDNS'] = str(config['enable_mdns'])
            
            # Launch main app
            import uvicorn
            from app.main import app
            
            # Get local IP for display
            local_ip = self._get_local_ip()
            print(f"\n✅ LANVAN ready on Termux!")
            print(f"📱 Local access: http://localhost:{config['default_port']}")
            print(f"🌐 Network access: http://{local_ip}:{config['default_port']}")
            print(f"💡 Share the network URL with other devices")
            print(f"🔄 Press Ctrl+C to stop\n")
            
            uvicorn.run(
                app,
                host=config['host'],
                port=config['default_port'],
                log_level="info",
                access_log=False
            )
            
        except Exception as e:
            print(f"❌ Termux server failed: {e}")
            print("🔄 Trying fallback port...")
            try:
                uvicorn.run(
                    app,
                    host=config['host'],
                    port=config['fallback_port'],
                    log_level="info"
                )
            except Exception as fallback_error:
                print(f"❌ Fallback also failed: {fallback_error}")
                sys.exit(1)
    
    def _launch_windows_server(self, config):
        """Launch server using existing Windows run.py"""
        print("🪟 Using existing Windows launcher...")
        
        # Check if we should use venv
        if config['venv_path'] and os.path.exists(config['venv_path']):
            python_exec = config['venv_path']
            print(f"🐍 Using virtual environment: {python_exec}")
        else:
            python_exec = sys.executable
            print(f"🐍 Using system Python: {python_exec}")
        
        # Launch the existing run.py
        run_py_path = os.path.join(os.path.dirname(__file__), "run.py")
        if os.path.exists(run_py_path):
            try:
                subprocess.run([python_exec, run_py_path], check=True)
            except KeyboardInterrupt:
                print("\n🛑 Server stopped by user")
            except subprocess.CalledProcessError as e:
                print(f"❌ Windows server failed: {e}")
                sys.exit(1)
        else:
            print("❌ run.py not found - falling back to direct launch")
            self._direct_launch(config)
    
    def _direct_launch(self, config):
        """Direct launch when run.py is not available"""
        try:
            import uvicorn
            from app.main import app
            
            uvicorn.run(
                app,
                host=config['host'],
                port=config['default_port'],
                log_level="info"
            )
        except Exception as e:
            print(f"❌ Direct launch failed: {e}")
            sys.exit(1)
    
    def _apply_termux_patches(self):
        """Apply Termux-specific compatibility patches"""
        print("🔧 Applying Termux compatibility patches...")
        
        # Patch psutil for Termux
        try:
            import psutil
            
            # Store original functions
            original_cpu_percent = psutil.cpu_percent
            original_virtual_memory = psutil.virtual_memory
            
            # Create Termux-safe wrappers
            def safe_cpu_percent(*args, **kwargs):
                try:
                    return original_cpu_percent(*args, **kwargs)
                except (PermissionError, OSError):
                    return 50.0  # Safe fallback
            
            def safe_virtual_memory(*args, **kwargs):
                try:
                    return original_virtual_memory(*args, **kwargs)
                except (PermissionError, OSError):
                    # Create mock memory info
                    class MockMemory:
                        def __init__(self):
                            self.total = 2 * 1024 * 1024 * 1024  # 2GB
                            self.available = 1 * 1024 * 1024 * 1024  # 1GB
                            self.percent = 50.0
                    return MockMemory()
            
            # Apply patches
            psutil.cpu_percent = safe_cpu_percent
            psutil.virtual_memory = safe_virtual_memory
            
            print("✅ psutil patched for Termux")
            
        except ImportError:
            print("⚠️ psutil not available - some features may be limited")
    
    def _get_local_ip(self):
        """Get local IP address"""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

def main():
    """Main entry point"""
    print("🌍 LANVAN Universal Launcher - Final Version")
    print("=" * 50)
    
    launcher = UniversalLauncher()
    
    # Setup environment based on platform
    if launcher.is_termux:
        launcher.setup_termux_environment()
    
    # Ensure dependencies
    launcher.ensure_dependencies()
    
    # Setup signal handlers
    launcher.setup_signal_handlers()
    
    # Launch server
    try:
        launcher.launch_server()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Launch failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()