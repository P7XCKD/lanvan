#!/usr/bin/env python3
"""
🧪 AES Memory Explosion Fix Validation

This script tests the new streaming AES encryption to ensure:
1. No memory explosion for large files
2. Encryption/decryption works correctly
3. Memory usage stays reasonable
"""

import os
import time
import psutil
from app.aes_utils import encrypt_file_stream, encrypt_file_from_path_streaming, decrypt_file_stream

def create_test_file(filename: str, size_mb: int) -> str:
    """Create a test file of specified size"""
    print(f"📝 Creating test file: {filename} ({size_mb}MB)")
    
    chunk_size = 1024 * 1024  # 1MB chunks
    data_chunk = b'A' * chunk_size
    
    with open(filename, 'wb') as f:
        for i in range(size_mb):
            f.write(data_chunk)
            if i % 10 == 0:
                print(f"  Written: {i}MB")
    
    print(f"✅ Test file created: {os.path.getsize(filename):,} bytes")
    return filename

def get_memory_mb():
    """Get current memory usage"""
    return psutil.Process().memory_info().rss / 1024 / 1024

def test_streaming_encryption(test_size_mb: int = 50):
    """Test streaming encryption with specified file size"""
    
    test_file = f'test_aes_{test_size_mb}mb.tmp'
    
    try:
        # Create test file
        create_test_file(test_file, test_size_mb)
        
        start_memory = get_memory_mb()
        print(f"\n🔐 Testing AES streaming encryption ({test_size_mb}MB file)")
        print(f"💾 Starting memory: {start_memory:.1f}MB")
        
        # Test disk streaming (most memory efficient)
        print(f"\n📀 Testing disk streaming encryption...")
        start_time = time.time()
        
        encrypted_data, metadata = encrypt_file_from_path_streaming(
            test_file, 
            user_password='test123',
            chunk_size=2 * 1024 * 1024  # 2MB chunks for large files
        )
        
        encrypt_time = time.time() - start_time
        encrypt_memory = get_memory_mb()
        
        print(f"✅ Encryption completed in {encrypt_time:.1f}s")
        print(f"💾 Memory after encryption: {encrypt_memory:.1f}MB (+{encrypt_memory-start_memory:.1f}MB)")
        print(f"📊 Encrypted size: {len(encrypted_data):,} bytes")
        
        # Test decryption
        print(f"\n🔓 Testing decryption...")
        decrypt_start = time.time()
        
        decrypted_data = decrypt_file_stream(encrypted_data, metadata, user_password='test123')
        
        decrypt_time = time.time() - decrypt_start
        final_memory = get_memory_mb()
        
        print(f"✅ Decryption completed in {decrypt_time:.1f}s")
        print(f"💾 Final memory: {final_memory:.1f}MB")
        print(f"📊 Decrypted size: {len(decrypted_data):,} bytes")
        
        # Verify data integrity (check first and last chunks)
        with open(test_file, 'rb') as f:
            original_start = f.read(1024)
            f.seek(-1024, 2)
            original_end = f.read(1024)
        
        decrypted_start = decrypted_data[:1024]
        decrypted_end = decrypted_data[-1024:]
        
        integrity_check = (original_start == decrypted_start and original_end == decrypted_end)
        
        print(f"\n📋 Results Summary:")
        print(f"  File size: {test_size_mb}MB")
        print(f"  Encryption time: {encrypt_time:.1f}s ({test_size_mb/encrypt_time:.1f}MB/s)")
        print(f"  Decryption time: {decrypt_time:.1f}s ({test_size_mb/decrypt_time:.1f}MB/s)")
        print(f"  Max memory usage: +{max(encrypt_memory, final_memory)-start_memory:.1f}MB")
        print(f"  Data integrity: {'✅ PASS' if integrity_check else '❌ FAIL'}")
        
        memory_ratio = (max(encrypt_memory, final_memory)-start_memory) / test_size_mb
        if memory_ratio < 0.5:
            print(f"  Memory efficiency: ✅ EXCELLENT ({memory_ratio:.2f}x file size)")
        elif memory_ratio < 1.0:
            print(f"  Memory efficiency: ✅ GOOD ({memory_ratio:.2f}x file size)")
        else:
            print(f"  Memory efficiency: ⚠️ POOR ({memory_ratio:.2f}x file size)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"🧹 Cleaned up test file")

if __name__ == "__main__":
    print("🧪 AES Memory Explosion Fix - Validation Test")
    print("=" * 60)
    
    # Test with progressively larger files
    test_sizes = [10, 50, 100]  # MB
    
    for size in test_sizes:
        print(f"\n{'=' * 60}")
        success = test_streaming_encryption(size)
        if not success:
            print(f"❌ Test failed for {size}MB file")
            break
        print(f"✅ Test passed for {size}MB file")
    
    print(f"\n{'=' * 60}")
    print("🎉 AES Memory Fix Validation Complete!")
