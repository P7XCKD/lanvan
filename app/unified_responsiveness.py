"""
🎯 LANVAN Unified Responsiveness Manager
Consolidates multiple overlapping responsiveness systems into a single, efficient solution.
"""

import asyncio
import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging

from app.thread_manager import thread_manager, ThreadPriority

class ResponsivenessMode(Enum):
    """Responsiveness optimization modes"""
    DESKTOP = "desktop"      # High-performance desktop environment
    MOBILE = "mobile"        # Mobile/Termux optimized
    SERVER = "server"        # Server environment focused
    MINIMAL = "minimal"      # Minimal overhead mode

@dataclass
class ResponsivenessConfig:
    """Responsiveness configuration settings"""
    mode: ResponsivenessMode = ResponsivenessMode.DESKTOP
    
    # Yield intervals (how often to yield control)
    streaming_yield_size: int = 64 * 1024      # 64KB chunks
    upload_yield_frequency: int = 10            # Every 10 chunks
    monitoring_interval: float = 0.1            # 100ms monitoring
    
    # Memory thresholds
    memory_check_frequency: int = 50            # Every 50 operations
    memory_warning_threshold: float = 80.0      # 80% memory usage
    
    # Timing controls
    async_sleep_duration: float = 0.01          # 10ms async sleep
    sync_sleep_duration: float = 0.05           # 50ms sync sleep
    error_backoff_duration: float = 1.0         # 1s error backoff
    
    # Performance optimizations
    use_request_animation_frame: bool = True    # For frontend
    batch_size: int = 100                       # Operations per batch
    max_concurrent_operations: int = 5          # Concurrent limit

    @classmethod
    def for_mode(cls, mode: ResponsivenessMode) -> 'ResponsivenessConfig':
        """Create optimized config for specific mode"""
        configs = {
            ResponsivenessMode.DESKTOP: cls(
                mode=mode,
                streaming_yield_size=128 * 1024,  # 128KB
                upload_yield_frequency=5,          # More frequent yields
                monitoring_interval=0.05,          # 50ms
                async_sleep_duration=0.005,        # 5ms
                max_concurrent_operations=8        # Higher concurrency
            ),
            ResponsivenessMode.MOBILE: cls(
                mode=mode,
                streaming_yield_size=32 * 1024,   # 32KB
                upload_yield_frequency=15,         # Less frequent yields
                monitoring_interval=0.2,           # 200ms
                async_sleep_duration=0.02,         # 20ms
                sync_sleep_duration=0.1,           # 100ms
                max_concurrent_operations=3        # Lower concurrency
            ),
            ResponsivenessMode.SERVER: cls(
                mode=mode,
                streaming_yield_size=256 * 1024,  # 256KB
                upload_yield_frequency=20,         # Less frequent yields
                monitoring_interval=0.5,           # 500ms
                memory_check_frequency=100,        # Less frequent checks
                max_concurrent_operations=10       # Higher concurrency
            ),
            ResponsivenessMode.MINIMAL: cls(
                mode=mode,
                streaming_yield_size=512 * 1024,  # 512KB
                upload_yield_frequency=50,         # Minimal yields
                monitoring_interval=1.0,           # 1s
                memory_check_frequency=200,        # Minimal checks
                async_sleep_duration=0.001,        # 1ms
                sync_sleep_duration=0.01,          # 10ms
                max_concurrent_operations=15       # Maximum throughput
            )
        }
        return configs.get(mode, cls())

class UnifiedResponsivenessManager:
    """
    🎯 Unified Responsiveness Manager
    
    Consolidates:
    - Memory monitoring (from aes_utils.py)
    - Streaming yields (from routes.py)
    - Background monitoring (from streaming_assembly.py)
    - Frontend resource monitoring (from index.html)
    - Async responsiveness controls
    """
    
    def __init__(self, config: Optional[ResponsivenessConfig] = None):
        self.config = config or ResponsivenessConfig.for_mode(ResponsivenessMode.DESKTOP)
        self.logger = logging.getLogger(__name__)
        
        # State tracking
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self.performance_metrics: Dict[str, List[float]] = {
            'memory_usage': [],
            'operation_times': [],
            'yield_intervals': []
        }
        
        self.lock = threading.Lock()
        self._monitoring_active = False
        
        print(f"🎯 Unified Responsiveness Manager initialized ({self.config.mode.value} mode)")
    
    def detect_environment(self) -> ResponsivenessMode:
        """Auto-detect optimal responsiveness mode"""
        try:
            import platform
            import os
            
            # Check for Termux/Android
            if 'ANDROID_ROOT' in os.environ or 'TERMUX_VERSION' in os.environ:
                return ResponsivenessMode.MOBILE
            
            # Check for server environment
            if os.environ.get('SERVER_SOFTWARE') or not hasattr(os, 'getuid'):
                return ResponsivenessMode.SERVER
            
            # Check system capabilities
            system = platform.system().lower()
            if system == 'windows':
                try:
                    import psutil
                    memory_gb = psutil.virtual_memory().total / (1024**3)
                    if memory_gb >= 16:
                        return ResponsivenessMode.DESKTOP
                    elif memory_gb >= 8:
                        return ResponsivenessMode.DESKTOP
                    else:
                        return ResponsivenessMode.MOBILE
                except ImportError:
                    return ResponsivenessMode.DESKTOP
            
            return ResponsivenessMode.DESKTOP
            
        except Exception as e:
            self.logger.warning(f"Environment detection failed: {e}")
            return ResponsivenessMode.DESKTOP
    
    def optimize_for_environment(self):
        """Auto-optimize configuration for current environment"""
        detected_mode = self.detect_environment()
        if detected_mode != self.config.mode:
            self.config = ResponsivenessConfig.for_mode(detected_mode)
            print(f"🔧 Auto-optimized for {detected_mode.value} environment")
    
    def register_operation(self, operation_id: str, operation_type: str, estimated_size: int = 0):
        """Register a new operation for monitoring"""
        with self.lock:
            self.active_operations[operation_id] = {
                'type': operation_type,
                'start_time': time.time(),
                'estimated_size': estimated_size,
                'processed_size': 0,
                'yield_count': 0,
                'last_yield': time.time()
            }
    
    def unregister_operation(self, operation_id: str):
        """Unregister completed operation"""
        with self.lock:
            if operation_id in self.active_operations:
                operation = self.active_operations.pop(operation_id)
                duration = time.time() - operation['start_time']
                self.performance_metrics['operation_times'].append(duration)
                
                # Keep only recent metrics
                if len(self.performance_metrics['operation_times']) > 100:
                    self.performance_metrics['operation_times'] = \
                        self.performance_metrics['operation_times'][-50:]
    
    def should_yield(self, operation_id: str, processed_amount: int = 0) -> bool:
        """Determine if operation should yield control"""
        with self.lock:
            if operation_id not in self.active_operations:
                return False
            
            operation = self.active_operations[operation_id]
            operation['processed_size'] += processed_amount
            
            # Check yield frequency
            if operation['yield_count'] >= self.config.upload_yield_frequency:
                return True
            
            # Check time-based yielding
            time_since_yield = time.time() - operation['last_yield']
            if time_since_yield >= self.config.monitoring_interval:
                return True
            
            return False
    
    def yield_control(self, operation_id: str, async_context: bool = False):
        """Yield control to maintain responsiveness"""
        with self.lock:
            if operation_id in self.active_operations:
                operation = self.active_operations[operation_id]
                operation['yield_count'] += 1
                operation['last_yield'] = time.time()
                
                # Reset yield counter
                if operation['yield_count'] >= self.config.upload_yield_frequency:
                    operation['yield_count'] = 0
        
        # Perform appropriate yield
        if async_context:
            # Return coroutine for async context
            return asyncio.sleep(self.config.async_sleep_duration)
        else:
            time.sleep(self.config.sync_sleep_duration)
            return None
    
    async def ayield_control(self, operation_id: str):
        """Async version of yield_control"""
        with self.lock:
            if operation_id in self.active_operations:
                operation = self.active_operations[operation_id]
                operation['yield_count'] += 1
                operation['last_yield'] = time.time()
                
                # Reset yield counter
                if operation['yield_count'] >= self.config.upload_yield_frequency:
                    operation['yield_count'] = 0
        
        await asyncio.sleep(self.config.async_sleep_duration)
    
    def get_optimal_chunk_size(self, operation_type: str) -> int:
        """Get optimal chunk size for operation type"""
        base_size = self.config.streaming_yield_size
        
        # Adjust based on operation type
        multipliers = {
            'file_streaming': 1.0,
            'encryption': 0.5,    # Smaller chunks for CPU-intensive operations
            'upload': 0.8,        # Balanced for network operations
            'download': 1.2,      # Larger chunks for downloads
            'compression': 0.3    # Very small chunks for compression
        }
        
        multiplier = multipliers.get(operation_type, 1.0)
        return int(base_size * multiplier)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        with self.lock:
            active_count = len(self.active_operations)
            avg_operation_time = 0
            
            if self.performance_metrics['operation_times']:
                recent_times = self.performance_metrics['operation_times'][-10:]
                avg_operation_time = sum(recent_times) / len(recent_times)
            
            return {
                'active_operations': active_count,
                'average_operation_time': avg_operation_time,
                'config_mode': self.config.mode.value,
                'yield_frequency': self.config.upload_yield_frequency,
                'chunk_size': self.config.streaming_yield_size
            }
    
    def start_monitoring(self):
        """Start background performance monitoring"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        
        def monitor_performance(stop_event=None):
            while self._monitoring_active and not (stop_event and stop_event.is_set()):
                try:
                    # Collect performance metrics
                    metrics = self.get_performance_metrics()
                    
                    # Log performance if needed
                    if metrics['active_operations'] > 0:
                        self.logger.debug(f"Active operations: {metrics['active_operations']}")
                    
                    # Adaptive optimization
                    self._adaptive_optimization()
                    
                    # Sleep for monitoring interval
                    time.sleep(self.config.monitoring_interval)
                    
                except Exception as e:
                    self.logger.error(f"Performance monitoring error: {e}")
                    time.sleep(1.0)
        
        thread_manager.create_thread(
            target=monitor_performance,
            name="unified_responsiveness_monitor",
            priority=ThreadPriority.LOW,
            timeout=5.0
        )
        
        print("🔍 Unified responsiveness monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._monitoring_active = False
        thread_manager.stop_thread("unified_responsiveness_monitor", timeout=3.0)
        print("🔍 Unified responsiveness monitoring stopped")
    
    def _adaptive_optimization(self):
        """Perform adaptive optimization based on metrics"""
        with self.lock:
            active_count = len(self.active_operations)
            
            # Adjust yield frequency based on load
            if active_count > 5:
                # High load - yield more frequently
                self.config.upload_yield_frequency = max(5, self.config.upload_yield_frequency - 1)
            elif active_count < 2:
                # Low load - yield less frequently
                self.config.upload_yield_frequency = min(50, self.config.upload_yield_frequency + 1)
    
    def create_streaming_generator(self, data_source, operation_id: str, chunk_size: Optional[int] = None):
        """Create a responsiveness-aware streaming generator"""
        actual_chunk_size = chunk_size or self.get_optimal_chunk_size('file_streaming')
        
        def responsive_generator():
            chunk_count = 0
            
            try:
                if hasattr(data_source, 'read'):
                    # File-like object
                    while True:
                        chunk = data_source.read(actual_chunk_size)
                        if not chunk:
                            break
                        
                        chunk_count += 1
                        yield chunk
                        
                        # Check if we should yield
                        if self.should_yield(operation_id, len(chunk)):
                            self.yield_control(operation_id)
                
                elif hasattr(data_source, '__iter__'):
                    # Iterable
                    for chunk in data_source:
                        chunk_count += 1
                        yield chunk
                        
                        if self.should_yield(operation_id, len(chunk) if hasattr(chunk, '__len__') else 1):
                            self.yield_control(operation_id)
                            
            finally:
                self.unregister_operation(operation_id)
        
        self.register_operation(operation_id, 'file_streaming')
        return responsive_generator()

# Global instance
responsiveness_manager = UnifiedResponsivenessManager()

# Convenience functions
def optimize_responsiveness_for_environment():
    """Auto-optimize responsiveness for current environment"""
    responsiveness_manager.optimize_for_environment()

def create_responsive_operation(operation_id: str, operation_type: str, estimated_size: int = 0):
    """Create a responsive operation context"""
    responsiveness_manager.register_operation(operation_id, operation_type, estimated_size)
    return operation_id

def should_yield_now(operation_id: str, processed_amount: int = 0) -> bool:
    """Check if operation should yield control now"""
    return responsiveness_manager.should_yield(operation_id, processed_amount)

def yield_if_needed(operation_id: str, async_context: bool = False):
    """Yield control if needed for responsiveness"""
    return responsiveness_manager.yield_control(operation_id, async_context)

async def async_yield_if_needed(operation_id: str):
    """Async yield control if needed"""
    await responsiveness_manager.ayield_control(operation_id)

def get_optimal_chunk_size(operation_type: str) -> int:
    """Get optimal chunk size for operation type"""
    return responsiveness_manager.get_optimal_chunk_size(operation_type)

def start_responsiveness_monitoring():
    """Start unified responsiveness monitoring"""
    responsiveness_manager.start_monitoring()

def stop_responsiveness_monitoring():
    """Stop unified responsiveness monitoring"""
    responsiveness_manager.stop_monitoring()

def get_responsiveness_metrics() -> Dict[str, Any]:
    """Get current responsiveness metrics"""
    return responsiveness_manager.get_performance_metrics()
