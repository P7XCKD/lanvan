#!/usr/bin/env python3
"""
Quick test to answer: Is processing happening during upload or after?
"""

import requests
import time

def quick_processing_test():
    print("🔍 QUICK BACKGROUND PROCESSING TEST")
    print("=" * 50)
    
    # Create a small test file
    test_content = "A" * (1024 * 1024 * 5)  # 5MB file
    with open("quick_test.txt", "w") as f:
        f.write(test_content)
    
    # Upload in chunks with delays
    chunk_size = 256 * 1024  # 256KB chunks
    total_chunks = len(test_content) // chunk_size + 1
    
    print(f"📤 Uploading 5MB file in {total_chunks} chunks with delays...")
    
    upload_start = time.time()
    
    # Upload chunks
    for i in range(total_chunks):
        start_pos = i * chunk_size
        chunk_data = test_content[start_pos:start_pos + chunk_size].encode()
        if not chunk_data:
            break
            
        files = {'chunk': (f'chunk_{i+1}', chunk_data)}
        data = {
            'filename': 'quick_test.txt',
            'part_number': i + 1,
            'total_parts': total_chunks
        }
        
        response = requests.post("http://127.0.0.1/upload_chunk", files=files, data=data)
        print(f"   Chunk {i+1}/{total_chunks} uploaded")
        time.sleep(0.2)  # Delay to simulate real upload
    
    upload_time = time.time() - upload_start
    print(f"✅ Upload completed in {upload_time:.1f}s")
    
    # Now finalize
    print("🔄 Finalizing...")
    finalize_start = time.time()
    
    finalize_data = {
        'filename': 'quick_test.txt',
        'total_parts': total_chunks,
        'encrypt': 'false'
    }
    
    response = requests.post("http://127.0.0.1/finalize_upload", data=finalize_data)
    finalize_time = time.time() - finalize_start
    
    print(f"📊 RESULTS:")
    print(f"   Upload time: {upload_time:.1f}s")
    print(f"   Finalize time: {finalize_time:.1f}s")
    
    if finalize_time < 1.0:
        print("   ⚡ GOOD: Finalize is fast - background processing likely working!")
    else:
        print("   🐌 SLOW: Finalize is slow - processing happening after upload")
    
    # Cleanup
    import os
    try:
        os.remove("quick_test.txt")
    except:
        pass

if __name__ == "__main__":
    quick_processing_test()
