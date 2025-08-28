#!/usr/bin/env python3
"""
Test the auto-detecting streaming assembly with proper interface
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    print("🔍 Testing auto-detecting streaming assembly...")
    
    # Import the auto-detecting version
    from streaming_assembly import (
        initialize_streaming_assembly,
        get_streaming_assembler,
        shutdown_streaming_assembly
    )
    
    print("✅ Import successful!")
    
    # Test initialization
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_folder = Path(tmp_dir) / "test_chunks"
        upload_folder = Path(tmp_dir) / "test_uploads"
        
        temp_folder.mkdir(exist_ok=True)
        upload_folder.mkdir(exist_ok=True)
        
        initialize_streaming_assembly(temp_folder, upload_folder)
        print("✅ Initialization successful!")
        
        # Test assembler
        assembler = get_streaming_assembler()
        print(f"✅ Assembler created: {type(assembler)}")
        
        # Test shutdown
        shutdown_streaming_assembly()
        print("✅ Shutdown successful!")
    
    print("🎉 All tests passed!")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
