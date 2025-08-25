"""
🔄 Universal Platform Optimizer with Termux Compatibility
Performance optimizations for large file uploads on ALL platforms (Windows, Linux, Mac, Android)
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
from .termux_compat import (
    is_termux_environment, 
    is_android_environment,
    should_use_lightweight_mode,
    get_termux_system_info,
    get_safe_cpu_usage,
    get_safe_memory_info,
    get_termux_chunk_size,
    safe_psutil_call
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
        
        print(f"🔄 Platform detected: {self.platform_type.title()}")
        if self.is_termux:
            print(f"🤖 Termux environment detected")
    
    def _detect_platform(self) -> str:
        """Detect the current platform"""
        if ("ANDROID_STORAGE" in os.environ or 
            os.path.exists("/data/data/com.termux") or 
            "TERMUX_VERSION" in os.environ):
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
                print(f"🧹 Strategic memory cleanup for {operation_type}")
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
            print(f"⚠️ Optimization warning: {e}")
            return optimizations
    
    def _optimize_termux(self) -> Dict:
        """Termux-specific optimizations"""
        print("🤖 Applying Termux optimizations")
        
        try:
            # Set environment variables for better Termux performance
            os.environ['PYTHONUNBUFFERED'] = '1'
            os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
            
            # Use Termux-compatible settings
            return {
                'chunk_size': get_termux_chunk_size(),
                'memory_limit': get_safe_memory_info().get('available_mb', 512),
                'performance_mode': 'termux_optimized'
            }
        except Exception as e:
            print(f"⚠️ Termux optimization warning: {e}")
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
        """Start background keepalive for Termux stability"""
        if self.keep_alive_active or not self.is_termux:
            return
            
        def keepalive_worker():
            """Background keepalive worker"""
            try:
                keepalive_file = "/tmp/lanvan_keepalive"
                while self.keep_alive_active:
                    with open(keepalive_file, 'w') as f:
                        f.write(str(time.time()))
                    time.sleep(30)  # Update every 30 seconds
            except Exception as e:
                print(f"⚠️ Keepalive warning: {e}")
        
        self.keep_alive_active = True
        self.background_keeper = threading.Thread(target=keepalive_worker, daemon=True)
        self.background_keeper.start()
        print("🔄 Background keepalive started")
    
    def stop_background_keepalive(self):
        """Stop background keepalive"""
        if self.keep_alive_active:
            self.keep_alive_active = False
            print("🔄 Background keepalive stopped")
    
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

# Global optimizer instance
universal_optimizer = UniversalOptimizer()
