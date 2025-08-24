#!/usr/bin/env python3
"""
🧪 Test Concurrent Upload Start Speed
Test to verify that concurrent uploads start immediately without validation delays.
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

def create_mock_upload_file(filename: str, size_mb: int = 1):
    """Create a mock UploadFile for testing"""
    content = b"0" * (size_mb * 1024 * 1024)  # Create content of specified size
    
    # Create a proper UploadFile instance
    file_obj = io.BytesIO(content)
    upload_file = UploadFile(filename=filename, file=file_obj)
    upload_file.size = len(content)  # Set size attribute
    
    return upload_file

async def test_validation_speed():
    """Test how fast validation completes for multiple files"""
    print("🧪 Testing Validation Speed...")
    
    # Create test files of different sizes
    test_files = [
        create_mock_upload_file("small_file_1.txt", 1),      # 1MB
        create_mock_upload_file("small_file_2.txt", 1),      # 1MB
        create_mock_upload_file("medium_file.txt", 10),      # 10MB
        create_mock_upload_file("large_file.txt", 50),       # 50MB
        create_mock_upload_file("huge_file.txt", 100),       # 100MB
    ]
    
    print(f"📁 Created {len(test_files)} test files")
    
    # Test fast validation
    print("🚀 Testing fast validation...")
    start_time = time.time()
    
    is_valid, errors, validated_files, warnings = await validate_upload_files_enhanced_fast(
        test_files, encrypt=False, is_https=True
    )
    
    fast_validation_time = time.time() - start_time
    
    print(f"⏱️ Fast validation completed in: {fast_validation_time:.3f} seconds")
    print(f"✅ Valid: {is_valid}")
    print(f"📊 Files validated: {len(validated_files)}")
    print(f"❌ Errors: {len(errors)}")
    
    if fast_validation_time > 0.1:  # Should be under 100ms
        print("⚠️ WARNING: Validation taking too long for immediate upload start!")
        return False
    else:
        print("🎉 SUCCESS: Validation fast enough for immediate concurrent upload!")
        return True

async def test_concurrent_validation():
    """Test that validation of multiple files happens concurrently"""
    print("\n🧪 Testing Concurrent Validation...")
    
    # Create many small files to test concurrency
    test_files = [
        create_mock_upload_file(f"concurrent_test_{i}.txt", 1) 
        for i in range(20)  # 20 files
    ]
    
    print(f"📁 Created {len(test_files)} files for concurrent validation")
    
    start_time = time.time()
    
    is_valid, errors, validated_files, warnings = await validate_upload_files_enhanced_fast(
        test_files, encrypt=False, is_https=True
    )
    
    validation_time = time.time() - start_time
    
    print(f"⏱️ Concurrent validation of {len(test_files)} files: {validation_time:.3f} seconds")
    print(f"📊 Average per file: {validation_time/len(test_files)*1000:.1f}ms")
    
    # Should validate 20 files almost as fast as 1 file due to concurrency
    if validation_time < 0.5:  # Under 500ms for 20 files
        print("🎉 SUCCESS: True concurrent validation achieved!")
        return True
    else:
        print("⚠️ WARNING: Validation not truly concurrent - too slow!")
        return False

async def main():
    print("🚀 Concurrent Upload Start Speed Test")
    print("=" * 50)
    
    test1_passed = await test_validation_speed()
    test2_passed = await test_concurrent_validation()
    
    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS:")
    print(f"   Fast Validation Test: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"   Concurrent Validation Test: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED - Concurrent uploads will start immediately!")
        return True
    else:
        print("❌ Some tests failed - Validation still causing delays")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
