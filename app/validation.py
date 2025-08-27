"""
🔐 Enhanced security validation module for LANVAN project.
Provides advanced file validation, extension manipulation detection, and security checks.
"""

import os
import io
import re
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from fastapi import UploadFile


class AdvancedFileValidator:
    """Advanced file validation with security-focused features."""
    
    # Security configuration
    MAX_FILENAME_LENGTH = 255
    MAX_PATH_LENGTH = 4096
    
    # 🚨 DANGEROUS EXTENSIONS - Always blocked regardless of content
    BLOCKED_EXTENSIONS = {
        # Executables (Windows)
        '.exe', '.com', '.scr', '.bat', '.cmd', '.pif', '.msi', '.msp',
        # Scripts (Dangerous)
        '.vbs', '.vbe', '.jse', '.ws', '.wsf', '.wsc', '.hta',
        # System files
        '.dll', '.sys', '.drv', '.ocx', '.cpl', '.scf',
        # Linux/Unix executables
        '.bin', '.run', '.deb', '.rpm', '.pkg',
        # macOS executables
        '.app', '.dmg', '.pkg',
        # Browser exploits
        '.jar', '.class', '.swf',
        # Office macros (high risk)
        '.xlsm', '.xltm', '.docm', '.dotm', '.pptm', '.potm', '.ppam',
        # Database executables
        '.mdb', '.accdb'
    }
    
    # 📋 ALLOWED EXTENSIONS - Comprehensive list for normal file sharing
    ALLOWED_EXTENSIONS = {
        # Documents (safe)
        '.txt', '.pdf', '.doc', '.docx', '.rtf', '.odt', '.ods', '.odp',
        '.pages', '.numbers', '.key', '.epub', '.mobi',
        # Images (comprehensive)
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif',
        '.ico', '.raw', '.cr2', '.nef', '.arw', '.dng', '.psd', '.ai', '.eps',
        '.heic', '.heif', '.avif', '.jxl', '.jp2', '.j2k', '.jpx', '.jpm',
        # Audio (comprehensive)
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff',
        '.opus', '.amr', '.ac3', '.dts', '.ape', '.mpc', '.ra', '.au',
        '.snd', '.mid', '.midi', '.kar', '.rmi',
        # Video (comprehensive - all common formats)
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
        '.mpg', '.mpeg', '.3gp', '.3g2', '.asf', '.vob', '.ts', '.mts',
        '.m2ts', '.mxf', '.rm', '.rmvb', '.divx', '.xvid', '.f4v', '.m2v',
        '.ogv', '.dv', '.amv', '.mp2', '.mpe', '.mpv', '.m4p', '.m4b',
        # Archives (content will be scanned)
        '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.lzma',
        '.cab', '.iso', '.dmg', '.sit', '.sitx', '.ace', '.arj', '.lha',
        '.lzh', '.zoo', '.arc', '.pak', '.pk3', '.pk4', '.war', '.ear',
        # Spreadsheets (safe versions)
        '.xls', '.xlsx', '.csv', '.tsv', '.ods', '.xlr', '.xlw',
        # Presentations (safe versions)
        '.ppt', '.pptx', '.odp', '.key', '.pps', '.ppsx',
        # Code/Text (source code, not executable)
        '.py', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go',
        '.rust', '.swift', '.kt', '.scala', '.r', '.m', '.pl', '.sh',
        '.html', '.htm', '.css', '.js', '.json', '.xml', '.yaml', '.yml',
        '.md', '.rst', '.tex', '.log', '.conf', '.cfg', '.ini', '.toml',
        '.vue', '.jsx', '.tsx', '.ts', '.sass', '.scss', '.less', '.styl',
        '.coffee', '.dart', '.elm', '.clj', '.cljs', '.erl', '.ex', '.exs',
        '.f90', '.f95', '.for', '.pas', '.pp', '.asm', '.s', '.vhdl', '.v',
        # Data files
        '.sql', '.db', '.sqlite', '.sqlite3', '.json', '.xml', '.csv',
        '.geojson', '.kml', '.gpx', '.gpkg', '.shp', '.dbf', '.prj',
        # Fonts
        '.ttf', '.otf', '.woff', '.woff2', '.eot', '.pfb', '.pfm',
        # 3D/CAD
        '.obj', '.fbx', '.dae', '.3ds', '.blend', '.max', '.dwg', '.dxf',
        '.step', '.stp', '.iges', '.igs', '.stl', '.ply', '.x3d', '.collada',
        # eBooks
        '.epub', '.mobi', '.azw', '.azw3', '.fb2', '.lit', '.pdb', '.prc',
        # Virtual disk/system files (safe)
        '.vdi', '.vhd', '.vhdx', '.vmdk', '.qcow2', '.img', '.bin', '.cue',
        # Design/Graphics
        '.sketch', '.fig', '.xd', '.indd', '.idml', '.qxd', '.pub',
        # Scientific/Research
        '.mat', '.h5', '.hdf5', '.nc', '.cdf', '.fits', '.fts',
        # Configuration/Settings
        '.properties', '.env', '.editorconfig', '.gitignore', '.dockerignore',
        # Encrypted (our format)
        '.enc', '.encrypted',
        # Backup files
        '.bak', '.backup', '.old', '.tmp', '.orig', '.save',
        # Mobile app packages (source/data only)
        '.apk', '.ipa', '.xap',
        # Game files (data/assets)
        '.pak', '.vpk', '.pk3', '.pk4', '.wad', '.bsp', '.map',
        # Subtitles/Captions
        '.srt', '.sub', '.sbv', '.ass', '.ssa', '.vtt', '.smi', '.sami'
    }
    
    # 🔍 MAGIC BYTES for file type detection (first few bytes of files)
    FILE_SIGNATURES = {
        # Images
        b'\xFF\xD8\xFF': '.jpg',
        b'\x89PNG\r\n\x1a\n': '.png',
        b'GIF8': '.gif',
        b'BM': '.bmp',
        b'RIFF': '.webp',  # WebP files start with RIFF
        b'\x00\x00\x01\x00': '.ico',
        
        # Documents
        b'%PDF': '.pdf',
        b'PK\x03\x04': '.zip',  # Also used by .docx, .xlsx, .pptx
        b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1': '.doc',  # Old Office format
        
        # Audio
        b'ID3': '.mp3',
        b'\xFF\xFB': '.mp3',
        b'\xFF\xF3': '.mp3',
        b'\xFF\xF2': '.mp3',
        b'RIFF': '.wav',  # WAV files also use RIFF
        b'fLaC': '.flac',
        b'\x00\x00\x00\x20ftypM4A': '.m4a',
        
        # Video (Enhanced MP4 detection)
        b'\x00\x00\x00\x18ftypmp4': '.mp4',           # Standard MP4
        b'\x00\x00\x00\x20ftypisom': '.mp4',          # ISO Base Media MP4
        b'\x00\x00\x00\x1cftyp': '.mp4',              # Generic ftyp box (MP4 family)
        b'\x00\x00\x00\x14ftyp': '.mp4',              # Shorter ftyp box
        b'ftypmp4': '.mp4',                            # MP4 signature (partial)
        b'ftypisom': '.mp4',                           # ISO MP4 signature (partial)
        b'ftypM4V': '.m4v',                            # iTunes M4V
        b'ftypqt': '.mov',                             # QuickTime MOV
        b'RIFF': '.avi',                               # AVI files use RIFF
        b'\x1A\x45\xDF\xA3': '.mkv',                  # Matroska MKV
        b'FLV\x01': '.flv',                            # Flash Video
        
        # Archives
        b'PK\x03\x04': '.zip',
        b'PK\x05\x06': '.zip',
        b'PK\x07\x08': '.zip',
        b'Rar!\x1A\x07\x00': '.rar',
        b'Rar!\x1A\x07\x01\x00': '.rar',
        b'7z\xBC\xAF\x27\x1C': '.7z',
        
        # Executables (DANGEROUS - will be blocked)
        b'MZ': '.exe',
        b'\x7fELF': '.bin',  # Linux executable
        b'\xCA\xFE\xBA\xBE': '.class',  # Java class
        b'\xFE\xED\xFA\xCE': '.app',  # macOS binary
    }
    
    # 🚨 DANGEROUS MAGIC BYTES - Files with these signatures are always blocked
    DANGEROUS_SIGNATURES = {
        b'MZ',  # Windows executables
        b'\x7fELF',  # Linux executables
        b'\xCA\xFE\xBA\xBE',  # Java class files
        b'\xFE\xED\xFA\xCE',  # macOS binaries
        b'\x4D\x5A',  # Another exe variant
    }

    @classmethod
    def detect_file_type_by_content(cls, file_path: Path) -> Optional[str]:
        """
        Detect actual file type by analyzing magic bytes (file signature).
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            str: Detected file extension based on content, or None if unknown
        """
        try:
            with open(file_path, 'rb') as f:
                # Read first 32 bytes for signature detection
                header = f.read(32)
                
                # Check against known signatures
                for signature, extension in cls.FILE_SIGNATURES.items():
                    if header.startswith(signature):
                        return extension
                        
                # Special handling for RIFF files (WAV, AVI, WebP)
                if header.startswith(b'RIFF') and len(header) >= 12:
                    format_type = header[8:12]
                    if format_type == b'WAVE':
                        return '.wav'
                    elif format_type == b'AVI ':
                        return '.avi'
                    elif format_type == b'WEBP':
                        return '.webp'
                
                return None
                
        except Exception as e:
            print(f"⚠️ Error detecting file type: {e}")
            return None

    @classmethod
    def is_dangerous_content(cls, file_path: Path) -> bool:
        """
        Check if file contains dangerous content based on magic bytes.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            bool: True if file contains dangerous content
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
                
                # Check against dangerous signatures
                for dangerous_sig in cls.DANGEROUS_SIGNATURES:
                    if header.startswith(dangerous_sig):
                        return True
                        
                return False
                
        except Exception:
            # If we can't read the file, consider it suspicious
            return True

    @classmethod
    def validate_file_extension_integrity(cls, file_path: Path, claimed_filename: str) -> Dict[str, Any]:
        """
        Advanced validation to detect extension manipulation.
        
        This detects when someone changes a file extension to bypass security
        (e.g., renaming malware.exe to malware.txt).
        
        Args:
            file_path: Path to the actual file
            claimed_filename: The filename the user claims it is
            
        Returns:
            dict: Validation result with security assessment
        """
        claimed_ext = Path(claimed_filename).suffix.lower()
        
        # Step 1: Detect actual file type by content
        actual_type = cls.detect_file_type_by_content(file_path)
        
        # Step 2: Check for dangerous content
        is_dangerous = cls.is_dangerous_content(file_path)
        
        if is_dangerous:
            return {
                'valid': False,
                'security_risk': 'HIGH',
                'reason': 'File contains executable code or dangerous content',
                'action': 'BLOCKED',
                'claimed_extension': claimed_ext,
                'detected_type': actual_type or 'executable'
            }
        
        # Step 3: Extension vs Content mismatch detection
        mismatch_detected = False
        mismatch_severity = 'NONE'
        
        if actual_type and actual_type != claimed_ext:
            # Check if this is a significant mismatch
            if cls._is_significant_mismatch(claimed_ext, actual_type):
                mismatch_detected = True
                mismatch_severity = cls._assess_mismatch_risk(claimed_ext, actual_type)
        
        # Step 4: Final security assessment
        if mismatch_detected and mismatch_severity == 'HIGH':
            return {
                'valid': False,
                'security_risk': 'HIGH',
                'reason': f'Extension manipulation detected: file claims to be {claimed_ext} but content is {actual_type}',
                'action': 'BLOCKED',
                'claimed_extension': claimed_ext,
                'detected_type': actual_type,
                'mismatch': True
            }
        elif mismatch_detected and mismatch_severity == 'MEDIUM':
            return {
                'valid': True,
                'security_risk': 'MEDIUM',
                'reason': f'Possible extension mismatch: {claimed_ext} vs {actual_type}',
                'action': 'ALLOW_WITH_WARNING',
                'claimed_extension': claimed_ext,
                'detected_type': actual_type,
                'mismatch': True
            }
        else:
            return {
                'valid': True,
                'security_risk': 'LOW',
                'reason': 'File extension and content match expected patterns',
                'action': 'ALLOW',
                'claimed_extension': claimed_ext,
                'detected_type': actual_type,
                'mismatch': False
            }

    @classmethod
    def _is_significant_mismatch(cls, claimed_ext: str, detected_ext: str) -> bool:
        """Check if extension mismatch is significant enough to be suspicious."""
        
        # Group related extensions that might be interchangeable
        equivalent_groups = [
            {'.jpg', '.jpeg'},
            {'.tiff', '.tif'},
            {'.htm', '.html'},
            {'.yaml', '.yml'},
            # Archive formats that might be misdetected
            {'.zip', '.docx', '.xlsx', '.pptx'},  # Office files are ZIP-based
        ]
        
        # Check if both extensions are in the same equivalence group
        for group in equivalent_groups:
            if claimed_ext in group and detected_ext in group:
                return False
                
        # If detected type is None (unknown), don't consider it a mismatch
        if detected_ext is None:
            return False
            
        # Otherwise, it's a significant mismatch
        return claimed_ext != detected_ext

    @classmethod
    def _assess_mismatch_risk(cls, claimed_ext: str, detected_ext: str) -> str:
        """Assess the security risk level of an extension mismatch."""
        
        # HIGH RISK: Executable disguised as safe file
        if detected_ext in ['.exe', '.bin', '.class', '.app'] and claimed_ext in ['.txt', '.jpg', '.pdf', '.doc']:
            return 'HIGH'
            
        # HIGH RISK: Archive disguised as document
        if detected_ext in ['.zip', '.rar', '.7z'] and claimed_ext in ['.txt', '.jpg', '.pdf']:
            return 'HIGH'
            
        # MEDIUM RISK: Wrong document type
        if detected_ext in ['.pdf', '.doc'] and claimed_ext in ['.txt', '.jpg']:
            return 'MEDIUM'
            
        # MEDIUM RISK: Wrong media type
        if detected_ext in ['.jpg', '.png', '.gif'] and claimed_ext in ['.txt', '.doc']:
            return 'MEDIUM'
            
        # LOW RISK: Minor differences
        return 'LOW'
class FileValidator(AdvancedFileValidator):
    """Main file validator class with backward compatibility."""
    
    @classmethod
    def validate_filename(cls, filename: str) -> Dict[str, Any]:
        """
        Comprehensive filename validation with enhanced security.
        
        Args:
            filename: The filename to validate
            
        Returns:
            dict: Validation result with 'valid' boolean and 'errors' list
        """
        errors = []
        warnings = []
        
        if not filename:
            errors.append("Filename cannot be empty")
            return {'valid': False, 'errors': errors}
        
        # Length check
        if len(filename) > cls.MAX_FILENAME_LENGTH:
            errors.append(f"Filename too long (max {cls.MAX_FILENAME_LENGTH} characters)")
        
        # Extension check
        file_ext = Path(filename).suffix.lower()
        
        # 🚨 SECURITY: Block dangerous extensions
        if file_ext in cls.BLOCKED_EXTENSIONS:
            errors.append(f"File type '{file_ext}' is blocked for security reasons (potentially dangerous)")
            return {'valid': False, 'errors': errors, 'security_risk': 'HIGH'}
        
        # ✅ SECURITY: Allow most extensions but warn about unknown ones
        if file_ext and file_ext not in cls.ALLOWED_EXTENSIONS:
            warnings.append(f"File type '{file_ext}' is uncommon - will be scanned for security")
        
        # Pattern checks for suspicious filenames
        suspicious_patterns = [
            r'\.\./',  # Directory traversal
            r'[<>:"|?*]',  # Invalid filename characters
            r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',  # Windows reserved names
            r'[\x00-\x1f\x7f-\x9f]',  # Control characters
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                errors.append(f"Filename contains invalid characters or patterns")
                break
        
        # Null byte check
        if '\0' in filename:
            errors.append("Filename contains null bytes")
        
        # 🔍 SECURITY: Check for double extensions (e.g., file.txt.exe)
        if cls._has_suspicious_double_extension(filename):
            errors.append("Filename has suspicious double extension pattern")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'sanitized_name': cls.sanitize_filename(filename),
            'security_risk': 'HIGH' if errors else ('MEDIUM' if warnings else 'LOW')
        }

    @classmethod
    def _has_suspicious_double_extension(cls, filename: str) -> bool:
        """Detect suspicious double extensions like file.txt.exe"""
        parts = filename.lower().split('.')
        if len(parts) < 3:  # Need at least file.ext1.ext2
            return False
        
        # Check if any of the middle parts are dangerous extensions
        for i in range(1, len(parts) - 1):
            ext = '.' + parts[i]
            if ext in cls.BLOCKED_EXTENSIONS:
                return True
        
        return False

    @classmethod
    def validate_uploaded_file(cls, file_path: Path, original_filename: str) -> Dict[str, Any]:
        """
        🔐 ENHANCED SECURITY: Comprehensive file validation with content analysis.
        
        This is the main security function that:
        1. Validates filename
        2. Detects extension manipulation
        3. Scans for dangerous content
        4. Verifies file integrity
        
        Args:
            file_path: Path to the uploaded file
            original_filename: Original filename from upload
            
        Returns:
            dict: Comprehensive security assessment
        """
        # Step 1: Basic filename validation
        filename_result = cls.validate_filename(original_filename)
        if not filename_result['valid']:
            return {
                'valid': False,
                'security_risk': 'HIGH',
                'errors': filename_result['errors'],
                'stage': 'filename_validation'
            }
        
        # Step 2: 🚨 ADVANCED: Extension manipulation detection
        try:
            extension_check = cls.validate_file_extension_integrity(file_path, original_filename)
            
            if not extension_check['valid']:
                return {
                    'valid': False,
                    'security_risk': extension_check['security_risk'],
                    'errors': [extension_check['reason']],
                    'extension_manipulation_detected': True,
                    'claimed_extension': extension_check['claimed_extension'],
                    'actual_type': extension_check['detected_type'],
                    'stage': 'content_analysis'
                }
            
            # If there's a warning-level mismatch, proceed but flag it
            content_warnings = []
            if extension_check.get('mismatch', False) and extension_check['security_risk'] == 'MEDIUM':
                content_warnings.append(extension_check['reason'])
            
        except Exception as e:
            return {
                'valid': False,
                'security_risk': 'HIGH',
                'errors': [f"File content analysis failed: {str(e)}"],
                'stage': 'content_analysis_error'
            }
        
        # Step 3: File size and basic properties
        try:
            file_size = file_path.stat().st_size
            mime_type = cls.get_mime_type(file_path)
            file_hash = cls.calculate_file_hash(file_path)
            
            # Step 4: Final safety assessment
            is_safe = cls.is_file_safe(file_path, mime_type)
            
            return {
                'valid': is_safe,
                'security_risk': 'LOW' if is_safe else 'MEDIUM',
                'mime_type': mime_type,
                'file_size': file_size,
                'file_hash': file_hash,
                'sanitized_name': filename_result['sanitized_name'],
                'warnings': filename_result.get('warnings', []) + content_warnings,
                'extension_check': extension_check,
                'stage': 'complete'
            }
            
        except Exception as e:
            return {
                'valid': False,
                'security_risk': 'HIGH',
                'errors': [f"File validation failed: {str(e)}"],
                'stage': 'file_analysis_error'
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
        
        # Overall size limits - REMOVED for testing large files
        # max_total_size = 50 * 1024 * 1024 * 1024  # 50GB total limit
        # if total_size > max_total_size:
        #     errors.append(f"Total upload size ({total_size / (1024**3):.1f}GB) exceeds limit (50GB)")
        
        print(f"📊 Total upload size: {total_size / (1024**3):.1f}GB - NO LIMITS ENFORCED")
        
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
        
        # Size limits for AES (memory considerations) - REMOVED for testing
        # max_aes_size = 2 * 1024 * 1024 * 1024  # 2GB limit for AES
        # if file_size > max_aes_size:
        #     errors.append(f"File too large for AES encryption (max 2GB, got {file_size / (1024**3):.1f}GB)")
        
        print(f"📊 AES encryption requested for {file_size / (1024**3):.1f}GB file - NO SIZE LIMITS")
        
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


async def validate_upload_files_enhanced_fast(files: List[UploadFile], encrypt: bool = False, is_https: bool = False) -> Tuple[bool, List[str], List[Dict], List[str]]:
    """
    🚀 ULTRA-FAST CONCURRENT VALIDATION: Immediate upload start with lightweight validation.
    
    This optimized function:
    1. Validates filenames and extensions concurrently
    2. Skips expensive content analysis to start uploads immediately
    3. Uses basic file size detection only
    4. Processes ALL files simultaneously
    5. Allows uploads to start while validation completes
    
    Returns:
        tuple: (is_valid, error_messages, validated_files, security_warnings)
    """
    import asyncio
    
    async def validate_single_file_fast(file: UploadFile) -> Dict[str, Any]:
        """Fast validation of a single file"""
        if not file.filename:
            return {"error": "File without filename detected"}
        
        # 🔍 Basic filename validation only
        filename_validation = FileValidator.validate_filename(file.filename)
        if not filename_validation['valid']:
            return {"error": f"{file.filename}: {filename_validation['error']}"}
        
        # 🚀 FAST: Get file size without expensive content analysis
        try:
            file_size = getattr(file, 'size', 0)
            if file_size == 0:
                # Quick size detection without reading full content
                try:
                    await asyncio.to_thread(file.file.seek, 0, 2)
                    file_size = await asyncio.to_thread(file.file.tell)
                    await asyncio.to_thread(file.file.seek, 0)
                except:
                    file_size = 0  # Will be detected during upload
            
            return {
                "success": True,
                "file_data": {
                    'original_name': file.filename,
                    'sanitized_name': filename_validation['sanitized_name'],
                    'size': file_size,
                    'mime_type': 'application/octet-stream',
                    'file_hash': 'will_be_calculated_during_upload',
                    'security_level': 'fast_validation'
                }
            }
            
        except Exception as e:
            return {"error": f"{file.filename}: Failed to get file size - {str(e)}"}
    
    # 🚀 CONCURRENT VALIDATION: Process all files simultaneously  
    print(f"🚀 Starting fast concurrent validation of {len(files)} files...")
    validation_tasks = [validate_single_file_fast(file) for file in files]
    validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
    
    # Process results super fast
    errors = []
    validated_files = []
    security_warnings = []
    
    for i, result in enumerate(validation_results):
        if isinstance(result, Exception):
            errors.append(f"🚫 {files[i].filename}: Validation exception - {str(result)}")
        elif isinstance(result, dict) and "error" in result:
            errors.append(f"🚫 {result['error']}")
        elif isinstance(result, dict) and "success" in result:
            validated_files.append(result["file_data"])
    
    is_valid = len(errors) == 0
    
    print(f"✅ Fast validation completed in minimal time: {len(validated_files)} valid, {len(errors)} errors")
    
    return is_valid, errors, validated_files, security_warnings


async def validate_upload_files_enhanced_async(files: List[UploadFile], encrypt: bool = False, is_https: bool = False) -> Tuple[bool, List[str], List[Dict], List[str]]:
    """
    � ASYNC ENHANCED SECURITY: Non-blocking comprehensive validation with content analysis.
    
    This async function:
    1. Validates filenames and extensions
    2. Checks for dangerous file types  
    3. Detects extension manipulation attempts
    4. Uses async file operations to prevent blocking
    5. Provides security warnings for suspicious files
    
    Returns:
        tuple: (is_valid, error_messages, validated_files, security_warnings)
    """
    import asyncio
    
    errors = []
    validated_files = []
    security_warnings = []
    total_size = 0
    
    # Create temporary directory for content analysis
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        
        for file in files:
            if not file.filename:
                errors.append("🚫 File without filename detected")
                continue
            
            # 🔍 STEP 1: Basic filename validation
            filename_validation = FileValidator.validate_filename(file.filename)
            if not filename_validation['valid']:
                errors.append(f"🚫 {file.filename}: {filename_validation['error']}")
                continue
            
            # 🔍 STEP 2: Async file size detection and content analysis
            temp_file_path = temp_dir / file.filename
            try:
                # 🚀 ASYNC: Get file size without blocking
                try:
                    await asyncio.to_thread(file.file.seek, 0, 2)
                    file_size = await asyncio.to_thread(file.file.tell)
                    await asyncio.to_thread(file.file.seek, 0)
                except:
                    # Fallback: use UploadFile.size if available
                    file_size = getattr(file, 'size', 0)
                    if file_size == 0:
                        # Last resort: read to get size, then reset
                        content = await file.read()
                        file_size = len(content)
                        file.file = io.BytesIO(content)
                
                # 🚀 OPTIMIZED: Skip content analysis for very large files (>1GB)
                if file_size > 1 * 1024 * 1024 * 1024:  # Files > 1GB
                    print(f"📊 Skipping content analysis for large file: {file.filename} ({file_size / (1024**3):.1f}GB)")
                    total_size += file_size
                    
                    # For large files, just do basic filename validation
                    validated_files.append({
                        'original_name': file.filename,
                        'sanitized_name': filename_validation['sanitized_name'],
                        'size': file_size,
                        'mime_type': 'application/octet-stream',
                        'file_hash': 'skipped_for_large_file',
                        'security_level': 'basic_validation_only'
                    })
                    continue
                else:
                    # 🚀 ASYNC: Normal content analysis for smaller files
                    import aiofiles
                    async with aiofiles.open(temp_file_path, 'wb') as temp_file:
                        content = await file.read()
                        await temp_file.write(content)
                        await asyncio.to_thread(file.file.seek, 0)  # Reset for later use
                    
                    file_size = len(content)
                    total_size += file_size
                
            except Exception as e:
                errors.append(f"🚫 {file.filename}: Failed to process file - {str(e)}")
                continue
            
            # 🔍 STEP 3: ASYNC SECURITY - Content analysis and extension validation
            # Skip security analysis for very large files
            if file_size > 1 * 1024 * 1024 * 1024:  # Files > 1GB
                print(f"⚠️ Skipping security analysis for large file: {file.filename} ({file_size / (1024**3):.1f}GB)")
                continue
                
            # Use async file operations for security analysis
            try:
                security_result = await asyncio.to_thread(
                    FileValidator.validate_uploaded_file, 
                    temp_file_path, 
                    file.filename
                )
                
                if not security_result['valid']:
                    errors.append(f"🚫 {file.filename}: {security_result['error']}")
                    continue
                
                # Add security warnings if any
                if security_result.get('warnings'):
                    for warning in security_result['warnings']:
                        security_warnings.append(f"⚠️ {file.filename}: {warning}")
                
                # Store validated file info
                validated_files.append({
                    'original_name': file.filename,
                    'sanitized_name': security_result['sanitized_name'],
                    'size': file_size,
                    'mime_type': security_result.get('mime_type', 'application/octet-stream'),
                    'file_hash': security_result.get('file_hash', 'unknown'),
                    'security_level': 'full_analysis'
                })
                
            except Exception as e:
                errors.append(f"🚫 {file.filename}: Security analysis failed - {str(e)}")
                continue
    
    # 🔍 Final validation
    is_valid = len(errors) == 0
    
    return is_valid, errors, validated_files, security_warnings


def validate_upload_files_enhanced(files: List[UploadFile], encrypt: bool = False, is_https: bool = False) -> Tuple[bool, List[str], List[Dict], List[str]]:
    """
    🔄 LEGACY SYNC VERSION: Comprehensive validation with content analysis (BLOCKING).
    
    ⚠️ WARNING: This function uses blocking file operations and should be replaced with 
    validate_upload_files_enhanced_async() for better performance.
    
    This function:
    1. Validates filenames and extensions
    2. Checks for dangerous file types
    3. Detects extension manipulation attempts
    4. Analyzes file content vs claimed file type (BLOCKING for files <1GB)
    5. Provides security warnings for suspicious files
    
    Returns:
        tuple: (is_valid, error_messages, validated_files, security_warnings)
    """
    errors = []
    warnings = []
    validated_files = []
    total_size = 0
    
    if not files:
        errors.append("No files provided")
        return False, errors, [], []
    
    # Create temporary directory for security analysis
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        for file in files:
            if not file.filename:
                warnings.append("Skipping file with no filename")
                continue
            
            # 🔍 STEP 1: Basic filename validation
            filename_result = FileValidator.validate_filename(file.filename)
            if not filename_result['valid']:
                errors.extend([f"🚫 {file.filename}: {error}" for error in filename_result['errors']])
                continue
            
            # 🔍 STEP 2: Save file temporarily for content analysis
            temp_file_path = temp_dir / file.filename
            try:
                # 🚀 OPTIMIZED: Skip content analysis for very large files (>1GB)
                file.file.seek(0, 2)  # Seek to end to get size
                file_size = file.file.tell()
                file.file.seek(0)  # Reset to beginning
                
                if file_size > 1 * 1024 * 1024 * 1024:  # Files > 1GB
                    print(f"📊 Skipping content analysis for large file: {file.filename} ({file_size / (1024**3):.1f}GB)")
                    # Don't write to temp file for huge files, just validate filename
                    total_size += file_size
                else:
                    # Normal content analysis for smaller files
                    with open(temp_file_path, 'wb') as temp_file:
                        content = file.file.read()
                        temp_file.write(content)
                        file.file.seek(0)  # Reset for later use
                    
                    file_size = len(content)
                    total_size += file_size
                
            except Exception as e:
                errors.append(f"🚫 {file.filename}: Failed to process file - {str(e)}")
                continue
            
            # 🔍 STEP 3: ADVANCED SECURITY - Content analysis and extension validation
            # Skip security analysis for very large files to avoid memory issues
            if file_size > 1 * 1024 * 1024 * 1024:  # Files > 1GB
                print(f"⚠️ Skipping security analysis for large file: {file.filename} ({file_size / (1024**3):.1f}GB)")
                # For large files, just do basic filename validation
                security_result = {
                    'valid': True,
                    'sanitized_name': file.filename,
                    'mime_type': 'application/octet-stream',
                    'file_hash': 'skipped_for_large_file',
                    'security_risk': 'UNKNOWN',
                    'warnings': [f"Security analysis skipped for large file ({file_size / (1024**3):.1f}GB)"]
                }
            else:
                security_result = FileValidator.validate_uploaded_file(temp_file_path, file.filename)
            
            if not security_result['valid']:
                # 🚨 SECURITY BLOCK: Dangerous file detected
                security_risk = security_result.get('security_risk', 'HIGH')
                stage = security_result.get('stage', 'unknown')
                
                if 'extension_manipulation_detected' in security_result:
                    errors.append(f"🚫 SECURITY THREAT: {file.filename} - Extension manipulation detected! "
                                f"File claims to be {security_result['claimed_extension']} but is actually {security_result['actual_type']}")
                else:
                    error_msg = security_result.get('errors', ['Unknown security issue'])[0]
                    errors.append(f"🚫 SECURITY BLOCK: {file.filename} - {error_msg}")
                continue
            
            # 🚨 STEP 4: Collect security warnings
            file_warnings = security_result.get('warnings', [])
            extension_check = security_result.get('extension_check', {})
            
            if extension_check.get('security_risk') == 'MEDIUM':
                warnings.append(f"⚠️ {file.filename}: {extension_check['reason']}")
            
            if file_warnings:
                warnings.extend([f"⚠️ {file.filename}: {warning}" for warning in file_warnings])
            
            # ✅ STEP 5: File passed security checks
            validated_files.append({
                'filename': file.filename,
                'sanitized_name': security_result.get('sanitized_name', file.filename),
                'size': file_size,
                'mime_type': security_result.get('mime_type', 'application/octet-stream'),
                'file_hash': security_result.get('file_hash', ''),
                'security_risk': security_result.get('security_risk', 'LOW'),
                'extension_check': extension_check
            })
    
    finally:
        # 🧹 Cleanup temporary files
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass  # Non-critical cleanup failure
    
    # Overall size limits - REMOVED for testing large files
    # max_total_size = 50 * 1024 * 1024 * 1024  # 50GB total limit
    # if total_size > max_total_size:
    #     errors.append(f"Total upload size ({total_size / (1024**3):.1f}GB) exceeds limit (50GB)")
    
    print(f"📊 Enhanced validation: {total_size / (1024**3):.1f}GB total - NO LIMITS ENFORCED")
    
    # Additional AES validation if encryption requested - LIMITS REMOVED
    # if encrypt and not errors:
    #     for file_info in validated_files:
    #         aes_result = UploadValidator.validate_aes_request(file_info['size'], is_https)
    #         if not aes_result['valid']:
    #             errors.extend(aes_result['errors'])
    #             break
    
    return len(errors) == 0, errors, validated_files, warnings


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

# Additional async functions for API compatibility
async def validate_files_async(files, max_size_mb=1000):
    """Async file validation for API compatibility"""
    try:
        validator = AdvancedFileValidator()
        results = []
        
        for file in files:
            if hasattr(file, 'filename') and hasattr(file, 'size'):
                # Basic validation
                result = {
                    'valid': True,
                    'filename': file.filename,
                    'size': getattr(file, 'size', 0),
                    'message': 'Validation passed'
                }
                
                # Check extension
                if file.filename:
                    ext = Path(file.filename).suffix.lower()
                    if ext in validator.BLOCKED_EXTENSIONS:
                        result['valid'] = False
                        result['message'] = f'Blocked extension: {ext}'
                
                results.append(result)
            else:
                # Basic validation for other file types
                results.append({
                    'valid': True,
                    'filename': str(file),
                    'size': 0,
                    'message': 'Basic validation passed'
                })
        
        return results
    except Exception as e:
        return [{'valid': False, 'error': str(e)}]
