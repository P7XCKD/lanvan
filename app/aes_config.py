# 🔒 AES Configuration and Validation Module
import os
from typing import Dict, Any

class AESConfig:
    """Centralized AES configuration and validation"""
    
    # 🔐 AES Settings
    MAX_FILE_SIZE_MB = 200
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
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
        
        if file_size > cls.MAX_FILE_SIZE_BYTES:
            return {
                'valid': False,
                'error': f'AES is blocked for files >{cls.MAX_FILE_SIZE_MB}MB to ensure smooth & efficient file transfer.'
            }
        
        return {'valid': True, 'error': None}
    
    @classmethod
    def get_size_limit_mb(cls) -> int:
        """Get the AES file size limit in MB"""
        return cls.MAX_FILE_SIZE_MB
    
    @classmethod
    def get_size_limit_bytes(cls) -> int:
        """Get the AES file size limit in bytes"""
        return cls.MAX_FILE_SIZE_BYTES
    
    @classmethod
    def is_https_required(cls) -> bool:
        """Check if HTTPS is required for AES"""
        return cls.HTTPS_ONLY
