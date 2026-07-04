#!/usr/bin/env python3
"""
[BOT] Termux Memory Monitor
Monitors memory usage and enforces limits on Termux/Android environments
"""

import os
import gc
import time
import threading
import asyncio
from typing import Dict, Any, Optional, Callable
from app.utils.termux_compat import (
    is_termux_environment, 
    is_android_environment,
    get_safe_memory_info,
    get_termux_chunk_size
)

class TermuxMemoryMonitor:
    """Memory monitoring and enforcement for Termux environments"""
    
    def __init__(self):
        self.is_termux = is_termux_environment()
        self.is_android = is_android_environment()
        self.monitoring_active = False
        self.monitor_thread = None
        self.memory_callbacks = []
        self.last_gc_time = 0
        self.gc_interval = 30  # 30 seconds between GC on Termux
        
        # Memory thresholds (in MB)
        if self.is_termux:
            self.warning_threshold = 200  # 200MB remaining
            self.critical_threshold = 100  # 100MB remaining
            self.emergency_threshold = 50   # 50MB remaining
        else:
            self.warning_threshold = 500   # 500MB remaining
            self.critical_threshold = 200  # 200MB remaining  
            self.emergency_threshold = 100 # 100MB remaining
            
        self.current_status = "normal"
        
    def start_monitoring(self):
        """Start memory monitoring in background thread"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        if self.is_termux:
            print("[BOT] Termux memory monitoring started")
        
    def stop_monitoring(self):
        """Stop memory monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
            
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                self._check_memory_status()
                
                # More frequent checks on Termux
                sleep_time = 5 if self.is_termux else 10
                time.sleep(sleep_time)
                
            except Exception as e:
                if self.is_termux:
                    print(f"[WARN] Memory monitor warning: {e}")
                time.sleep(10)  # Longer sleep on error
                
    def _check_memory_status(self):
        """Check current memory status and take action if needed"""
        memory_info = get_safe_memory_info()
        available_mb = memory_info.get('available_mb', 1024)
        
        old_status = self.current_status
        
        # Determine status based on available memory
        if available_mb <= self.emergency_threshold:
            self.current_status = "emergency"
        elif available_mb <= self.critical_threshold:
            self.current_status = "critical"
        elif available_mb <= self.warning_threshold:
            self.current_status = "warning"
        else:
            self.current_status = "normal"
            
        # Take action if status changed or time for regular GC
        if old_status != self.current_status or self._should_run_gc():
            self._handle_memory_status(available_mb)
            
    def _should_run_gc(self) -> bool:
        """Check if it's time for regular garbage collection"""
        current_time = time.time()
        if current_time - self.last_gc_time > self.gc_interval:
            return True
        return False
        
    def _handle_memory_status(self, available_mb: int):
        """Handle memory status changes"""
        if self.current_status == "emergency":
            if self.is_termux:
                print(f"[!] EMERGENCY: Only {available_mb}MB memory remaining!")
            self._emergency_cleanup()
            
        elif self.current_status == "critical":
            if self.is_termux:
                print(f"[WARN] CRITICAL: Only {available_mb}MB memory remaining")
            self._critical_cleanup()
            
        elif self.current_status == "warning":
            if self.is_termux:
                print(f" WARNING: {available_mb}MB memory remaining")
            self._warning_cleanup()
            
        elif self.current_status == "normal" and self._should_run_gc():
            self._regular_cleanup()
            
        # Notify callbacks
        for callback in self.memory_callbacks:
            try:
                callback(self.current_status, available_mb)
            except Exception as e:
                print(f"Memory callback error: {e}")
                
    def _emergency_cleanup(self):
        """Emergency memory cleanup - most aggressive"""
        self._force_garbage_collection()
        
        # Clear any non-essential caches
        if hasattr(gc, 'set_threshold'):
            gc.set_threshold(100, 10, 10)  # More aggressive GC
            
        self.last_gc_time = time.time()
        
    def _critical_cleanup(self):
        """Critical memory cleanup"""
        self._force_garbage_collection()
        self.last_gc_time = time.time()
        
    def _warning_cleanup(self):
        """Warning level cleanup"""
        if self.is_termux or self.is_android:
            gc.collect()
            self.last_gc_time = time.time()
            
    def _regular_cleanup(self):
        """Regular maintenance cleanup"""
        if self.is_termux or self.is_android:
            gc.collect()
            self.last_gc_time = time.time()
            
    def _force_garbage_collection(self):
        """Force aggressive garbage collection"""
        # Multiple GC passes for thorough cleanup
        for _ in range(3):
            gc.collect()
            
        # Clear weakref callbacks if available
        if hasattr(gc, 'garbage'):
            del gc.garbage[:]
            
    def register_memory_callback(self, callback: Callable[[str, int], None]):
        """Register a callback for memory status changes"""
        self.memory_callbacks.append(callback)
        
    def get_memory_status(self) -> Dict[str, Any]:
        """Get current memory status"""
        memory_info = get_safe_memory_info()
        return {
            "status": self.current_status,
            "available_mb": memory_info.get('available_mb', 1024),
            "is_termux": self.is_termux,
            "is_android": self.is_android,
            "monitoring_active": self.monitoring_active,
            "thresholds": {
                "warning": self.warning_threshold,
                "critical": self.critical_threshold,
                "emergency": self.emergency_threshold
            }
        }
        
    def get_adaptive_chunk_size(self, file_size: int = 0) -> int:
        """Get chunk size based on current memory status"""
        if self.current_status == "emergency":
            return get_termux_chunk_size(file_size) // 4  # Quarter size in emergency
        elif self.current_status == "critical":
            return get_termux_chunk_size(file_size) // 2  # Half size in critical
        elif self.current_status == "warning":
            return int(get_termux_chunk_size(file_size) * 0.75)  # 75% size in warning
        else:
            return get_termux_chunk_size(file_size)  # Normal size
            
    def enforce_memory_limit(self, operation_name: str = "operation") -> bool:
        """Check if operation should proceed based on memory status"""
        if self.current_status == "emergency":
            print(f"[!] Operation '{operation_name}' blocked - emergency memory situation")
            return False
        elif self.current_status == "critical":
            print(f"[WARN] Operation '{operation_name}' proceeding with caution - critical memory")
            return True
        else:
            return True

# Global memory monitor instance
termux_memory_monitor = TermuxMemoryMonitor()

def start_termux_memory_monitoring():
    """Start Termux memory monitoring if applicable"""
    if is_termux_environment() or is_android_environment():
        termux_memory_monitor.start_monitoring()
        
def stop_termux_memory_monitoring():
    """Stop Termux memory monitoring"""
    termux_memory_monitor.stop_monitoring()
    
def get_termux_memory_status() -> Dict[str, Any]:
    """Get current Termux memory status"""
    return termux_memory_monitor.get_memory_status()
    
def enforce_termux_memory_limit(operation_name: str = "operation") -> bool:
    """Enforce Termux memory limits for operations"""
    return termux_memory_monitor.enforce_memory_limit(operation_name)

def get_memory_adaptive_chunk_size(file_size: int = 0) -> int:
    """Get memory-adaptive chunk size for current conditions"""
    return termux_memory_monitor.get_adaptive_chunk_size(file_size)