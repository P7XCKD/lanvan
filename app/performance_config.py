"""
🏃‍♂️ LANVAN Performance Optimizations
Configuration to reduce startup time and improve responsiveness
"""

import os
import sys

def apply_performance_tweaks():
    """Apply performance optimizations for faster startup"""
    
    # Environment optimizations
    performance_env = {
        # Python optimizations
        "PYTHONDONTWRITEBYTECODE": "1",    # Skip .pyc file generation
        "PYTHONUNBUFFERED": "1",           # Immediate output
        "PYTHONHASHSEED": "0",             # Consistent hashing for caching
        
        # FastAPI optimizations
        "UVICORN_LOG_LEVEL": "warning",    # Reduce logging overhead
        "FASTAPI_ENV": "production",       # Production mode
        
        # System optimizations
        "MALLOC_ARENA_MAX": "2",           # Reduce memory fragmentation
        "PYTHONMALLOC": "malloc",          # Use system malloc
    }
    
    for key, value in performance_env.items():
        os.environ[key] = value
    
    # Import optimizations
    if hasattr(sys, 'set_int_max_str_digits'):
        sys.set_int_max_str_digits(4300)  # Prevent int conversion slowdown

def get_optimized_uvicorn_config(host="127.0.0.1", port=8080, dev=False):
    """Get optimized uvicorn configuration"""
    return {
        "host": host,
        "port": port,
        "log_level": "warning" if not dev else "info",
        "access_log": False,               # Disable access logging
        "reload": dev,                     # Only reload in dev mode
        "workers": 1,                      # Single worker for simplicity
        "loop": "asyncio",                 # Use asyncio event loop
        "http": "httptools",               # Use faster HTTP parser
        "ws": "websockets",                # Use websockets for WebSocket
        "lifespan": "on",                  # Enable lifespan events
        "timeout_keep_alive": 5,           # Shorter keep-alive timeout
        "limit_concurrency": 1000,        # Limit concurrent connections
        "limit_max_requests": 10000,       # Limit max requests per worker
    }

def get_performance_tips():
    """Get performance improvement tips"""
    return [
        "💡 Use fast_boot.py for quicker startup",
        "💡 Close unnecessary applications to free RAM", 
        "💡 Use --dev flag only during development",
        "💡 Use localhost (127.0.0.1) for faster local access",
        "💡 Disable antivirus real-time scanning for project folder",
        "💡 Use SSD storage for better file I/O performance",
    ]

if __name__ == "__main__":
    print("🏃‍♂️ LANVAN Performance Tips:")
    for tip in get_performance_tips():
        print(tip)
