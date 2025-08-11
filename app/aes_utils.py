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

def encrypt_file_with_metadata(data: bytes, filename: Optional[str] = None, user_password: Optional[str] = None) -> Tuple[bytes, Dict[str, Optional[str]]]:
    """
    Encrypt file data and return encrypted data with metadata for secure storage.
    
    Args:
        data: File content as bytes
        filename: Optional filename for metadata
        user_password: Optional user password for key derivation
    
    Returns:
        tuple: (encrypted_data, metadata_dict)
    """
    # Generate unique key and IV for this file
    if user_password:
        # Use password-based key derivation
        key, salt = generate_secure_key(user_password)
    else:
        # Generate random key for session-based encryption
        key, salt = generate_secure_key()
    
    iv = generate_secure_iv()
    
    encrypted_data, final_key, final_iv = encrypt_bytes(data, key, iv)
    
    metadata = {
        'salt': salt.hex(),
        'iv': final_iv.hex(),
        'algorithm': 'AES-256-CBC',
        'filename_hash': hashlib.sha256(filename.encode('utf-8')).hexdigest() if filename else None,
        'key_derivation': 'password' if user_password else 'random',
        'iterations': '100000' if user_password else None
    }
    
    # SECURITY: Key is NOT stored in metadata
    # For password-based: key can be re-derived from password + salt
    # For random keys: this is session-based encryption only
    
    return encrypted_data, metadata

def decrypt_file_with_metadata(encrypted_data: bytes, metadata: Dict[str, Optional[str]], user_password: Optional[str] = None) -> bytes:
    """
    Decrypt file data using stored metadata.
    
    Args:
        encrypted_data: The encrypted file content
        metadata: Metadata dict containing salt, iv, etc.
        user_password: Required if file was encrypted with password
    
    Returns:
        bytes: Decrypted file content
    """
    iv_hex = metadata.get('iv')
    salt_hex = metadata.get('salt')
    key_derivation = metadata.get('key_derivation', 'random')
    
    if not iv_hex or not salt_hex:
        raise ValueError("Missing iv or salt in metadata")
    
    iv = bytes.fromhex(iv_hex)
    salt = bytes.fromhex(salt_hex)
    
    if key_derivation == 'password':
        if not user_password:
            raise ValueError("Password required for password-encrypted file")
        # Re-derive key from password and salt
        key, _ = generate_secure_key(user_password, salt)
    else:
        raise ValueError("Cannot decrypt random-key encrypted file without session key storage")
    
    return decrypt_bytes(encrypted_data, key, iv)

def encrypt_file_stream(file_data: bytes, user_password: Optional[str] = None, chunk_size: int = 1024 * 1024) -> Tuple[bytes, Dict[str, str]]:
    """
    Memory-efficient streaming AES encryption for large files.
    
    Args:
        file_data: File content as bytes
        user_password: Optional user password for key derivation
        chunk_size: Size of chunks to process (default 1MB)
    
    Returns:
        tuple: (encrypted_data, metadata_dict)
    """
    if user_password:
        key, salt = generate_secure_key(user_password)
    else:
        key, salt = generate_secure_key()
    
    iv = generate_secure_iv()
    
    # Properly pad the entire data first for CBC mode
    padded_data = pad(file_data)
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    encrypted_chunks = []
    data_length = len(padded_data)
    
    # Process padded data in chunks
    for i in range(0, data_length, chunk_size):
        chunk = padded_data[i:i + chunk_size]
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
        'algorithm': 'AES-256-CBC-Stream',
        'original_size': str(len(file_data)),
        'encrypted_size': str(len(encrypted_data)),
        'key_derivation': 'password' if user_password else 'random',
        'iterations': '100000' if user_password else None
    }
    
    return encrypted_data, metadata

def decrypt_file_stream(encrypted_data: bytes, metadata: Dict[str, str], user_password: Optional[str] = None, chunk_size: int = 1024 * 1024) -> bytes:
    """
    Memory-efficient streaming AES decryption for large files.
    
    Args:
        encrypted_data: The encrypted file content
        metadata: Metadata dict containing salt, iv, etc.
        user_password: Required if file was encrypted with password
        chunk_size: Size of chunks to process (default 1MB)
    
    Returns:
        bytes: Decrypted file content
    """
    salt_hex = metadata.get('salt')
    iv_hex = metadata.get('iv')
    key_derivation = metadata.get('key_derivation', 'random')
    
    if not salt_hex or not iv_hex:
        raise ValueError("Missing salt or iv in metadata")
    
    salt = bytes.fromhex(salt_hex)
    iv = bytes.fromhex(iv_hex)
    
    if key_derivation == 'password':
        if not user_password:
            raise ValueError("Password required for password-encrypted file")
        key, _ = generate_secure_key(user_password, salt)
    else:
        raise ValueError("Cannot decrypt random-key encrypted file without session key storage")
    
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
    
    decrypted_padded_data = b''.join(decrypted_chunks)
    
    # Remove padding from the final result
    return unpad(decrypted_padded_data)

# � Secure session-based encryption functions for temporary use
def encrypt_session_data(data: bytes, session_key: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt data with session-based keys (for temporary/in-memory use only).
    
    Args:
        data: Data to encrypt
        session_key: Optional session key, generates random if None
    
    Returns:
        tuple: (encrypted_data, key, iv) - Keep key in memory only
    """
    return encrypt_bytes(data, session_key)

def decrypt_session_data(encrypted_data: bytes, key: bytes, iv: bytes) -> bytes:
    """
    Decrypt session-based encrypted data.
    
    Args:
        encrypted_data: Encrypted data
        key: Session key (from memory)
        iv: IV used for encryption
    
    Returns:
        bytes: Decrypted data
    """
    return decrypt_bytes(encrypted_data, key, iv)
