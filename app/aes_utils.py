import os
import hashlib
from typing import Optional, Tuple, Dict
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# 🔒 SECURE: Remove hardcoded keys - generate unique keys per session/file
# AES_KEY = bytes.fromhex("8f9c02a7d6f7cbb1da0499e18b113fe65c7a6d2f538b0a6412ccab5ede6b8839")  # REMOVED - Security vulnerability
# AES_IV  = bytes.fromhex("f012bc7d298e34af6509cb471d3a8250")  # REMOVED - IV reuse vulnerability

def generate_secure_key(password: Optional[str] = None, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """
    Generate a cryptographically secure AES key and salt.
    
    Args:
        password: Optional password for key derivation. If None, uses random key.
        salt: Optional salt. If None, generates random salt.
    
    Returns:
        tuple: (aes_key, salt) - 32-byte key and 16-byte salt
    """
    if salt is None:
        salt = os.urandom(16)  # Generate random 16-byte salt
    
    if password is None:
        # Generate completely random key for maximum security
        return os.urandom(32), salt
    else:
        # Derive key from password using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key
            salt=salt,
            iterations=100000,  # Strong iteration count
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))
        return key, salt

def generate_secure_iv() -> bytes:
    """Generate a cryptographically secure random IV."""
    return os.urandom(16)  # Always generate random IV

def pad(data: bytes) -> bytes:
    """PKCS7 padding for AES block cipher."""
    padding_len = 16 - (len(data) % 16)
    return data + bytes([padding_len] * padding_len)

def unpad(data: bytes) -> bytes:
    """Remove PKCS7 padding."""
    if len(data) == 0:
        raise ValueError("Cannot unpad empty data")
    padding_len = data[-1]
    if padding_len > 16 or padding_len == 0:
        raise ValueError("Invalid padding")
    return data[:-padding_len]

def encrypt_bytes(data: bytes, key: Optional[bytes] = None, iv: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt bytes with AES-256-CBC using secure random key and IV.
    
    Args:
        data: Raw bytes to encrypt
        key: Optional 32-byte key. If None, generates random key.
        iv: Optional 16-byte IV. If None, generates random IV.
    
    Returns:
        tuple: (encrypted_data, key, iv) - All components needed for decryption
    """
    if key is None:
        key, _ = generate_secure_key()
    if iv is None:
        iv = generate_secure_iv()
    
    if len(key) != 32:
        raise ValueError("AES key must be 32 bytes (256 bits)")
    if len(iv) != 16:
        raise ValueError("AES IV must be 16 bytes")
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padded = pad(data)
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return encrypted, key, iv

def decrypt_bytes(encrypted_data: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Decrypt AES-256-CBC encrypted bytes.
    
    Args:
        encrypted_data: The encrypted bytes
        key: 32-byte decryption key
        iv: 16-byte initialization vector
    
    Returns:
        bytes: Decrypted data
    """
    if len(key) != 32:
        raise ValueError("AES key must be 32 bytes (256 bits)")
    if len(iv) != 16:
        raise ValueError("AES IV must be 16 bytes")
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()
    decrypted = unpad(decrypted_padded)
    return decrypted

def encrypt_file_with_metadata(data: bytes, filename: Optional[str] = None) -> Tuple[bytes, Dict[str, Optional[str]]]:
    """
    Encrypt file data and return encrypted data with metadata for secure storage.
    
    Args:
        data: File content as bytes
        filename: Optional filename for additional entropy
    
    Returns:
        tuple: (encrypted_data, metadata_dict)
    """
    # Generate unique key and IV for this file
    key, salt = generate_secure_key()
    iv = generate_secure_iv()
    
    # Add filename to entropy if provided
    if filename:
        filename_hash = hashlib.sha256(filename.encode('utf-8')).digest()
        # Mix filename hash with key for additional entropy
        key = bytes(a ^ b for a, b in zip(key, filename_hash))
    
    encrypted_data, final_key, final_iv = encrypt_bytes(data, key, iv)
    
    metadata = {
        'salt': salt.hex(),
        'iv': final_iv.hex(),
        'key': final_key.hex(),  # In production, store this securely (e.g., separate key management)
        'algorithm': 'AES-256-CBC',
        'filename_hash': hashlib.sha256(filename.encode('utf-8')).hexdigest() if filename else None
    }
    
    return encrypted_data, metadata

def decrypt_file_with_metadata(encrypted_data: bytes, metadata: Dict[str, Optional[str]]) -> bytes:
    """
    Decrypt file data using stored metadata.
    
    Args:
        encrypted_data: The encrypted file content
        metadata: Metadata dict containing key, iv, salt, etc.
    
    Returns:
        bytes: Decrypted file content
    """
    key_hex = metadata.get('key')
    iv_hex = metadata.get('iv')
    
    if not key_hex or not iv_hex:
        raise ValueError("Missing key or iv in metadata")
    
    key = bytes.fromhex(key_hex)
    iv = bytes.fromhex(iv_hex)
    
    return decrypt_bytes(encrypted_data, key, iv)

def encrypt_file_stream(file_data: bytes, chunk_size: int = 1024 * 1024) -> Tuple[bytes, Dict[str, str]]:
    """
    Memory-efficient streaming AES encryption for large files.
    
    Args:
        file_data: File content as bytes
        chunk_size: Size of chunks to process (default 1MB)
    
    Returns:
        tuple: (encrypted_data, metadata_dict)
    """
    key, salt = generate_secure_key()
    iv = generate_secure_iv()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    encrypted_chunks = []
    data_length = len(file_data)
    
    # Process file in chunks to reduce memory usage
    for i in range(0, data_length, chunk_size):
        chunk = file_data[i:i + chunk_size]
        
        # Pad the last chunk if necessary
        if i + chunk_size >= data_length:
            chunk = pad(chunk)
        
        encrypted_chunk = encryptor.update(chunk)
        encrypted_chunks.append(encrypted_chunk)
    
    # Finalize encryption
    final_chunk = encryptor.finalize()
    if final_chunk:
        encrypted_chunks.append(final_chunk)
    
    encrypted_data = b''.join(encrypted_chunks)
    
    metadata = {
        'salt': salt.hex(),
        'iv': iv.hex(),
        'key': key.hex(),
        'algorithm': 'AES-256-CBC-Stream',
        'original_size': str(data_length),
        'encrypted_size': str(len(encrypted_data))
    }
    
    return encrypted_data, metadata

def decrypt_file_stream(encrypted_data: bytes, metadata: Dict[str, str], chunk_size: int = 1024 * 1024) -> bytes:
    """
    Memory-efficient streaming AES decryption for large files.
    
    Args:
        encrypted_data: The encrypted file content
        metadata: Metadata dict containing key, iv, etc.
        chunk_size: Size of chunks to process (default 1MB)
    
    Returns:
        bytes: Decrypted file content
    """
    key = bytes.fromhex(metadata['key'])
    iv = bytes.fromhex(metadata['iv'])
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    decrypted_chunks = []
    data_length = len(encrypted_data)
    
    # Process encrypted data in chunks
    for i in range(0, data_length, chunk_size):
        chunk = encrypted_data[i:i + chunk_size]
        decrypted_chunk = decryptor.update(chunk)
        decrypted_chunks.append(decrypted_chunk)
    
    # Finalize decryption
    final_chunk = decryptor.finalize()
    if final_chunk:
        decrypted_chunks.append(final_chunk)
    
    decrypted_data = b''.join(decrypted_chunks)
    
    # Remove padding from the final result
    return unpad(decrypted_data)

# 🔄 Legacy support functions (for backward compatibility during migration)
def encrypt_bytes_legacy(data: bytes) -> bytes:
    """
    DEPRECATED: Legacy function for backward compatibility.
    Use encrypt_bytes() or encrypt_file_with_metadata() instead.
    """
    import warnings
    warnings.warn("encrypt_bytes_legacy is deprecated and insecure. Use encrypt_file_with_metadata().", 
                  DeprecationWarning, stacklevel=2)
    
    # Use old hardcoded values only for legacy compatibility
    legacy_key = bytes.fromhex("8f9c02a7d6f7cbb1da0499e18b113fe65c7a6d2f538b0a6412ccab5ede6b8839")
    legacy_iv = bytes.fromhex("f012bc7d298e34af6509cb471d3a8250")
    
    encrypted, _, _ = encrypt_bytes(data, legacy_key, legacy_iv)
    return encrypted

def decrypt_bytes_legacy(data: bytes) -> bytes:
    """
    DEPRECATED: Legacy function for backward compatibility.
    Use decrypt_bytes() or decrypt_file_with_metadata() instead.
    """
    import warnings
    warnings.warn("decrypt_bytes_legacy is deprecated and insecure. Use decrypt_file_with_metadata().", 
                  DeprecationWarning, stacklevel=2)
    
    # Use old hardcoded values only for legacy compatibility
    legacy_key = bytes.fromhex("8f9c02a7d6f7cbb1da0499e18b113fe65c7a6d2f538b0a6412ccab5ede6b8839")
    legacy_iv = bytes.fromhex("f012bc7d298e34af6509cb471d3a8250")
    
    return decrypt_bytes(data, legacy_key, legacy_iv)
