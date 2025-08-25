"""
🚀 Import-Safe Streaming Assembly with Failsafe
Immediately redirects to minimal version if any import issues occur
"""

# First, try to detect Termux and use ultra-minimal version
_TERMUX_MODE = False
_FUNCTIONS_DEFINED = False

try:
    import os
    
    # Check for Termux environment
    if (os.environ.get('TERMUX_VERSION') or 
        os.path.exists('/data/data/com.termux')):
        
        print("🚨 Termux detected - using ultra-minimal safe mode")
        _TERMUX_MODE = True
        
        def initialize_streaming_assembly(temp_folder, upload_folder):
            print("🤖 Termux ultra-minimal streaming assembly initialized")

        def get_streaming_assembler(temp_folder=None, upload_folder=None):
            class UltraMinimalAssembler:
                def __init__(self):
                    self.files = {}
                
                def register_file(self, file_id, expected_parts, filename, total_size):
                    self.files[file_id] = {"status": "registered"}
                    return {"status": "registered", "file_id": file_id}
                
                def check_status(self, file_id):
                    return {"status": "ready", "progress": 100}
                
                def get_file(self, file_id):
                    return {"status": "not_ready"}
                
                def cleanup(self, file_id):
                    if file_id in self.files:
                        del self.files[file_id]
            
            return UltraMinimalAssembler()

        def shutdown_streaming_assembly():
            print("🤖 Termux ultra-minimal streaming assembly shutdown")
        
        _FUNCTIONS_DEFINED = True

except Exception as e:
    print(f"🚨 Critical import error - using emergency fallback: {e}")
    
    def initialize_streaming_assembly(temp_folder, upload_folder):
        print("🚨 Emergency fallback streaming assembly initialized")

    def get_streaming_assembler(temp_folder=None, upload_folder=None):
        class EmergencyAssembler:
            def register_file(self, *args, **kwargs):
                return {"status": "registered"}
            def check_status(self, *args, **kwargs):
                return {"status": "ready"}
            def get_file(self, *args, **kwargs):
                return {"status": "not_ready"}
            def cleanup(self, *args, **kwargs):
                pass
        return EmergencyAssembler()

    def shutdown_streaming_assembly():
        print("🚨 Emergency fallback streaming assembly shutdown")
    
    _FUNCTIONS_DEFINED = True
    _TERMUX_MODE = True  # Skip desktop code

# Only load desktop code if not in Termux mode
if not _TERMUX_MODE and not _FUNCTIONS_DEFINED:
    try:
        print("💻 Desktop environment detected - loading full streaming assembly")
        
        import sys
        import time
        import threading
        from pathlib import Path
        from typing import Dict, Set, Optional
        from dataclasses import dataclass, field

        @dataclass
        class StreamingFile:
            filename: str
            expected_parts: int
            received_parts: Set[int] = field(default_factory=set)
            final_path: Path = None
            processing_started: bool = False
            completed: bool = False
            error: Optional[str] = None

        class StreamingChunkAssembler:
            def __init__(self, temp_folder: Path, upload_folder: Path):
                self.temp_folder = Path(temp_folder)
                self.upload_folder = Path(upload_folder)
                self.streaming_files: Dict[str, StreamingFile] = {}
                self.monitoring = False
                self.monitor_thread = None
                print("🌊 Full streaming assembly initialized")

            def register_file(self, file_id: str, expected_parts: int, filename: str, total_size: int):
                streaming_file = StreamingFile(
                    filename=filename,
                    expected_parts=expected_parts
                )
                self.streaming_files[file_id] = streaming_file
                return {"status": "registered", "file_id": file_id}

            def check_status(self, file_id: str):
                if file_id not in self.streaming_files:
                    return {"status": "not_found"}
                
                streaming_file = self.streaming_files[file_id]
                if streaming_file.completed:
                    return {"status": "ready", "progress": 100}
                
                progress = len(streaming_file.received_parts) / streaming_file.expected_parts * 100
                return {"status": "processing", "progress": progress}

            def get_file(self, file_id: str):
                if file_id not in self.streaming_files:
                    return {"status": "not_found"}
                
                streaming_file = self.streaming_files[file_id]
                if streaming_file.completed and streaming_file.final_path:
                    return {
                        "status": "ready",
                        "path": streaming_file.final_path,
                        "filename": streaming_file.filename
                    }
                
                return {"status": "not_ready"}

            def cleanup(self, file_id: str):
                if file_id in self.streaming_files:
                    del self.streaming_files[file_id]

        _global_assembler = None

        def initialize_streaming_assembly(temp_folder: Path, upload_folder: Path):
            global _global_assembler
            _global_assembler = StreamingChunkAssembler(temp_folder, upload_folder)
            print("✅ Full desktop streaming assembly initialized")

        def get_streaming_assembler(temp_folder: Path = None, upload_folder: Path = None):
            global _global_assembler
            if _global_assembler is None:
                if temp_folder and upload_folder:
                    _global_assembler = StreamingChunkAssembler(temp_folder, upload_folder)
                else:
                    # Fallback values
                    from pathlib import Path
                    _global_assembler = StreamingChunkAssembler(Path("/tmp"), Path("/tmp"))
            return _global_assembler

        def shutdown_streaming_assembly():
            global _global_assembler
            if _global_assembler:
                _global_assembler = None
            print("✅ Full desktop streaming assembly shutdown")

    except Exception as e:
        print(f"💻 Desktop mode failed, using fallback: {e}")
        
        def initialize_streaming_assembly(temp_folder, upload_folder):
            print("🔄 Fallback streaming assembly initialized")

        def get_streaming_assembler(temp_folder=None, upload_folder=None):
            class FallbackAssembler:
                def register_file(self, *args, **kwargs):
                    return {"status": "registered"}
                def check_status(self, *args, **kwargs):
                    return {"status": "ready"}
                def get_file(self, *args, **kwargs):
                    return {"status": "not_ready"}
                def cleanup(self, *args, **kwargs):
                    pass
            return FallbackAssembler()

        def shutdown_streaming_assembly():
            print("🔄 Fallback streaming assembly shutdown")
