"""
🚀 Simplified Chunk Management System
Eliminates complex chunk size adaptation logic and CPU overhead

Key Optimizations:
- Single source of truth for chunk sizes
- Pre-calculated chunk sizes based on platform
- Eliminates runtime calculations and adaptations
- Reduced CPU overhead from complex logic
- Platform-optimized defaults with no runtime adjustment
"""

from dataclasses import dataclass
from typing import Dict, Optional, Any
from enum import Enum
from app.platform_detector import platform_detector


class ChunkProfile(Enum):
    """Simplified chunk profiles based on device capabilities"""
    MOBILE_CONSERVATIVE = "mobile_conservative"    # Android/Termux devices
    DESKTOP_BALANCED = "desktop_balanced"          # Standard desktop/laptop
    DESKTOP_PERFORMANCE = "desktop_performance"    # High-end desktop systems
    SERVER_OPTIMIZED = "server_optimized"          # Server environments


@dataclass
class ChunkConfiguration:
    """Fixed chunk configuration for a profile - no runtime adaptation"""
    upload_chunk_size: int      # For file uploads
    download_chunk_size: int    # For file downloads  
    encryption_chunk_size: int  # For encryption operations
    streaming_chunk_size: int   # For streaming operations
    zip_chunk_size: int         # For ZIP operations
    
    # Frontend configuration
    frontend_chunk_size: int    # Fixed chunk size for frontend uploads
    frontend_min_size: int      # Minimum chunk size (safety)
    frontend_max_size: int      # Maximum chunk size (safety)
    
    # Memory and performance settings
    memory_check_frequency: int # How often to check memory (0 = disabled)
    adaptation_disabled: bool   # Disable all runtime adaptation


class SimplifiedChunkManager:
    """
    🎯 Simplified chunk management with zero runtime overhead
    
    Features:
    - Pre-calculated chunk sizes based on device profile
    - No runtime adaptation or complex calculations
    - Single source of truth for all chunk operations
    - Platform-optimized defaults
    - Eliminates CPU overhead from chunk size calculations
    """
    
    def __init__(self):
        self.platform_info = platform_detector.get_platform_info()
        self.profile = self._determine_profile()
        self.config = self._get_profile_config()
        
        print(f"🚀 Simplified chunk manager initialized")
        print(f"   Profile: {self.profile.value}")
        print(f"   Upload chunks: {self.config.upload_chunk_size // (1024*1024)}MB")
        print(f"   Download chunks: {self.config.download_chunk_size // (1024*1024)}MB")
        print(f"   Frontend chunks: {self.config.frontend_chunk_size // (1024*1024)}MB")
        print(f"   Runtime adaptation: {'DISABLED' if self.config.adaptation_disabled else 'ENABLED'}")
    
    def _determine_profile(self) -> ChunkProfile:
        """Determine the optimal chunk profile for this platform"""
        if self.platform_info.is_android or self.platform_info.is_termux:
            return ChunkProfile.MOBILE_CONSERVATIVE
        elif self.platform_info.cpu_count >= 12 and not self.platform_info.memory_conservative:
            return ChunkProfile.DESKTOP_PERFORMANCE
        elif self.platform_info.cpu_count >= 4:
            return ChunkProfile.DESKTOP_BALANCED
        else:
            return ChunkProfile.MOBILE_CONSERVATIVE
    
    def _get_profile_config(self) -> ChunkConfiguration:
        """Get the fixed configuration for the current profile"""
        configs = {
            ChunkProfile.MOBILE_CONSERVATIVE: ChunkConfiguration(
                upload_chunk_size=1 * 1024 * 1024,      # 1MB uploads
                download_chunk_size=2 * 1024 * 1024,     # 2MB downloads
                encryption_chunk_size=512 * 1024,        # 512KB encryption
                streaming_chunk_size=1 * 1024 * 1024,    # 1MB streaming
                zip_chunk_size=1 * 1024 * 1024,          # 1MB ZIP
                frontend_chunk_size=2 * 1024 * 1024,     # 2MB frontend
                frontend_min_size=512 * 1024,             # 512KB minimum
                frontend_max_size=8 * 1024 * 1024,       # 8MB maximum
                memory_check_frequency=0,                 # Disabled for performance
                adaptation_disabled=True                   # No runtime changes
            ),
            
            ChunkProfile.DESKTOP_BALANCED: ChunkConfiguration(
                upload_chunk_size=4 * 1024 * 1024,      # 4MB uploads
                download_chunk_size=8 * 1024 * 1024,     # 8MB downloads
                encryption_chunk_size=2 * 1024 * 1024,   # 2MB encryption
                streaming_chunk_size=4 * 1024 * 1024,    # 4MB streaming
                zip_chunk_size=4 * 1024 * 1024,          # 4MB ZIP
                frontend_chunk_size=8 * 1024 * 1024,     # 8MB frontend
                frontend_min_size=2 * 1024 * 1024,       # 2MB minimum
                frontend_max_size=32 * 1024 * 1024,      # 32MB maximum
                memory_check_frequency=0,                 # Disabled for performance
                adaptation_disabled=True                   # No runtime changes
            ),
            
            ChunkProfile.DESKTOP_PERFORMANCE: ChunkConfiguration(
                upload_chunk_size=8 * 1024 * 1024,      # 8MB uploads
                download_chunk_size=16 * 1024 * 1024,    # 16MB downloads
                encryption_chunk_size=4 * 1024 * 1024,   # 4MB encryption
                streaming_chunk_size=8 * 1024 * 1024,    # 8MB streaming
                zip_chunk_size=8 * 1024 * 1024,          # 8MB ZIP
                frontend_chunk_size=16 * 1024 * 1024,    # 16MB frontend
                frontend_min_size=4 * 1024 * 1024,       # 4MB minimum
                frontend_max_size=64 * 1024 * 1024,      # 64MB maximum
                memory_check_frequency=0,                 # Disabled for performance
                adaptation_disabled=True                   # No runtime changes
            ),
            
            ChunkProfile.SERVER_OPTIMIZED: ChunkConfiguration(
                upload_chunk_size=16 * 1024 * 1024,     # 16MB uploads
                download_chunk_size=32 * 1024 * 1024,    # 32MB downloads
                encryption_chunk_size=8 * 1024 * 1024,   # 8MB encryption
                streaming_chunk_size=16 * 1024 * 1024,   # 16MB streaming
                zip_chunk_size=16 * 1024 * 1024,         # 16MB ZIP
                frontend_chunk_size=32 * 1024 * 1024,    # 32MB frontend
                frontend_min_size=8 * 1024 * 1024,       # 8MB minimum
                frontend_max_size=128 * 1024 * 1024,     # 128MB maximum
                memory_check_frequency=0,                 # Disabled for performance
                adaptation_disabled=True                   # No runtime changes
            )
        }
        
        return configs[self.profile]
    
    def get_chunk_size(self, operation_type: str) -> int:
        """
        Get fixed chunk size for operation type - NO runtime calculations
        
        Args:
            operation_type: Type of operation ('upload', 'download', 'encryption', etc.)
        
        Returns:
            Fixed chunk size in bytes
        """
        operation_map = {
            'upload': self.config.upload_chunk_size,
            'download': self.config.download_chunk_size,
            'file_streaming': self.config.streaming_chunk_size,
            'streaming': self.config.streaming_chunk_size,
            'encryption': self.config.encryption_chunk_size,
            'zip': self.config.zip_chunk_size,
            'frontend': self.config.frontend_chunk_size,
            'chunked_upload': self.config.upload_chunk_size,
            'chunked_download': self.config.download_chunk_size
        }
        
        return operation_map.get(operation_type, self.config.upload_chunk_size)
    
    def get_frontend_config(self) -> Dict[str, Any]:
        """
        Get fixed frontend configuration - eliminates all runtime adaptation
        
        Returns:
            Dictionary with fixed frontend chunk configuration
        """
        return {
            'chunk_size': self.config.frontend_chunk_size,
            'min_chunk_size': self.config.frontend_min_size,
            'max_chunk_size': self.config.frontend_max_size,
            'memory_check_frequency': self.config.memory_check_frequency,
            'adaptation_disabled': 1 if self.config.adaptation_disabled else 0,
            'profile': self.profile.value
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of the simplified chunk system"""
        return {
            'profile': self.profile.value,
            'platform': self.platform_info.platform_type.value,
            'cpu_count': self.platform_info.cpu_count,
            'is_mobile': self.platform_info.is_mobile,
            'chunk_sizes': {
                'upload_mb': self.config.upload_chunk_size // (1024*1024),
                'download_mb': self.config.download_chunk_size // (1024*1024),
                'frontend_mb': self.config.frontend_chunk_size // (1024*1024),
                'encryption_mb': self.config.encryption_chunk_size // (1024*1024)
            },
            'optimizations': {
                'runtime_adaptation_disabled': self.config.adaptation_disabled,
                'memory_monitoring_disabled': self.config.memory_check_frequency == 0,
                'fixed_chunk_sizes': True,
                'cpu_overhead_eliminated': True
            }
        }


# Global simplified chunk manager instance
chunk_manager = SimplifiedChunkManager()
