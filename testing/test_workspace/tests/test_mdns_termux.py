#!/usr/bin/env python3
"""
Quick test script for mDNS Termux compatibility
Run this to verify the enhanced mDNS system works properly
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.simple_mdns import SimpleMDNSManager, check_mdns_dependencies, force_cleanup_mdns_resources
import time

def test_mdns_lifecycle():
    """Test complete mDNS lifecycle with Termux optimizations"""
    print("=" * 60)
    print("🧪 Testing Enhanced mDNS System (Termux-Optimized)")
    print("=" * 60)
    
    # 1. Check dependencies
    print("\n1️⃣ Checking mDNS Dependencies...")
    available, status = check_mdns_dependencies()
    print(f"   Available: {available}")
    print(f"   Status: {status}")
    
    if not available:
        print("❌ Cannot proceed - mDNS dependencies missing")
        return False
    
    # 2. Test cleanup function
    print("\n2️⃣ Testing Resource Cleanup...")
    cleanup_result = force_cleanup_mdns_resources()
    print(f"   Cleanup result: {cleanup_result}")
    
    # 3. Test network detection
    print("\n3️⃣ Testing Network Detection...")
    manager = SimpleMDNSManager(port=80, use_https=False)
    ip = manager.get_lan_ip()
    print(f"   Detected IP: {ip}")
    
    # 4. Test service lifecycle multiple times
    print("\n4️⃣ Testing Service Lifecycle (3 iterations)...")
    for i in range(3):
        print(f"\n   --- Iteration {i+1} ---")
        
        # Create fresh manager with different ports to avoid conflicts
        test_manager = SimpleMDNSManager(port=8000 + i, use_https=False)
        
        # Start service
        start_result = test_manager.start_service()
        print(f"   Start result: {start_result}")
        
        if start_result:
            # Brief run time
            time.sleep(2)
            
            # Check status
            info = test_manager.get_mdns_info()
            print(f"   Status: {info['status']}")
            print(f"   Domain: {info.get('domain', 'N/A')}")
            print(f"   URL: {info.get('url', 'N/A')}")
            
            # Stop service
            test_manager.stop_service()
            print("   ✅ Service stopped")
            
            # Verify cleanup
            info_after = test_manager.get_mdns_info()
            print(f"   Status after stop: {info_after['status']}")
        else:
            print("   ❌ Service failed to start")
        
        # Brief pause between iterations
        time.sleep(1)
    
    print("\n" + "=" * 60)
    print("🎉 mDNS Lifecycle Test Completed")
    print("=" * 60)
    
    # Environment info
    print("\n📋 Environment Information:")
    print(f"   Platform: {sys.platform}")
    print(f"   Python: {sys.version}")
    
    # Check for Android/Termux
    is_android = ("ANDROID_STORAGE" in os.environ or 
                 os.path.exists("/data/data/com.termux") or 
                 "TERMUX_VERSION" in os.environ)
    print(f"   Android/Termux: {is_android}")
    
    if is_android:
        print("   📱 Termux-specific optimizations active")
    
    return True

if __name__ == "__main__":
    try:
        test_mdns_lifecycle()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
