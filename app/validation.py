"""
🔐 Input validation and sanitization module for LANVAN project.
Provides comprehensive validation for file uploads, filenames, and security checks.
"""

import os
import re
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from fastapi import UploadFile


class FileValidator:
    """Comprehensive file validation and sanitization."""
    
    # Security configuration
    MAX_FILENAME_LENGTH = 255
    MAX_PATH_LENGTH = 4096
    
    # Allowed file extensions (comprehensive list)
    ALLOWED_EXTENSIONS = {
        # Documents
        '.txt', '.pdf', '.doc', '.docx', '.rtf', '.odt',
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.tiff',
        # Audio
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a',
        # Video
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
        # Archives
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz',
        # Spreadsheets
        '.xls', '.xlsx', '.csv', '.ods',
        # Presentations
        '.ppt', '.pptx', '.odp',
        # Code/Text
        '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml',
        '.md', '.log', '.conf', '.cfg', '.ini',
        # Data
        '.sql', '.db', '.sqlite', '.json', '.xml',
        # Encrypted (our format)
        '.enc'
    }
    
    # Dangerous extensions to block
    BLOCKED_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
        '.vbs', '.vbe', '.js', '.jse', '.ws', '.wsf', '.wsc',
        '.msi', '.msp', '.dll', '.app', '.deb', '.rpm'
    }
    
    # Suspicious filename patterns
    SUSPICIOUS_PATTERNS = [
        r'\.\./',  # Directory traversal
        r'[<>:"|?*]',  # Invalid filename characters
        r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',  # Windows reserved names
        r'^\.',  # Hidden files starting with dot (optional restriction)
        r'[\x00-\x1f\x7f-\x9f]',  # Control characters
    ]

    @classmethod
    def validate_filename(cls, filename: str) -> Dict[str, Any]:
        """
        Comprehensive filename validation.
        
        Args:
            filename: The filename to validate
            
        Returns:
            dict: Validation result with 'valid' boolean and 'errors' list
        """
        errors = []
        
        if not filename:
            errors.append("Filename cannot be empty")
            return {'valid': False, 'errors': errors}
        
        # Length check
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            errors.append(f"Filename too long (max {cls.MAX_FILENAME_LENGTH} characters)")
        
        # Extension check
        file_ext = Path(filename).suffix.lower()
        if file_ext in cls.BLOCKED_EXTENSIONS:
            errors.append(f"File type '{file_ext}' is not allowed for security reasons")
        
        if file_ext not in cls.ALLOWED_EXTENSIONS:
            errors.append(f"File type '{file_ext}' is not supported")
        
        # Pattern checks
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                errors.append(f"Filename contains invalid characters or patterns")
                break
        
        # Null byte check
        if '\0' in filename:
            errors.append("Filename contains null bytes")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'sanitized_name': cls.sanitize_filename(filename)
        }

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename by removing/replacing dangerous characters.
        
        Args:
            filename: Original filename
            
        Returns:
            str: Sanitized filename
        """
        # Remove/replace dangerous characters
        sanitized = re.sub(r'[<>:"|?*\x00-\x1f\x7f-\x9f]', '_', filename)
        
        # Remove directory traversal attempts
        sanitized = sanitized.replace('..', '_')
        
        # Ensure it doesn't start with a dot (optional)
        if sanitized.startswith('.'):
            sanitized = '_' + sanitized[1:]
        
        # Truncate if too long
        if len(sanitized) > cls.MAX_FILENAME_LENGTH:
            name_part = Path(sanitized).stem[:cls.MAX_FILENAME_LENGTH - 10]
            ext_part = Path(sanitized).suffix
            sanitized = name_part + ext_part
        
        # Ensure it's not empty after sanitization
        if not sanitized or sanitized == '.':
            sanitized = 'unnamed_file'
        
        return sanitized

    @classmethod
    def get_mime_type(cls, file_path: Path) -> str:
        """Get MIME type using standard library mimetypes."""
        # Use standard library for MIME type detection
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'

    @classmethod
    def validate_file_content(cls, file_path: Path) -> Dict[str, Any]:
        """
        Validate file content and detect potential security issues.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            dict: Validation result with MIME type and security info
        """
        try:
            # Get file size
            file_size = file_path.stat().st_size
            
            # MIME type detection with fallback
            mime_type = cls.get_mime_type(file_path)
            
            # Calculate file hash for integrity
            file_hash = cls.calculate_file_hash(file_path)
            
            # Basic security checks
            is_safe = cls.is_file_safe(file_path, mime_type)
            
            return {
                'valid': is_safe,
                'mime_type': mime_type,
                'file_size': file_size,
                'file_hash': file_hash,
                'security_level': 'safe' if is_safe else 'suspicious'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"File validation failed: {str(e)}"
            }

    @classmethod
    def calculate_file_hash(cls, file_path: Path, algorithm: str = 'sha256') -> str:
        """Calculate file hash for integrity verification."""
        hash_func = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()

    @classmethod
    def is_file_safe(cls, file_path: Path, mime_type: str) -> bool:
        """
        Perform security checks on file content.
        
        Args:
            file_path: Path to file
            mime_type: Detected MIME type
            
        Returns:
            bool: True if file appears safe
        """
        # Extension vs MIME type mismatch check
        file_ext = file_path.suffix.lower()
        
        # Common MIME type mappings for verification
        mime_mappings = {
            '.txt': ['text/plain'],
            '.pdf': ['application/pdf'],
            '.jpg': ['image/jpeg'],
            '.jpeg': ['image/jpeg'],
            '.png': ['image/png'],
            '.gif': ['image/gif'],
            '.mp4': ['video/mp4'],
            '.zip': ['application/zip'],
            '.json': ['application/json', 'text/plain'],
            '.enc': ['application/octet-stream']  # Encrypted files
        }
        
        # Check for MIME type spoofing
        if file_ext in mime_mappings:
            expected_types = mime_mappings[file_ext]
            if mime_type not in expected_types:
                print(f"⚠️ MIME type mismatch: {file_ext} file has MIME type {mime_type}")
                # Don't reject, but log for monitoring
        
        # Block executable MIME types
        dangerous_mime_types = [
            'application/x-executable',
            'application/x-msdos-program',
            'application/x-msdownload',
            'application/x-winexe'
        ]
        
        if mime_type in dangerous_mime_types:
            return False
        
        return True


class UploadValidator:
    """Validator for upload requests and parameters."""
    
    @classmethod
    def validate_upload_request(cls, files: List[UploadFile], encrypt: bool = False) -> Dict[str, Any]:
        """
        Validate an upload request with multiple files.
        
        Args:
            files: List of uploaded files
            encrypt: Whether encryption is requested
            
        Returns:
            dict: Validation result
        """
        errors = []
        warnings = []
        total_size = 0
        validated_files = []
        
        if not files:
            errors.append("No files provided")
            return {'valid': False, 'errors': errors}
        
        for file in files:
            if not file.filename:
                warnings.append("Skipping file with no filename")
                continue
            
            # Validate filename
            filename_result = FileValidator.validate_filename(file.filename)
            if not filename_result['valid']:
                errors.extend([f"{file.filename}: {error}" for error in filename_result['errors']])
                continue
            
            # Check file size (approximate)
            file.file.seek(0, os.SEEK_END)
            file_size = file.file.tell()
            file.file.seek(0)
            
            total_size += file_size
            
            validated_files.append({
                'filename': file.filename,
                'sanitized_name': filename_result['sanitized_name'],
                'size': file_size
            })
        
        # Overall size limits
        max_total_size = 50 * 1024 * 1024 * 1024  # 50GB total limit
        if total_size > max_total_size:
            errors.append(f"Total upload size ({total_size / (1024**3):.1f}GB) exceeds limit (50GB)")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_size': total_size,
            'file_count': len(validated_files),
            'validated_files': validated_files
        }

    @classmethod
    def validate_aes_request(cls, file_size: int, is_https: bool) -> Dict[str, Any]:
        """
        Validate AES encryption request.
        
        Args:
            file_size: Size of file to encrypt
            is_https: Whether connection is HTTPS
            
        Returns:
            dict: Validation result
        """
        errors = []
        
        # HTTPS requirement for AES
        if not is_https:
            errors.append("AES encryption requires HTTPS connection")
        
        # Size limits for AES (memory considerations)
        max_aes_size = 2 * 1024 * 1024 * 1024  # 2GB limit for AES
        if file_size > max_aes_size:
            errors.append(f"File too large for AES encryption (max 2GB, got {file_size / (1024**3):.1f}GB)")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


# Utility functions for route integration
def secure_filename(filename: str) -> str:
    """Get a secure version of filename."""
    result = FileValidator.validate_filename(filename)
    return result['sanitized_name']


def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    result = FileValidator.validate_filename(filename)
    return result['valid']


def validate_upload_files(files: List[UploadFile], encrypt: bool = False, is_https: bool = False) -> Tuple[bool, List[str], List[Dict]]:
    """
    Comprehensive validation for upload files.
    
    Returns:
        tuple: (is_valid, error_messages, validated_files)
    """
    upload_result = UploadValidator.validate_upload_request(files, encrypt)
    
    if not upload_result['valid']:
        return False, upload_result['errors'], []
    
    # Additional AES validation if encryption requested
    if encrypt:
        for file_info in upload_result['validated_files']:
            aes_result = UploadValidator.validate_aes_request(file_info['size'], is_https)
            if not aes_result['valid']:
                return False, aes_result['errors'], []
    
    return True, [], upload_result['validated_files']
