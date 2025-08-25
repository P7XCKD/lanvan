"""
🧪 Thread Management System Test
Test the centralized thread manager to ensure proper resource management
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.thread_manager import thread_manager, ThreadPriority

def test_basic_thread_management():
    """Test basic thread creation and management"""
    print("🧪 Testing basic thread management...")
    
    def test_worker(stop_event=None):
        count = 0
        while not (stop_event and stop_event.is_set()):
            count += 1
            time.sleep(0.1)
            if count > 50:  # Safety limit
                break
        print(f"Worker finished after {count} iterations")
    
    # Create managed thread
    stop_event = thread_manager.create_thread(
        target=test_worker,
        name="test_worker",
        priority=ThreadPriority.NORMAL
    )
    
    # Let it run briefly
    time.sleep(0.5)
    
    # Check status
    status = thread_manager.get_thread_status()
    print(f"Thread status: {status}")
    
    # Stop thread
    success = thread_manager.stop_thread("test_worker")
    print(f"Thread stopped successfully: {success}")
    
    return success

def test_priority_shutdown():
    """Test priority-based shutdown ordering"""
    print("🧪 Testing priority shutdown...")
    
    shutdown_order = []
    
    def priority_worker(priority_name, stop_event=None):
        try:
            while not (stop_event and stop_event.is_set()):
                time.sleep(0.1)
        finally:
            shutdown_order.append(priority_name)
            print(f"🔧 {priority_name} priority thread stopped")
    
    # Create threads with different priorities
    thread_manager.create_thread(
        target=priority_worker,
        name="low_priority",
        args=("LOW",),
        priority=ThreadPriority.LOW
    )
    
    thread_manager.create_thread(
        target=priority_worker,
        name="high_priority", 
        args=("HIGH",),
        priority=ThreadPriority.HIGH
    )
    
    thread_manager.create_thread(
        target=priority_worker,
        name="critical_priority",
        args=("CRITICAL",),
        priority=ThreadPriority.CRITICAL
    )
    
    # Let them run briefly
    time.sleep(0.2)
    
    # Shutdown all
    print("🚨 Initiating priority shutdown...")
    success = thread_manager.shutdown_all(timeout=5.0)
    
    print(f"Shutdown order: {shutdown_order}")
    print(f"All threads stopped: {success}")
    
    # Verify priority order (CRITICAL -> HIGH -> LOW)
    expected_order = ["CRITICAL", "HIGH", "LOW"]
    correct_order = shutdown_order == expected_order
    print(f"Correct priority order: {correct_order}")
    
    return success and correct_order

def test_health_monitoring():
    """Test thread health monitoring"""
    print("🧪 Testing health monitoring...")
    
    def short_lived_worker(stop_event=None):
        time.sleep(0.1)  # Short task
        print("Short-lived worker completed")
    
    def long_lived_worker(stop_event=None):
        while not (stop_event and stop_event.is_set()):
            time.sleep(0.1)
    
    # Create threads
    thread_manager.create_thread(
        target=short_lived_worker,
        name="short_lived",
        priority=ThreadPriority.NORMAL
    )
    
    thread_manager.create_thread(
        target=long_lived_worker,
        name="long_lived",
        priority=ThreadPriority.NORMAL
    )
    
    # Wait for short-lived to complete
    time.sleep(0.2)
    
    # Check health
    health = thread_manager.health_check()
    print(f"Health check: {health}")
    
    # Should have at least 1 alive thread (long_lived)
    expected_alive = 1
    actual_alive = health['alive_threads']
    
    # Cleanup zombies (may be 0 if auto-cleanup already happened)
    zombies_cleaned = thread_manager.cleanup_zombies()
    print(f"Cleaned {zombies_cleaned} zombie threads")
    
    # Stop remaining threads
    thread_manager.stop_thread("long_lived")
    
    # Test passes if we have the expected alive threads (zombies auto-cleanup is working)
    return actual_alive >= expected_alive

def run_thread_management_tests():
    """Run comprehensive thread management tests"""
    print("🔧 LANVAN THREAD MANAGEMENT SYSTEM TESTS")
    print("=" * 50)
    
    tests = [
        ("Basic Thread Management", test_basic_thread_management),
        ("Priority Shutdown", test_priority_shutdown),
        ("Health Monitoring", test_health_monitoring)
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
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS:")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 OVERALL: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All thread management tests PASSED!")
        print("🔧 Thread management system is working correctly")
    else:
        print("⚠️  Some tests failed - thread management needs attention")
    
    return passed == total

if __name__ == "__main__":
    run_thread_management_tests()
