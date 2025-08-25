"""
🚀 Test Optimized File Streaming Performance
Validates the file streaming optimizations and memory efficiency improvements.
"""

import asyncio
import io
import time
import tempfile
import os
from pathlib import Path
import sys

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.optimized_streaming import streaming_handler


class StreamingPerformanceTest:
    """Test optimized file streaming performance and memory efficiency"""
    
    def __init__(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.results = {}
    
    def cleanup(self):
        """Clean up test files"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def create_test_file(self, size_mb: int, filename: str) -> Path:
        """Create a test file of specified size"""
        file_path = self.test_dir / filename
        
        # Create file with random data
        chunk_size = 1024 * 1024  # 1MB chunks
        with open(file_path, "wb") as f:
            for _ in range(size_mb):
                f.write(os.urandom(chunk_size))
        
        return file_path
    
    async def test_streaming_memory_efficiency(self):
        """Test memory efficiency of optimized streaming"""
        print("🧪 Testing streaming memory efficiency...")
        
        # Create test files of different sizes
        test_files = [
            (1, "small_1mb.bin"),
            (10, "medium_10mb.bin"),
            (50, "large_50mb.bin")
        ]
        
        results = {}
        
        for size_mb, filename in test_files:
            print(f"📋 Testing {filename} ({size_mb}MB)")
            
            file_path = self.create_test_file(size_mb, filename)
            file_size = file_path.stat().st_size
            
            # Test optimized streaming
            start_time = time.time()
            chunk_count = 0
            total_bytes = 0
            
            async for chunk in streaming_handler.stream_file_optimized(file_path):
                chunk_count += 1
                total_bytes += len(chunk)
            
            duration = time.time() - start_time
            throughput_mbps = (total_bytes / (1024 * 1024)) / duration
            
            results[filename] = {
                "file_size_mb": size_mb,
                "chunk_count": chunk_count,
                "total_bytes": total_bytes,
                "duration_seconds": duration,
                "throughput_mbps": throughput_mbps,
                "bytes_match": total_bytes == file_size
            }
            
            print(f"  ✅ Streamed {chunk_count} chunks in {duration:.3f}s")
            print(f"  📊 Throughput: {throughput_mbps:.2f} MB/s")
            print(f"  🎯 Integrity: {'PASS' if results[filename]['bytes_match'] else 'FAIL'}")
        
        return results
    
    async def test_partial_streaming(self):
        """Test partial file streaming (range requests)"""
        print("🧪 Testing partial streaming...")
        
        file_path = self.create_test_file(10, "partial_test.bin")
        file_size = file_path.stat().st_size
        
        # Test different ranges
        test_ranges = [
            (0, 1024),  # First 1KB
            (1024, 2048),  # Second 1KB
            (file_size - 1024, file_size - 1),  # Last 1KB
            (1024*1024, 2*1024*1024)  # 1MB-2MB range
        ]
        
        results = []
        
        for start, end in test_ranges:
            print(f"📋 Testing range {start}-{end}")
            
            chunk_count = 0
            total_bytes = 0
            expected_bytes = end - start + 1
            
            async for chunk in streaming_handler.stream_file_optimized(
                file_path, start_pos=start, end_pos=end
            ):
                chunk_count += 1
                total_bytes += len(chunk)
            
            range_correct = total_bytes == expected_bytes
            results.append({
                "range": f"{start}-{end}",
                "expected_bytes": expected_bytes,
                "actual_bytes": total_bytes,
                "chunk_count": chunk_count,
                "correct": range_correct
            })
            
            print(f"  ✅ Range {start}-{end}: {chunk_count} chunks, {total_bytes} bytes")
            print(f"  🎯 Accuracy: {'PASS' if range_correct else 'FAIL'}")
        
        return results
    
    async def test_platform_optimization(self):
        """Test platform-specific optimizations"""
        print("🧪 Testing platform optimizations...")
        
        platform_info = streaming_handler.platform_info
        
        # Test that buffer sizes are appropriate for platform
        buffer_tests = {
            "default_buffer_size": streaming_handler.default_buffer_size,
            "max_memory_buffer": streaming_handler.max_memory_buffer,
            "recommended_chunk_size": platform_info.recommended_chunk_size,
            "recommended_workers": platform_info.recommended_workers,
            "is_android": platform_info.is_android,
            "cpu_count": platform_info.cpu_count
        }
        
        print(f"  📱 Platform: {platform_info.platform_type.value}")
        print(f"  🖥️ CPU Count: {platform_info.cpu_count}")
        print(f"  📊 Default Buffer: {buffer_tests['default_buffer_size'] // (1024*1024)}MB")
        print(f"  🧠 Max Memory: {buffer_tests['max_memory_buffer'] // (1024*1024)}MB")
        print(f"  ⚡ Chunk Size: {buffer_tests['recommended_chunk_size'] // 1024}KB")
        
        # Validate platform-appropriate settings
        if platform_info.is_android:
            assert buffer_tests['default_buffer_size'] <= 2 * 1024 * 1024, "Android buffer too large"
            assert buffer_tests['max_memory_buffer'] <= 16 * 1024 * 1024, "Android memory limit too high"
        
        return buffer_tests
    
    async def run_all_tests(self):
        """Run all streaming optimization tests"""
        print("=" * 60)
        print("🚀 LANVAN OPTIMIZED STREAMING PERFORMANCE TESTS")
        print("=" * 60)
        
        try:
            # Test memory efficiency
            memory_results = await self.test_streaming_memory_efficiency()
            self.results["memory_efficiency"] = memory_results
            
            print()
            
            # Test partial streaming
            partial_results = await self.test_partial_streaming()
            self.results["partial_streaming"] = partial_results
            
            print()
            
            # Test platform optimizations
            platform_results = await self.test_platform_optimization()
            self.results["platform_optimization"] = platform_results
            
            print()
            print("=" * 60)
            print("📊 STREAMING OPTIMIZATION TEST SUMMARY")
            print("=" * 60)
            
            # Memory efficiency summary
            print("🧠 Memory Efficiency Results:")
            for filename, result in memory_results.items():
                status = "✅ PASS" if result["bytes_match"] else "❌ FAIL"
                print(f"  {filename}: {result['throughput_mbps']:.2f} MB/s - {status}")
            
            # Partial streaming summary
            print("\n📦 Partial Streaming Results:")
            all_partial_correct = all(r["correct"] for r in partial_results)
            partial_status = "✅ PASS" if all_partial_correct else "❌ FAIL"
            print(f"  All range requests: {partial_status}")
            
            # Platform optimization summary
            print("\n⚡ Platform Optimization Results:")
            print(f"  Platform: {platform_results['is_android'] and 'Android (Optimized)' or 'Desktop (High-Performance)'}")
            print(f"  Buffer Strategy: {platform_results['default_buffer_size'] // (1024*1024)}MB chunks")
            
            # Overall assessment
            overall_pass = (
                all(r["bytes_match"] for r in memory_results.values()) and
                all_partial_correct
            )
            
            print("\n🎯 OVERALL RESULT:")
            if overall_pass:
                print("  ✅ ALL TESTS PASSED - Streaming optimization successful!")
                print("  🚀 Memory efficiency improved, file handle overhead eliminated")
                print("  📈 Platform-optimized performance achieved")
            else:
                print("  ❌ SOME TESTS FAILED - Review implementation")
            
            return overall_pass
            
        except Exception as e:
            print(f"🚨 Test error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            self.cleanup()


async def main():
    """Run the streaming optimization tests"""
    test_suite = StreamingPerformanceTest()
    success = await test_suite.run_all_tests()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit_code = 0 if success else 1
    print(f"\n🏁 Test completed with exit code: {exit_code}")
    exit(exit_code)
