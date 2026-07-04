"""
[START] Consolidated Streaming Assembly with Failsafe
Clean implementation without duplicate functions
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Set, Optional, Union
from dataclasses import dataclass, field

from app.utils.termux_compat import is_android_environment

_TERMUX_MODE = False

try:
    # Check for Termux environment
    if is_android_environment():
        
        print("[!] Termux detected - using ultra-minimal safe mode")
        _TERMUX_MODE = True

except Exception as e:
    print(f"[!] Critical import error - using emergency fallback: {e}")
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
    total_size: int = 0
    assembled_size: int = 0
    chunk_data: Dict[int, bytes] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

class StreamingChunkAssembler:
    def __init__(self, temp_folder: Path, upload_folder: Path):
        self.temp_folder = Path(temp_folder)
        self.upload_folder = Path(upload_folder)
        self.streaming_files: Dict[str, StreamingFile] = {}
        self.monitoring = False
        self.monitor_thread = None
        print(f"[STREAM] Streaming assembly initialized ({'Termux mode' if _TERMUX_MODE else 'Full mode'})")

    def register_file(self, file_id: str, expected_parts: int, filename: str, total_size: int):
        """Register a file for streaming assembly"""
        streaming_file = StreamingFile(
            filename=filename,
            expected_parts=expected_parts,
            total_size=total_size
        )
        self.streaming_files[file_id] = streaming_file
        print(f"[STREAM] Registered file for streaming: {filename} ({expected_parts} parts, {total_size:,} bytes)")
        return {"status": "registered", "file_id": file_id}

    def add_chunk(self, file_id: str, chunk_number: int, chunk_data: bytes):
        """Add a chunk to the streaming file and attempt real-time assembly"""
        if file_id not in self.streaming_files:
            return {"status": "error", "msg": "File not registered"}
        
        streaming_file = self.streaming_files[file_id]
        
        # Store chunk data for assembly
        streaming_file.chunk_data[chunk_number] = chunk_data
        streaming_file.received_parts.add(chunk_number)
        streaming_file.assembled_size += len(chunk_data)
        
        print(f"[CFG] Added chunk {chunk_number}/{streaming_file.expected_parts} for {streaming_file.filename} ({len(chunk_data):,} bytes)")
        
        # Try real-time assembly if we have consecutive chunks
        self._try_real_time_assembly(file_id)
        
        # Check if file is complete
        if len(streaming_file.received_parts) == streaming_file.expected_parts:
            return self._finalize_assembly(file_id)
        
        progress = len(streaming_file.received_parts) / streaming_file.expected_parts * 100
        return {"status": "chunk_added", "progress": progress}

    def _try_real_time_assembly(self, file_id: str):
        """Attempt real-time assembly of consecutive chunks to save memory"""
        if _TERMUX_MODE:
            # In Termux mode, be more aggressive about assembly to save memory
            streaming_file = self.streaming_files[file_id]
            if len(streaming_file.chunk_data) >= 3:  # Start assembling after 3 chunks
                self._assemble_available_chunks(file_id)

    def _assemble_available_chunks(self, file_id: str):
        """Assemble consecutive chunks and write to disk to free memory"""
        streaming_file = self.streaming_files[file_id]
        
        if not streaming_file.final_path:
            streaming_file.final_path = self.upload_folder / streaming_file.filename
            # Ensure unique filename
            counter = 1
            original_path = streaming_file.final_path
            while streaming_file.final_path.exists():
                stem = original_path.stem
                suffix = original_path.suffix
                streaming_file.final_path = self.upload_folder / f"{stem}_{counter}{suffix}"
                counter += 1

        # Find consecutive chunks starting from 1
        consecutive_chunks = []
        for chunk_num in sorted(streaming_file.chunk_data.keys()):
            if chunk_num == len(consecutive_chunks) + 1:
                consecutive_chunks.append(chunk_num)
            else:
                break

        if consecutive_chunks:
            # Write consecutive chunks to file
            mode = 'ab' if streaming_file.final_path.exists() else 'wb'
            try:
                with open(streaming_file.final_path, mode) as f:
                    for chunk_num in consecutive_chunks:
                        chunk_data = streaming_file.chunk_data.pop(chunk_num)
                        f.write(chunk_data)
                
                print(f"[STREAM] Real-time assembled chunks {consecutive_chunks[0]}-{consecutive_chunks[-1]} for {streaming_file.filename}")
                
                # Mark as processing started
                streaming_file.processing_started = True
                
            except Exception as e:
                streaming_file.error = f"Assembly error: {str(e)}"
                print(f"[ERR] Real-time assembly failed for {streaming_file.filename}: {e}")

    def _finalize_assembly(self, file_id: str):
        """Finalize the assembly of a complete file"""
        streaming_file = self.streaming_files[file_id]
        
        try:
            if not streaming_file.final_path:
                streaming_file.final_path = self.upload_folder / streaming_file.filename
                # Ensure unique filename
                counter = 1
                original_path = streaming_file.final_path
                while streaming_file.final_path.exists():
                    stem = original_path.stem
                    suffix = original_path.suffix
                    streaming_file.final_path = self.upload_folder / f"{stem}_{counter}{suffix}"
                    counter += 1

            # Write any remaining chunks in order
            if streaming_file.chunk_data:
                mode = 'ab' if streaming_file.final_path.exists() else 'wb'
                with open(streaming_file.final_path, mode) as f:
                    for chunk_num in sorted(streaming_file.chunk_data.keys()):
                        chunk_data = streaming_file.chunk_data[chunk_num]
                        f.write(chunk_data)

            # Clear chunk data to free memory
            streaming_file.chunk_data.clear()
            streaming_file.completed = True
            
            # Verify file size
            actual_size = streaming_file.final_path.stat().st_size
            duration = time.time() - streaming_file.start_time
            
            print(f"[OK] Streaming assembly completed: {streaming_file.filename}")
            print(f"   [STATS] Size: {actual_size:,} bytes in {duration:.1f}s")
            
            return {
                "status": "completed", 
                "path": streaming_file.final_path,
                "filename": streaming_file.filename,
                "size": actual_size
            }
            
        except Exception as e:
            streaming_file.error = f"Finalization error: {str(e)}"
            streaming_file.completed = False
            print(f"[ERR] Assembly finalization failed for {streaming_file.filename}: {e}")
            return {"status": "error", "msg": str(e)}

    def assemble_file(self, file_id: str):
        """Force assembly of a file (for manual triggers)"""
        if file_id not in self.streaming_files:
            return {"status": "not_found"}
        
        streaming_file = self.streaming_files[file_id]
        
        if streaming_file.completed:
            return {
                "status": "already_completed",
                "path": streaming_file.final_path,
                "filename": streaming_file.filename
            }
        
        # Check if we have all parts
        if len(streaming_file.received_parts) == streaming_file.expected_parts:
            return self._finalize_assembly(file_id)
        else:
            missing_parts = set(range(1, streaming_file.expected_parts + 1)) - streaming_file.received_parts
            return {
                "status": "incomplete",
                "missing_parts": sorted(list(missing_parts)),
                "progress": len(streaming_file.received_parts) / streaming_file.expected_parts * 100
            }

    def cleanup_chunks(self, file_id: str):
        """Clean up chunk files for a specific file"""
        if file_id in self.streaming_files:
            streaming_file = self.streaming_files[file_id]
            
            # Clear in-memory chunk data
            streaming_file.chunk_data.clear()
            
            # Clean up temporary chunk files
            try:
                pattern = f"{streaming_file.filename}.part*"
                for chunk_file in self.temp_folder.glob(pattern):
                    chunk_file.unlink()
                    print(f"[CLEAN] Cleaned up chunk: {chunk_file.name}")
            except Exception as e:
                print(f"[WARN] Cleanup warning for {file_id}: {e}")

    def get_memory_usage(self):
        """Get current memory usage of streaming assembly"""
        total_chunks = 0
        total_memory = 0
        
        for streaming_file in self.streaming_files.values():
            chunks_in_memory = len(streaming_file.chunk_data)
            memory_usage = sum(len(data) for data in streaming_file.chunk_data.values())
            total_chunks += chunks_in_memory
            total_memory += memory_usage
        
        return {
            "total_chunks_in_memory": total_chunks,
            "total_memory_bytes": total_memory,
            "total_memory_mb": total_memory / (1024 * 1024),
            "active_files": len(self.streaming_files)
        }

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
            # Clean up chunks first
            self.cleanup_chunks(file_id)
            # Remove from tracking
            del self.streaming_files[file_id]
            print(f"[CLEAN] Cleaned up streaming file: {file_id}")

# Convenience functions for external use
def register_streaming_file(file_id: str, expected_parts: int, filename: str, total_size: int):
    """Register a file for streaming assembly"""
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.register_file(file_id, expected_parts, filename, total_size)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def add_streaming_chunk(file_id: str, chunk_number: int, chunk_data: bytes):
    """Add a chunk to streaming assembly"""
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.add_chunk(file_id, chunk_number, chunk_data)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def check_streaming_status(file_id: str):
    """Check streaming assembly status"""
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.check_status(file_id)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def get_assembled_file(file_id: str):
    """Get assembled file information"""
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.get_file(file_id)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def cleanup_streaming_file(file_id: str):
    """Clean up streaming file"""
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.cleanup(file_id)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

# Global assembler instance
_global_assembler = None

def initialize_streaming_assembly(temp_folder: Union[Path, str], upload_folder: Union[Path, str]):
    """Initialize the global streaming assembler"""
    global _global_assembler
    _global_assembler = StreamingChunkAssembler(Path(temp_folder), Path(upload_folder))
    print("[OK] Streaming assembly initialized")

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
        # Clean up all active streaming files
        for file_id in list(_global_assembler.streaming_files.keys()):
            _global_assembler.cleanup(file_id)
        _global_assembler = None
    print("[OK] Streaming assembly shutdown")
