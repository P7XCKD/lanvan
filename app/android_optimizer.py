"""
📱 Android/Termux Performance Optimizations
Handles background task management, resource limits, and process survival for large uploads
"""

import os
import sys
import time
import gc
import threading
from typing import Optional
import subprocess

class AndroidOptimizer:
    """Android/Termux specific performance optimizations"""
    
    def __init__(self):
        self.is_android = self._detect_android()
        self.is_termux = self._detect_termux()
        self.background_keeper = None
        self.keep_alive_active = False
        
        if self.is_android:
            print(f"📱 Android detected - enabling optimizations")
        if self.is_termux:
            print(f"🤖 Termux detected - enabling Termux-specific optimizations")
    
    def _detect_android(self) -> bool:
        """Detect if running on Android"""
        return ("ANDROID_STORAGE" in os.environ or 
                os.path.exists("/data/data/com.termux") or 
                "TERMUX_VERSION" in os.environ or
                "android" in str(os.environ.get("PREFIX", "")).lower())
    
    def _detect_termux(self) -> bool:
        """Detect if running in Termux specifically"""
        return ("TERMUX_VERSION" in os.environ or 
                os.path.exists("/data/data/com.termux") or
                "/data/data/com.termux" in str(os.environ.get("PREFIX", "")))
    
    def optimize_for_large_upload(self):
        """Apply optimizations for large file uploads"""
        if not self.is_android:
            return
        
        try:
            # 🧹 Force aggressive garbage collection
            gc.collect()
            
            # 📱 Termux-specific optimizations
            if self.is_termux:
                self._apply_termux_optimizations()
            
            # 🔋 Start background keep-alive
            self._start_keep_alive()
            
            print(f"📱 Android optimizations applied for large upload")
            
        except Exception as e:
            print(f"⚠️ Android optimization warning: {e}")
    
    def _apply_termux_optimizations(self):
        """Apply Termux-specific optimizations"""
        try:
            # 🧹 Disable Python's garbage collection threshold for better performance
            # during large uploads (we'll manage it manually)
            gc.disable()
            
            # Set environment variables for better memory management
            os.environ['PYTHONUNBUFFERED'] = '1'  # Immediate output
            os.environ['MALLOC_TRIM_THRESHOLD_'] = '100000'  # More aggressive memory trimming
            
            print(f"🤖 Termux optimizations applied")
            
        except Exception as e:
            print(f"⚠️ Termux optimization warning: {e}")
    
    def _start_keep_alive(self):
        """Start background thread to keep process alive during uploads"""
        if self.keep_alive_active:
            return
        
        self.keep_alive_active = True
        self.background_keeper = threading.Thread(
            target=self._keep_alive_worker, 
            daemon=True
        )
        self.background_keeper.start()
        print(f"🔋 Keep-alive thread started")
    
    def _keep_alive_worker(self):
        """Background worker to prevent process killing"""
        while self.keep_alive_active:
            try:
                # 🔋 Perform minimal activity to show we're alive
                time.sleep(30)  # Check every 30 seconds
                
                # 🧹 Gentle garbage collection
                gc.collect()
                
                # 📱 Termux: Touch a file to show activity (prevents idle killing)
                if self.is_termux:
                    keepalive_file = "/tmp/lanvan_keepalive"
                    with open(keepalive_file, 'w') as f:
                        f.write(str(time.time()))
                
            except Exception as e:
                # Silently handle errors in background
                pass
    
    def stop_keep_alive(self):
        """Stop the keep-alive thread"""
        if self.keep_alive_active:
            self.keep_alive_active = False
            print(f"🔋 Keep-alive thread stopped")
            
            # Re-enable garbage collection
            if self.is_termux:
                gc.enable()
    
    def memory_cleanup(self, force: bool = False):
        """Perform memory cleanup optimized for Android"""
        if not self.is_android and not force:
            return
        
        try:
            # 🧹 Force garbage collection
            gc.collect()
            
            # 📱 Android: Request explicit memory trim
            if self.is_android:
                try:
                    # Try to trim memory using system call
                    subprocess.run(['sync'], capture_output=True, timeout=5)
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
            
            # 🤖 Termux: Clear Python caches
            if self.is_termux:
                sys.modules.clear()  # Clear module cache
                
        except Exception as e:
            pass  # Silent cleanup
    
    def get_memory_info(self) -> dict:
        """Get current memory usage info"""
        info = {
            'platform': 'android' if self.is_android else 'other',
            'termux': self.is_termux,
            'keep_alive': self.keep_alive_active
        }
        
        try:
            # Try to get memory stats
            if self.is_android:
                try:
                    # Read memory info from /proc/meminfo
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = f.read()
                        for line in meminfo.split('\n'):
                            if 'MemAvailable:' in line:
                                available_kb = int(line.split()[1])
                                info['available_memory_mb'] = available_kb // 1024
                                break
                except:
                    pass
        except Exception:
            pass
        
        return info
    
    def check_upload_feasibility(self, file_size: int) -> dict:
        """Check if large upload is feasible on current device"""
        result = {
            'feasible': True,
            'warnings': [],
            'recommendations': []
        }
        
        if not self.is_android:
            return result
        
        # Check available memory
        memory_info = self.get_memory_info()
        available_mb = memory_info.get('available_memory_mb', 0)
        
        file_size_mb = file_size / (1024 * 1024)
        
        # Android-specific checks
        if file_size_mb > 1000:  # Files > 1GB
            result['warnings'].append(f"Large file ({file_size_mb:.0f}MB) detected on Android")
            
            if available_mb > 0 and available_mb < 500:  # Less than 500MB available
                result['warnings'].append(f"Low memory available ({available_mb}MB)")
                result['recommendations'].append("Close other apps to free memory")
            
            result['recommendations'].append("Keep device plugged in during upload")
            result['recommendations'].append("Avoid switching apps during upload")
        
        if self.is_termux:
            result['recommendations'].append("Consider using 'termux-wake-lock' to prevent sleep")
        
        return result

# Global optimizer instance
android_optimizer = AndroidOptimizer()

def optimize_for_android_upload(file_size: int = 0) -> dict:
    """Quick function to optimize for Android uploads"""
    if file_size > 100 * 1024 * 1024:  # Files > 100MB
        android_optimizer.optimize_for_large_upload()
    
    return android_optimizer.check_upload_feasibility(file_size)

def cleanup_android_resources():
    """Clean up Android-specific resources"""
    android_optimizer.stop_keep_alive()
    android_optimizer.memory_cleanup(force=True)
