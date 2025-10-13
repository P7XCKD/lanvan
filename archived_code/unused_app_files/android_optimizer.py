"""
🤖 Android/Termux Optimizer Module
Provides optimization functions for Android and Termux environments.
"""

import gc
import psutil
import platform
from typing import Dict, Any, Optional
from pathlib import Path


class UniversalOptimizer:
    """Universal optimizer for cross-platform performance"""
    
    def __init__(self):
        self.upload_active = False
        self.platform_info = self._detect_platform()
    
    def _detect_platform(self) -> Dict[str, Any]:
        """Detect current platform and capabilities"""
        return {
            "platform": platform.system(),
            "machine": platform.machine(),
            "is_android": "termux" in str(Path.home()).lower() or "android" in platform.platform().lower(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available
        }
    
    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform information"""
        return self.platform_info
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        return self.get_platform_info()
    
    def get_adaptive_chunk_size(self, file_size: int) -> int:
        """Get adaptive chunk size"""
        return get_adaptive_chunk_size(file_size)
    
    def memory_cleanup(self, force: bool = False) -> None:
        """Perform memory cleanup"""
        if force or self.platform_info.get("is_android", False):
            gc.collect()
    
    def get_optimal_chunk_size(self, file_size: int) -> int:
        """Get optimal chunk size based on platform and file size"""
        available_memory = psutil.virtual_memory().available
        
        # Conservative chunk sizing for Android/Termux
        if self.platform_info.get("is_android", False):
            if available_memory < 1024 * 1024 * 1024:  # Less than 1GB RAM
                return min(1024 * 1024, file_size // 10)  # 1MB max
            else:
                return min(8 * 1024 * 1024, file_size // 5)  # 8MB max
        
        # Desktop sizing
        if file_size < 10 * 1024 * 1024:  # < 10MB
            return 1024 * 1024  # 1MB
        elif file_size < 100 * 1024 * 1024:  # < 100MB
            return 8 * 1024 * 1024  # 8MB
        else:
            return 32 * 1024 * 1024  # 32MB


# Global instance
universal_optimizer = UniversalOptimizer()


def optimize_for_upload(file_size: int) -> Dict[str, Any]:
    """Optimize settings for file upload"""
    chunk_size = universal_optimizer.get_optimal_chunk_size(file_size)
    
    return {
        "chunk_size": chunk_size,
        "concurrent_chunks": 2 if universal_optimizer.platform_info.get("is_android", False) else 4,
        "memory_management": True
    }


def get_adaptive_chunk_size(file_size: int, available_memory: Optional[int] = None) -> int:
    """Get adaptive chunk size based on file size and available memory"""
    if available_memory is None:
        available_memory = psutil.virtual_memory().available
    
    # Ensure chunk size doesn't exceed 10% of available memory
    max_chunk = available_memory // 10
    optimal_chunk = universal_optimizer.get_optimal_chunk_size(file_size)
    
    return min(optimal_chunk, max_chunk)


def should_run_gc() -> bool:
    """Determine if garbage collection should be run"""
    available_memory = psutil.virtual_memory().available
    total_memory = psutil.virtual_memory().total
    
    # Run GC if less than 20% memory available
    return (available_memory / total_memory) < 0.2