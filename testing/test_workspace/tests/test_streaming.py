"""
Test script to verify streaming chunk assembly functionality
"""
import os
import requests
import time
from pathlib import Path

def create_test_file(size_mb=2):
    """Create a test file of specified size"""
    test_file = Path(f"test_file_{size_mb}mb.txt")
    with open(test_file, "w") as f:
        # Create file with repeated content
        content = "This is test content for streaming assembly verification. " * 100
        chunk = content * (size_mb * 1024 // len(content))
        f.write(chunk)
    return test_file

def upload_file_chunked(file_path, chunk_size_kb=64):
    """Upload file in chunks to test streaming assembly"""
    base_url = "http://127.0.0.1"
    
    file_size = file_path.stat().st_size
    total_chunks = (file_size + chunk_size_kb * 1024 - 1) // (chunk_size_kb * 1024)
    
    print(f"📂 Uploading {file_path.name} ({file_size:,} bytes) in {total_chunks} chunks")
    
    start_time = time.time()
    
    # Upload chunks
    with open(file_path, "rb") as f:
        for chunk_num in range(1, total_chunks + 1):
            chunk_data = f.read(chunk_size_kb * 1024)
            if not chunk_data:
                break
            
            # Prepare chunk upload
            files = {'chunk': chunk_data}
            data = {
                'filename': file_path.name,
                'part_number': chunk_num,
                'total_parts': total_chunks
            }
            
            # Upload chunk
            response = requests.post(f"{base_url}/upload_chunk", files=files, data=data)
            
            if response.status_code == 200:
                print(f"✅ Chunk {chunk_num}/{total_chunks} uploaded")
            else:
                print(f"❌ Chunk {chunk_num} failed: {response.text}")
                return False
            
            # Small delay to test streaming assembly
            time.sleep(0.1)
    
    # Finalize upload
    print("🔄 Finalizing upload...")
    finalize_data = {
        'filename': file_path.name,
        'total_parts': total_chunks,
        'encrypt': 'false'
    }
    
    response = requests.post(f"{base_url}/finalize_upload", data=finalize_data)
    
    upload_time = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        streaming_used = result.get('streaming_assembly', False)
        assembly_method = result.get('assembly_method', 'unknown')
        
        print(f"✅ Upload completed in {upload_time:.1f}s")
        print(f"🌊 Streaming assembly: {'YES' if streaming_used else 'NO'}")
        print(f"⚙️ Assembly method: {assembly_method}")
        
        return True
    else:
        print(f"❌ Finalization failed: {response.text}")
        return False

def main():
    print("🧪 Testing Streaming Chunk Assembly")
    print("=" * 50)
    
    # Create test file
    test_file = create_test_file(2)  # 2MB test file
    
    try:
        # Test chunked upload
        success = upload_file_chunked(test_file, chunk_size_kb=64)
        
        if success:
            print("\n✅ Streaming assembly test completed successfully!")
        else:
            print("\n❌ Test failed")
    
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
            print(f"🧹 Cleaned up {test_file.name}")

if __name__ == "__main__":
    main()
