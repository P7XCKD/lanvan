"""
[LOCK] Advanced File Locking System for Lanvan
Cross-platform file locking to prevent race conditions in concurrent file operations.

Key Features:
- Platform-specific file locking (Windows, Linux, Android/Termux)
- Async context managers for automatic lock cleanup
- Retry logic with exponential backoff
- Timeout handling for deadlock prevention
- Resource leak prevention with proper cleanup
"""

import os
import asyncio
import time
import contextlib
from pathlib import Path
from typing import Optional, Union, AsyncIterator
import logging

from app.utils.termux_compat import is_android_environment

# Platform detection
IS_WINDOWS = os.name == 'nt'
IS_ANDROID = is_android_environment()
PLATFORM_NAME = "Windows" if IS_WINDOWS else "Android/Termux" if IS_ANDROID else "Linux/Unix"

# Configure logging
logger = logging.getLogger(__name__)

class FileLockError(Exception):
    """Exception raised when file locking operations fail"""
    pass

class FileLockTimeout(FileLockError):
    """Exception raised when file lock timeout is exceeded"""
    pass

class CrossPlatformFileLock:
    """
    [LOCK] Cross-platform file locking implementation
    """
    
    def __init__(
        self, 
        lock_file: Union[str, Path], 
        timeout: float = 30.0,
        retry_interval: float = 0.1
    ):
        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.lock_handle = None
        self.is_locked = False
        self._lock_acquired_time = None
        
        # Create lock file directory if it doesn't exist
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        
    async def acquire(self) -> bool:
        """
        [TARGET] Acquire file lock with platform-specific implementation
        """
        start_time = time.time()
        
        logger.debug(f"[{PLATFORM_NAME}] Attempting to acquire lock: {self.lock_file}")
        
        while time.time() - start_time < self.timeout:
            try:
                if IS_WINDOWS:
                    success = await self._acquire_windows_lock()
                else:
                    success = await self._acquire_unix_lock()
                
                if success:
                    self.is_locked = True
                    self._lock_acquired_time = time.time()
                    logger.debug(f"[OK] [{PLATFORM_NAME}] Lock acquired: {self.lock_file}")
                    return True
                    
            except Exception as e:
                logger.warning(f"[WARN] [{PLATFORM_NAME}] Lock acquisition error: {e}")
            
            # Wait before retry
            await asyncio.sleep(self.retry_interval)
            
            # Increase retry interval gradually (exponential backoff)
            self.retry_interval = min(self.retry_interval * 1.2, 1.0)
        
        # Timeout reached
        elapsed = time.time() - start_time
        error_msg = f"Lock timeout after {elapsed:.1f}s on {PLATFORM_NAME}: {self.lock_file}"
        logger.error(f"[ERR] {error_msg}")
        raise FileLockTimeout(error_msg)
    
    async def _acquire_windows_lock(self) -> bool:
        """Windows-specific file locking using exclusive file access"""
        try:
            import msvcrt
            
            # Try to open file in exclusive mode
            self.lock_handle = await asyncio.to_thread(
                open, self.lock_file, 'w+b'
            )
            
            # Apply Windows file lock
            await asyncio.to_thread(
                msvcrt.locking, 
                self.lock_handle.fileno(), 
                msvcrt.LK_NBLCK,  # Non-blocking exclusive lock
                1
            )
            
            # Write lock metadata
            lock_info = f"LOCKED:{os.getpid()}:{time.time()}\n".encode()
            await asyncio.to_thread(self.lock_handle.write, lock_info)
            await asyncio.to_thread(self.lock_handle.flush)
            
            return True
            
        except (OSError, IOError, ImportError) as e:
            # Clean up on failure
            if self.lock_handle:
                try:
                    await asyncio.to_thread(self.lock_handle.close)
                except Exception:
                    pass
                self.lock_handle = None
            return False
    
    async def _acquire_unix_lock(self) -> bool:
        """Unix/Linux/Android-specific file locking using flock"""
        try:
            # Import fcntl with error handling for platforms that don't support it
            try:
                import fcntl
                # Check if required constants exist using getattr
                LOCK_EX = getattr(fcntl, 'LOCK_EX', None)
                LOCK_NB = getattr(fcntl, 'LOCK_NB', None)
                flock_func = getattr(fcntl, 'flock', None)
                
                if not all([LOCK_EX is not None, LOCK_NB is not None, flock_func is not None]):
                    return await self._acquire_fallback_lock()
            except ImportError:
                return await self._acquire_fallback_lock()
            
            # Try to create lock file
            self.lock_handle = await asyncio.to_thread(
                open, self.lock_file, 'w+b'
            )
            
            # Apply Unix file lock (non-blocking) - now we know all values are not None
            lock_flags = LOCK_EX | LOCK_NB  # type: ignore
            file_descriptor = self.lock_handle.fileno()
            
            # Use lambda to properly pass arguments to flock
            await asyncio.to_thread(
                lambda: flock_func(file_descriptor, lock_flags)  # type: ignore
            )
            
            # Write lock metadata
            lock_info = f"LOCKED:{os.getpid()}:{time.time()}\n".encode()
            await asyncio.to_thread(self.lock_handle.write, lock_info)
            await asyncio.to_thread(self.lock_handle.flush)
            
            return True
            
        except (OSError, IOError, ImportError, BlockingIOError) as e:
            # Clean up on failure
            if self.lock_handle:
                try:
                    await asyncio.to_thread(self.lock_handle.close)
                except Exception:
                    pass
                self.lock_handle = None
            return False
    
    async def _acquire_fallback_lock(self) -> bool:
        """Fallback file locking using exclusive file creation"""
        try:
            # Use atomic file creation as lock mechanism
            if self.lock_file.exists():
                # Check if lock is stale (older than 5 minutes)
                try:
                    lock_age = time.time() - self.lock_file.stat().st_mtime
                    if lock_age > 300:  # 5 minutes
                        await asyncio.to_thread(self.lock_file.unlink)
                        logger.debug(f"[CLEAN] Removed stale lock file: {self.lock_file}")
                    else:
                        return False  # Valid lock exists
                except Exception:
                    pass
            
            # Try to create lock file atomically
            self.lock_handle = await asyncio.to_thread(
                open, self.lock_file, 'x+b'  # Exclusive creation
            )
            
            # Write lock metadata
            lock_info = f"LOCKED:{os.getpid()}:{time.time()}\n".encode()
            await asyncio.to_thread(self.lock_handle.write, lock_info)
            await asyncio.to_thread(self.lock_handle.flush)
            
            return True
            
        except FileExistsError:
            # Lock file already exists
            return False
        except Exception as e:
            # Clean up on failure
            if self.lock_handle:
                try:
                    await asyncio.to_thread(self.lock_handle.close)
                except Exception:
                    pass
                self.lock_handle = None
            return False
    
    async def release(self) -> None:
        """
        [UNLOCK] Release file lock and clean up resources
        """
        if not self.is_locked:
            return
            
        try:
            if self.lock_handle:
                # Close file handle (automatically releases lock)
                await asyncio.to_thread(self.lock_handle.close)
                self.lock_handle = None
            
            # Remove lock file
            if self.lock_file.exists():
                await asyncio.to_thread(self.lock_file.unlink)
            
            self.is_locked = False
            
            # Calculate lock duration for debugging
            if self._lock_acquired_time:
                duration = time.time() - self._lock_acquired_time
                logger.debug(f"[UNLOCK] [{PLATFORM_NAME}] Lock released after {duration:.2f}s: {self.lock_file}")
            
        except Exception as e:
            logger.warning(f"[WARN] [{PLATFORM_NAME}] Error releasing lock: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.release()

class FileOperationLock:
    """
    [TARGET] High-level file operation locking for upload operations
    """
    
    def __init__(self, base_path: Union[str, Path]):
        self.base_path = Path(base_path)
        self.locks_dir = self.base_path.parent / ".locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
    
    @contextlib.asynccontextmanager
    async def upload_lock(
        self, 
        filename: str, 
        timeout: float = 30.0
    ) -> AsyncIterator[CrossPlatformFileLock]:
        """
        [LOCK] Context manager for upload file locking
        """
        # Create lock file based on target filename
        lock_file = self.locks_dir / f"{filename}.upload.lock"
        
        lock = CrossPlatformFileLock(
            lock_file=lock_file,
            timeout=timeout,
            retry_interval=0.1
        )
        
        try:
            async with lock:
                logger.info(f"[LOCK] [{PLATFORM_NAME}] Upload lock acquired for: {filename}")
                yield lock
        finally:
            logger.info(f"[UNLOCK] [{PLATFORM_NAME}] Upload lock released for: {filename}")
    
    @contextlib.asynccontextmanager 
    async def directory_lock(
        self, 
        directory: Union[str, Path], 
        timeout: float = 10.0
    ) -> AsyncIterator[CrossPlatformFileLock]:
        """
        [LOCK] Context manager for directory operation locking
        """
        dir_path = Path(directory)
        lock_file = self.locks_dir / f"{dir_path.name}.dir.lock"
        
        lock = CrossPlatformFileLock(
            lock_file=lock_file,
            timeout=timeout,
            retry_interval=0.05
        )
        
        try:
            async with lock:
                logger.info(f"[LOCK] [{PLATFORM_NAME}] Directory lock acquired for: {dir_path}")
                yield lock
        finally:
            logger.info(f"[UNLOCK] [{PLATFORM_NAME}] Directory lock released for: {dir_path}")

# Global file operation lock manager
file_lock_manager = None

def get_file_lock_manager(upload_folder: Path) -> FileOperationLock:
    """Get or create global file lock manager"""
    global file_lock_manager
    if file_lock_manager is None:
        file_lock_manager = FileOperationLock(upload_folder)
    return file_lock_manager

async def cleanup_stale_locks(locks_dir: Path, max_age_seconds: int = 300):
    """
    [CLEAN] Clean up stale lock files (older than max_age_seconds)
    """
    try:
        if not locks_dir.exists():
            return
            
        current_time = time.time()
        cleaned_count = 0
        
        for lock_file in locks_dir.glob("*.lock"):
            try:
                # Check if lock file is stale
                file_age = current_time - lock_file.stat().st_mtime
                
                if file_age > max_age_seconds:
                    # Try to remove stale lock
                    await asyncio.to_thread(lock_file.unlink)
                    cleaned_count += 1
                    logger.info(f"[CLEAN] [{PLATFORM_NAME}] Removed stale lock: {lock_file.name}")
                    
            except Exception as e:
                logger.warning(f"[WARN] [{PLATFORM_NAME}] Error cleaning lock {lock_file.name}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"[CLEAN] [{PLATFORM_NAME}] Cleaned {cleaned_count} stale lock files")
            
    except Exception as e:
        logger.error(f"[ERR] [{PLATFORM_NAME}] Error during lock cleanup: {e}")

# Initialize logging
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)