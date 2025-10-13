#!/usr/bin/env python3
"""
🤖 Termux Compatibility Test for Streaming Assembly
Tests the key import that was failing on Android Termux
"""

import sys
import traceback

def test_termux_compatibility():
    print("🤖 TERMUX COMPATIBILITY TEST")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    try:
        print("\n1️⃣  Testing basic import...")
        import app.streaming_assembly
        print("✅ Basic streaming assembly import successful")
        
        print("\n2️⃣  Testing specific functions...")
        from app.streaming_assembly import (
            StreamingChunkAssembler,
            initialize_streaming_assembly, 
            get_streaming_assembler,
            shutdown_streaming_assembly
        )
        print("✅ All streaming functions imported successfully")
        
        print("\n3️⃣  Testing initialization...")
        from pathlib import Path
        temp_folder = Path("test_temp")
        upload_folder = Path("test_upload")
        
        initialize_streaming_assembly(temp_folder, upload_folder)
        print("✅ Streaming assembly initialization successful")
        
        print("\n4️⃣  Testing assembler retrieval...")
        assembler = get_streaming_assembler()
        print(f"✅ Assembler retrieved: {type(assembler)}")
        
        print("\n5️⃣  Testing shutdown...")
        shutdown_streaming_assembly()
        print("✅ Streaming assembly shutdown successful")
        
        print("\n🎉 ALL TESTS PASSED - TERMUX COMPATIBILITY CONFIRMED!")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        print("\n📋 Full traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_termux_compatibility()
    if success:
        print("\n✅ This streaming assembly version should work on Termux!")
    else:
        print("\n❌ Further fixes needed for Termux compatibility")
    
    sys.exit(0 if success else 1)
