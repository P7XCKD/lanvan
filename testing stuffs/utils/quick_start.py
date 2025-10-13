#!/usr/bin/env python3
"""
🚀 Quick Start Script for LANVAN
Optimized startup with performance monitoring
"""

import time
import sys
import os
from pathlib import Path

def print_status(message, start_time=None):
    """Print status with timing information"""
    if start_time:
        elapsed = time.time() - start_time
        print(f"✅ {message} ({elapsed:.2f}s)")
    else:
        print(f"🔄 {message}")

def main():
    print("🚀 LANVAN Quick Start - Optimized Loading")
    print("=" * 50)
    
    overall_start = time.time()
    
    # Check if we're in the right directory
    if not Path("app/main.py").exists():
        print("❌ Error: Not in LANVAN directory")
        sys.exit(1)
    
    # Step 1: Basic imports (fast)
    step_start = time.time()
    print_status("Loading basic modules...")
    import argparse
    import asyncio
    print_status("Basic modules loaded", step_start)
    
    # Step 2: Core LANVAN imports (potentially slow)
    step_start = time.time()
    print_status("Loading LANVAN core...")
    try:
        from app.main import app
        print_status("LANVAN core loaded", step_start)
    except Exception as e:
        print(f"❌ Failed to load LANVAN core: {e}")
        sys.exit(1)
    
    # Step 3: Server framework (potentially slow)
    step_start = time.time()
    print_status("Loading server framework...")
    try:
        import uvicorn
        print_status("Server framework loaded", step_start)
    except Exception as e:
        print(f"❌ Failed to load server: {e}")
        sys.exit(1)
    
    print_status("All modules loaded successfully", overall_start)
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="LANVAN Quick Start")
    parser.add_argument("--port", default=8080, type=int, help="Port to run on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--dev", action="store_true", help="Development mode")
    args = parser.parse_args()
    
    print(f"🌐 Starting server on {args.host}:{args.port}")
    
    # Configure uvicorn for optimal performance
    config = {
        "host": args.host,
        "port": args.port,
        "log_level": "info",
        "access_log": False,  # Disable access logs for performance
        "reload": args.dev,
        "workers": 1 if args.dev else min(4, os.cpu_count() or 1),
    }
    
    try:
        uvicorn.run("app.main:app", **config)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
