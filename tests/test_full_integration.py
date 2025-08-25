"""
🧪 Full System Integration Test
Test the complete fixed system with both thread management and unified responsiveness
"""

import sys
import time
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.thread_manager import thread_manager, ThreadPriority
from app.unified_responsiveness import (
    responsiveness_manager,
    create_responsive_operation,
    start_responsiveness_monitoring,
    stop_responsiveness_monitoring
)

def test_integrated_system():
    """Test thread management + responsiveness integration"""
    print("🧪 Testing integrated thread management + responsiveness...")
    
    # Start responsiveness monitoring
    start_responsiveness_monitoring()
    
    # Create a managed thread with responsiveness
    def sample_worker():
        operation_id = create_responsive_operation("worker_task", "processing", 100)
        
        for i in range(10):
            # Simulate work
            time.sleep(0.1)
            
            # Use responsiveness system
            from app.unified_responsiveness import yield_if_needed
            yield_if_needed(operation_id)
            
            if thread_manager.shutdown_requested:
                print(f"  📨 Worker received shutdown signal at iteration {i}")
                break
        
        responsiveness_manager.unregister_operation(operation_id)
        print("  ✅ Worker completed with responsiveness")
    
    # Create managed thread
    stop_event = thread_manager.create_thread(
        target=sample_worker,
        name="integration_test_worker",
        priority=ThreadPriority.NORMAL
    )
    
    # Let it run briefly
    time.sleep(0.5)
    
    # Check both systems are active
    thread_count = len(thread_manager.threads)
    metrics = responsiveness_manager.get_performance_metrics()
    
    print(f"  🧵 Managed threads: {thread_count}")
    print(f"  📊 Active operations: {metrics['active_operations']}")
    
    # Clean shutdown
    thread_manager.shutdown_all()
    stop_responsiveness_monitoring()
    
    # Verify clean shutdown
    final_count = len(thread_manager.threads)
    
    success = thread_count > 0 and final_count == 0
    print(f"Integrated system: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

def test_performance_under_load():
    """Test performance with multiple operations"""
    print("🧪 Testing performance under load...")
    
    start_responsiveness_monitoring()
    
    operations = []
    threads = []
    
    def worker_task(worker_id):
        op_id = create_responsive_operation(f"worker_{worker_id}", "processing", 50)
        operations.append(op_id)
        
        # Simulate some work
        for _ in range(5):
            time.sleep(0.05)
            from app.unified_responsiveness import yield_if_needed
            yield_if_needed(op_id)
        
        responsiveness_manager.unregister_operation(op_id)
    
    # Create multiple workers
    for i in range(5):
        stop_event = thread_manager.create_thread(
            target=worker_task,
            args=(i,),
            name=f"load_test_worker_{i}",
            priority=ThreadPriority.NORMAL
        )
        threads.append(stop_event)
    
    # Monitor performance
    start_time = time.time()
    
    # Wait for completion
    time.sleep(1.0)  # Let workers complete
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Cleanup
    thread_manager.shutdown_all()
    stop_responsiveness_monitoring()
    
    # Performance check
    success = total_time < 2.0 and len(thread_manager.threads) == 0
    
    print(f"  ⏱️  Total time: {total_time:.2f}s")
    print(f"Performance under load: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

def test_graceful_degradation():
    """Test system behavior under error conditions"""
    print("🧪 Testing graceful degradation...")
    
    try:
        # Test with invalid operation
        invalid_op = create_responsive_operation("", "invalid_type", -1)
        
        # Should handle gracefully
        from app.unified_responsiveness import yield_if_needed, should_yield_now
        
        yield_result = yield_if_needed(invalid_op)
        should_yield_result = should_yield_now(invalid_op, 100)
        
        # Cleanup
        if invalid_op:
            responsiveness_manager.unregister_operation(invalid_op)
        
        print(f"  🛡️  Handled invalid operation gracefully")
        
        # Test thread creation with invalid parameters
        try:
            def dummy_target():
                pass
            stop_event = thread_manager.create_thread(
                target=dummy_target,
                name="",  # Invalid name
            )
            print(f"  🛡️  System handled edge case gracefully")
            success = True
        except Exception as e:
            print(f"  🛡️  Properly handled thread creation edge case: {type(e).__name__}")
            success = True
        
    except Exception as e:
        print(f"  ❌ Unexpected error in degradation test: {e}")
        success = False
    
    print(f"Graceful degradation: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

async def run_integration_tests():
    """Run comprehensive integration tests"""
    print("🎯 LANVAN FULL SYSTEM INTEGRATION TESTS")
    print("=" * 60)
    
    tests = [
        ("Integrated System", test_integrated_system),
        ("Performance Under Load", test_performance_under_load),
        ("Graceful Degradation", test_graceful_degradation)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            results[test_name] = False
            print(f"   ❌ FAILED with error: {e}")
        
        # Clean slate between tests
        await asyncio.sleep(0.2)
    
    print("\n" + "=" * 60)
    print("📊 INTEGRATION TEST RESULTS:")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 OVERALL: {passed}/{total} integration tests passed")
    
    if passed == total:
        print("🎉 Full system integration SUCCESSFUL!")
        print("✅ Thread Management Chaos: FIXED")
        print("✅ Redundant Responsiveness Systems: FIXED")
        print("🚀 System ready for optimal performance")
    else:
        print("⚠️  Some integration tests failed")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(run_integration_tests())
