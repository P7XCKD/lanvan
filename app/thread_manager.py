"""
🔧 LANVAN Thread Management System
Centralized thread management to prevent resource leaks and zombie processes.
"""

import threading
import time
import signal
import atexit
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging

class ThreadPriority(Enum):
    """Thread priority levels for shutdown order"""
    CRITICAL = 1    # Shutdown handlers, resource cleanup
    HIGH = 2        # Core services (mDNS, streaming)
    NORMAL = 3      # Background workers, monitoring
    LOW = 4         # Non-essential services

@dataclass
class ManagedThread:
    """Wrapper for managed thread with metadata"""
    thread: threading.Thread
    name: str
    priority: ThreadPriority
    stop_event: threading.Event
    stop_callback: Optional[Callable] = None
    timeout: float = 5.0
    created_at: float = 0.0
    
    def __post_init__(self):
        self.created_at = time.time()

class ThreadManager:
    """
    🎯 Centralized Thread Manager
    
    Features:
    - Automatic thread registration and tracking
    - Graceful shutdown with priority ordering
    - Resource leak prevention
    - Zombie process cleanup
    - Thread health monitoring
    """
    
    def __init__(self):
        self.threads: Dict[str, ManagedThread] = {}
        self.shutdown_requested = False
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Register shutdown handlers
        atexit.register(self.shutdown_all)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        print("🔧 Thread Manager initialized")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Signal {signum} received - initiating thread shutdown")
        self.shutdown_all()
    
    def create_thread(self, 
                     target: Callable,
                     name: str,
                     priority: ThreadPriority = ThreadPriority.NORMAL,
                     args: tuple = (),
                     kwargs: Optional[dict] = None,
                     stop_callback: Optional[Callable] = None,
                     timeout: float = 5.0,
                     daemon: bool = True) -> threading.Event:
        """
        Create and register a managed thread
        
        Returns:
            threading.Event: Stop event for the thread
        """
        if kwargs is None:
            kwargs = {}
        
        stop_event = threading.Event()
        
        # Create wrapper function that respects stop_event
        def managed_target(*args, **kwargs):
            try:
                if hasattr(target, '__call__'):
                    # Pass stop_event to target if it accepts it
                    try:
                        target(*args, stop_event=stop_event, **kwargs)
                    except TypeError:
                        # Target doesn't accept stop_event parameter
                        target(*args, **kwargs)
                else:
                    self.logger.error(f"Thread {name}: target is not callable")
            except Exception as e:
                self.logger.error(f"Thread {name} error: {e}")
            finally:
                # Auto-cleanup on thread completion
                self._cleanup_thread(name)
        
        thread = threading.Thread(
            target=managed_target,
            name=name,
            args=args,
            kwargs=kwargs,
            daemon=daemon
        )
        
        managed_thread = ManagedThread(
            thread=thread,
            name=name,
            priority=priority,
            stop_event=stop_event,
            stop_callback=stop_callback,
            timeout=timeout
        )
        
        with self.lock:
            if name in self.threads:
                self.logger.warning(f"Thread {name} already exists - stopping old thread")
                self.stop_thread(name)
            
            self.threads[name] = managed_thread
        
        thread.start()
        self.logger.info(f"Started thread: {name} (priority: {priority.name})")
        
        return stop_event
    
    def stop_thread(self, name: str, timeout: Optional[float] = None) -> bool:
        """Stop a specific thread gracefully"""
        with self.lock:
            if name not in self.threads:
                self.logger.warning(f"Thread {name} not found")
                return False
            
            managed_thread = self.threads[name]
        
        # Use thread-specific timeout or default
        actual_timeout = timeout or managed_thread.timeout
        
        try:
            # Signal stop
            managed_thread.stop_event.set()
            
            # Call stop callback if provided
            if managed_thread.stop_callback:
                try:
                    managed_thread.stop_callback()
                except Exception as e:
                    self.logger.error(f"Stop callback error for {name}: {e}")
            
            # Wait for thread to finish
            if managed_thread.thread.is_alive():
                managed_thread.thread.join(timeout=actual_timeout)
                
                if managed_thread.thread.is_alive():
                    self.logger.warning(f"Thread {name} did not stop within {actual_timeout}s")
                    return False
            
            self.logger.info(f"Stopped thread: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping thread {name}: {e}")
            return False
        finally:
            self._cleanup_thread(name)
    
    def _cleanup_thread(self, name: str):
        """Remove thread from tracking"""
        with self.lock:
            if name in self.threads:
                del self.threads[name]
    
    def shutdown_all(self, timeout: float = 30.0) -> bool:
        """
        Shutdown all threads in priority order
        
        Returns:
            bool: True if all threads stopped gracefully
        """
        if self.shutdown_requested:
            return True
        
        self.shutdown_requested = True
        start_time = time.time()
        
        self.logger.info("Starting graceful thread shutdown...")
        
        # Get threads sorted by priority
        with self.lock:
            threads_by_priority = sorted(
                self.threads.items(),
                key=lambda x: x[1].priority.value
            )
        
        success = True
        remaining_timeout = timeout
        
        # Stop threads by priority
        for priority in ThreadPriority:
            priority_threads = [
                (name, thread) for name, thread in threads_by_priority
                if thread.priority == priority
            ]
            
            if not priority_threads:
                continue
                
            self.logger.info(f"Stopping {priority.name} priority threads...")
            
            # Calculate timeout per thread for this priority level
            thread_timeout = min(remaining_timeout / len(priority_threads), 5.0)
            
            for name, managed_thread in priority_threads:
                thread_start = time.time()
                
                if not self.stop_thread(name, thread_timeout):
                    success = False
                
                # Update remaining timeout
                elapsed = time.time() - thread_start
                remaining_timeout = max(0, remaining_timeout - elapsed)
                
                if remaining_timeout <= 0:
                    self.logger.warning("Thread shutdown timeout exceeded")
                    break
        
        # Final cleanup check
        with self.lock:
            active_threads = [name for name, thread in self.threads.items() 
                            if thread.thread.is_alive()]
        
        if active_threads:
            self.logger.warning(f"Some threads still active: {active_threads}")
            success = False
        else:
            self.logger.info("All threads stopped successfully")
        
        total_time = time.time() - start_time
        self.logger.info(f"Thread shutdown completed in {total_time:.2f}s")
        
        return success
    
    def get_thread_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all managed threads"""
        status = {}
        
        with self.lock:
            for name, managed_thread in self.threads.items():
                status[name] = {
                    'alive': managed_thread.thread.is_alive(),
                    'priority': managed_thread.priority.name,
                    'uptime': time.time() - managed_thread.created_at,
                    'daemon': managed_thread.thread.daemon,
                    'stop_requested': managed_thread.stop_event.is_set()
                }
        
        return status
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on thread system"""
        status = self.get_thread_status()
        
        total_threads = len(status)
        alive_threads = sum(1 for s in status.values() if s['alive'])
        zombie_threads = sum(1 for s in status.values() if not s['alive'])
        
        return {
            'healthy': zombie_threads == 0,
            'total_threads': total_threads,
            'alive_threads': alive_threads,
            'zombie_threads': zombie_threads,
            'threads': status
        }
    
    def cleanup_zombies(self):
        """Remove zombie threads from tracking"""
        zombies = []
        
        with self.lock:
            for name, managed_thread in list(self.threads.items()):
                if not managed_thread.thread.is_alive():
                    zombies.append(name)
                    del self.threads[name]
        
        if zombies:
            self.logger.info(f"Cleaned up zombie threads: {zombies}")
        
        return len(zombies)

# Global thread manager instance
thread_manager = ThreadManager()

# Convenience functions
def create_managed_thread(target: Callable, name: str, **kwargs) -> threading.Event:
    """Create a managed thread (convenience function)"""
    return thread_manager.create_thread(target, name, **kwargs)

def stop_managed_thread(name: str, timeout: Optional[float] = None) -> bool:
    """Stop a managed thread (convenience function)"""
    return thread_manager.stop_thread(name, timeout)

def shutdown_all_threads(timeout: float = 30.0) -> bool:
    """Shutdown all managed threads (convenience function)"""
    return thread_manager.shutdown_all(timeout)

def get_thread_health() -> Dict[str, Any]:
    """Get thread system health status (convenience function)"""
    return thread_manager.health_check()
