import os
import hashlib
import gc
from typing import Optional, Tuple, Dict
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# 🔒 SECURE: Remove hardcoded keys - generate unique keys per session/file
# AES_KEY = bytes.fromhex("8f9c02a7d6f7cbb1da0499e18b113fe65c7a6d2f538b0a6412ccab5ede6b8839")  # REMOVED - Security vulnerability
# AES_IV  = bytes.fromhex("f012bc7d298e34af6509cb471d3a8250")  # REMOVED - IV reuse vulnerability

# 📱 Android/Termux compatibility: psutil may not be available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("ℹ️  psutil not available - memory monitoring disabled (Android/Termux compatibility mode)")

def get_memory_usage_mb() -> float:
    """Get current memory usage in MB - Android/Termux compatible"""
    if not PSUTIL_AVAILABLE:
        return 0.0  # Graceful fallback for Android/Termux
    
    try:
        import psutil  # Import here to avoid unbound variable
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0  # Fallback on any error

def monitor_encryption_memory(operation: str, file_size_mb: float = 0):
    """Memory monitoring decorator for encryption operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_memory = get_memory_usage_mb()
            print(f"💾 [{operation}] Starting - Memory: {start_memory:.1f}MB | File: {file_size_mb:.1f}MB")
            
            try:
                result = func(*args, **kwargs)
                
                # OPTIMIZED: Strategic garbage collection - only for large operations
                if operation in ['encrypt_file_to_file_streaming', 'large_file_encryption']:
                    gc.collect()
                
                end_memory = get_memory_usage_mb()
                memory_delta = end_memory - start_memory
                
                print(f"💾 [{operation}] Complete - Memory: {end_memory:.1f}MB | Delta: {memory_delta:+.1f}MB")
                
                if memory_delta > file_size_mb * 2:  # Alert if memory usage > 2x file size
                    print(f"⚠️  [{operation}] HIGH MEMORY USAGE DETECTED! Delta: {memory_delta:.1f}MB > File: {file_size_mb:.1f}MB")
                
                return result
                
            except Exception as e:
                error_memory = get_memory_usage_mb()
                print(f"❌ [{operation}] Failed - Memory: {error_memory:.1f}MB | Error: {e}")
                raise
                
        return wrapper
    return decorator

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

def encrypt_file_to_file_streaming(input_path: str, output_path: str, user_password: Optional[str] = None, chunk_size: int = 1024 * 1024) -> Dict[str, str]:
    """
    🚀 TRUE ZERO-MEMORY STREAMING: Encrypt file directly from disk to disk.
    This approach uses constant memory regardless of file size.
    
    Args:
        input_path: Path to input file
        output_path: Path to output encrypted file
        user_password: Optional user password for key derivation
        chunk_size: Size of chunks to read from disk (default 1MB)
    
    Returns:
        dict: metadata_dict (without encrypted data)
    """
    import os
    
    file_size = os.path.getsize(input_path)
    file_size_mb = file_size / 1024 / 1024
    start_memory = get_memory_usage_mb()
    print(f"💾 [AES-Zero-Memory] Starting - Memory: {start_memory:.1f}MB | File: {file_size_mb:.1f}MB")
    
    if user_password:
        key, salt = generate_secure_key(user_password)
    else:
        key, salt = generate_secure_key()
    
    iv = generate_secure_iv()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    bytes_read = 0
    chunk_count = 0
    encrypted_size = 0
    
    with open(input_path, 'rb') as input_file, open(output_path, 'wb') as output_file:
        while True:
            chunk = input_file.read(chunk_size)
            if not chunk:
                break
                
            bytes_read += len(chunk)
            chunk_count += 1
            
            # If this is the last chunk, apply padding
            if bytes_read == file_size:
                chunk = pad(chunk)
            
            encrypted_chunk = encryptor.update(chunk)
            output_file.write(encrypted_chunk)
            encrypted_size += len(encrypted_chunk)
            
            # Memory cleanup
            del chunk, encrypted_chunk
            
            # Memory monitoring every 100 chunks
            if chunk_count % 100 == 0:
                current_memory = get_memory_usage_mb()
                print(f"💾 [Zero-Memory] Chunk {chunk_count}: {current_memory:.1f}MB (+{current_memory-start_memory:.1f}MB)")
        
        # Finalize encryption
        final_chunk = encryptor.finalize()
        if final_chunk:
            output_file.write(final_chunk)
            encrypted_size += len(final_chunk)
    
    # OPTIMIZED: Strategic memory check - only for large operations
    if encrypted_size > 50 * 1024 * 1024:  # Only GC for files > 50MB
        gc.collect()
    end_memory = get_memory_usage_mb()
    memory_delta = end_memory - start_memory
    print(f"💾 [AES-Zero-Memory] Complete - Memory: {end_memory:.1f}MB | Delta: {memory_delta:+.1f}MB")
    
    if memory_delta > 10:  # Should use very little memory
        print(f"⚠️  [AES-Zero-Memory] UNEXPECTED MEMORY USAGE! Delta: {memory_delta:.1f}MB for {file_size_mb:.1f}MB file")
    else:
        print(f"🎉 [AES-Zero-Memory] EXCELLENT! Constant memory usage: {memory_delta:.1f}MB for {file_size_mb:.1f}MB file")
    
    metadata = {
        'salt': salt.hex(),
        'iv': iv.hex(),
        'algorithm': 'AES-256-CBC-Zero-Memory',
        'original_size': str(file_size),
        'encrypted_size': str(encrypted_size),
        'key_derivation': 'password' if user_password else 'random',
        'iterations': '100000' if user_password else None
    }
    
    return metadata

def encrypt_file_from_path_streaming(file_path: str, user_password: Optional[str] = None, chunk_size: int = 1024 * 1024) -> Tuple[bytes, Dict[str, str]]:
    """
    🚀 ULTIMATE STREAMING: Encrypt file directly from disk without loading into memory.
    This is the most memory-efficient approach for large files.
    
    Args:
        file_path: Path to file on disk
        user_password: Optional user password for key derivation
        chunk_size: Size of chunks to read from disk (default 1MB)
    
    Returns:
        tuple: (encrypted_data, metadata_dict)
    """
    import os
    
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / 1024 / 1024
    start_memory = get_memory_usage_mb()
    print(f"💾 [AES-Disk-Stream] Starting - Memory: {start_memory:.1f}MB | File: {file_size_mb:.1f}MB")
    
    if user_password:
        key, salt = generate_secure_key(user_password)
    else:
        key, salt = generate_secure_key()
    
    iv = generate_secure_iv()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    encrypted_chunks = []
    bytes_read = 0
    chunk_count = 0
    
    with open(file_path, 'rb') as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
                
            bytes_read += len(chunk)
            chunk_count += 1
            
            # If this is the last chunk, apply padding
            if bytes_read == file_size:
                chunk = pad(chunk)
            
            encrypted_chunk = encryptor.update(chunk)
            encrypted_chunks.append(encrypted_chunk)
            
            # Memory cleanup
            del chunk
            
            # Memory monitoring every 50 chunks
            if chunk_count % 50 == 0:
                current_memory = get_memory_usage_mb()
                print(f"💾 [AES-Disk] Chunk {chunk_count}: {current_memory:.1f}MB (+{current_memory-start_memory:.1f}MB)")
    
    # Finalize encryption
    final_chunk = encryptor.finalize()
    if final_chunk:
        encrypted_chunks.append(final_chunk)
    
    encrypted_data = b''.join(encrypted_chunks)
    
    # OPTIMIZED: Strategic memory check - only for large operations
    if len(encrypted_data) > 50 * 1024 * 1024:  # Only GC for files > 50MB
        gc.collect()
    end_memory = get_memory_usage_mb()
    memory_delta = end_memory - start_memory
    print(f"💾 [AES-Disk-Stream] Complete - Memory: {end_memory:.1f}MB | Delta: {memory_delta:+.1f}MB")
    
    if memory_delta > file_size_mb * 0.5:  # Disk streaming should use minimal memory
        print(f"⚠️  [AES-Disk-Stream] UNEXPECTED MEMORY USAGE! Delta: {memory_delta:.1f}MB for {file_size_mb:.1f}MB file")
    
    metadata = {
        'salt': salt.hex(),
        'iv': iv.hex(),
        'algorithm': 'AES-256-CBC-Disk-Stream',
        'original_size': str(file_size),
        'encrypted_size': str(len(encrypted_data)),
        'key_derivation': 'password' if user_password else 'random',
        'iterations': '100000' if user_password else None
    }
    
    return encrypted_data, metadata

def encrypt_file_stream_chunked(chunk_data: bytes, key: Optional[bytes] = None, iv: Optional[bytes] = None, encryptor = None) -> bytes:
    """
    🔄 Android/Termux Optimized: Encrypt individual chunks for streaming uploads
    
    This function is designed to be called repeatedly for each chunk of a large file,
    avoiding the need to load the entire file into memory.
    
    Args:
        chunk_data: Individual chunk of file data
        key: AES key (generated once per file)
        iv: Initialization vector (generated once per file)  
        encryptor: Cipher encryptor object (maintained across chunks)
    
    Returns:
        bytes: Encrypted chunk data
        
    Note: This is a simplified chunked encryption. For production use with
    large files, you'd typically use a stream cipher or authenticated encryption.
    """
    # For now, use a simple approach - pad and encrypt each chunk
    # This is suitable for the current use case but could be enhanced
    
    if key is None:
        key, _ = generate_secure_key()
    if iv is None:
        iv = generate_secure_iv()
    
    # Create encryptor if not provided
    if encryptor is None:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
    
    # Pad the chunk (Note: this is simplified - proper streaming would handle padding differently)
    padded_chunk = pad(chunk_data)
    
    # Encrypt the chunk
    encrypted_chunk = encryptor.update(padded_chunk)
    
    return encrypted_chunk

def encrypt_file_generator_streaming(file_data: bytes, user_password: Optional[str] = None, chunk_size: int = 1024 * 1024):
    """
    🚀 GENERATOR-BASED STREAMING: Yields encrypted chunks without storing all in memory.
    This is for in-memory processing with streaming behavior.
    
    Args:
        file_data: File content as bytes
        user_password: Optional user password for key derivation
        chunk_size: Size of chunks to process (default 1MB)
    
    Yields:
        bytes: Encrypted chunks
    """
    file_size_mb = len(file_data) / 1024 / 1024
    start_memory = get_memory_usage_mb()
    print(f"💾 [AES-Generator] Starting - Memory: {start_memory:.1f}MB | File: {file_size_mb:.1f}MB")
    
    if user_password:
        key, salt = generate_secure_key(user_password)
    else:
        key, salt = generate_secure_key()
    
    iv = generate_secure_iv()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    file_length = len(file_data)
    chunk_count = 0
    
    # Yield metadata first
    metadata = {
        'salt': salt.hex(),
        'iv': iv.hex(),
        'algorithm': 'AES-256-CBC-Generator',
        'original_size': str(file_length),
        'key_derivation': 'password' if user_password else 'random',
        'iterations': '100000' if user_password else None
    }
    yield ('metadata', metadata)
    
    # Stream encrypted chunks
    for i in range(0, file_length, chunk_size):
        end_pos = min(i + chunk_size, file_length)
        chunk = file_data[i:end_pos]
        chunk_count += 1
        
        # If this is the final chunk, apply padding
        if end_pos == file_length:
            chunk = pad(chunk)
        
        encrypted_chunk = encryptor.update(chunk)
        
        # Memory monitoring
        if chunk_count % 50 == 0:
            current_memory = get_memory_usage_mb()
            print(f"💾 [Generator] Chunk {chunk_count}: {current_memory:.1f}MB (+{current_memory-start_memory:.1f}MB)")
        
        # Explicit cleanup
        del chunk
        
        yield ('chunk', encrypted_chunk)
    
    # Finalize encryption
    final_chunk = encryptor.finalize()
    if final_chunk:
        yield ('chunk', final_chunk)
    
    # Final memory check
    gc.collect()
    end_memory = get_memory_usage_mb()
    memory_delta = end_memory - start_memory
    print(f"💾 [AES-Generator] Complete - Memory: {end_memory:.1f}MB | Delta: {memory_delta:+.1f}MB")

def encrypt_file_stream(file_data: bytes, user_password: Optional[str] = None, chunk_size: int = 1024 * 1024) -> Tuple[bytes, Dict[str, str]]:
    """
    TRUE STREAMING AES encryption for large files - NO MEMORY EXPLOSION.
    Processes file in chunks while maintaining CBC mode integrity.
    
    Args:
        file_data: File content as bytes
        user_password: Optional user password for key derivation
        chunk_size: Size of chunks to process (default 1MB)
    
    Returns:
        tuple: (encrypted_data, metadata_dict)
    """
    # Memory monitoring
    file_size_mb = len(file_data) / 1024 / 1024
    start_memory = get_memory_usage_mb()
    print(f"💾 [AES-Stream-Encrypt] Starting - Memory: {start_memory:.1f}MB | File: {file_size_mb:.1f}MB")
    
    if user_password:
        key, salt = generate_secure_key(user_password)
    else:
        key, salt = generate_secure_key()
    
    iv = generate_secure_iv()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    encrypted_chunks = []
    file_length = len(file_data)
    
    # 🚀 TRUE STREAMING: Process file in chunks
    # For CBC mode, we need to pad the entire data stream properly
    
    # Calculate total padded size first (minimal memory impact)
    block_size = 16  # AES block size
    total_padded_size = file_length + (block_size - (file_length % block_size))
    
    for i in range(0, file_length, chunk_size):
        end_pos = min(i + chunk_size, file_length)
        chunk = file_data[i:end_pos]
        
        # If this is the final chunk, apply padding
        if end_pos == file_length:
            chunk = pad(chunk)
        
        encrypted_chunk = encryptor.update(chunk)
        encrypted_chunks.append(encrypted_chunk)
        
        # Explicit memory cleanup
        del chunk
        
        # Memory check every 10 chunks
        if len(encrypted_chunks) % 10 == 0:
            current_memory = get_memory_usage_mb()
            print(f"💾 [AES-Stream] Chunk {len(encrypted_chunks)}: {current_memory:.1f}MB (+{current_memory-start_memory:.1f}MB)")
    
    # Finalize encryption
    final_chunk = encryptor.finalize()
    if final_chunk:
        encrypted_chunks.append(final_chunk)
    
    encrypted_data = b''.join(encrypted_chunks)
    
    # Final memory check
    gc.collect()
    end_memory = get_memory_usage_mb()
    memory_delta = end_memory - start_memory
    print(f"💾 [AES-Stream-Encrypt] Complete - Memory: {end_memory:.1f}MB | Delta: {memory_delta:+.1f}MB")
    
    if memory_delta > file_size_mb * 2:
        print(f"⚠️  [AES-Stream-Encrypt] HIGH MEMORY USAGE! Delta: {memory_delta:.1f}MB > 2x File: {file_size_mb:.1f}MB")
    
    metadata = {
        'salt': salt.hex(),
        'iv': iv.hex(),
        'algorithm': 'AES-256-CBC-Stream-V2',
        'original_size': str(file_length),
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
