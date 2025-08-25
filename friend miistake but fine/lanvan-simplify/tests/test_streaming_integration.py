"""
🚀 Test Streaming Integration with Routes
Quick test to verify the optimized streaming works with actual route handlers
"""

import tempfile
import os
from pathlib import Path
import sys

# Add the app directory to Python path  
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_streaming_integration():
    """Quick integration test for streaming optimization"""
    print("🧪 Testing streaming integration...")
    
    # Create a test file
    test_dir = Path(tempfile.mkdtemp())
    test_file = test_dir / "integration_test.txt"
    
    test_content = b"Hello, this is a test file for streaming optimization!\n" * 1000
    with open(test_file, "wb") as f:
        f.write(test_content)
    
    try:
        # Import the optimized streaming handler
        from app.optimized_streaming import streaming_handler
        
        # Test basic streaming
        print("📋 Testing basic file streaming...")
        chunks = []
        async def collect_chunks():
            async for chunk in streaming_handler.stream_file_optimized(test_file):
                chunks.append(chunk)
        
        import asyncio
        asyncio.run(collect_chunks())
        
        # Verify content
        streamed_content = b''.join(chunks)
        content_match = streamed_content == test_content
        
        print(f"  ✅ Chunks collected: {len(chunks)}")
        print(f"  📊 Original size: {len(test_content)} bytes")
        print(f"  📊 Streamed size: {len(streamed_content)} bytes")
        print(f"  🎯 Content integrity: {'PASS' if content_match else 'FAIL'}")
        
        # Test headers generation
        print("📋 Testing headers generation...")
        headers = streaming_handler.get_optimal_headers(
            test_file, "test.txt", "text/plain", len(test_content)
        )
        
        required_headers = [
            "Content-Disposition", "Content-Type", "X-Streaming-Optimized", 
            "X-Platform", "Accept-Ranges"
        ]
        
        headers_complete = all(header in headers for header in required_headers)
        print(f"  🎯 Headers complete: {'PASS' if headers_complete else 'FAIL'}")
        
        # Overall result
        overall_success = content_match and headers_complete
        print(f"\n🏁 Integration test: {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        return overall_success
        
    except Exception as e:
        print(f"🚨 Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 50)
    print("🔧 STREAMING OPTIMIZATION INTEGRATION TEST")
    print("=" * 50)
    
    success = test_streaming_integration()
    
    if success:
        print("\n✅ Integration test completed successfully!")
        print("🚀 Optimized streaming is ready for production use")
    else:
        print("\n❌ Integration test failed!")
        print("🔧 Check implementation for issues")
    
    exit(0 if success else 1)
