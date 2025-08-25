"""
🧪 Unified Responsiveness System Test
Test the consolidated responsiveness management system
"""

import sys
import time
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.unified_responsiveness import (
    responsiveness_manager, 
    ResponsivenessMode,
    ResponsivenessConfig,
    create_responsive_operation,
    should_yield_now,
    yield_if_needed,
    get_optimal_chunk_size,
    start_responsiveness_monitoring,
    stop_responsiveness_monitoring
)

def test_environment_detection():
    """Test automatic environment detection"""
    print("🧪 Testing environment detection...")
    
    detected_mode = responsiveness_manager.detect_environment()
    print(f"Detected environment: {detected_mode.value}")
    
    # Should detect one of the valid modes
    valid_modes = [mode.value for mode in ResponsivenessMode]
    success = detected_mode.value in valid_modes
    
    print(f"Environment detection: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

def test_config_optimization():
    """Test configuration optimization for different modes"""
    print("🧪 Testing configuration optimization...")
    
    # Test all modes
    modes_tested = []
    for mode in ResponsivenessMode:
        config = ResponsivenessConfig.for_mode(mode)
        
        # Verify config is properly set
        if config.mode == mode:
            modes_tested.append(mode.value)
            print(f"  ✅ {mode.value}: chunk_size={config.streaming_yield_size}, interval={config.monitoring_interval}")
        else:
            print(f"  ❌ {mode.value}: configuration mismatch")
    
    success = len(modes_tested) == len(ResponsivenessMode)
    print(f"Configuration optimization: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

def test_operation_management():
    """Test operation registration and management"""
    print("🧪 Testing operation management...")
    
    # Register operations
    op1 = create_responsive_operation("test_op1", "file_streaming", 1000)
    op2 = create_responsive_operation("test_op2", "encryption", 500)
    
    # Check if operations are registered
    metrics = responsiveness_manager.get_performance_metrics()
    active_ops = metrics['active_operations']
    
    if active_ops >= 2:
        print(f"  ✅ Operations registered: {active_ops} active")
        
        # Test yielding
        should_yield1 = should_yield_now(op1, 100)
        should_yield2 = should_yield_now(op2, 50)
        
        print(f"  ℹ️  Yield check: op1={should_yield1}, op2={should_yield2}")
        
        # Test yield control
        start_time = time.time()
        yield_if_needed(op1)
        yield_time = time.time() - start_time
        
        print(f"  ✅ Yield control: {yield_time*1000:.1f}ms delay")
        
        # Cleanup
        responsiveness_manager.unregister_operation(op1)
        responsiveness_manager.unregister_operation(op2)
        
        success = True
    else:
        print(f"  ❌ Failed to register operations: {active_ops} active")
        success = False
    
    print(f"Operation management: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

def test_chunk_size_optimization():
    """Test optimal chunk size calculation"""
    print("🧪 Testing chunk size optimization...")
    
    operation_types = ['file_streaming', 'encryption', 'upload', 'download', 'compression']
    chunk_sizes = {}
    
    for op_type in operation_types:
        chunk_size = get_optimal_chunk_size(op_type)
        chunk_sizes[op_type] = chunk_size
        print(f"  📏 {op_type}: {chunk_size:,} bytes")
    
    # Verify different operations get different optimizations
    unique_sizes = len(set(chunk_sizes.values()))
    
    # Should have at least some variation
    success = unique_sizes > 1 and all(size > 0 for size in chunk_sizes.values())
    
    print(f"Chunk size optimization: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

async def test_async_responsiveness():
    """Test async responsiveness features"""
    print("🧪 Testing async responsiveness...")
    
    operation_id = create_responsive_operation("async_test", "file_streaming", 100)
    
    try:
        # Test async yield
        start_time = time.time()
        await responsiveness_manager.ayield_control(operation_id)
        async_yield_time = time.time() - start_time
        
        print(f"  ✅ Async yield: {async_yield_time*1000:.1f}ms delay")
        
        # Cleanup
        responsiveness_manager.unregister_operation(operation_id)
        
        success = async_yield_time < 1.0  # Should be very quick
    except Exception as e:
        print(f"  ❌ Async yield failed: {e}")
        success = False
    
    print(f"Async responsiveness: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

def test_monitoring_system():
    """Test background monitoring"""
    print("🧪 Testing monitoring system...")
    
    try:
        # Start monitoring
        start_responsiveness_monitoring()
        
        # Let it run briefly
        time.sleep(0.5)
        
        # Check if monitoring is active
        metrics = responsiveness_manager.get_performance_metrics()
        config_mode = metrics.get('config_mode')
        
        if config_mode:
            print(f"  ✅ Monitoring active: {config_mode} mode")
            
            # Stop monitoring
            stop_responsiveness_monitoring()
            
            print(f"  ✅ Monitoring stopped successfully")
            success = True
        else:
            print(f"  ❌ Monitoring not active")
            success = False
            
    except Exception as e:
        print(f"  ❌ Monitoring system error: {e}")
        success = False
    
    print(f"Monitoring system: {'✅ PASSED' if success else '❌ FAILED'}")
    return success

async def run_responsiveness_tests():
    """Run comprehensive responsiveness tests"""
    print("🎯 LANVAN UNIFIED RESPONSIVENESS SYSTEM TESTS")
    print("=" * 55)
    
    tests = [
        ("Environment Detection", test_environment_detection),
        ("Configuration Optimization", test_config_optimization),
        ("Operation Management", test_operation_management),
        ("Chunk Size Optimization", test_chunk_size_optimization),
        ("Async Responsiveness", test_async_responsiveness),
        ("Monitoring System", test_monitoring_system)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            results[test_name] = False
            print(f"   ❌ FAILED with error: {e}")
        
        # Small delay between tests
        await asyncio.sleep(0.1)
    
    print("\n" + "=" * 55)
    print("📊 TEST RESULTS:")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 OVERALL: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All responsiveness tests PASSED!")
        print("🔧 Unified responsiveness system is working correctly")
        print("📈 Multiple overlapping systems successfully consolidated")
    else:
        print("⚠️  Some tests failed - responsiveness system needs attention")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(run_responsiveness_tests())
