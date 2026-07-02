#!/usr/bin/env python3
"""
 Background Task Manager Validation Test

Tests the new task manager for:
1. Performance impact (should be near-zero)
2. Memory leak prevention
3. Proper task cleanup
4. Graceful degradation under load
5. Resource limits enforcement
"""
import asyncio
import time
import sys
import os
from pathlib import Path
import psutil
import requests
import json

# Add app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

async def test_task_manager_direct():
    """Test task manager functionality directly"""
    print(" Testing TaskManager directly...")
    
    from app.task_manager import LightweightTaskManager
    
    # Create test task manager
    tm = LightweightTaskManager(max_concurrent_tasks=5, cleanup_interval=10)
    
    async def dummy_task(duration=0.1):
        """Simple test task"""
        await asyncio.sleep(duration)
        return "completed"
    
    # Test 1: Normal task submission
    print("   Testing normal task submission...")
    task1 = tm.submit_task(dummy_task(0.1), "test_task_1")
    assert task1 is not None, "Task submission should succeed"
    
    # Test 2: Task limit enforcement
    print("   Testing task limit enforcement...")
    tasks = []
    for i in range(10):  # Submit more than limit (5)
        task = tm.submit_task(dummy_task(1.0), f"limit_test_{i}")
        if task:
            tasks.append(task)
    
    assert len(tasks) <= 5, f"Should not exceed task limit, got {len(tasks)} tasks"
    
    # Test 3: Task completion and cleanup
    print("   Testing task completion...")
    await asyncio.sleep(0.2)  # Let first task complete
    stats = tm.get_stats()
    assert stats['total_submitted'] >= 1, "Should track submitted tasks"
    assert stats['total_completed'] >= 1, "Should track completed tasks"
    
    # Test 4: Performance - should be very fast
    print("   Testing performance impact...")
    start_time = time.time()
    for i in range(100):
        tm.submit_task(dummy_task(0.001), f"perf_test_{i}")
    submit_time = time.time() - start_time
    
    assert submit_time < 0.1, f"Task submission too slow: {submit_time:.3f}s"
    print(f"   [OK] 100 task submissions in {submit_time:.3f}s")
    
    # Cleanup
    await tm.shutdown()
    print("   [OK] Direct task manager tests passed")

async def test_file_scanning_integration():
    """Test integration with file scanning functionality"""
    print(" Testing file scanning integration...")
    
    try:
        from app.routes import scan_file
        from app.task_manager import get_task_stats
        
        # Create test file
        test_file = Path("temp_chunks/test_scan.txt")
        test_file.parent.mkdir(exist_ok=True)
        test_file.write_text("Test file for background scanning")
        
        # Get initial stats
        initial_stats = get_task_stats()
        initial_submitted = initial_stats['total_submitted']
        
        # Trigger file scan
        scan_file(test_file)
        
        # Wait a bit for task to be submitted
        await asyncio.sleep(0.1)
        
        # Check stats updated
        new_stats = get_task_stats()
        if new_stats['total_submitted'] > initial_submitted:
            print("   [OK] File scanning creates background tasks correctly")
        else:
            print("   [WARN] File scanning may not be using task manager (or limit reached)")
        
        # Cleanup
        test_file.unlink(missing_ok=True)
        
    except ImportError as e:
        print(f"   [WARN] Could not test file scanning integration: {e}")
    except Exception as e:
        print(f"   [ERR] File scanning integration test failed: {e}")

def test_api_endpoint():
    """Test the task stats API endpoint"""
    print(" Testing task stats API endpoint...")
    
    try:
        # Try to connect to running server
        response = requests.get("http://localhost:8000/api/task-stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            assert 'task_stats' in data, "API should return task_stats"
            stats = data['task_stats']
            
            required_fields = [
                'active_tasks', 'total_submitted', 'total_completed',
                'peak_concurrent', 'max_concurrent', 'success_rate'
            ]
            
            for field in required_fields:
                assert field in stats, f"Missing required field: {field}"
            
            print(f"   [OK] API endpoint working - {stats['active_tasks']} active tasks")
            print(f"   [STATS] Stats: {stats['total_submitted']} submitted, {stats['total_completed']} completed")
            
        else:
            print(f"   [WARN] API endpoint returned status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("   [WARN] Server not running - skipping API test")
    except Exception as e:
        print(f"   [ERR] API endpoint test failed: {e}")

async def test_memory_usage():
    """Test memory usage and leak prevention"""
    print(" Testing memory usage...")
    
    process = psutil.Process()
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    async def memory_test():
        from app.task_manager import LightweightTaskManager
        
        # Create many tasks to check memory usage
        tm = LightweightTaskManager(max_concurrent_tasks=20)
        
        async def mini_task():
            await asyncio.sleep(0.01)
            return "done"
        
        # Submit many tasks
        for i in range(200):
            tm.submit_task(mini_task(), f"memory_test_{i}")
            if i % 50 == 0:
                await asyncio.sleep(0.1)  # Let some tasks complete
        
        # Wait for completion
        await asyncio.sleep(1)
        
        # Get final stats
        stats = tm.get_stats()
        await tm.shutdown()
        
        return stats
    
    # Run memory test in current event loop
    try:
        stats = await memory_test()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"   [STATS] Memory usage: {initial_memory:.1f}MB → {final_memory:.1f}MB (+{memory_increase:.1f}MB)")
        print(f"   [STATS] Task stats: {stats['total_submitted']} submitted, {stats['total_completed']} completed")
        
        # Memory increase should be minimal (< 5MB for this test)
        if memory_increase < 5:
            print("   [OK] Memory usage acceptable")
        else:
            print(f"   [WARN] Memory usage higher than expected: +{memory_increase:.1f}MB")
    except Exception as e:
        print(f"   [ERR] Memory test failed: {e}")

async def test_performance_comparison():
    """Compare performance with and without task manager"""
    print(" Testing performance comparison...")
    
    async def raw_asyncio_test():
        """Test raw asyncio.create_task performance"""
        start_time = time.time()
        tasks = []
        
        async def dummy_task():
            await asyncio.sleep(0.001)
        
        for i in range(100):
            task = asyncio.create_task(dummy_task())
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        return time.time() - start_time
    
    async def task_manager_test():
        """Test task manager performance"""
        from app.task_manager import LightweightTaskManager
        
        tm = LightweightTaskManager()
        start_time = time.time()
        
        async def dummy_task():
            await asyncio.sleep(0.001)
        
        tasks = []
        for i in range(100):
            task = tm.submit_task(dummy_task(), f"perf_test_{i}")
            if task:
                tasks.append(task)
        
        # Wait for completion
        await asyncio.sleep(0.5)
        await tm.shutdown()
        return time.time() - start_time
    
    # Run both tests
    raw_time = await raw_asyncio_test()
    managed_time = await task_manager_test()
    
    overhead = ((managed_time - raw_time) / raw_time) * 100 if raw_time > 0 else 0
    
    print(f"   [STATS] Raw asyncio: {raw_time:.3f}s")
    print(f"   [STATS] Task manager: {managed_time:.3f}s")
    print(f"   [STATS] Overhead: {overhead:.1f}%")
    
    # Overhead should be minimal (< 50%)
    if overhead < 50:
        print("   [OK] Performance overhead acceptable")
    else:
        print(f"   [WARN] Performance overhead high: {overhead:.1f}%")

async def main():
    """Run all tests"""
    print("[START] Background Task Manager Validation Tests")
    print("=" * 50)
    
    try:
        await test_task_manager_direct()
        print()
        
        await test_file_scanning_integration()
        print()
        
        test_api_endpoint()
        print()
        
        await test_memory_usage()
        print()
        
        await test_performance_comparison()
        print()
        
        print("[OK] All tests completed!")
        
    except Exception as e:
        print(f"[ERR] Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())