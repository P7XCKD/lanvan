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
            return 'other'
    
    def _detect_termux(self) -> bool:
        """Detect if running in Termux specifically"""
        return ("TERMUX_VERSION" in os.environ or 
                os.path.exists("/data/data/com.termux") or
                "/data/data/com.termux" in str(os.environ.get("PREFIX", "")))
    
    def optimize_for_large_upload(self, file_size: int):
        """Apply platform-specific optimizations for large file uploads"""
        print(f"🚀 Enabling optimizations for {file_size//1024//1024}MB file on {self.platform_type}")
        
        try:
            # 🧹 Universal: Force garbage collection
            gc.collect()
            
            # 🔋 Start keep-alive for all platforms during large uploads
            if file_size > 500 * 1024 * 1024:  # Files > 500MB
                self._start_keep_alive()
            
            # Platform-specific optimizations
            if self.is_android:
                self._apply_android_optimizations()
            elif self.is_windows:
                self._apply_windows_optimizations()
            elif self.is_linux:
                self._apply_linux_optimizations()
            elif self.is_mac:
                self._apply_mac_optimizations()
            
            print(f"✅ {self.platform_type.title()} optimizations applied")
            
        except Exception as e:
            print(f"⚠️ Optimization warning: {e}")
    
    def _apply_android_optimizations(self):
        """Android/Termux specific optimizations"""
        try:
            # Disable Python GC during upload (manual management)
            gc.disable()
            
            # Set environment variables for better memory management
            os.environ['PYTHONUNBUFFERED'] = '1'
            os.environ['MALLOC_TRIM_THRESHOLD_'] = '100000'
            
            print(f"📱 Android optimizations applied")
            
        except Exception as e:
            print(f"⚠️ Android optimization warning: {e}")
    
    def _apply_windows_optimizations(self):
        """Windows specific optimizations"""
        try:
            # Set high priority for the process (if possible)
            priority_result = safe_psutil_call(
                lambda: __import__('psutil').Process().nice(__import__('psutil').HIGH_PRIORITY_CLASS)
            )
            if priority_result is not None:
                print(f"💻 Windows: Process priority set to high")
            
            # Disable Windows write caching for immediate disk writes
            os.environ['PYTHONUNBUFFERED'] = '1'
            
            print(f"💻 Windows optimizations applied")
            
        except Exception as e:
            print(f"⚠️ Windows optimization warning: {e}")
    
    def _apply_linux_optimizations(self):
        """Linux specific optimizations"""
        try:
            # Linux-specific optimizations (nice priority only on Linux)
            if platform.system().lower() == 'linux':
                try:
                    # Check if we can modify process priority
                    os.system('renice -n -5 {} > /dev/null 2>&1'.format(os.getpid()))
                    print(f"🐧 Linux: Process priority increased")
                except:
                    pass  # Not critical
            
            # Optimize for sequential I/O
            os.environ['PYTHONUNBUFFERED'] = '1'
            
            print(f"🐧 Linux optimizations applied")
            
        except Exception as e:
            print(f"⚠️ Linux optimization warning: {e}")
    
    def _apply_mac_optimizations(self):
        """macOS specific optimizations"""
        try:
            # macOS memory management
            os.environ['PYTHONUNBUFFERED'] = '1'
            
            # Basic macOS optimizations (avoid complex priority changes)
            print(f"🍎 macOS optimizations applied")
            
        except Exception as e:
            print(f"⚠️ macOS optimization warning: {e}")
    
    def _start_keep_alive(self):
        """Start background thread to keep process active during large uploads"""
        if self.keep_alive_active:
            return
        
        self.keep_alive_active = True
        self.background_keeper = threading.Thread(
            target=self._keep_alive_worker, 
            daemon=True
        )
        self.background_keeper.start()
        print(f"🔋 Keep-alive thread started for {self.platform_type}")
    
    def _keep_alive_worker(self):
        """Background worker to prevent process termination"""
        while self.keep_alive_active:
            try:
                time.sleep(30)  # Check every 30 seconds
                
                # Gentle garbage collection
                gc.collect()
                
                # Platform-specific keep-alive actions
                if self.is_android or self.is_termux:
                    # Touch a file to show activity
                    keepalive_file = "/tmp/lanvan_keepalive"
                    with open(keepalive_file, 'w') as f:
                        f.write(str(time.time()))
                elif self.is_windows:
                    # Windows: Just the memory management is enough
                    pass
                else:
                    # Linux/Mac: Touch temp file
                    keepalive_file = "/tmp/lanvan_keepalive"
                    try:
                        with open(keepalive_file, 'w') as f:
                            f.write(str(time.time()))
                    except PermissionError:
                        pass  # May not have /tmp access
                
            except Exception:
                pass  # Silent handling in background
    
    def stop_keep_alive(self):
        """Stop the keep-alive thread"""
        if self.keep_alive_active:
            self.keep_alive_active = False
            print(f"🔋 Keep-alive thread stopped")
            
            # Re-enable garbage collection if disabled
            if self.is_android:
                gc.enable()
    
    def memory_cleanup(self, force: bool = False):
        """Perform memory cleanup optimized for current platform"""
        try:
            # Universal garbage collection
            gc.collect()
            
            # Platform-specific cleanup
            if self.is_windows:
                try:
                    # Windows: Request memory trim
                    subprocess.run(['powershell', '-Command', '[GC]::Collect()'], 
                                 capture_output=True, timeout=3)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
            elif self.is_linux or self.is_mac:
                try:
                    # Unix: Sync filesystem
                    subprocess.run(['sync'], capture_output=True, timeout=5)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
            elif self.is_android:
                try:
                    # Android: More aggressive cleanup
                    subprocess.run(['sync'], capture_output=True, timeout=5)
                    if self.is_termux:
                        # Clear Python module caches
                        sys.modules.clear()
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                
        except Exception:
            pass  # Silent cleanup
    
    def get_platform_info(self) -> Dict:
        """Get current platform and optimization info"""
        info = {
            'platform': self.platform_type,
            'platform_details': platform.platform(),
            'python_version': platform.python_version(),
            'is_android': self.is_android,
            'is_termux': self.is_termux,
            'keep_alive_active': self.keep_alive_active
        }
        
        # Add memory info if available
        try:
            if self.is_android or self.is_linux:
                # Read from /proc/meminfo
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if 'MemAvailable:' in line:
                            available_kb = int(line.split()[1])
                            info['available_memory_mb'] = available_kb // 1024
                            break
            elif self.is_windows:
                # Use safe memory detection for all platforms
                memory_info = get_safe_memory_info()
                if memory_info and 'available' in memory_info:
                    info['available_memory_mb'] = int(memory_info['available'] / (1024**2))
        except Exception:
            pass
        
        return info
    
    def check_upload_feasibility(self, file_size: int) -> Dict:
        """Check if large upload is feasible on current platform"""
        result = {
            'feasible': True,
            'warnings': [],
            'recommendations': []
        }
        
        file_size_mb = file_size / (1024 * 1024)
        platform_info = self.get_platform_info()
        available_mb = platform_info.get('available_memory_mb', 0)
        
        # Universal checks for all platforms
        if file_size_mb > 1000:  # Files > 1GB
            result['warnings'].append(f"Large file ({file_size_mb:.0f}MB) detected on {self.platform_type}")
            
            if available_mb > 0 and available_mb < 1000:  # Less than 1GB available
                result['warnings'].append(f"Low memory available ({available_mb}MB)")
                result['recommendations'].append("Close other applications to free memory")
        
        # Platform-specific recommendations
        if self.is_android:
            result['recommendations'].extend([
                "Keep device plugged in during upload",
                "Avoid switching apps during upload"
            ])
            if self.is_termux:
                result['recommendations'].append("Consider using 'termux-wake-lock' to prevent sleep")
        elif self.is_windows:
            result['recommendations'].extend([
                "Ensure sufficient disk space",
                "Consider pausing Windows Updates during upload"
            ])
        elif self.is_linux or self.is_mac:
            result['recommendations'].extend([
                "Ensure sufficient disk space",
                "Avoid hibernation/sleep during upload"
            ])
        
        return result

# Global universal optimizer instance
universal_optimizer = UniversalOptimizer()

def optimize_for_large_upload(file_size: int = 0) -> Dict:
    """Quick function to optimize for large uploads on any platform"""
    if file_size > 100 * 1024 * 1024:  # Files > 100MB
        universal_optimizer.optimize_for_large_upload(file_size)
    
    return universal_optimizer.check_upload_feasibility(file_size)

def cleanup_resources():
    """Clean up optimization resources for any platform"""
    universal_optimizer.stop_keep_alive()
    universal_optimizer.memory_cleanup(force=True)
