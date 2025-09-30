"""
🚀 Consolidated Streaming Assembly with Failsafe
Clean implementation without duplicate functions
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Set, Optional, Union
from dataclasses import dataclass, field

# First, try to detect Termux and use ultra-minimal version
_TERMUX_MODE = False

try:
    # Check for Termux environment
    if (os.environ.get('TERMUX_VERSION') or 
        os.path.exists('/data/data/com.termux')):
        
        print("🚨 Termux detected - using ultra-minimal safe mode")
        _TERMUX_MODE = True

except Exception as e:
    print(f"🚨 Critical import error - using emergency fallback: {e}")
    _TERMUX_MODE = True

@dataclass
class StreamingFile:
    filename: str
    expected_parts: int
    received_parts: Set[int] = field(default_factory=set)
    final_path: Optional[Path] = None
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
        print(f"🌊 Streaming assembly initialized ({'Termux mode' if _TERMUX_MODE else 'Full mode'})")

    def register_file(self, file_id: str, expected_parts: int, filename: str, total_size: int):
        """Register a file for streaming assembly"""
        streaming_file = StreamingFile(
            filename=filename,
            expected_parts=expected_parts
        )
        self.streaming_files[file_id] = streaming_file
        return {"status": "registered", "file_id": file_id}

    def check_status(self, file_id: str):
        """Check the status of a streaming file"""
        if file_id not in self.streaming_files:
            return {"status": "not_found"}
        
        streaming_file = self.streaming_files[file_id]
        if streaming_file.completed:
            return {"status": "ready", "progress": 100}
        
        progress = len(streaming_file.received_parts) / streaming_file.expected_parts * 100
        return {"status": "processing", "progress": progress}

    def get_file(self, file_id: str):
        """Get file information if ready"""
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
        """Clean up a file's streaming data"""
        if file_id in self.streaming_files:
            del self.streaming_files[file_id]

# Global assembler instance
_global_assembler = None

def initialize_streaming_assembly(temp_folder: Union[Path, str], upload_folder: Union[Path, str]):
    """Initialize the global streaming assembler"""
    global _global_assembler
    _global_assembler = StreamingChunkAssembler(Path(temp_folder), Path(upload_folder))
    print("✅ Streaming assembly initialized")

def get_streaming_assembler(temp_folder: Optional[Union[Path, str]] = None, upload_folder: Optional[Union[Path, str]] = None):
    """Get the global streaming assembler instance"""
    global _global_assembler
    if _global_assembler is None:
        if temp_folder and upload_folder:
            _global_assembler = StreamingChunkAssembler(Path(temp_folder), Path(upload_folder))
        else:
            # Fallback values
            import tempfile
            temp_dir = Path(tempfile.gettempdir())
            _global_assembler = StreamingChunkAssembler(temp_dir, temp_dir)
    return _global_assembler

def shutdown_streaming_assembly():
    """Shutdown the streaming assembly"""
    global _global_assembler
    if _global_assembler:
        _global_assembler = None
    print("✅ Streaming assembly shutdown")
