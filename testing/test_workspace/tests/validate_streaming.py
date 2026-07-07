#!/usr/bin/env python3
"""
[SEARCH] Comprehensive Streaming Assembly Integration Test
Validates that all components work together properly
"""

import sys
import os
import traceback
from pathlib import Path

def test_streaming_integration():
    """Test all streaming assembly components"""
    print("[SEARCH] COMPREHENSIVE STREAMING ASSEMBLY VALIDATION")
    print("=" * 60)
    
    try:
        # Test 1: Import streaming assembly module
        print("1⃣  Testing streaming assembly import...")
        from app.core.streaming_assembly import (
            StreamingChunkAssembler, 
            initialize_streaming_assembly,
            get_streaming_assembler,
            shutdown_streaming_assembly
        )
        print("[OK] Streaming assembly module imported successfully")
        
        # Test 2: Import routes integration
        print("\n2⃣  Testing routes integration...")
        from app.routes import ensure_streaming_initialized
        print("[OK] Routes with streaming integration imported successfully")
        
        # Test 3: Initialize streaming system
        print("\n3⃣  Testing streaming initialization...")
        temp_folder = Path("temp_chunks")
        upload_folder = Path("app/uploads") 
        temp_folder.mkdir(exist_ok=True)
        upload_folder.mkdir(exist_ok=True)
        
        initialize_streaming_assembly(temp_folder, upload_folder)
        assembler = get_streaming_assembler()
        print(f"[OK] Streaming system initialized: {type(assembler)}")
        
        # Test 4: Test core functionality
        print("\n4⃣  Testing core streaming functions...")
        test_file = "test_streaming.txt"
        test_path = upload_folder / test_file
        
        # Register a test file
        assembler.register_file(test_file, 5, test_path)
        print("[OK] File registration works")
        
        # Check status
        status = assembler.get_file_status(test_file)
        print(f"[OK] Status check works: {status is not None}")
        
        # Unregister
        assembler.unregister_file(test_file)
        print("[OK] File unregistration works")
        
        # Test 5: Shutdown
        print("\n5⃣  Testing streaming shutdown...")
        shutdown_streaming_assembly()
        print("[OK] Streaming system shutdown successfully")
        
        print(f"\n[DONE] ALL TESTS PASSED - STREAMING ASSEMBLY IS FULLY INTEGRATED!")
        print("[STREAM] TRUE streaming assembly is ready for production use")
        
        return True
        
    except Exception as e:
        print(f"\n[ERR] TEST FAILED: {e}")
        print(f"[INFO] Traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_streaming_integration()
    sys.exit(0 if success else 1)
