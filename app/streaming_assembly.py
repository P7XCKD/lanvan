"""
🤖 Auto-Detecting Streaming Assembly     print("🤖 Termux environment detected - using emergency mode")
    try:
        import sys
        from pathlib import Path
        
        # Add the app directory to the path to import the emergency module
        app_dir = Path(__file__).parent
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
            
        import streaming_assembly_termux_emergency
        from streaming_assembly_termux_emergency import (
            initialize_streaming_assembly,
            get_streaming_assembler,
            shutdown_streaming_assembly
        )
        print("✅ Emergency Termux streaming assembly loaded")
    except Exception as e:
        print(f"⚠️ Emergency mode failed: {e}")
        # Ultra-simple fallbacktomatically switches between full and emergency mode based on environment

This module detects if it's running on Termux and automatically uses
the appropriate implementation to avoid import errors.
"""

import os
import platform

def is_termux():
    """Detect if running in Termux environment"""
    try:
        # Check for Termux-specific environment variables
        if os.environ.get('TERMUX_VERSION'):
            return True
        
        # Check for Android in platform info
        try:
            import subprocess
            result = subprocess.run(['uname', '-o'], capture_output=True, text=True, timeout=2)
            if 'Android' in result.stdout:
                return True
        except:
            pass
            
        # Check for typical Termux paths
        if os.path.exists('/data/data/com.termux'):
            return True
            
        # Check Python executable path for Termux pattern
        import sys
        if 'com.termux' in sys.executable:
            return True
            
        return False
    except:
        return False

# Detect environment and import appropriate implementation
if is_termux():
    print("🤖 Termux environment detected - using emergency mode")
    try:
        from streaming_assembly_termux_emergency import (
            initialize_streaming_assembly,
            get_streaming_assembler,
            shutdown_streaming_assembly
        )
        print("✅ Emergency Termux streaming assembly loaded")
    except Exception as e:
        print(f"⚠️ Emergency mode failed: {e}")
        # Ultra-simple fallback
        def initialize_streaming_assembly(temp_folder, upload_folder):
            print("🔄 Using ultra-simple fallback initialization")
        
        def get_streaming_assembler():
            print("🔄 Using ultra-simple fallback assembler")
            class FallbackAssembler:
                def register_file(self, *args, **kwargs):
                    return {"status": "registered"}
                def check_status(self, *args, **kwargs):
                    return {"status": "pending"}
                def get_file(self, *args, **kwargs):
                    return {"status": "not_ready"}
                def cleanup(self, *args, **kwargs):
                    pass
            return FallbackAssembler()
        
        def shutdown_streaming_assembly():
            print("🔄 Using ultra-simple fallback shutdown")
else:
    print("💻 Desktop environment detected - using full mode")
    try:
        import sys
        from pathlib import Path
        
        # Add the app directory to the path to import the full module
        app_dir = Path(__file__).parent
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
            
        import streaming_assembly_full
        from streaming_assembly_full import (
            initialize_streaming_assembly,
            get_streaming_assembler,
            shutdown_streaming_assembly
        )
        print("✅ Full streaming assembly loaded")
    except Exception as e:
        print(f"⚠️ Full mode failed: {e}")
        # Ultra-simple fallback
        def initialize_streaming_assembly(temp_folder, upload_folder):
            print("🔄 Using ultra-simple fallback initialization")
        
        def get_streaming_assembler():
            print("🔄 Using ultra-simple fallback assembler")
            class FallbackAssembler:
                def register_file(self, *args, **kwargs):
                    return {"status": "registered"}
                def check_status(self, *args, **kwargs):
                    return {"status": "pending"}
                def get_file(self, *args, **kwargs):
                    return {"status": "not_ready"}
                def cleanup(self, *args, **kwargs):
                    pass
            return FallbackAssembler()
        
        def shutdown_streaming_assembly():
            print("🔄 Using ultra-simple fallback shutdown")
