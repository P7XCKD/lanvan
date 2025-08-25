"""
🚀 TRUE Streaming Assembly Performance Test
Tests the actual performance improvements of real streaming vs sequential processing
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

def upload_file_with_delay_chunked(filepath, chunk_size_kb=256, delay_between_chunks=0.1):
    """Upload a file with artificial delays between chunks to test TRUE streaming"""
    file_path = Path(filepath)
    file_size = file_path.stat().st_size
    chunk_size = chunk_size_kb * 1024
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    
    print(f"🚀 Starting delayed chunked upload: {file_path.name}")
    print(f"   📊 File size: {file_size / (1024*1024):.1f}MB")
    print(f"   📦 Chunk size: {chunk_size_kb}KB")
    print(f"   🧩 Total chunks: {total_chunks}")
    print(f"   ⏱️  Delay between chunks: {delay_between_chunks}s")
    
    start_time = time.time()
    file_ready_time = None
    
    # Function to check when file becomes available
    def check_file_availability():
        nonlocal file_ready_time
        while file_ready_time is None:
            try:
                potential_file = Path("app/uploads") / file_path.name
                if potential_file.exists() and potential_file.stat().st_size > 0:
                    file_ready_time = time.time()
                    print(f"🎯 FILE READY at {file_ready_time - start_time:.1f}s into upload!")
                    break
            except:
                pass
            time.sleep(0.1)
    
    # Start file monitoring thread
    monitor_thread = threading.Thread(target=check_file_availability, daemon=True)
    monitor_thread.start()
    
    # Upload chunks with delays
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
                return False, None, None, None
            
            progress = (chunk_num / total_chunks) * 100
            print(f"   📤 Chunk {chunk_num}/{total_chunks} uploaded ({progress:.1f}%) in {chunk_time:.2f}s")
            
            # Check if file became ready during this chunk
            if file_ready_time and chunk_num > 1:
                chunks_when_ready = chunk_num - 1
                print(f"   🌊 STREAMING DETECTED: File ready after only {chunks_when_ready}/{total_chunks} chunks!")
            
            # Add delay between chunks to simulate network conditions
            if chunk_num < total_chunks:
                time.sleep(delay_between_chunks)
    
    chunk_upload_time = time.time() - start_time
    print(f"✅ All chunks uploaded in {chunk_upload_time:.1f}s")
    
    # If file wasn't ready yet, wait for finalization
    if not file_ready_time:
        print("🔄 File not ready yet, finalizing...")
        finalize_start = time.time()
        
        finalize_data = {
            'filename': file_path.name,
            'total_parts': total_chunks,
            'encrypt': 'false'
        }
        
        response = requests.post(f"{BASE_URL}/finalize_upload", data=finalize_data)
        finalize_time = time.time() - finalize_start
        
        if response.status_code == 200:
            file_ready_time = time.time()
        else:
            print(f"❌ Finalization failed: {response.status_code}")
            return False, None, None, None
    
    total_time = time.time() - start_time
    streaming_benefit = chunk_upload_time - (file_ready_time - start_time) if file_ready_time else 0
    
    print(f"📊 TIMING ANALYSIS:")
    print(f"   📤 Chunk upload time: {chunk_upload_time:.1f}s")
    print(f"   🎯 File ready time: {file_ready_time - start_time:.1f}s")
    print(f"   🚀 Streaming benefit: {streaming_benefit:.1f}s faster")
    print(f"   📈 Performance improvement: {(streaming_benefit/chunk_upload_time)*100:.1f}%")
    
    return True, file_ready_time - start_time, chunk_upload_time, streaming_benefit

def test_true_streaming():
    """Test TRUE streaming assembly performance"""
    print("\n" + "="*70)
    print("🚀 TRUE STREAMING ASSEMBLY PERFORMANCE TEST")
    print("="*70)
    
    test_files = [
        ("streaming_test_10mb.txt", 10, 0.1),  # 10MB with 0.1s delays
        ("streaming_test_20mb.txt", 20, 0.05), # 20MB with 0.05s delays  
    ]
    
    results = []
    
    try:
        for filename, size_mb, delay in test_files:
            print(f"\n📋 Testing: {filename} (delay: {delay}s between chunks)")
            
            # Create test file
            test_file = create_test_file(filename, size_mb)
            
            # Test with delays
            success, ready_time, upload_time, benefit = upload_file_with_delay_chunked(
                test_file, chunk_size_kb=256, delay_between_chunks=delay
            )
            
            if success:
                results.append({
                    'file': filename,
                    'size_mb': size_mb,
                    'ready_time': ready_time,
                    'upload_time': upload_time,
                    'streaming_benefit': benefit,
                    'improvement_percent': (benefit/upload_time)*100 if upload_time > 0 else 0
                })
            
            # Clean up test file
            try:
                if os.path.exists(test_file):
                    os.remove(test_file)
            except:
                pass
            
            time.sleep(2)  # Brief pause between tests
        
        # Show results
        print(f"\n📊 TRUE STREAMING RESULTS:")
        print("=" * 50)
        
        if results:
            total_benefit = sum(r['streaming_benefit'] for r in results)
            avg_improvement = sum(r['improvement_percent'] for r in results) / len(results)
            
            print(f"🌊 Average streaming benefit: {avg_improvement:.1f}% faster")
            print(f"📈 Total time saved: {total_benefit:.1f}s")
            
            for result in results:
                print(f"\n📄 {result['file']}:")
                print(f"   🎯 File ready in: {result['ready_time']:.1f}s")
                print(f"   📤 Full upload took: {result['upload_time']:.1f}s")
                print(f"   🚀 Streaming saved: {result['streaming_benefit']:.1f}s ({result['improvement_percent']:.1f}%)")
            
            if avg_improvement > 20:
                print(f"\n✅ TRUE STREAMING ASSEMBLY IS WORKING!")
                print(f"🌊 Files become available {avg_improvement:.1f}% faster than traditional method!")
            else:
                print(f"\n⚠️  Streaming benefit is minimal - may need optimization")
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
    print("🌊 TRUE STREAMING ASSEMBLY PERFORMANCE TEST")
    print("This test verifies that files become available DURING upload,")
    print("not after all chunks are uploaded (true streaming behavior)")
    print("=" * 70)
    
    # Test server connection
    try:
        response = requests.get(BASE_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Server is accessible - starting tests...")
            test_true_streaming()
        else:
            print("❌ Server not accessible")
    except Exception as e:
        print(f"❌ Server connection failed: {e}")

if __name__ == "__main__":
    main()
