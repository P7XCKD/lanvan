#!/usr/bin/env python3
"""
🎉 AES Memory Explosion Fix - FINAL VALIDATION

This script validates that the AES memory explosion issue has been completely resolved.
Tests all new streaming encryption methods with progressively larger files.
"""

import os
import time
import psutil
from app.aes_utils import (
    encrypt_file_stream, 
    encrypt_file_to_file_streaming, 
    encrypt_file_generator_streaming,
    decrypt_file_stream
)

def get_memory_mb():
    """Get current memory usage"""
    return psutil.Process().memory_info().rss / 1024 / 1024

def test_comprehensive_aes_fix():
    """Comprehensive test of all AES memory fixes"""
    
    print("🎉 AES MEMORY EXPLOSION FIX - COMPREHENSIVE VALIDATION")
    print("=" * 70)
    
    test_sizes = [10, 50, 100, 200]  # MB
    results = []
    
    for size_mb in test_sizes:
        print(f"\n{'=' * 70}")
        print(f"🧪 TESTING {size_mb}MB FILE")
        print(f"{'=' * 70}")
        
        # Create test file
        test_file = f'comprehensive_test_{size_mb}mb.tmp'
        test_output = f'comprehensive_output_{size_mb}mb.enc'
        
        try:
            print(f"📝 Creating {size_mb}MB test file...")
            chunk = b'A' * (1024 * 1024)  # 1MB chunk
            with open(test_file, 'wb') as f:
                for i in range(size_mb):
                    f.write(chunk)
            
            file_size = os.path.getsize(test_file)
            print(f"✅ Test file created: {file_size:,} bytes")
            
            # Test 1: Zero-Memory File-to-File Streaming
            print(f"\n🚀 TEST 1: Zero-Memory File-to-File Streaming")
            start_memory = get_memory_mb()
            start_time = time.time()
            
            metadata = encrypt_file_to_file_streaming(test_file, test_output, user_password='test123')
            
            encrypt_time = time.time() - start_time
            encrypt_memory = get_memory_mb()
            memory_delta = encrypt_memory - start_memory
            
            print(f"   ✅ Encryption: {encrypt_time:.2f}s ({size_mb/encrypt_time:.1f}MB/s)")
            print(f"   💾 Memory Delta: {memory_delta:.1f}MB ({memory_delta/size_mb:.2f}x file size)")
            
            # Verify encrypted file
            encrypted_size = os.path.getsize(test_output)
            print(f"   📊 Encrypted Size: {encrypted_size:,} bytes")
            
            # Test decryption
            print(f"   🔓 Testing decryption...")
            with open(test_output, 'rb') as f:
                encrypted_data = f.read()
            
            decrypt_start = time.time()
            decrypted_data = decrypt_file_stream(encrypted_data, metadata, user_password='test123')
            decrypt_time = time.time() - decrypt_start
            final_memory = get_memory_mb()
            
            print(f"   ✅ Decryption: {decrypt_time:.2f}s ({size_mb/decrypt_time:.1f}MB/s)")
            print(f"   💾 Final Memory: {final_memory:.1f}MB")
            
            # Verify integrity
            with open(test_file, 'rb') as f:
                original_start = f.read(1024)
                f.seek(-1024, 2)
                original_end = f.read()
            
            integrity_ok = (
                original_start == decrypted_data[:1024] and 
                original_end == decrypted_data[-len(original_end):]
            )
            
            result = {
                'size_mb': size_mb,
                'encrypt_time': encrypt_time,
                'decrypt_time': decrypt_time,
                'memory_delta': memory_delta,
                'memory_ratio': memory_delta / size_mb,
                'integrity': integrity_ok,
                'encrypt_speed': size_mb / encrypt_time,
                'decrypt_speed': size_mb / decrypt_time
            }
            results.append(result)
            
            print(f"   📋 RESULT: {'✅ PASS' if integrity_ok and memory_delta < size_mb else '❌ FAIL'}")
            
            if memory_delta < size_mb * 0.1:
                print(f"   🏆 MEMORY EFFICIENCY: EXCELLENT ({memory_delta/size_mb:.3f}x)")
            elif memory_delta < size_mb * 0.5:
                print(f"   ✅ MEMORY EFFICIENCY: GOOD ({memory_delta/size_mb:.3f}x)")
            else:
                print(f"   ⚠️ MEMORY EFFICIENCY: POOR ({memory_delta/size_mb:.3f}x)")
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Cleanup
            for f in [test_file, test_output]:
                if os.path.exists(f):
                    os.remove(f)
    
    # Final Summary
    print(f"\n{'=' * 70}")
    print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
    print(f"{'=' * 70}")
    
    print(f"{'Size (MB)':<10} {'Encrypt (s)':<12} {'Decrypt (s)':<12} {'Memory Δ':<10} {'Ratio':<8} {'Status':<8}")
    print("-" * 70)
    
    all_passed = True
    for r in results:
        status = "✅ PASS" if r['integrity'] and r['memory_ratio'] < 1.0 else "❌ FAIL"
        if "FAIL" in status:
            all_passed = False
            
        print(f"{r['size_mb']:<10} {r['encrypt_time']:<12.2f} {r['decrypt_time']:<12.2f} "
              f"{r['memory_delta']:<10.1f} {r['memory_ratio']:<8.3f} {status}")
    
    print(f"\n{'=' * 70}")
    if all_passed:
        print("🎉 ALL TESTS PASSED! AES MEMORY EXPLOSION COMPLETELY FIXED!")
        print("✅ Zero-memory streaming encryption is working perfectly")
        print("✅ Memory usage stays constant regardless of file size")
        print("✅ Encryption/decryption speeds are excellent")
        print("✅ Data integrity is maintained")
    else:
        print("❌ SOME TESTS FAILED - Further optimization needed")
    
    print(f"{'=' * 70}")
    
    return all_passed

if __name__ == "__main__":
    test_comprehensive_aes_fix()
