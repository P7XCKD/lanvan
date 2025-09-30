"""
🚀 LANVAN Cached Platform Detection System
Eliminates redundant platform detection calls for improved performance.

Provides cached platform information that's determined once at startup
and reused throughout the application lifecycle.
"""

import os
import sys
import platform
import threading
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class PlatformType(Enum):
    """Platform type enumeration"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID_TERMUX = "android_termux"
    ANDROID_OTHER = "android_other"
    OTHER = "other"

@dataclass
class PlatformInfo:
    """Cached platform information"""
    platform_type: PlatformType
    is_termux: bool
    is_android: bool
    is_mobile: bool
    is_desktop: bool
    cpu_count: int
    system_name: str
    python_version: str
    has_psutil: bool
    detection_time: float
    
    # Performance-related cached values
    recommended_chunk_size: int
    recommended_workers: int
    memory_conservative: bool
    file_io_conservative: bool

class CachedPlatformDetector:
    """
    🎯 Cached Platform Detection System
    
    Features:
    - One-time platform detection at startup
    - Cached results for all platform queries
    - Performance-optimized recommendations
    - Thread-safe access to cached data
    - Automatic fallbacks for unknown platforms
    """
    
    def __init__(self):
        self._info: Optional[PlatformInfo] = None
        self._lock = threading.Lock()
        self._detection_started = False
        
    def _detect_platform_once(self) -> PlatformInfo:
        """Perform comprehensive platform detection (called only once)"""
        start_time = time.time()
        
        # Basic system detection
        system_name = platform.system().lower()
        
        # Termux detection (most specific first)
        is_termux = self._detect_termux_environment()
        
        # Android detection (broader)
        is_android = self._detect_android_environment() or is_termux
        
        # Platform type classification
        if is_termux:
            platform_type = PlatformType.ANDROID_TERMUX
        elif is_android:
            platform_type = PlatformType.ANDROID_OTHER
        elif system_name == "windows":
            platform_type = PlatformType.WINDOWS
        elif system_name == "darwin":
            platform_type = PlatformType.MACOS
        elif system_name == "linux":
            platform_type = PlatformType.LINUX
        else:
            platform_type = PlatformType.OTHER
        
        # Mobile vs Desktop classification
        is_mobile = is_android
        is_desktop = not is_mobile
        
        # CPU detection
        cpu_count = self._detect_cpu_count()
        
        # Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        # psutil availability
        has_psutil = self._detect_psutil_availability()
        
        # Performance recommendations based on platform
        performance_config = self._calculate_performance_recommendations(
            platform_type, cpu_count, is_mobile
        )
        
        detection_time = time.time() - start_time
        
        return PlatformInfo(
            platform_type=platform_type,
            is_termux=is_termux,
            is_android=is_android,
            is_mobile=is_mobile,
            is_desktop=is_desktop,
            cpu_count=cpu_count,
            system_name=system_name,
            python_version=python_version,
            has_psutil=has_psutil,
            detection_time=detection_time,
            **performance_config
        )
    
    def _detect_termux_environment(self) -> bool:
        """Detect Termux environment specifically"""
        return any([
            "TERMUX_VERSION" in os.environ,
            "ANDROID_STORAGE" in os.environ,
            os.path.exists("/data/data/com.termux"),
            os.path.exists("/system/bin/termux-setup-storage"),
            "com.termux" in os.environ.get("PREFIX", ""),
            "/data/data/com.termux" in sys.executable
        ])
    
    def _detect_android_environment(self) -> bool:
        """Detect Android environment (broader than Termux)"""
        return any([
            "ANDROID_STORAGE" in os.environ,
            "ANDROID_ROOT" in os.environ,
            os.path.exists("/system/build.prop"),
            os.path.exists("/android_asset"),
            "android" in sys.platform.lower()
        ])
    
    def _detect_cpu_count(self) -> int:
        """Detect CPU count with fallback"""
        try:
            return os.cpu_count() or 4
        except:
            return 4
    
    def _detect_psutil_availability(self) -> bool:
        """Check if psutil is available and functional"""
        try:
            import psutil
            # Test a basic function
            psutil.cpu_count()
            return True
        except (ImportError, Exception):
            return False
    
    def _calculate_performance_recommendations(self, platform_type: PlatformType, 
                                             cpu_count: int, is_mobile: bool) -> Dict[str, Any]:
        """Calculate performance recommendations based on platform"""
        
        if platform_type == PlatformType.ANDROID_TERMUX:
            return {
                'recommended_chunk_size': 512 * 1024,  # 512KB for Termux
                'recommended_workers': min(2, cpu_count),  # Conservative for mobile
                'memory_conservative': True,
                'file_io_conservative': True
            }
        elif is_mobile:
            return {
                'recommended_chunk_size': 1024 * 1024,  # 1MB for other mobile
                'recommended_workers': min(3, cpu_count),
                'memory_conservative': True,
                'file_io_conservative': True
            }
        elif platform_type == PlatformType.WINDOWS:
            return {
                'recommended_chunk_size': 2 * 1024 * 1024,  # 2MB for Windows
                'recommended_workers': min(cpu_count, 8),
                'memory_conservative': False,
                'file_io_conservative': False
            }
        else:  # Linux, macOS, other desktop
            return {
                'recommended_chunk_size': 4 * 1024 * 1024,  # 4MB for other desktop
                'recommended_workers': min(cpu_count, 6),
                'memory_conservative': False,
                'file_io_conservative': False
            }
    
    def get_platform_info(self) -> PlatformInfo:
        """Get cached platform information (thread-safe)"""
        if self._info is None:
            with self._lock:
                # Double-check locking pattern
                if self._info is None:
                    print("🔍 Performing one-time platform detection...")
                    self._info = self._detect_platform_once()
                    self._log_detection_results()
        
        return self._info
    
    def _log_detection_results(self):
        """Log the detection results (called only once)"""
        if self._info is None:
            return
            
        info = self._info
        print(f"✅ Platform detected: {info.platform_type.value}")
        print(f"   System: {info.system_name} | Python: {info.python_version}")
        print(f"   CPUs: {info.cpu_count} | Mobile: {info.is_mobile} | Termux: {info.is_termux}")
        print(f"   Recommended chunk size: {info.recommended_chunk_size // 1024}KB")
        print(f"   Recommended workers: {info.recommended_workers}")
        print(f"   Detection time: {info.detection_time:.3f}s")
        
        if info.is_termux:
            print("🤖 Termux optimizations enabled")
        elif info.is_mobile:
            print("📱 Mobile optimizations enabled")
        else:
            print("🖥️  Desktop optimizations enabled")
    
    # Convenience methods that replace the old functions
    def is_termux_environment(self) -> bool:
        """CACHED: Check if running in Termux environment"""
        return self.get_platform_info().is_termux
    
    def is_android_environment(self) -> bool:
        """CACHED: Check if running in Android environment"""
        return self.get_platform_info().is_android
    
    def is_mobile_environment(self) -> bool:
        """CACHED: Check if running in mobile environment"""
        return self.get_platform_info().is_mobile
    
    def get_recommended_chunk_size(self) -> int:
        """CACHED: Get recommended chunk size for platform"""
        return self.get_platform_info().recommended_chunk_size
    
    def get_recommended_workers(self) -> int:
        """CACHED: Get recommended worker count for platform"""
        return self.get_platform_info().recommended_workers
    
    def should_use_conservative_memory(self) -> bool:
        """CACHED: Check if conservative memory usage is recommended"""
        return self.get_platform_info().memory_conservative
    
    def should_use_conservative_file_io(self) -> bool:
        """CACHED: Check if conservative file I/O is recommended"""
        return self.get_platform_info().file_io_conservative
    
    def get_cpu_count(self) -> int:
        """CACHED: Get CPU count"""
        return self.get_platform_info().cpu_count
    
    def has_psutil(self) -> bool:
        """CACHED: Check if psutil is available"""
        return self.get_platform_info().has_psutil
    
    def get_platform_summary(self) -> Dict[str, Any]:
        """Get a summary of platform information for debugging"""
        info = self.get_platform_info()
        return {
            'platform_type': info.platform_type.value,
            'is_termux': info.is_termux,
            'is_android': info.is_android,
            'is_mobile': info.is_mobile,
            'cpu_count': info.cpu_count,
            'system_name': info.system_name,
            'python_version': info.python_version,
            'has_psutil': info.has_psutil,
            'recommended_chunk_size': info.recommended_chunk_size,
            'recommended_workers': info.recommended_workers,
            'memory_conservative': info.memory_conservative,
            'file_io_conservative': info.file_io_conservative,
            'detection_time': info.detection_time
        }

# Global cached platform detector instance
platform_detector = CachedPlatformDetector()

# Convenience functions that use the cached detector
def is_termux_environment() -> bool:
    """OPTIMIZED: Cached Termux environment detection"""
    return platform_detector.is_termux_environment()

def is_android_environment() -> bool:
    """OPTIMIZED: Cached Android environment detection"""
    return platform_detector.is_android_environment()

def is_mobile_environment() -> bool:
    """OPTIMIZED: Cached mobile environment detection"""
    return platform_detector.is_mobile_environment()

def get_platform_info() -> PlatformInfo:
    """OPTIMIZED: Get cached platform information"""
    return platform_detector.get_platform_info()

def get_recommended_chunk_size() -> int:
    """OPTIMIZED: Get platform-optimized chunk size"""
    return platform_detector.get_recommended_chunk_size()

def get_recommended_workers() -> int:
    """OPTIMIZED: Get platform-optimized worker count"""
    return platform_detector.get_recommended_workers()

def should_use_conservative_mode() -> bool:
    """OPTIMIZED: Check if conservative resource usage is recommended"""
    return platform_detector.should_use_conservative_memory()

def get_platform_summary() -> Dict[str, Any]:
    """OPTIMIZED: Get platform summary for debugging"""
    return platform_detector.get_platform_summary()
