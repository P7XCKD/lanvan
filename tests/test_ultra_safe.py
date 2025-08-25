#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    print("🔍 Testing ultra-safe streaming assembly...")
    from streaming_assembly import initialize_streaming_assembly, get_streaming_assembler, shutdown_streaming_assembly
    print("✅ Import successful!")
    
    # Test with temp paths
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_folder = Path(tmp_dir) / "chunks"
        upload_folder = Path(tmp_dir) / "uploads"
        temp_folder.mkdir()
        upload_folder.mkdir()
        
        initialize_streaming_assembly(temp_folder, upload_folder)
        assembler = get_streaming_assembler()
        print(f"✅ Assembler: {type(assembler)}")
        
        shutdown_streaming_assembly()
        print("✅ All tests passed!")
        
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
