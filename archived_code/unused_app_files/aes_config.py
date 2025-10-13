# 🔒 AES Configuration and Validation Module
import os
from typing import Dict, Any

class AESConfig:
    """Centralized AES configuration and validation"""
    
    # 🔐 AES Settings - SIZE LIMITS REMOVED FOR STREAMING ENCRYPTION
    MAX_FILE_SIZE_MB = None  # No limit - streaming encryption handles any size
    MAX_FILE_SIZE_BYTES = None  # No limit - streaming encryption handles any size
    
    # 🔒 Security Settings
    ALGORITHM = "AES-256-CBC"
    KEY_LENGTH = 32  # 256 bits
    IV_LENGTH = 16   # 128 bits
    PBKDF2_ITERATIONS = 100000
    
    # 🚫 Protocol Restrictions - DISABLED for HTTP as requested
    HTTPS_ONLY = False
    
    @classmethod
    def validate_file_for_aes(cls, file_size: int, is_https: bool) -> Dict[str, Any]:
        """
        Validate if a file can be encrypted with AES
        
        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        if not is_https and cls.HTTPS_ONLY:
            return {
                'valid': False,
                'error': 'AES encryption is only available over HTTPS connections for security.'
            }
        
        # SIZE LIMITS REMOVED - streaming encryption handles any file size
        print(f"📊 AES encryption requested for {file_size / (1024**3):.1f}GB file - STREAMING ENCRYPTION (NO SIZE LIMITS)")
        
        return {'valid': True, 'error': None}
    
    @classmethod
    def get_size_limit_mb(cls) -> int:
        """Get the AES file size limit in MB - REMOVED, returns 0 to indicate no limit"""
        return 0
    
    @classmethod
    def get_size_limit_bytes(cls) -> int:
        """Get the AES file size limit in bytes - REMOVED, returns 0 to indicate no limit"""
        return 0
    
    @classmethod
    def is_https_required(cls) -> bool:
        """Check if HTTPS is required for AES"""
        return cls.HTTPS_ONLY

# Global AES configuration dict for API access
AES_CONFIG = {
    "ENABLED": True,
    "MODE": "AES-256-CBC",
    "KEY_SIZE": 32,
    "CHUNK_SIZE": 64 * 1024,  # 64KB chunks
    "HTTPS_ONLY": False
}

def get_aes_config():
    """Get AES configuration for API"""
    return AES_CONFIG
