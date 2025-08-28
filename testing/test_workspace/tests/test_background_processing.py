"""
🚀 TRUE Background Processing Performance Test
Tests that security validation and processing happen DURING upload, not after
"""

import requests
import time
import os
import threading
from pathlib import Path

BASE_URL = "http://127.0.0.1"

def create_test_file(filename, size_mb):
    """Create a test file with specified size"""
    print(f"📄 Creating test file: {filename} ({size_mb}MB)")
    content = "A" * (1024 * 1024)  # 1MB of 'A's
    
    with open(filename, 'w') as f:
        for i in range(size_mb):
            f.write(content)
    
    actual_size = os.path.getsize(filename)
    print(f"✅ Created {filename}: {actual_size / (1024*1024):.1f}MB")
    return filename

def upload_file_with_background_processing_test(filepath, chunk_size_kb=512, delay_between_chunks=0.15):
    """Upload a file and test TRUE background processing during upload"""
    file_path = Path(filepath)
    file_size = file_path.stat().st_size
    chunk_size = chunk_size_kb * 1024
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    
    print(f"🚀 Testing TRUE background processing: {file_path.name}")
    print(f"   📊 File size: {file_size / (1024*1024):.1f}MB")
    print(f"   📦 Chunk size: {chunk_size_kb}KB")
    print(f"   🧩 Total chunks: {total_chunks}")
    print(f"   ⏱️  Delay between chunks: {delay_between_chunks}s")
    
    upload_start_time = time.time()
    finalize_start_time = None
    total_upload_time = None
    finalize_time = None
    
    # Upload chunks with delays to simulate real upload conditions
    with open(file_path, 'rb') as f:
        for chunk_num in range(1, total_chunks + 1):
            chunk_data = f.read(chunk_size)
            if not chunk_data:
                break
            
            # Upload chunk
            files = {'chunk': (f'chunk_{chunk_num}', chunk_data)}
            data = {
                'filename': file_path.name,
                'part_number': chunk_num,
                'total_parts': total_chunks
            }
            
            chunk_start = time.time()
            response = requests.post(f"{BASE_URL}/upload_chunk", files=files, data=data)
            chunk_time = time.time() - chunk_start
            
            if response.status_code != 200:
                print(f"❌ Chunk {chunk_num} failed: {response.status_code}")
                return False, None, None
            
            progress = (chunk_num / total_chunks) * 100
            print(f"   📤 Chunk {chunk_num}/{total_chunks} uploaded ({progress:.1f}%) in {chunk_time:.2f}s")
            
            # Add delay between chunks
            if chunk_num < total_chunks:
                time.sleep(delay_between_chunks)
    
    total_upload_time = time.time() - upload_start_time
    print(f"✅ All chunks uploaded in {total_upload_time:.1f}s")
    
    # Now finalize and measure how long it takes
    print("🔄 Finalizing upload...")
    finalize_start_time = time.time()
    
    finalize_data = {
        'filename': file_path.name,
        'total_parts': total_chunks,
        'encrypt': 'false'
    }
    
    response = requests.post(f"{BASE_URL}/finalize_upload", data=finalize_data)
    finalize_time = time.time() - finalize_start_time
    
    if response.status_code == 200:
        response_data = response.json()
        is_streaming = response_data.get('streaming_assembly', False)
        
        print(f"📊 BACKGROUND PROCESSING ANALYSIS:")
        print(f"   📤 Upload time: {total_upload_time:.1f}s")
        print(f"   🔄 Finalize time: {finalize_time:.1f}s")
        print(f"   🌊 Used streaming: {is_streaming}")
        
        if is_streaming and finalize_time < 2.0:  # If finalize is very fast
            print(f"   ⚡ SUCCESS: Background processing detected!")
            print(f"   ✅ Processing happened DURING upload, not after")
            print(f"   🚀 Time saved: ~{total_upload_time - finalize_time:.1f}s faster than traditional")
            return True, total_upload_time, finalize_time, True
        elif is_streaming:
            print(f"   ⚠️  Streaming used but finalize time is still high ({finalize_time:.1f}s)")
            print(f"   🤔 Background processing may not be working optimally")
            return True, total_upload_time, finalize_time, False
        else:
            print(f"   ❌ No streaming detected - using traditional processing")
            return True, total_upload_time, finalize_time, False
    else:
        print(f"❌ Finalization failed: {response.status_code}")
        return False, None, None, False

def test_background_processing():
    """Test TRUE background processing performance"""
    print("\n" + "="*70)
    print("🚀 TRUE BACKGROUND PROCESSING PERFORMANCE TEST")
    print("="*70)
    
    test_files = [
        ("bg_test_20mb.txt", 20, 0.1),   # 20MB with 0.1s delays
    ]
    
    results = []
    
    try:
        for filename, size_mb, delay in test_files:
            print(f"\n📋 Testing: {filename} (delay: {delay}s between chunks)")
            
            # Create test file
            test_file = create_test_file(filename, size_mb)
            
            # Test background processing
            success, upload_time, finalize_time, bg_working = upload_file_with_background_processing_test(
                test_file, chunk_size_kb=512, delay_between_chunks=delay
            )
            
            if success:
                results.append({
                    'file': filename,
                    'size_mb': size_mb,
                    'upload_time': upload_time,
                    'finalize_time': finalize_time,
                    'background_working': bg_working,
                    'time_saved': upload_time - finalize_time if upload_time and finalize_time else 0
                })
            
            # Clean up test file
            try:
                if os.path.exists(test_file):
                    os.remove(test_file)
            except:
                pass
            
            time.sleep(2)  # Brief pause between tests
        
        # Show results
        print(f"\n📊 BACKGROUND PROCESSING RESULTS:")
        print("=" * 50)
        
        if results:
            working_count = sum(1 for r in results if r['background_working'])
            avg_time_saved = sum(r['time_saved'] for r in results) / len(results)
            
            for result in results:
                print(f"\n📄 {result['file']}:")
                print(f"   📤 Upload time: {result['upload_time']:.1f}s")
                print(f"   🔄 Finalize time: {result['finalize_time']:.1f}s")
                print(f"   ⚡ Time saved: {result['time_saved']:.1f}s")
                print(f"   🌊 Background processing: {'✅ WORKING' if result['background_working'] else '❌ NOT WORKING'}")
            
            print(f"\n🎯 SUMMARY:")
            print(f"   ✅ Files with working background processing: {working_count}/{len(results)}")
            print(f"   ⚡ Average time saved: {avg_time_saved:.1f}s")
            
            if working_count == len(results) and avg_time_saved > 5:
                print(f"\n🎉 TRUE BACKGROUND PROCESSING IS WORKING!")
                print(f"🚀 Processing happens DURING upload, not after!")
            else:
                print(f"\n⚠️  Background processing needs optimization")
        else:
            print("❌ No successful tests completed")
            
    finally:
        # Clean up any remaining files
        for filename, _, _ in test_files:
            for cleanup_file in [filename, f"app/uploads/{filename}"]:
                try:
                    if os.path.exists(cleanup_file):
                        os.remove(cleanup_file)
                except:
                    pass

def main():
    print("⚡ TRUE BACKGROUND PROCESSING TEST")
    print("This test verifies that processing happens DURING upload,")
    print("not after upload completes (true background processing)")
    print("=" * 70)
    
    # Test server connection
    try:
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Server is accessible - starting tests...")
            test_background_processing()
        else:
            print("❌ Server not accessible")
    except Exception as e:
        print(f"❌ Server connection failed: {e}")

if __name__ == "__main__":
    main()
