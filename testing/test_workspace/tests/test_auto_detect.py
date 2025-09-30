#!/usr/bin/env python3
"""
Test the auto-detecting streaming assembly
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    print("🔍 Testing auto-detecting streaming assembly...")
    
    # Import the auto-detecting version
    from streaming_assembly import (
        register_streaming_file,
        check_streaming_status,
        get_assembled_file,
        cleanup_streaming_file,
        shutdown_streaming_assembly
    )
    
    print("✅ Import successful!")
    
    # Test basic functionality
    result = register_streaming_file("test123", 5, "test.txt", 1024)
    print(f"📝 Register result: {result}")
    
    status = check_streaming_status("test123")
    print(f"📊 Status result: {status}")
    
    print("✅ All tests passed!")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
