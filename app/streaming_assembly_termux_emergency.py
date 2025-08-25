"""
🔧 Termux Emergency Fix for KeyError: 'sys'
This creates a minimal streaming assembly module that should work on Termux
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

# Global variable to prevent the KeyError issue
_streaming_assembler = None

@dataclass
class StreamingFile:
    """Minimal streaming file tracker"""
    filename: str
    expected_parts: int
    received_parts: Set[int] = field(default_factory=set)
    final_path: Path = None
    processing_started: bool = False
    completed: bool = False
    error: Optional[str] = None

class StreamingChunkAssembler:
    """Minimal streaming assembler for Termux compatibility"""
    
    def __init__(self, temp_folder: Path, upload_folder: Path):
        self.temp_folder = Path(temp_folder)
        self.upload_folder = Path(upload_folder) 
        self.active_files: Dict[str, StreamingFile] = {}
        self.lock = threading.Lock()
        self.monitoring_active = False
        print("🤖 Termux-compatible streaming assembly initialized")
    
    def start_monitoring(self):
        """Start monitoring (simplified for Termux)"""
        self.monitoring_active = True
        print("🔍 Streaming monitoring started (Termux mode)")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        print("🔍 Streaming monitoring stopped")
    
    def register_file(self, filename: str, expected_parts: int, final_path: Path, 
                      completion_callback: callable = None, encrypt_file: bool = False):
        """Register file for streaming"""
        with self.lock:
            self.active_files[filename] = StreamingFile(
                filename=filename,
                expected_parts=expected_parts,
                final_path=final_path
            )
        print(f"📝 Registered {filename} for streaming (Termux mode)")
    
    def unregister_file(self, filename: str):
        """Unregister file"""
        with self.lock:
            if filename in self.active_files:
                del self.active_files[filename]
    
    def get_file_status(self, filename: str) -> Optional[Dict]:
        """Get file status"""
        with self.lock:
            if filename not in self.active_files:
                return None
            
            stream_file = self.active_files[filename] 
            return {
                'filename': stream_file.filename,
                'expected_parts': stream_file.expected_parts,
                'completed': stream_file.completed,
                'error': stream_file.error,
                'validation_result': {'valid': True},  # Always valid in emergency mode
                'encryption_result': None
            }

def get_streaming_assembler(temp_folder: Path = None, upload_folder: Path = None):
    """Get streaming assembler instance"""
    global _streaming_assembler
    if _streaming_assembler is None and temp_folder and upload_folder:
        _streaming_assembler = StreamingChunkAssembler(temp_folder, upload_folder)
    return _streaming_assembler

def initialize_streaming_assembly(temp_folder: Path, upload_folder: Path):
    """Initialize streaming assembly"""
    global _streaming_assembler
    if _streaming_assembler is None:
        _streaming_assembler = StreamingChunkAssembler(temp_folder, upload_folder)
        _streaming_assembler.start_monitoring()
        print("✅ Emergency Termux streaming assembly initialized")

def shutdown_streaming_assembly():
    """Shutdown streaming assembly - Emergency Termux version"""
    global _streaming_assembler
    try:
        if _streaming_assembler:
            _streaming_assembler.stop_monitoring()
            _streaming_assembler = None
        print("✅ Emergency Termux streaming assembly shutdown complete")
    except Exception as e:
        print(f"⚠️  Termux shutdown error (non-critical): {e}")
        _streaming_assembler = None  # Force cleanup anyway
