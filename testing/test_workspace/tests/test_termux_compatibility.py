#!/usr/bin/env python3
"""
[BOT] Termux Compatibility Test for Streaming Assembly
Tests the key import that was failing on Android Termux
"""

import sys
import traceback

def test_termux_compatibility():
    print("[BOT] TERMUX COMPATIBILITY TEST")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    try:
        print("\n1⃣  Testing basic import...")
        import app.core.streaming_assembly
        print("[OK] Basic streaming assembly import successful")
        
        print("\n2⃣  Testing specific functions...")
        from app.core.streaming_assembly import (
            StreamingChunkAssembler,
            initialize_streaming_assembly, 
            get_streaming_assembler,
            shutdown_streaming_assembly
        )
        print("[OK] All streaming functions imported successfully")
        
        print("\n3⃣  Testing initialization...")
        from pathlib import Path
        temp_folder = Path("test_temp")
        upload_folder = Path("test_upload")
        
        initialize_streaming_assembly(temp_folder, upload_folder)
        print("[OK] Streaming assembly initialization successful")
        
        print("\n4⃣  Testing assembler retrieval...")
        assembler = get_streaming_assembler()
        print(f"[OK] Assembler retrieved: {type(assembler)}")
        
        print("\n5⃣  Testing shutdown...")
        shutdown_streaming_assembly()
        print("[OK] Streaming assembly shutdown successful")
        
        print("\n[DONE] ALL TESTS PASSED - TERMUX COMPATIBILITY CONFIRMED!")
        return True
        
    except Exception as e:
        print(f"\n[ERR] TEST FAILED: {e}")
        print("\n[INFO] Full traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_termux_compatibility()
    if success:
        print("\n[OK] This streaming assembly version should work on Termux!")
    else:
        print("\n[ERR] Further fixes needed for Termux compatibility")
    
    sys.exit(0 if success else 1)
