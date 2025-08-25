#!/usr/bin/env python3
"""
🚀 Termux Compatibility Layer for LANVan
Ensures all adaptive systems work seamlessly on Android/Termux while preserving full functionality on other platforms.

OPTIMIZED: Now uses cached platform detection for improved performance.
"""

import os
import sys
import time
from typing import Any, Dict, Optional, Callable, Union

# OPTIMIZED: Use cached platform detection
from .platform_detector import platform_detector


def is_termux_environment() -> bool:
    """
    🔍 OPTIMIZED: Cached Termux environment detection
    """
    return platform_detector.is_termux_environment()


def is_android_environment() -> bool:
    """
    🤖 OPTIMIZED: Cached Android environment detection
    """
    return platform_detector.is_android_environment()


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
    # OPTIMIZED: Use cached platform detection
    if platform_detector.is_termux_environment() and termux_fallback is not None:
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
    📱 OPTIMIZED: Get system information using cached platform detection
    """
    # Use cached platform information
    platform_info = platform_detector.get_platform_info()
    
    return {
        'platform': platform_info.platform_type.value,
        'available_memory_mb': 2048 if platform_info.is_termux else 4096,
        'cpu_usage': 50.0,  # Neutral fallback
        'memory_usage': 60.0,  # Conservative fallback
        'cpu_count': platform_info.cpu_count,
        'termux_optimized': platform_info.is_termux,
        'recommended_chunk_size': platform_info.recommended_chunk_size,
        'recommended_workers': platform_info.recommended_workers
    }


def get_safe_cpu_usage() -> float:
    """
    🏃 OPTIMIZED: Get CPU usage with cached platform detection
    """
    def cpu_func():
        import psutil
        return psutil.cpu_percent(interval=0.1)
    
    # Use cached platform information for fallback values
    platform_info = platform_detector.get_platform_info()
    termux_fallback = 40.0 if platform_info.is_termux else 30.0
    
    return safe_psutil_call(
        cpu_func, 
        default_value=50.0,  # Neutral CPU usage
        termux_fallback=termux_fallback
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
        
        # OPTIMIZED: Natural cleanup instead of forced GC
        
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
    🪶 OPTIMIZED: Determine if we should use lightweight mode using cached detection
    """
    return platform_detector.is_termux_environment() or platform_detector.is_android_environment()


# OPTIMIZED: Initialize platform detection (cached, runs once)
platform_info = platform_detector.get_platform_info()
if platform_info.is_termux:
    print("🤖 Termux environment detected - initializing compatibility layer")
    optimize_for_termux()
