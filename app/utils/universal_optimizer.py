"""
[RETRY] Universal Platform Optimizer with Termux Compatibility
Applies performance optimizations for large file uploads on Windows, Linux, MacOS, and Android.

Key Features:
- Platform-adaptive file transfer chunk sizing (from 512KB to 4MB depending on size/memory)
- Strategic garbage collection sweeps to prevent memory pressure warnings
- Safe OS system calls mapping with error-resilient fallbacks
- Background processing limits keepalive tasks helper
"""

import os
import sys
import time
import gc
import platform
import threading
from typing import Optional, Dict
import subprocess

# Import Termux compatibility layer
try:
    from app.utils.termux_compat import (
        is_termux_environment, 
        is_android_environment,
        should_use_lightweight_mode,
        get_termux_system_info,
        get_safe_cpu_usage,
        get_safe_memory_info,
        get_termux_chunk_size,
        safe_psutil_call
    )
    from app.utils.termux_memory_monitor import (
        start_termux_memory_monitoring,
        get_memory_adaptive_chunk_size,
        enforce_termux_memory_limit,
        get_termux_memory_status
    )
except ImportError:
    from termux_compat import (
        is_termux_environment, 
        is_android_environment,
        should_use_lightweight_mode,
        get_termux_system_info,
        get_safe_cpu_usage,
        get_safe_memory_info,
        get_termux_chunk_size,
        safe_psutil_call
    )
    from termux_memory_monitor import (
        start_termux_memory_monitoring,
        get_memory_adaptive_chunk_size,
        enforce_termux_memory_limit,
        get_termux_memory_status
    )

class UniversalOptimizer:
    """Universal platform optimizer for large file operations"""
    
    def __init__(self):
        self.platform_type = self._detect_platform()
        self.is_android = self.platform_type == 'android'
        self.is_termux = self._detect_termux()
        self.is_windows = self.platform_type == 'windows'
        self.is_linux = self.platform_type == 'linux'
        self.is_mac = self.platform_type == 'mac'
        
        self.keep_alive_active = False
        self.background_keeper = None
        self.upload_active = False  # Track upload state for legacy compatibility
        
        # Start Termux memory monitoring if applicable
        if self.is_termux or self.is_android:
            try:
                start_termux_memory_monitoring()
                print("[BOT] Termux memory monitoring initialized")
            except Exception as e:
                print(f"[WARN] Memory monitoring init warning: {e}")
        
        print(f"[INFO] Platform detected: {self.platform_type.title()}")
        if self.is_termux:
            print(f"[BOT] Termux environment detected")
            
    def get_adaptive_chunk_size(self, file_size: int) -> int:
        """Get adaptive chunk size with Termux memory monitoring"""
        if self.is_termux or self.is_android:
            # Use memory-adaptive chunk size for Termux/Android - ALWAYS use Termux-optimized sizes
            try:
                return get_memory_adaptive_chunk_size(file_size)
            except Exception:
                # Fallback to standard Termux chunk size
                return get_termux_chunk_size(file_size)
        else:
            # Use standard chunk sizing for other platforms
            if file_size < 10 * 1024 * 1024:  # < 10MB
                return 512 * 1024  # 512KB for smaller files
            elif file_size < 100 * 1024 * 1024:  # < 100MB
                return 2 * 1024 * 1024  # 2MB for medium files
            else:  # Large files
                return 8 * 1024 * 1024  # 8MB for large files (optimized for high-speed local networks)
    
    def _detect_platform(self) -> str:
        """Detect the current platform"""
        if is_android_environment():
            return 'android'
        
        system = platform.system().lower()
        if system == 'windows':
            return 'windows'
        elif system == 'darwin':
            return 'mac'
        elif system == 'linux':
            return 'linux'
        else:
            return 'unknown'
    
    def _detect_termux(self) -> bool:
        """Check if running in Termux environment"""
        return is_termux_environment()
    
    def optimize_for_large_files(self, operation_type: str = "upload") -> Dict:
        """
        OPTIMIZED: Apply strategic memory management for large file operations
        Reduced gc.collect() frequency for better performance
        """
        optimizations = {
            'memory_optimization': False,
            'gc_optimization': False,
            'platform_optimization': False,
            'performance_mode': 'standard'
        }
        
        try:
            # OPTIMIZED: Only run GC optimization for major operations
            if operation_type in ['upload_complete', 'large_file_finished']:
                print(f"[CLEAN] Strategic memory cleanup for {operation_type}")
                gc.collect()
                optimizations['gc_optimization'] = True
            
            # Platform-specific optimizations
            if self.is_termux:
                optimizations.update(self._optimize_termux())
            elif self.is_android:
                optimizations.update(self._optimize_android())
            elif self.is_windows:
                optimizations.update(self._optimize_windows())
            else:
                optimizations.update(self._optimize_unix())
            
            optimizations['platform_optimization'] = True
            return optimizations
            
        except Exception as e:
            print(f"[WARN] Optimization warning: {e}")
            return optimizations
    
    def _optimize_termux(self) -> Dict:
        """Termux-specific optimizations with memory monitoring"""
        print("[BOT] Applying Termux optimizations")
        
        try:
            # Set environment variables for better Termux performance
            os.environ['PYTHONUNBUFFERED'] = '1'
            os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
            
            # Check memory status before optimization
            if not enforce_termux_memory_limit("termux_optimization"):
                return {'performance_mode': 'termux_emergency'}
            
            # Use Termux-compatible settings with memory monitoring
            return {
                'chunk_size': get_termux_chunk_size(1024 * 1024),  # Default 1MB for optimization
                'memory_limit': get_safe_memory_info().get('available_mb', 512),
                'performance_mode': 'termux_optimized',
                'memory_status': get_termux_memory_status()
            }
        except Exception as e:
            print(f"[WARN] Termux optimization warning: {e}")
            return {'performance_mode': 'termux_fallback'}
    
    def _optimize_android(self) -> Dict:
        """Android-specific optimizations"""
        return {
            'performance_mode': 'android_optimized',
            'memory_conservative': True
        }
    
    def _optimize_windows(self) -> Dict:
        """Windows-specific optimizations"""
        return {
            'performance_mode': 'windows_optimized',
            'high_performance': True
        }
    
    def _optimize_unix(self) -> Dict:
        """Unix/Linux/Mac optimizations"""
        return {
            'performance_mode': 'unix_optimized',
            'standard_performance': True
        }
    
    def should_run_gc(self, operation_count: int = 0, memory_threshold: float = 85.0) -> bool:
        """
        OPTIMIZED: Determine if garbage collection should run
        Much less frequent GC calls to improve performance
        """
        # Only run GC every 50 operations instead of frequent calls
        if operation_count > 0 and operation_count % 50 != 0:
            return False
        
        try:
            # Check memory usage
            memory_info = get_safe_memory_info()
            if memory_info and 'usage_percent' in memory_info:
                return memory_info['usage_percent'] > memory_threshold
            
            # Fallback: run GC less frequently
            return operation_count % 100 == 0  # Only every 100 operations
            
        except Exception:
            return False  # Don't run GC if we can't determine memory usage
    
    def start_background_keepalive(self):
        """Start background keepalive for Termux stability with memory monitoring"""
        if self.keep_alive_active or not (self.is_termux or self.is_android):
            return
            
        def keepalive_worker():
            """Enhanced background keepalive worker with memory awareness"""
            keepalive_count = 0
            try:
                keepalive_file = "/tmp/lanvan_keepalive"
                while self.keep_alive_active:
                    # Check memory status before doing any work
                    if not enforce_termux_memory_limit("background_keepalive"):
                        print("[BOT] Background keepalive paused due to memory pressure")
                        time.sleep(60)  # Wait longer during memory pressure
                        continue
                    
                    # Create keepalive marker
                    with open(keepalive_file, 'w') as f:
                        f.write(f"{time.time()}:{keepalive_count}")
                    
                    keepalive_count += 1
                    
                    # Gentle memory cleanup every 10 cycles
                    if keepalive_count % 10 == 0:
                        memory_status = get_termux_memory_status()
                        if memory_status.get('status') in ['warning', 'critical', 'emergency']:
                            gc.collect()
                    
                    # Conservative sleep time
                    time.sleep(60)  # 1 minute between cycles
                    
            except Exception as e:
                print(f"[WARN] Keepalive warning: {e}")
        
        self.keep_alive_active = True
        self.background_keeper = threading.Thread(target=keepalive_worker, daemon=True)
        self.background_keeper.start()
        print("[BOT] Background keepalive started with memory monitoring")
    
    def stop_background_keepalive(self):
        """Stop background keepalive"""
        if self.keep_alive_active:
            self.keep_alive_active = False
            print("[INFO] Background keepalive stopped")
    
    def memory_cleanup(self, force: bool = False):
        """Perform memory cleanup with garbage collection"""
        if force or self.should_run_gc():
            import gc
            gc.collect()
            if self.is_termux:
                # Extra cleanup for Termux/Android
                gc.collect()
    
    def get_performance_summary(self) -> Dict:
        """Get performance optimization summary"""
        return {
            'platform': self.platform_type,
            'termux_mode': self.is_termux,
            'android_mode': self.is_android,
            'optimizations_active': True,
            'memory_management': 'strategic_gc',  # OPTIMIZED: Strategic instead of frequent
            'performance_profile': 'optimized'
        }
        
    def get_system_info(self) -> Dict:
        """Get system info for client optimization"""
        from app.utils.termux_compat import get_safe_memory_info, get_safe_cpu_usage
        mem = get_safe_memory_info()
        cpu = get_safe_cpu_usage()
        
        # Calculate available memory in MB
        available_mb = mem.get('available_mb', 0.0)
        if available_mb == 0.0 and 'available_bytes' in mem:
            available_mb = mem['available_bytes'] / (1024 * 1024)
            
        # Determine if low memory (e.g. less than 1GB available)
        is_low = mem.get('is_low_memory', available_mb < 1024.0)
        
        return {
            "platform": self.platform_type,
            "available_memory_mb": round(available_mb, 2),
            "is_low_memory": is_low,
            "cpu_usage": cpu
        }

# Legacy Android optimizer functions (merged from android_optimizer.py)
def optimize_for_upload(file_size: int) -> Dict:
    """Optimize settings for file upload (legacy function)"""
    return universal_optimizer.optimize_for_large_files("upload")

def get_adaptive_chunk_size(file_size: int, available_memory: Optional[int] = None) -> int:
    """Get adaptive chunk size based on file size and available memory (legacy function)"""
    try:
        if available_memory is None:
            memory_info = get_safe_memory_info()
            available_memory = int(memory_info.get('available_bytes', 1024 * 1024 * 1024))  # 1GB fallback
        
        # Ensure chunk size doesn't exceed 10% of available memory
        max_chunk = available_memory // 10
        
        # Conservative chunk sizing for Android/Termux
        if universal_optimizer.is_android or universal_optimizer.is_termux:
            if available_memory < 1024 * 1024 * 1024:  # Less than 1GB RAM
                optimal_chunk = min(1024 * 1024, file_size // 10)  # 1MB max
            else:
                optimal_chunk = min(8 * 1024 * 1024, file_size // 5)  # 8MB max
        else:
            # Desktop sizing
            if file_size < 10 * 1024 * 1024:  # < 10MB
                optimal_chunk = 1024 * 1024  # 1MB
            elif file_size < 100 * 1024 * 1024:  # < 100MB
                optimal_chunk = 8 * 1024 * 1024  # 8MB
            else:
                optimal_chunk = 32 * 1024 * 1024  # 32MB
        
        return min(optimal_chunk, max_chunk)
    except Exception:
        return 1024 * 1024  # 1MB fallback

def should_run_gc() -> bool:
    """Determine if garbage collection should be run (legacy function)"""
    return universal_optimizer.should_run_gc()

def get_available_memory_mb() -> float:
    """Get available memory in MB (legacy function)"""
    memory_info = get_safe_memory_info()
    return memory_info.get('available_mb', 0.0)

def get_cpu_usage() -> float:
    """Get CPU usage percentage (legacy function)"""
    return get_safe_cpu_usage()

# Global optimizer instance
universal_optimizer = UniversalOptimizer()
