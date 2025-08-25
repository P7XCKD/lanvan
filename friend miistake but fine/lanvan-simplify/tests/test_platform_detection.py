"""
🧪 Platform Detection Overhead Test
Test the cached platform detection system to verify performance improvements
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.platform_detector import platform_detector, is_termux_environment, get_platform_info
from app.termux_compat import should_use_lightweight_mode, get_termux_system_info

def test_platform_detection_caching():
    """Test that platform detection is cached and not repeated"""
    print("🧪 Testing platform detection caching...")
    
    # Clear any existing cache by creating a new detector
    from app.platform_detector import CachedPlatformDetector
    test_detector = CachedPlatformDetector()
    
    # Time the first detection (should do actual detection)
    start_time = time.time()
    info1 = test_detector.get_platform_info()
    first_detection_time = time.time() - start_time
    
    # Time subsequent detections (should use cache)
    times = []
    info2 = None
    for i in range(10):
        start_time = time.time()
        info2 = test_detector.get_platform_info()
        cached_time = time.time() - start_time
        times.append(cached_time)
    
    avg_cached_time = sum(times) / len(times)
    
    print(f"First detection time: {first_detection_time:.6f}s")
    print(f"Average cached time: {avg_cached_time:.6f}s")
    print(f"Speedup factor: {first_detection_time / avg_cached_time:.1f}x")
    
    # Verify cache consistency
    if info2 is not None:
        assert info1.platform_type == info2.platform_type
        assert info1.is_termux == info2.is_termux
        assert info1.cpu_count == info2.cpu_count
    
    # Should be much faster (at least 10x speedup)
    speedup = first_detection_time / avg_cached_time
    cache_working = speedup > 10
    
    print(f"Cache working correctly: {cache_working}")
    print(f"Platform: {info1.platform_type.value}")
    print(f"Termux: {info1.is_termux}")
    print(f"Mobile: {info1.is_mobile}")
    
    return cache_working

def test_convenience_functions():
    """Test that convenience functions use cached detection"""
    print("🧪 Testing convenience function performance...")
    
    # Test multiple calls to convenience functions
    start_time = time.time()
    for i in range(100):
        is_termux = is_termux_environment()
        info = get_platform_info()
        lightweight = should_use_lightweight_mode()
        system_info = get_termux_system_info()
    total_time = time.time() - start_time
    
    avg_time_per_call = total_time / 100
    print(f"100 convenience function calls took: {total_time:.6f}s")
    print(f"Average time per call: {avg_time_per_call:.6f}s")
    
    # Should be very fast (less than 0.001s per call on average)
    fast_enough = avg_time_per_call < 0.001
    print(f"Performance acceptable: {fast_enough}")
    
    return fast_enough

def test_no_repeated_detection():
    """Test that platform detection only happens once during startup"""
    print("🧪 Testing single detection during startup...")
    
    # Monitor detection calls by checking if _info is None
    detector = platform_detector
    
    # Force a fresh start by clearing the cache
    detector._info = None
    
    # First call should trigger detection
    info1 = detector.get_platform_info()
    detection_time1 = info1.detection_time
    
    # Subsequent calls should use the same cached result
    info2 = detector.get_platform_info()
    detection_time2 = info2.detection_time
    
    # Detection times should be identical (same object)
    same_detection = detection_time1 == detection_time2
    
    print(f"First detection time: {detection_time1:.6f}s")
    print(f"Second call detection time: {detection_time2:.6f}s")
    print(f"Using same cached result: {same_detection}")
    
    return same_detection

def test_performance_recommendations():
    """Test that performance recommendations are cached"""
    print("🧪 Testing performance recommendations...")
    
    info = platform_detector.get_platform_info()
    
    # Test performance values are reasonable
    chunk_size = info.recommended_chunk_size
    workers = info.recommended_workers
    
    print(f"Recommended chunk size: {chunk_size // 1024}KB")
    print(f"Recommended workers: {workers}")
    print(f"Memory conservative: {info.memory_conservative}")
    print(f"File I/O conservative: {info.file_io_conservative}")
    
    # Verify recommendations make sense
    reasonable_chunk = 128 * 1024 <= chunk_size <= 8 * 1024 * 1024  # 128KB to 8MB
    reasonable_workers = 1 <= workers <= 16
    
    print(f"Reasonable chunk size: {reasonable_chunk}")
    print(f"Reasonable worker count: {reasonable_workers}")
    
    return reasonable_chunk and reasonable_workers

def run_platform_detection_tests():
    """Run comprehensive platform detection performance tests"""
    print("🔍 LANVAN PLATFORM DETECTION OPTIMIZATION TESTS")
    print("=" * 55)
    
    tests = [
        ("Platform Detection Caching", test_platform_detection_caching),
        ("Convenience Functions Performance", test_convenience_functions),
        ("No Repeated Detection", test_no_repeated_detection),
        ("Performance Recommendations", test_performance_recommendations)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {status}")
        except Exception as e:
            results[test_name] = False
            print(f"   ❌ FAILED with error: {e}")
        
        # Small delay between tests
        time.sleep(0.1)
    
    print("\n" + "=" * 55)
    print("📊 TEST RESULTS:")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 OVERALL: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All platform detection tests PASSED!")
        print("🔍 Platform detection overhead eliminated!")
        print("📈 Cached platform detection working optimally")
    else:
        print("⚠️  Some tests failed - platform detection needs attention")
    
    return passed == total

if __name__ == "__main__":
    run_platform_detection_tests()
