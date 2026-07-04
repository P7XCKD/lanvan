"""
[START] Lightweight Background Task Manager
Prevents task accumulation without performance impact

Design Principles:
- Zero performance overhead during normal operation
- Automatic cleanup without blocking main operations
- Weak references to prevent memory leaks
- Configurable limits for safety
"""
import asyncio
import weakref
import time
import logging
from typing import Dict, Set, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor
import secrets

logger = logging.getLogger(__name__)

class LightweightTaskManager:
    """
    [TARGET] Ultra-lightweight task manager that prevents accumulation
    without any performance impact on normal operations
    """
    
    def __init__(self, max_concurrent_tasks: int = 50, cleanup_interval: int = 300):
        # Use weak references to prevent memory leaks
        self._active_tasks = weakref.WeakSet()
        self._task_count = 0
        self._max_concurrent = max_concurrent_tasks
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._executor = None  # Lazy initialization
        
        # Performance metrics (lightweight counters)
        self._total_submitted = 0
        self._total_completed = 0
        self._peak_concurrent = 0
    
    def submit_task(self, coro, name: Optional[str] = None) -> Optional[asyncio.Task]:
        """
        [START] Submit async task with automatic cleanup
        Returns None if task limit exceeded (graceful degradation)
        """
        try:
            # Quick limit check (prevents runaway task creation)
            if self._task_count >= self._max_concurrent:
                logger.warning(f"Task limit reached ({self._max_concurrent}), skipping task: {name}")
                return None
            
            # Create task with automatic cleanup callback
            task = asyncio.create_task(coro, name=name)
            self._active_tasks.add(task)
            self._task_count += 1
            self._total_submitted += 1
            
            # Update peak concurrent tracking (lightweight)
            if self._task_count > self._peak_concurrent:
                self._peak_concurrent = self._task_count
            
            # Add completion callback (lightweight cleanup)
            task.add_done_callback(self._task_done_callback)
            
            # Less frequent cleanup (every 20 tasks instead of every task)
            if self._total_submitted % 20 == 0:
                self._maybe_cleanup()
            
            return task
            
        except Exception as e:
            logger.error(f"Error submitting task {name}: {e}")
            return None
    
    def submit_sync_task(self, func: Callable, *args, **kwargs) -> Optional[asyncio.Future]:
        """
        [RETRY] Submit synchronous function to thread pool
        Returns None if task limit exceeded
        """
        try:
            if self._task_count >= self._max_concurrent:
                logger.warning(f"Task limit reached, skipping sync task: {func.__name__}")
                return None
            
            # Lazy initialization of thread pool
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="LTM")
            
            # Submit to thread pool
            future = asyncio.get_event_loop().run_in_executor(
                self._executor, func, *args, **kwargs
            )
            
            # Track as active task
            self._task_count += 1
            self._total_submitted += 1
            future.add_done_callback(lambda f: self._sync_task_done())
            
            return future
            
        except Exception as e:
            logger.error(f"Error submitting sync task {func.__name__}: {e}")
            return None
    
    def _task_done_callback(self, task: asyncio.Task):
        """[CLEAN] Lightweight task completion callback"""
        self._task_count = max(0, self._task_count - 1)
        self._total_completed += 1
        
        # Log exceptions (but don't raise them)
        if not task.cancelled() and task.exception():
            logger.error(f"Task {task.get_name()} failed: {task.exception()}")
    
    def _sync_task_done(self):
        """[CLEAN] Sync task completion callback"""
        self._task_count = max(0, self._task_count - 1)
        self._total_completed += 1
    
    def _maybe_cleanup(self):
        """
        [CLEAN] Opportunistic cleanup - only runs if enough time has passed
        No blocking operations, no performance impact
        """
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._last_cleanup = now
            self._cleanup_completed_tasks()
    
    def _cleanup_completed_tasks(self):
        """
        [DEL] Remove completed tasks from tracking
        Uses weak references so this is very lightweight
        """
        try:
            # WeakSet automatically removes dead references
            # Just update our counter to match reality
            actual_active = len([t for t in self._active_tasks if not t.done()])
            if actual_active != self._task_count:
                logger.debug(f"Corrected task count: {self._task_count} -> {actual_active}")
                self._task_count = actual_active
                
        except Exception as e:
            logger.debug(f"Cleanup error (non-critical): {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """[STATS] Get performance statistics"""
        return {
            "active_tasks": self._task_count,
            "total_submitted": self._total_submitted,
            "total_completed": self._total_completed,
            "peak_concurrent": self._peak_concurrent,
            "max_concurrent": self._max_concurrent,
            "success_rate": (
                self._total_completed / max(1, self._total_submitted) * 100
            )
        }
    
    async def shutdown(self):
        """ Graceful shutdown with timeout"""
        try:
            logger.info(f"Shutting down TaskManager - {self._task_count} active tasks")
            
            # Cancel all active tasks
            for task in list(self._active_tasks):
                if not task.done():
                    task.cancel()
            
            # Wait briefly for cancellation
            if self._active_tasks:
                await asyncio.sleep(0.1)
            
            # Shutdown thread pool
            if self._executor:
                self._executor.shutdown(wait=False)
                
            logger.info("TaskManager shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during TaskManager shutdown: {e}")

#  Global task manager instance
task_manager = LightweightTaskManager()

def submit_background_task(coro, name: Optional[str] = None) -> Optional[asyncio.Task]:
    """
    [START] Global function for submitting background tasks
    
    Usage:
        submit_background_task(scan_file_async(path), "file_scan")
    """
    return task_manager.submit_task(coro, name)

def submit_sync_background_task(func: Callable, *args, **kwargs) -> Optional[asyncio.Future]:
    """
    [RETRY] Global function for submitting sync tasks to thread pool
    
    Usage:
        submit_sync_background_task(heavy_computation, arg1, arg2)
    """
    return task_manager.submit_sync_task(func, *args, **kwargs)

def get_task_stats() -> Dict[str, Any]:
    """[STATS] Get background task statistics"""
    return task_manager.get_stats()

async def shutdown_task_manager():
    """ Shutdown task manager"""
    await task_manager.shutdown()