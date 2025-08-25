"""
🚀 Universal Performance Optimizer with Termux Compatibility
Handles memory management, chunk sizing, and process optimization for ALL platforms:
- Android/Termux: Resource-constrained optimization with safe system access
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

def get_available_memory_mb() -> int:
    """Get available memory in MB across platforms with Termux-safe fallback"""
    # Use Termux-compatible memory detection
    memory_info = get_safe_memory_info()
    if memory_info and 'available' in memory_info:
        return int(memory_info['available'] / (1024**2))  # Convert bytes to MB
    
    # Fallback for systems without safe memory access
    print("⚠️  Memory detection unavailable, using conservative estimate")
    return 512  # Conservative default for resource-constrained environments

def get_cpu_usage() -> float:
    """Get current CPU usage percentage with Termux-safe fallback"""
    cpu_usage = get_safe_cpu_usage()
    return cpu_usage if cpu_usage is not None else 50.0  # Conservative fallback

def calculate_optimal_chunk_size(file_size: int, available_memory_mb: int) -> int:
    """Calculate optimal chunk size based on file size and system resources with Termux awareness"""
    
    # Use Termux-specific chunk sizing if in Termux environment
    if is_termux_environment():
        chunk_size = get_termux_chunk_size(file_size)
        print(f"🤖 Termux chunk size: {chunk_size // 1024}KB")
        return chunk_size
    
    # Desktop/server optimization for non-Termux environments
    available_memory_bytes = available_memory_mb * 1024 * 1024
    
    # Calculate based on file size
    if file_size < 1024 * 1024:  # < 1MB
        base_chunk = min(64 * 1024, file_size)  # 64KB max
    elif file_size < 10 * 1024 * 1024:  # < 10MB
        base_chunk = min(256 * 1024, file_size // 4)  # 256KB max
    elif file_size < 100 * 1024 * 1024:  # < 100MB
        base_chunk = min(1024 * 1024, file_size // 10)  # 1MB max
    else:  # >= 100MB
        base_chunk = min(4 * 1024 * 1024, file_size // 20)  # 4MB max
    
    # Adjust for available memory
    memory_limited_chunk = min(base_chunk, available_memory_bytes // 8)
    
    # Ensure minimum chunk size
    final_chunk = max(memory_limited_chunk, 32 * 1024)  # 32KB minimum
    
    print(f"💡 Optimal chunk size: {final_chunk // 1024}KB (File: {file_size // 1024}KB, RAM: {available_memory_mb}MB)")
    return final_chunk

def optimize_for_android() -> Dict[str, Any]:
    """Android-specific optimizations including Termux compatibility"""
    optimizations = {}
    
    if is_termux_environment():
        print("🔧 Applying Termux-specific optimizations...")
        system_info = get_termux_system_info()
        
        # Use safe system information
        optimizations.update({
            'max_concurrent_uploads': 2,  # Conservative for Termux
            'memory_threshold': 0.7,  # Lower threshold for resource constraints
            'gc_frequency': 5,  # More frequent garbage collection
            'chunk_multiplier': 0.5,  # Smaller chunks
            'cpu_throttle_threshold': 70,
            'system_info': system_info,
            'platform': 'termux'
        })
    else:
        print("🔧 Applying Android optimizations...")
        # Standard Android optimizations
        optimizations.update({
            'max_concurrent_uploads': 3,
            'memory_threshold': 0.8,
            'gc_frequency': 10,
            'chunk_multiplier': 0.8,
            'cpu_throttle_threshold': 80,
            'platform': 'android'
        })
    
    # Force garbage collection
    gc.collect()
    
    return optimizations

def optimize_for_desktop() -> Dict[str, Any]:
    """Desktop-specific optimizations"""
    print("🖥️  Applying desktop optimizations...")
    
    # Get safe system metrics
    available_memory = get_available_memory_mb()
    cpu_usage = get_cpu_usage()
    
    # Desktop can handle more aggressive optimization
    optimizations = {
        'max_concurrent_uploads': min(6, max(2, available_memory // 512)),
        'memory_threshold': 0.85,
        'gc_frequency': 20,
        'chunk_multiplier': 1.2,
        'cpu_throttle_threshold': 85,
        'available_memory': available_memory,
        'cpu_usage': cpu_usage,
        'platform': 'desktop'
    }
    
    return optimizations

def optimize_for_server() -> Dict[str, Any]:
    """Server-specific optimizations"""
    print("🖥️  Applying server optimizations...")
    
    # Get safe system metrics
    available_memory = get_available_memory_mb()
    cpu_usage = get_cpu_usage()
    
    # Server optimization focuses on throughput and stability
    optimizations = {
        'max_concurrent_uploads': min(10, max(3, available_memory // 256)),
        'memory_threshold': 0.75,  # More conservative for stability
        'gc_frequency': 15,
        'chunk_multiplier': 1.0,
        'cpu_throttle_threshold': 75,
        'available_memory': available_memory,
        'cpu_usage': cpu_usage,
        'platform': 'server'
    }
    
    return optimizations

class ResourceMonitor:
    """Monitor system resources with Termux-safe implementations"""
    
    def __init__(self):
        self.is_termux = is_termux_environment()
        self.monitoring = False
        self.monitor_thread = None
        self.stats = {
            'memory_usage': [],
            'cpu_usage': [],
            'last_update': time.time()
        }
    
    def start_monitoring(self):
        """Start resource monitoring"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"📊 Resource monitoring started ({'Termux-safe' if self.is_termux else 'full'})")
    
    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        print("📊 Resource monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop with Termux-safe implementations"""
        while self.monitoring:
            try:
                # Get safe metrics
                memory_info = get_safe_memory_info()
                cpu_usage = get_safe_cpu_usage()
                
                if memory_info:
                    memory_usage = (memory_info.get('used', 0) / memory_info.get('total', 1)) * 100
                    self.stats['memory_usage'].append(memory_usage)
                
                if cpu_usage is not None:
                    self.stats['cpu_usage'].append(cpu_usage)
                
                self.stats['last_update'] = time.time()
                
                # Keep only recent data
                max_samples = 60  # Last 60 samples
                for key in ['memory_usage', 'cpu_usage']:
                    if len(self.stats[key]) > max_samples:
                        self.stats[key] = self.stats[key][-max_samples:]
                
                # Adaptive monitoring frequency
                if self.is_termux:
                    time.sleep(2.0)  # Slower monitoring for Termux
                else:
                    time.sleep(1.0)  # Normal monitoring
                    
            except Exception as e:
                print(f"⚠️  Monitoring error: {e}")
                time.sleep(5.0)  # Back off on error
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current system statistics"""
        stats = self.stats.copy()
        
        # Add current readings
        stats['current_memory'] = self.stats['memory_usage'][-1] if self.stats['memory_usage'] else 0
        stats['current_cpu'] = self.stats['cpu_usage'][-1] if self.stats['cpu_usage'] else 0
        stats['platform'] = 'termux' if self.is_termux else 'desktop'
        
        return stats
    
    def should_throttle(self) -> bool:
        """Determine if system should throttle operations"""
        if not self.stats['memory_usage'] or not self.stats['cpu_usage']:
            return False
            
        current_memory = self.stats['memory_usage'][-1]
        current_cpu = self.stats['cpu_usage'][-1]
        
        # Termux has lower thresholds
        if self.is_termux:
            memory_threshold = 70  # 70% memory
            cpu_threshold = 70     # 70% CPU
        else:
            memory_threshold = 85  # 85% memory
            cpu_threshold = 85     # 85% CPU
        
        return current_memory > memory_threshold or current_cpu > cpu_threshold

def get_platform_optimizer() -> Dict[str, Any]:
    """Get appropriate optimizer based on platform with Termux detection"""
    
    if is_termux_environment():
        return optimize_for_android()  # Termux uses Android optimizations
    elif is_android_environment():
        return optimize_for_android()
    elif os.name == 'nt':  # Windows
        return optimize_for_desktop()
    elif 'linux' in sys.platform.lower():
        # Check if it's a server environment (no GUI)
        if os.environ.get('DISPLAY') is None and os.environ.get('WAYLAND_DISPLAY') is None:
            return optimize_for_server()
        else:
            return optimize_for_desktop()
    else:
        return optimize_for_desktop()  # Default fallback

def cleanup_resources():
    """Clean up system resources with platform awareness"""
    print("🧹 Cleaning up system resources...")
    
    # Force garbage collection
    gc.collect()
    
    # Platform-specific cleanup
    if is_termux_environment():
        print("🤖 Termux cleanup - conservative approach")
        # More conservative cleanup for Termux
        time.sleep(0.1)
    else:
        print("💻 Standard cleanup")
        # Standard cleanup
        pass
    
    print("✅ Resource cleanup complete")

# Global resource monitor instance
_resource_monitor = None

def get_resource_monitor() -> ResourceMonitor:
    """Get global resource monitor instance"""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor

def initialize_optimizer():
    """Initialize the optimizer system"""
    print("🚀 Initializing Universal Performance Optimizer...")
    
    # Detect platform
    platform_info = get_platform_optimizer()
    print(f"📱 Platform: {platform_info.get('platform', 'unknown')}")
    
    # Start resource monitoring
    monitor = get_resource_monitor()
    monitor.start_monitoring()
    
    print("✅ Optimizer initialization complete")
    return platform_info

def shutdown_optimizer():
    """Shutdown the optimizer system"""
    print("🔄 Shutting down optimizer...")
    
    # Stop monitoring
    global _resource_monitor
    if _resource_monitor:
        _resource_monitor.stop_monitoring()
        _resource_monitor = None
    
    # Clean up resources
    cleanup_resources()
    
    print("✅ Optimizer shutdown complete")

# Initialize on module import
if __name__ != "__main__":
    try:
        _platform_config = initialize_optimizer()
    except Exception as e:
        print(f"⚠️  Optimizer initialization failed: {e}")
        _platform_config = {'platform': 'fallback', 'max_concurrent_uploads': 2}

class UniversalOptimizer:
    """Universal optimizer class for compatibility with existing code"""
    
    def __init__(self):
        self.platform = _platform_config.get('platform', 'unknown')
        self.upload_active = False
        self.resource_monitor = get_resource_monitor()
    
    def get_adaptive_chunk_size(self, file_size: int) -> int:
        """Get adaptive chunk size for a file"""
        available_memory = get_available_memory_mb()
        return calculate_optimal_chunk_size(file_size, available_memory)
    
    def optimize_for_upload(self, file_size: int):
        """Optimize system for upload"""
        self.upload_active = True
        print(f"🚀 Optimizing system for {file_size} byte upload")
    
    def should_run_gc(self, bytes_processed: int, chunk_size: int) -> bool:
        """Check if garbage collection should run"""
        # Run GC every 10 chunks or when system is under pressure
        chunk_count = bytes_processed // chunk_size if chunk_size > 0 else 0
        should_gc = (chunk_count > 0 and chunk_count % 10 == 0)
        
        # Also check system pressure
        if self.resource_monitor.should_throttle():
            should_gc = True
            
        return should_gc
    
    def memory_cleanup(self, force: bool = False):
        """Clean up memory"""
        self.upload_active = False
        cleanup_resources()

# Global optimizer instance for compatibility
universal_optimizer = UniversalOptimizer()
