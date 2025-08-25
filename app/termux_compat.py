#!/usr/bin/env python3
"""
🚀 Termux Compatibility Layer for LANVan
Ensures all adaptive systems work seamlessly on Android/Termux while preserving full functionality on other platforms.
"""

import os
import sys
import time
import gc
from typing import Any, Dict, Optional, Callable, Union


def is_termux_environment() -> bool:
    """
    🔍 Reliable Termux environment detection
    """
    # Check for Termux-specific environment variables and paths
    is_termux = any([
        "TERMUX_VERSION" in os.environ,
        "ANDROID_STORAGE" in os.environ,
        os.path.exists("/data/data/com.termux"),
        os.path.exists("/system/bin/termux-setup-storage"),
        "com.termux" in os.environ.get("PREFIX", ""),
        "/data/data/com.termux" in sys.executable
    ])
    
    # Only log once per session
    if is_termux and not hasattr(is_termux_environment, '_logged'):
        print("🤖 Termux environment detected - using safe compatibility mode")
        is_termux_environment._logged = True
    
    return is_termux


def is_android_environment() -> bool:
    """
    🤖 Detect Android environment (broader than just Termux)
    """
    return any([
        is_termux_environment(),
        "ANDROID_STORAGE" in os.environ,
        "ANDROID_ROOT" in os.environ,
        os.path.exists("/system/build.prop"),
        os.path.exists("/android_asset"),
        "android" in sys.platform.lower()
    ])


def safe_psutil_call(
    func: Callable,
    default_value: Any = None,
    termux_fallback: Any = None,
    error_types: tuple = (PermissionError, OSError, FileNotFoundError)
) -> Any:
    """
    🛡️ Safe wrapper for psutil calls with Termux-specific fallbacks
    
    Args:
        func: The psutil function to call
        default_value: Default value if function fails
        termux_fallback: Specific fallback value for Termux
        error_types: Exception types to catch
    
    Returns:
        Function result or appropriate fallback value
    """
    # Use Termux-specific fallback if available and we're in Termux
    if is_termux_environment() and termux_fallback is not None:
        # Silent fallback - only log once per session if needed
        return termux_fallback
    
    try:
        result = func()
        return result
    except error_types as e:
        error_msg = str(e)
        if any(phrase in error_msg.lower() for phrase in [
            "permission denied", 
            "/proc/stat", 
            "/proc/meminfo", 
            "access denied",
            "errno 13"
        ]):
            # Silent fallback for permission errors in Termux
            return termux_fallback if termux_fallback is not None else default_value
        # Re-raise if it's not a known permission/access issue
        raise
    except ImportError:
        # Silent fallback for missing psutil
        return termux_fallback if termux_fallback is not None else default_value


def get_termux_system_info() -> Dict[str, Any]:
    """
    📱 Get system information using Termux-safe methods
    """
    info = {
        'platform': 'android-termux',
        'available_memory_mb': 1024,  # Conservative fallback
        'cpu_usage': 50.0,  # Neutral fallback
        'memory_usage': 60.0,  # Conservative fallback
        'cpu_count': 4,  # Reasonable fallback
        'termux_optimized': True
    }
    
    try:
        # Try to get CPU count from os (should work on Termux)
        info['cpu_count'] = os.cpu_count() or 4
    except:
        pass
    
    try:
        # Try alternative memory detection methods for Android
        # Method 1: Check /proc/version for Android kernel info
        if os.path.exists('/proc/version'):
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                if 'android' in version_info:
                    # Android detected, use conservative memory estimate
                    info['available_memory_mb'] = 1536  # Slightly higher for confirmed Android
    except:
        pass
    
    try:
        # Method 2: Check termux-info if available
        import subprocess
        result = subprocess.run(['termux-info'], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            # Parse termux-info output for better estimates
            info_output = result.stdout.lower()
            if 'android' in info_output:
                info['available_memory_mb'] = 2048  # Higher estimate with termux-info
    except:
        pass
    
    return info


def get_safe_cpu_usage() -> float:
    """
    🏃 Get CPU usage with Termux-safe fallback
    """
    def cpu_func():
        import psutil
        return psutil.cpu_percent(interval=0.1)
    
    return safe_psutil_call(
        cpu_func, 
        default_value=50.0,  # Neutral CPU usage
        termux_fallback=40.0  # Assume lighter load on mobile
    )


def get_safe_memory_info() -> Dict[str, Any]:
    """
    🧠 Get memory information with Termux-safe fallbacks
    """
    def memory_func():
        import psutil
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'available': mem.available,
            'percent': mem.percent
        }
    
    # Termux fallback values (conservative mobile estimates)
    termux_fallback = {
        'total': 2 * 1024 * 1024 * 1024,  # 2GB
        'available': 1 * 1024 * 1024 * 1024,  # 1GB available
        'percent': 50.0  # 50% usage
    }
    
    return safe_psutil_call(
        memory_func,
        default_value=termux_fallback,
        termux_fallback=termux_fallback
    )


def optimize_for_termux():
    """
    📱 Apply Termux-specific optimizations
    """
    if not is_termux_environment():
        return False
    
    try:
        print("🤖 Applying Termux optimizations...")
        
        # Set environment variables for better performance
        os.environ['PYTHONUNBUFFERED'] = '1'
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        
        # Create keepalive file for Termux stability
        keepalive_file = "/tmp/lanvan_keepalive"
        try:
            with open(keepalive_file, 'w') as f:
                f.write(str(time.time()))
            print(f"✅ Termux keepalive created: {keepalive_file}")
        except:
            pass  # Non-critical
        
        # Gentle memory cleanup
        gc.collect()
        
        return True
        
    except Exception as e:
        print(f"⚠️ Termux optimization warning: {e}")
        return False


def get_termux_chunk_size(file_size: int) -> int:
    """
    📦 Get Termux-optimized chunk size
    """
    # Conservative chunk sizes for mobile environment
    if file_size < 10 * 1024 * 1024:  # < 10MB
        return 256 * 1024  # 256KB
    elif file_size < 100 * 1024 * 1024:  # < 100MB
        return 512 * 1024  # 512KB
    elif file_size < 500 * 1024 * 1024:  # < 500MB
        return 1 * 1024 * 1024  # 1MB
    else:  # Large files
        return 2 * 1024 * 1024  # 2MB max for stability


def should_use_lightweight_mode() -> bool:
    """
    🪶 Determine if we should use lightweight mode
    """
    return is_termux_environment() or is_android_environment()


# Initialize Termux optimizations if we're in Termux
if is_termux_environment():
    print("🤖 Termux environment detected - initializing compatibility layer")
    optimize_for_termux()
