#!/usr/bin/env python3
"""
[FAST] LANVAN Fast Boot - Performance Optimized Startup
Reduces startup time by lazy loading and optimizing imports
"""

import os
import sys
import time
from pathlib import Path

def fast_startup():
    """Optimized startup sequence"""
    print("[FAST] LANVAN Fast Boot")
    print("=" * 30)
    
    startup_time = time.time()
    
    # Quick environment check
    if not Path("app").exists():
        print("[ERR] Not in LANVAN directory")
        sys.exit(1)
    
    print("[RETRY] Quick loading...")
    
    # Apply all performance optimizations
    try:
        from app.performance_config import apply_performance_tweaks
        apply_performance_tweaks()
        print("[OK] Performance tweaks applied")
    except ImportError:
        # Fallback to basic optimizations
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"  # Skip .pyc generation
        os.environ["PYTHONUNBUFFERED"] = "1"         # Immediate output
        os.environ["UVICORN_LOG_LEVEL"] = "warning"  # Reduce logging
    
    # Minimal imports first
    import argparse
    
    # Parse args early
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--workers", default=1, type=int)
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    
    # Show startup info immediately
    print(f"[NET] Starting on {args.host}:{args.port}")
    
    # Import heavy modules only when needed
    try:
        print("[RETRY] Loading server...")
        import uvicorn
        from app.main import app
        
        boot_time = time.time() - startup_time
        print(f"[OK] Ready in {boot_time:.1f}s")
        
        # Optimized uvicorn config with performance tweaks
        try:
            from app.performance_config import get_optimized_uvicorn_config
            config = get_optimized_uvicorn_config(args.host, args.port, args.dev)
        except ImportError:
            # Fallback configuration
            config = {
                "host": args.host,
                "port": args.port,
                "log_level": "warning",  # Reduce logging overhead
                "access_log": False,     # Disable access logs
                "reload": args.dev,
                "workers": args.workers,
                "loop": "asyncio",       # Use fastest event loop
            }
        
        # Start server with app string for uvicorn
        print("[START] Server starting...")
        uvicorn.run("app.main:app", **config)
        
    except KeyboardInterrupt:
        print("\n Stopped")
    except ImportError as e:
        print(f"[ERR] Missing dependency: {e}")
        print("[TIP] Run: pip install -r requirements.txt")
    except Exception as e:
        print(f"[ERR] Error: {e}")

if __name__ == "__main__":
    fast_startup()
