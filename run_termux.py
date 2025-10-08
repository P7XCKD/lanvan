#!/usr/bin/env python3
"""
🤖 LANVAN Termux Launcher - Final Version
Complete integration with universal mDNS and all features
"""

import os
import sys
import asyncio
import signal
import subprocess
import time
from pathlib import Path

def setup_termux_environment():
    """Setup Termux environment and acquire wake lock"""
    print("🤖 Setting up Termux environment...")
    
    # Set environment variables
    os.environ['PYTHONUNBUFFERED'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['LANVAN_PLATFORM'] = 'termux'
    
    # Acquire wake lock
    try:
        result = subprocess.run(['termux-wake-lock'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ Wake lock acquired - device won't sleep")
            return True
        else:
            print("⚠️ Wake lock failed - keep Termux in foreground")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️ Wake lock command not found")
        print("💡 Install termux-api: pkg install termux-api")
        return False

def release_wake_lock():
    """Release Termux wake lock"""
    try:
        subprocess.run(['termux-wake-unlock'], timeout=5)
        print("✅ Wake lock released")
    except:
        pass

def patch_imports_for_termux():
    """Patch problematic imports for Termux compatibility"""
    # Add app directory to path
    app_path = os.path.join(os.path.dirname(__file__), 'app')
    if app_path not in sys.path:
        sys.path.insert(0, app_path)
    
    # Patch psutil for Termux
    try:
        import psutil
        
        # Store original functions
        original_cpu_percent = getattr(psutil, 'cpu_percent', None)
        original_virtual_memory = getattr(psutil, 'virtual_memory', None)
        
        def safe_cpu_percent(*args, **kwargs):
            try:
                if original_cpu_percent:
                    return original_cpu_percent(*args, **kwargs)
                return 50.0
            except (PermissionError, OSError, AttributeError):
                return 45.0  # Conservative CPU usage estimate
        
        def safe_virtual_memory(*args, **kwargs):
            try:
                if original_virtual_memory:
                    return original_virtual_memory(*args, **kwargs)
            except (PermissionError, OSError, AttributeError):
                pass
            
            # Create mock memory object
            class MockMemory:
                def __init__(self):
                    self.total = 2 * 1024 * 1024 * 1024  # 2GB
                    self.available = 1024 * 1024 * 1024   # 1GB
                    self.percent = 50.0
                    self.used = self.total - self.available
            
            return MockMemory()
        
        # Apply patches
        psutil.cpu_percent = safe_cpu_percent
        psutil.virtual_memory = safe_virtual_memory
        
        print("✅ psutil patched for Termux compatibility")
        
    except ImportError:
        print("⚠️ psutil not available - some monitoring features disabled")

def get_local_ip():
    """Get local IP address"""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def create_termux_config():
    """Create Termux-specific configuration"""
    config = {
        'host': '0.0.0.0',
        'port': 8000,
        'workers': 1,
        'log_level': 'info',
        'access_log': False,
        'use_colors': True,
        'reload': False,
        'timeout_keep_alive': 5,
        'timeout_notify': 30,
        'limit_concurrency': 50,
        'limit_max_requests': 1000
    }
    
    # Set environment variables for the app
    os.environ['LANVAN_HOST'] = config['host']
    os.environ['LANVAN_PORT'] = str(config['port'])
    os.environ['LANVAN_WORKERS'] = str(config['workers'])
    
    return config

async def start_mdns_service(port: int):
    """Start mDNS service asynchronously"""
    try:
        from app.universal_mdns import get_mdns_manager
        
        print("🌐 Starting universal mDNS service...")
        mdns_manager = get_mdns_manager("lanvan", port)
        
        success = mdns_manager.start_service()
        if success:
            status = mdns_manager.get_status()
            print(f"✅ mDNS service active!")
            print(f"🌍 Domain: {status['domain']}")
            print(f"📡 Backend: {status['backend']}")
            print(f"🔗 URL: {status['url']}")
            
            # Test resolution
            await asyncio.sleep(2)  # Give it time to propagate
            if mdns_manager.test_resolution():
                print("✅ mDNS resolution working!")
            else:
                print("⚠️ mDNS resolution not working - using IP access")
            
            return mdns_manager
        else:
            print("❌ mDNS service failed to start")
            return None
            
    except Exception as e:
        print(f"❌ mDNS service error: {e}")
        return None

def setup_signal_handlers(mdns_manager=None):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        print(f"\n🛑 Shutting down LANVAN server...")
        
        if mdns_manager:
            mdns_manager.stop_service()
        
        release_wake_lock()
        print("👋 Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    return signal_handler

async def main():
    """Main async function"""
    print("🚀 LANVAN Termux Launcher - Final Version")
    print("=" * 50)
    
    # Setup Termux environment
    wake_lock_acquired = setup_termux_environment()
    
    # Patch imports for compatibility
    patch_imports_for_termux()
    
    # Create configuration
    config = create_termux_config()
    
    # Start mDNS service
    mdns_manager = await start_mdns_service(config['port'])
    
    # Setup signal handlers
    setup_signal_handlers(mdns_manager)
    
    # Get local IP for display
    local_ip = get_local_ip()
    
    print(f"\n✅ LANVAN ready on Termux!")
    print(f"📱 Local access: http://localhost:{config['port']}")
    print(f"🌐 Network access: http://{local_ip}:{config['port']}")
    
    if mdns_manager and mdns_manager.is_active:
        status = mdns_manager.get_status()
        print(f"🌍 mDNS access: {status['url']}")
    
    print(f"💡 Share the network URL with other devices on the same WiFi")
    print(f"🔋 Wake lock: {'Active' if wake_lock_acquired else 'Not available'}")
    print(f"🔄 Press Ctrl+C to stop")
    print(f"")
    
    try:
        # Import and start the main app
        import uvicorn
        from app.main import app
        
        # Start server
        uvicorn_config = uvicorn.Config(
            app,
            host=config['host'],
            port=config['port'],
            log_level=config['log_level'],
            access_log=config['access_log'],
            use_colors=config['use_colors'],
            timeout_keep_alive=config['timeout_keep_alive'],
            limit_concurrency=config['limit_concurrency'],
            limit_max_requests=config['limit_max_requests']
        )
        
        server = uvicorn.Server(uvicorn_config)
        await server.serve()
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        if "Address already in use" in str(e):
            print(f"💡 Try a different port: python {sys.argv[0]} --port 8080")
        raise
    finally:
        if mdns_manager:
            mdns_manager.stop_service()
        release_wake_lock()

def run():
    """Synchronous entry point"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Interrupted")
    except Exception as e:
        print(f"❌ Launch failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()