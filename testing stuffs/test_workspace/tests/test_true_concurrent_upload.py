#!/usr/bin/env python3
"""
🧪 Test True Concurrent Upload Start
Test to verify that files start uploading immediately without waiting for preparation of other files.
"""

import sys
import time
import asyncio
from pathlib import Path

# Add the parent directory to the path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.routes import upload_auto_file
from fastapi import UploadFile, BackgroundTasks, Request
import io

class MockRequest:
    """Mock request object for testing"""
    def __init__(self, scheme="https"):
        self.url = type('obj', (object,), {'scheme': scheme})()

class MockBackgroundTasks:
    """Mock background tasks for testing"""
    def __init__(self):
        self.tasks = []
    
    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))

def create_test_upload_file(filename: str, size_mb: int = 1):
    """Create a test UploadFile"""
    content = b"T" * (size_mb * 1024 * 1024)  # Create content of specified size
    file_obj = io.BytesIO(content)
    upload_file = UploadFile(filename=filename, file=file_obj)
    upload_file.size = len(content)
    return upload_file

async def test_concurrent_upload_timing():
    """Test that uploads start immediately without waiting for file preparation"""
    print("🧪 Testing Concurrent Upload Timing...")
    
    # Create test files with different sizes
    test_files = [
        create_test_upload_file("small_1.txt", 1),      # 1MB
        create_test_upload_file("small_2.txt", 1),      # 1MB  
        create_test_upload_file("medium.txt", 5),       # 5MB
        create_test_upload_file("large.txt", 10),       # 10MB
    ]
    
    print(f"📁 Created {len(test_files)} test files")
    
    # Mock dependencies
    request = MockRequest(scheme="https")
    background_tasks = MockBackgroundTasks()
    
    # Time the total operation
    start_time = time.time()
    
    try:
        # This should now be much faster due to concurrent preparation + upload
        response = await upload_auto_file(
            request=request,
            background_tasks=background_tasks,
            files=test_files,
            encrypt=False
        )
        
        total_time = time.time() - start_time
        
        print(f"⏱️ Total upload time: {total_time:.3f} seconds")
        print(f"📊 Average per file: {total_time/len(test_files):.3f} seconds")
        
        # Check if response indicates success
        if hasattr(response, 'status_code') and response.status_code == 200:
            print("✅ Upload completed successfully")
            return True
        else:
            print(f"❌ Upload failed with response: {response}")
            return False
            
    except Exception as e:
        print(f"❌ Upload failed with exception: {e}")
        return False

async def test_upload_order_independence():
    """Test that file upload order doesn't matter for start time"""
    print("\n🧪 Testing Upload Order Independence...")
    
    # Test 1: Small files first
    small_first_files = [
        create_test_upload_file("small_a.txt", 1),     # 1MB
        create_test_upload_file("small_b.txt", 1),     # 1MB
        create_test_upload_file("large_a.txt", 20),    # 20MB
    ]
    
    # Test 2: Large files first  
    large_first_files = [
        create_test_upload_file("large_b.txt", 20),    # 20MB
        create_test_upload_file("small_c.txt", 1),     # 1MB
        create_test_upload_file("small_d.txt", 1),     # 1MB
    ]
    
    request = MockRequest(scheme="https")
    
    # Test small files first
    start_time = time.time()
    try:
        await upload_auto_file(
            request=request,
            background_tasks=MockBackgroundTasks(),
            files=small_first_files,
            encrypt=False
        )
        small_first_time = time.time() - start_time
        print(f"⏱️ Small files first: {small_first_time:.3f} seconds")
    except Exception as e:
        print(f"❌ Small first test failed: {e}")
        return False
    
    # Test large files first
    start_time = time.time()
    try:
        await upload_auto_file(
            request=request,
            background_tasks=MockBackgroundTasks(),
            files=large_first_files,
            encrypt=False
        )
        large_first_time = time.time() - start_time
        print(f"⏱️ Large files first: {large_first_time:.3f} seconds")
    except Exception as e:
        print(f"❌ Large first test failed: {e}")
        return False
    
    # Times should be similar (within 50% of each other)
    time_ratio = max(small_first_time, large_first_time) / min(small_first_time, large_first_time)
    
    if time_ratio < 1.5:  # Within 50% of each other
        print(f"✅ Upload order independence confirmed (ratio: {time_ratio:.2f})")
        return True
    else:
        print(f"❌ Upload order still affects timing (ratio: {time_ratio:.2f})")
        return False

async def main():
    print("🚀 True Concurrent Upload Test Suite")
    print("=" * 60)
    
    test1_passed = await test_concurrent_upload_timing()
    test2_passed = await test_upload_order_independence()
    
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS:")
    print(f"   Concurrent Upload Timing: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"   Upload Order Independence: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED - True concurrent uploads achieved!")
        return True
    else:
        print("❌ Some tests failed - Sequential processing still present")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
