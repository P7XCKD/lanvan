#!/usr/bin/env python3
"""
🧪 Test Race Condition Fix - Temporary File Strategy
Test to verify that files are not visible in file list until upload is complete.
"""

import os
import sys
import time
import threading
from pathlib import Path

# Add the parent directory to the path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.routes import get_file_list, UPLOAD_FOLDER

def test_race_condition_fix():
    """
    Test that .tmp files are filtered from file list and only final files appear
    """
    print("🧪 Testing Race Condition Fix...")
    
    # Create test temporary file
    test_tmp_file = UPLOAD_FOLDER / "test_upload.txt.tmp"
    test_final_file = UPLOAD_FOLDER / "test_upload.txt"
    
    try:
        # Clean up any existing files
        if test_tmp_file.exists():
            test_tmp_file.unlink()
        if test_final_file.exists():
            test_final_file.unlink()
        
        print("✅ Step 1: Clean slate confirmed")
        
        # Get initial file list
        initial_files = get_file_list()
        initial_count = len(initial_files)
        print(f"📂 Initial file count: {initial_count}")
        
        # Create a .tmp file (simulating upload in progress)
        with open(test_tmp_file, 'w') as f:
            f.write("This is a temporary file being uploaded...")
        
        print("📁 Step 2: Created .tmp file")
        
        # Check that .tmp file is NOT visible in file list
        temp_files = get_file_list()
        temp_count = len(temp_files)
        
        if temp_count == initial_count:
            print("✅ Step 3: .tmp file correctly hidden from file list")
        else:
            print("❌ FAIL: .tmp file appeared in file list!")
            return False
        
        # Simulate atomic move (upload completion)
        test_tmp_file.rename(test_final_file)
        print("🔄 Step 4: Simulated atomic move (.tmp → final)")
        
        # Check that final file IS visible in file list
        final_files = get_file_list()
        final_count = len(final_files)
        
        if final_count == initial_count + 1:
            print("✅ Step 5: Final file correctly visible in file list")
            
            # Verify the file is in the list
            file_names = [str(f['name']) for f in final_files]
            if 'test_upload.txt' in file_names:
                print("✅ Step 6: Correct filename found in file list")
                return True
            else:
                print("❌ FAIL: Final file not found in file list!")
                return False
        else:
            print("❌ FAIL: Final file count incorrect!")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False
    finally:
        # Clean up test files
        if test_tmp_file.exists():
            test_tmp_file.unlink()
        if test_final_file.exists():
            test_final_file.unlink()
        print("🧹 Cleanup completed")

def test_concurrent_scenario():
    """
    Test concurrent uploads to ensure no race conditions
    """
    print("\n🧪 Testing Concurrent Upload Scenario...")
    
    results = []
    
    def simulate_upload(file_id):
        """Simulate an upload process"""
        # Use timestamp to ensure unique filenames
        timestamp = int(time.time() * 1000)  # milliseconds
        tmp_file = UPLOAD_FOLDER / f"concurrent_test_{file_id}_{timestamp}.txt.tmp"
        final_file = UPLOAD_FOLDER / f"concurrent_test_{file_id}_{timestamp}.txt"
        
        try:
            # Step 1: Create temp file
            with open(tmp_file, 'w') as f:
                f.write(f"Upload {file_id} in progress...")
            
            # Step 2: Simulate upload delay
            time.sleep(0.1)
            
            # Step 3: Check file list during upload
            files_during_upload = get_file_list()
            temp_visible = any(str(f['name']).endswith('.tmp') for f in files_during_upload)
            
            # Step 4: Complete upload (atomic move)
            if tmp_file.exists():  # Safety check
                tmp_file.rename(final_file)
            
            # Step 5: Check file list after upload
            files_after_upload = get_file_list()
            final_visible = any(str(f['name']) == f"concurrent_test_{file_id}_{timestamp}.txt" for f in files_after_upload)
            
            results.append({
                'file_id': file_id,
                'temp_visible': temp_visible,
                'final_visible': final_visible,
                'success': not temp_visible and final_visible
            })
            
        except Exception as e:
            results.append({
                'file_id': file_id,
                'error': str(e),
                'success': False
            })
        finally:
            # Safe cleanup - check if files exist before trying to delete
            try:
                if tmp_file.exists():
                    tmp_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors
            try:
                if final_file.exists():
                    final_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors
    
    # Start multiple concurrent uploads
    threads = []
    for i in range(5):
        thread = threading.Thread(target=simulate_upload, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all uploads to complete
    for thread in threads:
        thread.join()
    
    # Analyze results
    successful = sum(1 for r in results if r.get('success', False))
    
    print(f"📊 Results: {successful}/{len(results)} uploads successful")
    
    for result in results:
        if result.get('success'):
            print(f"✅ Upload {result['file_id']}: Temp hidden, Final visible")
        else:
            print(f"❌ Upload {result['file_id']}: Failed - {result}")
    
    return successful == len(results)

if __name__ == "__main__":
    print("🚀 Race Condition Fix Test Suite")
    print("=" * 50)
    
    # Ensure upload folder exists
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    
    # Run tests
    test1_passed = test_race_condition_fix()
    test2_passed = test_concurrent_scenario()
    
    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS:")
    print(f"   Basic Race Condition Test: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"   Concurrent Upload Test: {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED - Race condition fix working correctly!")
        sys.exit(0)
    else:
        print("❌ Some tests failed - Race condition fix needs attention")
        sys.exit(1)
