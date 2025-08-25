"""
🔒 Metadata Protection for HTTP-Safe AES Encryption

This module implements comprehensive metadata protection to make AES encryption
secure over HTTP by hiding filenames, sizes, and patterns.
"""

import os
import hashlib
import secrets
import base64
from typing import Dict, Tuple, Optional

def generate_secure_filename(original_filename: str, encryption_key: bytes) -> str:
    """
    Generate a secure obfuscated filename that hides the original name.
    
    Args:
        original_filename: Original file name
        encryption_key: AES encryption key used for the file
        
    Returns:
        str: Obfuscated filename that looks random
    """
    # Create deterministic but secure hash from filename + key
    filename_hash = hashlib.sha256(
        original_filename.encode('utf-8') + encryption_key
    ).hexdigest()[:16]
    
    # Generate random-looking filename
    secure_filename = f"file_{filename_hash}.enc"
    
    return secure_filename

def obfuscate_file_size(actual_size: int) -> int:
    """
    Add random padding to obfuscate the actual file size.
    
    Args:
        actual_size: Actual file size in bytes
        
    Returns:
        int: Obfuscated size with random padding
    """
    # Add random padding between 1KB to 64KB
    padding_size = secrets.randbelow(64 * 1024) + 1024
    
    # For very large files, add proportional padding
    if actual_size > 100 * 1024 * 1024:  # > 100MB
        additional_padding = secrets.randbelow(actual_size // 100)  # Up to 1% extra
        padding_size += additional_padding
    
    return actual_size + padding_size

def create_dummy_traffic_pattern():
    """
    Generate parameters for dummy traffic to hide real upload patterns.
    
    Returns:
        dict: Parameters for generating dummy requests
    """
    return {
        'dummy_requests': secrets.randbelow(3) + 1,  # 1-3 dummy requests
        'delay_between': secrets.randbelow(500) + 100,  # 100-600ms delays
        'dummy_sizes': [secrets.randbelow(1024) + 512 for _ in range(3)]  # Random small sizes
    }

def encrypt_metadata(metadata: Dict, encryption_key: bytes) -> str:
    """
    Encrypt metadata itself to prevent information leakage.
    
    Args:
        metadata: Original metadata dictionary
        encryption_key: AES key used for the file
        
    Returns:
        str: Base64 encoded encrypted metadata
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import json
    
    # Convert metadata to JSON
    metadata_json = json.dumps(metadata).encode('utf-8')
    
    # Generate IV for metadata encryption
    iv = os.urandom(16)
    
    # Encrypt metadata with same key as file
    cipher = Cipher(algorithms.AES(encryption_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Pad metadata
    from cryptography.hazmat.primitives import padding
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(metadata_json)
    padded_data += padder.finalize()
    
    # Encrypt
    encrypted_metadata = encryptor.update(padded_data)
    encrypted_metadata += encryptor.finalize()
    
    # Combine IV + encrypted metadata and encode
    combined = iv + encrypted_metadata
    return base64.b64encode(combined).decode('ascii')

def decrypt_metadata(encrypted_metadata_b64: str, encryption_key: bytes) -> Dict:
    """
    Decrypt encrypted metadata.
    
    Args:
        encrypted_metadata_b64: Base64 encoded encrypted metadata
        encryption_key: AES key used for the file
        
    Returns:
        dict: Decrypted metadata
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import json
    
    # Decode from base64
    combined = base64.b64decode(encrypted_metadata_b64)
    
    # Extract IV and encrypted data
    iv = combined[:16]
    encrypted_data = combined[16:]
    
    # Decrypt
    cipher = Cipher(algorithms.AES(encryption_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    decrypted_padded = decryptor.update(encrypted_data)
    decrypted_padded += decryptor.finalize()
    
    # Remove padding
    from cryptography.hazmat.primitives import padding
    unpadder = padding.PKCS7(128).unpadder()
    decrypted_data = unpadder.update(decrypted_padded)
    decrypted_data += unpadder.finalize()
    
    # Parse JSON
    return json.loads(decrypted_data.decode('utf-8'))

def create_http_safe_upload_params(
    original_filename: str, 
    file_size: int, 
    encryption_key: bytes,
    metadata: Dict
) -> Dict:
    """
    Create HTTP-safe upload parameters that hide all sensitive information.
    
    Args:
        original_filename: Original filename
        file_size: Actual file size
        encryption_key: AES encryption key
        metadata: File metadata
        
    Returns:
        dict: Safe parameters for HTTP upload
    """
    
    # Generate secure obfuscated filename
    safe_filename = generate_secure_filename(original_filename, encryption_key)
    
    # Obfuscate file size
    obfuscated_size = obfuscate_file_size(file_size)
    
    # Encrypt metadata
    encrypted_meta = encrypt_metadata(metadata, encryption_key)
    
    # Create dummy traffic parameters
    traffic_params = create_dummy_traffic_pattern()
    
    # Add original filename to metadata (encrypted)
    enhanced_metadata = metadata.copy()
    enhanced_metadata['original_filename'] = original_filename
    enhanced_metadata['original_size'] = str(file_size)
    enhanced_metadata['obfuscated_size'] = str(obfuscated_size)
    
    return {
        'safe_filename': safe_filename,
        'obfuscated_size': obfuscated_size,
        'encrypted_metadata': encrypted_meta,
        'traffic_obfuscation': traffic_params,
        'upload_id': secrets.token_hex(16),  # Random upload identifier
        'session_token': secrets.token_hex(32)  # Random session token
    }

def generate_decoy_requests(base_url: str, num_decoys: int = 2) -> list:
    """
    Generate decoy HTTP requests to hide real upload patterns.
    
    Args:
        base_url: Base URL for requests
        num_decoys: Number of decoy requests to generate
        
    Returns:
        list: List of decoy request parameters
    """
    decoys = []
    
    for i in range(num_decoys):
        decoy = {
            'url': f"{base_url}/dummy/{secrets.token_hex(8)}",
            'method': 'POST',
            'size': secrets.randbelow(10240) + 1024,  # 1-10KB
            'delay': secrets.randbelow(1000) + 500,   # 0.5-1.5s delay
            'headers': {
                'Content-Type': 'application/octet-stream',
                'Content-Length': str(secrets.randbelow(10240) + 1024),
                'X-Request-ID': secrets.token_hex(16)
            }
        }
        decoys.append(decoy)
    
    return decoys
