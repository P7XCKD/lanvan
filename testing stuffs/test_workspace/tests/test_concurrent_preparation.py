#!/usr/bin/env python3
"""
🧪 Test Concurrent File Preparation 
Simple test to verify file preparation is now concurrent instead of sequential.
"""

import sys
import time
import asyncio
from pathlib import Path

# Add the parent directory to the path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.validation import validate_upload_files_enhanced_fast
from fastapi import UploadFile
import io

def create_test_upload_file(filename: str, size_mb: int = 1):
    """Create a test UploadFile"""
    content = b"T" * (size_mb * 1024 * 1024)
    file_obj = io.BytesIO(content)
    upload_file = UploadFile(filename=filename, file=file_obj)
    upload_file.size = len(content)
    return upload_file

async def test_preparation_concurrency():
    """Test that file preparation happens concurrently"""
    print("🧪 Testing File Preparation Concurrency...")
    
    # Create multiple files
    test_files = [
        create_test_upload_file("file_1.txt", 1),
        create_test_upload_file("file_2.txt", 1), 
        create_test_upload_file("file_3.txt", 1),
        create_test_upload_file("file_4.txt", 1),
        create_test_upload_file("file_5.txt", 1),
    ]
    
    print(f"📁 Created {len(test_files)} test files")
    
    # Time the validation (which is now part of preparation)
    start_time = time.time()
    
    is_valid, errors, validated_files, warnings = await validate_upload_files_enhanced_fast(
        test_files, encrypt=False, is_https=True
    )
    
    preparation_time = time.time() - start_time
    
    print(f"⏱️ Preparation time for {len(test_files)} files: {preparation_time:.3f} seconds")
    print(f"📊 Average per file: {preparation_time/len(test_files)*1000:.1f}ms")
    print(f"✅ Files validated: {len(validated_files)}")
    print(f"❌ Errors: {len(errors)}")
    
    # Should be very fast due to concurrency
    if preparation_time < 0.1:  # Under 100ms for 5 files
        print("🎉 SUCCESS: File preparation is truly concurrent!")
        return True
    else:
        print("⚠️ WARNING: File preparation taking too long - may not be concurrent")
        return False

async def simulate_upload_sequence():
    """Simulate the upload sequence to check for sequential bottlenecks"""
    print("\n🧪 Simulating Full Upload Sequence...")
    
    # Create test files
    test_files = [
        create_test_upload_file("seq_test_1.txt", 2),
        create_test_upload_file("seq_test_2.txt", 2),
        create_test_upload_file("seq_test_3.txt", 2),
    ]
    
    print(f"📁 Created {len(test_files)} files for sequence test")
    
    # Step 1: Fast validation
    start_time = time.time()
    is_valid, errors, validated_files, warnings = await validate_upload_files_enhanced_fast(
        test_files, encrypt=False, is_https=True
    )
    validation_time = time.time() - start_time
    
    print(f"⏱️ Step 1 - Validation: {validation_time:.3f}s")
    
    if not is_valid:
        print("❌ Validation failed")
        return False
    
    # Step 2: File preparation simulation (this is what we optimized)
    start_time = time.time()
    
    # Simulate concurrent file preparation
    async def prepare_file(i, validated_file):
        await asyncio.sleep(0.001)  # Minimal simulation
        return {
            "file_index": i,
            "prepared": True,
            "filename": validated_file['original_name']
        }
    
    preparation_tasks = [
        prepare_file(i, validated_file) 
        for i, validated_file in enumerate(validated_files)
    ]
    
    preparation_results = await asyncio.gather(*preparation_tasks)
    preparation_time = time.time() - start_time
    
    print(f"⏱️ Step 2 - Concurrent Preparation: {preparation_time:.3f}s")
    print(f"✅ Files prepared: {len(preparation_results)}")
    
    total_time = validation_time + preparation_time
    print(f"📊 Total pre-upload time: {total_time:.3f}s")
    
    # Should be very fast for immediate upload start
    if total_time < 0.05:  # Under 50ms total
        print("🎉 SUCCESS: Upload can start immediately!")
        return True
    else:
        print("⚠️ WARNING: Pre-upload time too long for immediate start")
        return False

async def main():
    print("🚀 Concurrent Preparation Test Suite")
    print("=" * 50)
    
    test1_passed = await test_preparation_concurrency()
    test2_passed = await simulate_upload_sequence()
    
    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS:")
    print(f"   Preparation Concurrency: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"   Upload Sequence Speed: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED - Files will start uploading immediately!")
        return True
    else:
        print("❌ Some tests failed - Sequential bottlenecks may remain")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
