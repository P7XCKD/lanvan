"""
� Universal Performance Optimizer
Handles memory management, chunk sizing, and process optimization for ALL platforms:
- Android/Termux: Resource-constrained optimization
- Desktop: High-performance optimization  
- Server: Balanced optimization
"""

import os
import sys
import time
import gc
import threading
from typing import Optional, Dict, Any
import subprocess

def get_available_memory_mb() -> int:
    """Get available memory in MB across platforms"""
    try:
        # Try psutil first (most reliable)
        import psutil
        mem = psutil.virtual_memory()
        return int(mem.available / (1024 * 1024))
    except ImportError:
        pass
    
    try:
        # Linux/Android: read from /proc/meminfo
        if os.path.exists('/proc/meminfo'):
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemAvailable:' in line:
                        available_kb = int(line.split()[1])
                        return available_kb // 1024
    except:
        pass
    
    # Fallback: assume reasonable amount
    return 1024  # 1GB default

def get_cpu_usage() -> float:
    """Get current CPU usage percentage"""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.1)
    except ImportError:
        return 50.0  # Conservative fallback

class UniversalOptimizer:
    """Universal performance optimizer for all platforms"""
    
    def __init__(self):
        self.is_android = self._detect_android()
        self.is_termux = self._detect_termux()
        self.is_low_memory = self._detect_low_memory_device()
        self.platform = self._detect_platform()
        self.background_keeper = None
        self.keep_alive_active = False
        self.upload_active = False
        
        print(f"🚀 Universal optimizer initialized for {self.platform}")
        if self.is_android:
            print(f"📱 Android optimizations enabled")
        if self.is_termux:
            print(f"🤖 Termux-specific optimizations enabled")
        if self.is_low_memory:
            print(f"💾 Low-memory device optimizations enabled")
    
    def _detect_android(self) -> bool:
        """Detect Android environment"""
        return ("ANDROID_STORAGE" in os.environ or 
                os.path.exists("/data/data/com.termux") or 
                "TERMUX_VERSION" in os.environ or
                "android" in str(os.environ.get("PREFIX", "")).lower())
    
    def _detect_termux(self) -> bool:
        """Detect Termux specifically"""
        return ("TERMUX_VERSION" in os.environ or 
                os.path.exists("/data/data/com.termux") or
                "/data/data/com.termux" in str(os.environ.get("PREFIX", "")))
    
    def _detect_low_memory_device(self) -> bool:
        """Detect if device has limited memory"""
        available_mb = get_available_memory_mb()
        return available_mb < 2048  # Less than 2GB available = low memory
    
    def _detect_platform(self) -> str:
        """Detect platform type"""
        if self.is_termux:
            return "Termux"
        elif self.is_android:
            return "Android"
        elif sys.platform.startswith('win'):
            return "Windows"
        elif sys.platform.startswith('darwin'):
            return "macOS"
        elif sys.platform.startswith('linux'):
            return "Linux"
        else:
            return "Unknown"
    
    def get_adaptive_chunk_size(self, file_size: int, base_chunk: int = 1024 * 1024) -> int:
        """
        🚀 AGGRESSIVE Adaptive chunk sizing - maximizes performance based on system capabilities:
        - Available memory
        - Platform capabilities  
        - File size
        - Current system load
        - Network bandwidth potential
        """
        available_mb = get_available_memory_mb()
        cpu_usage = get_cpu_usage()
        
        # 🎯 MUCH MORE AGGRESSIVE base chunk sizes by platform
        if self.is_android or self.is_low_memory:
            min_chunk = 128 * 1024    # 128KB minimum (was 64KB)
            max_chunk = 8 * 1024 * 1024   # 8MB maximum for Android (was 512KB!)
            base_chunk = 1024 * 1024  # 1MB base (was 256KB)
        else:
            min_chunk = 512 * 1024    # 512KB minimum (was 256KB)
            max_chunk = 64 * 1024 * 1024  # 64MB maximum for desktop (was 4MB!)
            base_chunk = 4 * 1024 * 1024  # 4MB base (was 1MB)
        
        # 🚀 AGGRESSIVE memory-based scaling
        chunk_size = base_chunk
        
        # Memory-based multiplication factors
        if available_mb < 512:      # Very low memory - conservative
            chunk_size = min_chunk
        elif available_mb < 1024:   # Low memory - still conservative  
            chunk_size = min_chunk * 2
        elif available_mb < 2048:   # Medium memory - moderate
            chunk_size = base_chunk
        elif available_mb < 4096:   # Good memory - aggressive
            chunk_size = base_chunk * 2
        elif available_mb < 8192:   # High memory - very aggressive
            chunk_size = base_chunk * 4
        elif available_mb < 16384:  # Very high memory - extremely aggressive
            chunk_size = base_chunk * 8
        else:                       # Massive memory - MAXIMUM PERFORMANCE
            chunk_size = base_chunk * 16
        
        # 🎯 File size optimization - larger files can handle bigger chunks better
        if file_size > 10 * 1024 * 1024 * 1024:  # Files > 10GB - use largest possible
            if not self.is_android and available_mb > 4096:
                chunk_size = min(max_chunk, chunk_size * 2)  # Double chunk size for huge files
        elif file_size > 5 * 1024 * 1024 * 1024:  # Files > 5GB
            if available_mb > 2048:
                chunk_size = min(max_chunk, int(chunk_size * 1.5))  # 1.5x chunk size
        elif file_size > 1 * 1024 * 1024 * 1024:  # Files > 1GB
            # Keep current chunk size - no reduction
            pass
        elif file_size < 100 * 1024 * 1024:  # Files < 100MB - can use smaller efficient chunks
            if chunk_size > 2 * 1024 * 1024:  # If chunk would be > 2MB
                chunk_size = 2 * 1024 * 1024  # Cap at 2MB for small files (more efficient)
        
        # 📊 CPU usage adjustment - if CPU is busy, use smaller chunks
        if cpu_usage > 80:  # High CPU usage
            chunk_size = max(min_chunk, chunk_size // 2)
        elif cpu_usage > 60:  # Medium CPU usage  
            chunk_size = max(min_chunk, int(chunk_size * 0.75))
        # If CPU usage is low (< 60%), keep large chunks for maximum throughput
        
        # 🎯 Platform-specific optimization overrides
        if not self.is_android:  # Desktop/Server systems
            # Desktop systems can handle much larger chunks
            if available_mb > 8192 and cpu_usage < 50:  # 8GB+ RAM and low CPU
                chunk_size = min(max_chunk, max(chunk_size, 32 * 1024 * 1024))  # At least 32MB
            elif available_mb > 4096 and cpu_usage < 70:  # 4GB+ RAM and moderate CPU  
                chunk_size = min(max_chunk, max(chunk_size, 16 * 1024 * 1024))  # At least 16MB
        
        # Ensure we stay within bounds
        chunk_size = max(min_chunk, min(max_chunk, chunk_size))
        
        return chunk_size
        
        # 3. CPU load adjustment
        if cpu_usage > 80:
            chunk_size = max(min_chunk, chunk_size // 2)  # Reduce chunk size under high CPU load
        
        # 4. Ensure bounds
        chunk_size = max(min_chunk, min(max_chunk, chunk_size))
        
        return chunk_size
    
    def should_run_gc(self, bytes_processed: int, chunk_size: int) -> bool:
        """Determine if garbage collection should run"""
        available_mb = get_available_memory_mb()
        
        # More aggressive GC for constrained environments
        if self.is_android or available_mb < 1024:
            return bytes_processed % (chunk_size * 4) == 0  # GC every 4 chunks
        elif available_mb < 2048:
            return bytes_processed % (chunk_size * 8) == 0  # GC every 8 chunks
        else:
            return bytes_processed % (chunk_size * 16) == 0  # GC every 16 chunks
    
    def optimize_for_upload(self, file_size: int):
        """Apply optimizations for file upload"""
        self.upload_active = True
        
        if file_size > 100 * 1024 * 1024:  # Files > 100MB
            print(f"🚀 Applying upload optimizations for {file_size:,} byte file")
            
            # Start keep-alive for large uploads
            self._start_keep_alive()
            
            # Platform-specific optimizations
            if self.is_android or self.is_low_memory:
                self._apply_constrained_optimizations()
            else:
                self._apply_performance_optimizations()
        
        return self.check_upload_feasibility(file_size)
    
    def _apply_constrained_optimizations(self):
        """Apply optimizations for resource-constrained devices"""
        try:
            # Disable automatic GC - we'll manage it manually
            gc.disable()
            
            # Set environment variables for better memory management
            os.environ['PYTHONUNBUFFERED'] = '1'
            
            print(f"📱 Resource-constrained optimizations applied")
        except Exception as e:
            print(f"⚠️ Constrained optimization warning: {e}")
    
    def _apply_performance_optimizations(self):
        """Apply optimizations for high-performance systems"""
        try:
            # Enable more aggressive garbage collection threshold
            gc.set_threshold(700, 10, 10)
            
            print(f"🚀 Performance optimizations applied")
        except Exception as e:
            print(f"⚠️ Performance optimization warning: {e}")
    
    def _start_keep_alive(self):
        """Start background keep-alive for upload stability"""
        if self.keep_alive_active:
            return
        
        self.keep_alive_active = True
        self.background_keeper = threading.Thread(
            target=self._keep_alive_worker, 
            daemon=True
        )
        self.background_keeper.start()
        print(f"🔋 Upload keep-alive started")
    
    def _keep_alive_worker(self):
        """Background worker to maintain upload stability"""
        while self.keep_alive_active and self.upload_active:
            try:
                time.sleep(30)  # Check every 30 seconds
                
                # Gentle memory cleanup
                if self.is_android or self.is_low_memory:
                    gc.collect()
                
                # Touch keepalive file for Termux
                if self.is_termux:
                    try:
                        keepalive_file = "/tmp/lanvan_keepalive"
                        with open(keepalive_file, 'w') as f:
                            f.write(str(time.time()))
                    except:
                        pass
                
            except Exception:
                pass  # Silent background worker
    
    def finish_upload(self):
        """Clean up after upload completion"""
        self.upload_active = False
        
        if self.keep_alive_active:
            self.keep_alive_active = False
            print(f"🔋 Upload keep-alive stopped")
        
        # Re-enable GC if disabled
        if self.is_android or self.is_low_memory:
            gc.enable()
        
        # Final cleanup
        self.memory_cleanup(force=True)
    
    def memory_cleanup(self, force: bool = False):
        """Perform memory cleanup"""
        if self.is_android or self.is_low_memory or force:
            try:
                gc.collect()
                
                # Additional cleanup for constrained devices
                if self.is_android:
                    try:
                        subprocess.run(['sync'], capture_output=True, timeout=2)
                    except:
                        pass
            except Exception:
                pass
    
    def check_upload_feasibility(self, file_size: int) -> Dict[str, Any]:
        """Check if upload is feasible and provide recommendations"""
        result = {
            'feasible': True,
            'warnings': [],
            'recommendations': [],
            'chunk_size': self.get_adaptive_chunk_size(file_size)
        }
        
        available_mb = get_available_memory_mb()
        file_size_mb = file_size / (1024 * 1024)
        
        # Universal checks
        if file_size_mb > 1000:  # Files > 1GB
            result['warnings'].append(f"Large file ({file_size_mb:.0f}MB) upload initiated")
            
            if available_mb < 512:
                result['warnings'].append(f"Limited memory available ({available_mb}MB)")
                result['recommendations'].append("Close other applications to free memory")
            
            result['recommendations'].append("Keep device active during upload")
        
        # Platform-specific recommendations
        if self.is_android:
            result['recommendations'].append("Keep device plugged in")
            result['recommendations'].append("Avoid switching apps during upload")
            
            if self.is_termux:
                result['recommendations'].append("Consider using 'termux-wake-lock'")
        
        return result
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        return {
            'platform': self.platform,
            'android': self.is_android,
            'termux': self.is_termux,
            'low_memory': self.is_low_memory,
            'available_memory_mb': get_available_memory_mb(),
            'cpu_usage': get_cpu_usage(),
            'keep_alive_active': self.keep_alive_active,
            'upload_active': self.upload_active,
            'gc_enabled': gc.isenabled()
        }

# Global optimizer instance
universal_optimizer = UniversalOptimizer()

def optimize_for_upload(file_size: int = 0) -> Dict[str, Any]:
    """Quick function to optimize for uploads"""
    return universal_optimizer.optimize_for_upload(file_size)

def cleanup_resources():
    """Clean up all resources"""
    universal_optimizer.finish_upload()

def get_adaptive_chunk_size(file_size: int = 0) -> int:
    """Get adaptive chunk size for file"""
    return universal_optimizer.get_adaptive_chunk_size(file_size)

def should_run_gc(bytes_processed: int, chunk_size: int) -> bool:
    """Check if GC should run"""
    return universal_optimizer.should_run_gc(bytes_processed, chunk_size)
