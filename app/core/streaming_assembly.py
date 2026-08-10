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
    temp_path: Optional[Path] = None
    processing_started: bool = False
    completed: bool = False
    error: Optional[str] = None
    total_size: int = 0
    assembled_size: int = 0
    chunk_data: Dict[int, bytes] = field(default_factory=dict)
    last_assembled_chunk: int = 0
    start_time: float = field(default_factory=time.time)

class StreamingChunkAssembler:
    def __init__(self, temp_folder: Path, upload_folder: Path):
        self.temp_folder = Path(temp_folder)
        self.upload_folder = Path(upload_folder)
        self.streaming_files: Dict[str, StreamingFile] = {}
        self.monitoring = False
        self.monitor_thread = None
        self._last_cleanup_time = time.time()
        self._max_session_age_seconds = 900  # 15 minutes TTL for abandoned sessions
        self._max_total_chunks_memory = 512 * 1024 * 1024  # 512MB global cap
        self._current_chunks_memory = 0
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

    def _cleanup_stale_sessions(self):
        """Evict streaming sessions that have received no chunks for >15 minutes.
        This prevents unbounded memory growth from abandoned/refreshed browser uploads."""
        now = time.time()
        stale_ids = []
        for file_id, sf in self.streaming_files.items():
            age = now - sf.start_time
            if age > self._max_session_age_seconds and not sf.completed:
                stale_ids.append(file_id)
        
        for file_id in stale_ids:
            self.cleanup(file_id)
        
        if stale_ids:
            print(f"[STREAM] Evicted {len(stale_ids)} stale streaming sessions (idle > {self._max_session_age_seconds}s)")

    def add_chunk(self, file_id: str, chunk_number: int, chunk_data: bytes):
        """Add a chunk to the streaming file and attempt real-time assembly"""
        if file_id not in self.streaming_files:
            return {"status": "error", "msg": "File not registered"}
        
        streaming_file = self.streaming_files[file_id]
        
        # Check global memory cap before accepting new chunk data
        chunk_len = len(chunk_data)
        if self._current_chunks_memory + chunk_len > self._max_total_chunks_memory:
            print(f"[STREAM] Memory cap ({self._max_total_chunks_memory // 1048576}MB) exceeded — rejecting chunk {chunk_number} for {file_id}")
            return {"status": "error", "msg": "Server memory limit reached. Please try again later."}
        
        # Periodic cleanup of stale sessions (check every 60 seconds, amortized)
        now = time.time()
        if now - self._last_cleanup_time > 60:
            self._cleanup_stale_sessions()
            self._last_cleanup_time = now
        
        # Store chunk data for assembly & update memory counter
        streaming_file.chunk_data[chunk_number] = chunk_data
        streaming_file.received_parts.add(chunk_number)
        streaming_file.assembled_size += len(chunk_data)
        self._current_chunks_memory += len(chunk_data)
        
        # Log progress at 10% increments to prevent log flooding
        expected = streaming_file.expected_parts
        if chunk_number == 1 or chunk_number == expected or (expected > 10 and chunk_number % max(1, expected // 10) == 0):
            print(f"[CFG] Added chunk {chunk_number}/{expected} for {streaming_file.filename} ({len(chunk_data):,} bytes)")
        
        # Try real-time assembly if we have consecutive chunks
        self._try_real_time_assembly(file_id)
        
        # Check if file is complete
        if len(streaming_file.received_parts) == streaming_file.expected_parts:
            return self._finalize_assembly(file_id)
        
        progress = len(streaming_file.received_parts) / streaming_file.expected_parts * 100
        return {"status": "chunk_added", "progress": progress}

    def _try_real_time_assembly(self, file_id: str):
        """Attempt real-time assembly of consecutive chunks to save memory"""
        streaming_file = self.streaming_files[file_id]
        if _TERMUX_MODE:
            self._assemble_available_chunks(file_id)
        elif len(streaming_file.chunk_data) >= 5:
            self._assemble_available_chunks(file_id)

    def _assemble_available_chunks(self, file_id: str):
        """Assemble consecutive chunks and write to disk to free memory"""
        streaming_file = self.streaming_files[file_id]
        
        if not streaming_file.final_path:
            final_path = self.upload_folder / streaming_file.filename
            counter = 1
            original_path = final_path
            while final_path.exists() or final_path.with_suffix(final_path.suffix + '.tmp').exists():
                stem = original_path.stem
                suffix = original_path.suffix
                final_path = self.upload_folder / f"{stem}_{counter}{suffix}"
                counter += 1
            streaming_file.final_path = final_path
            streaming_file.temp_path = final_path.with_suffix(final_path.suffix + '.tmp')

        # Find consecutive chunks starting from last_assembled_chunk + 1
        consecutive_chunks = []
        next_expected = streaming_file.last_assembled_chunk + 1
        for chunk_num in sorted(streaming_file.chunk_data.keys()):
            if chunk_num == next_expected:
                consecutive_chunks.append(chunk_num)
                next_expected += 1
            elif chunk_num > next_expected:
                break

        if consecutive_chunks:
            mode = 'ab' if streaming_file.temp_path.exists() else 'wb'
            try:
                freed_bytes = 0
                with open(streaming_file.temp_path, mode) as f:
                    for chunk_num in consecutive_chunks:
                        chunk_data = streaming_file.chunk_data.pop(chunk_num)
                        freed_bytes += len(chunk_data)
                        f.write(chunk_data)
                
                self._current_chunks_memory = max(0, self._current_chunks_memory - freed_bytes)
                print(f"[STREAM] Real-time assembled chunks {consecutive_chunks[0]}-{consecutive_chunks[-1]} for {streaming_file.filename}")
                streaming_file.last_assembled_chunk = consecutive_chunks[-1]
                streaming_file.processing_started = True
                
            except Exception as e:
                streaming_file.error = f"Assembly error: {str(e)}"
                print(f"[ERR] Real-time assembly failed for {streaming_file.filename}: {e}")

    def _finalize_assembly(self, file_id: str):
        """Finalize the assembly of a complete file"""
        streaming_file = self.streaming_files[file_id]
        try:
            if not streaming_file.final_path:
                final_path = self.upload_folder / streaming_file.filename
                counter = 1
                original_path = final_path
                while final_path.exists() or final_path.with_suffix(final_path.suffix + '.tmp').exists():
                    stem = original_path.stem
                    suffix = original_path.suffix
                    final_path = self.upload_folder / f"{stem}_{counter}{suffix}"
                    counter += 1
                streaming_file.final_path = final_path
                streaming_file.temp_path = final_path.with_suffix(final_path.suffix + '.tmp')

            # Write any remaining chunks in order to temp file
            if streaming_file.chunk_data:
                mode = 'ab' if streaming_file.temp_path.exists() else 'wb'
                with open(streaming_file.temp_path, mode) as f:
                    for chunk_num in sorted(streaming_file.chunk_data.keys()):
                        chunk_data = streaming_file.chunk_data[chunk_num]
                        f.write(chunk_data)

            # Clear chunk data to free memory
            freed_bytes = sum(len(d) for d in streaming_file.chunk_data.values())
            self._current_chunks_memory = max(0, self._current_chunks_memory - freed_bytes)
            streaming_file.chunk_data.clear()
            
            # Atomic commit via VersionManager
            import shutil
            from app.core.version_manager import VersionManager
            
            success, lf = VersionManager.create_version_transaction(
                target_dir="",
                filename=streaming_file.filename,
                incoming_file_path=streaming_file.temp_path,
                uploaded_by="streaming_assembly",
                change_type="uploaded"
            )
            
            if not success and streaming_file.temp_path.exists():
                is_windows = os.name == 'nt'
                max_retries = 3 if is_windows else 1
                retry_delay = 0.3 if is_windows else 0.1
                
                if is_windows:
                    time.sleep(0.1)
                    
                for attempt in range(max_retries):
                    try:
                        if is_windows:
                            shutil.move(str(streaming_file.temp_path), str(streaming_file.final_path))
                        else:
                            try:
                                streaming_file.temp_path.rename(streaming_file.final_path)
                            except OSError:
                                shutil.move(str(streaming_file.temp_path), str(streaming_file.final_path))
                        break
                    except Exception as rename_err:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 1.5
                        else:
                            raise rename_err

            streaming_file.completed = True
            
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
            
            # Clear in-memory chunk data & update memory counter
            freed_bytes = sum(len(d) for d in streaming_file.chunk_data.values())
            self._current_chunks_memory = max(0, self._current_chunks_memory - freed_bytes)
            streaming_file.chunk_data.clear()
            
            try:
                pattern = f"{streaming_file.filename.replace('/', '__')}.part*"
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
            streaming_file = self.streaming_files[file_id]
            self.cleanup_chunks(file_id)
            if streaming_file.temp_path and streaming_file.temp_path.exists():
                try:
                    streaming_file.temp_path.unlink(missing_ok=True)
                except Exception as e:
                    print(f"[WARN] Failed to delete temp file {streaming_file.temp_path.name} in cleanup: {e}")
            del self.streaming_files[file_id]
            print(f"[CLEAN] Cleaned up streaming file: {file_id}")

# Convenience functions for external use
def register_streaming_file(file_id: str, expected_parts: int, filename: str, total_size: int):
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.register_file(file_id, expected_parts, filename, total_size)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def add_streaming_chunk(file_id: str, chunk_number: int, chunk_data: bytes):
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.add_chunk(file_id, chunk_number, chunk_data)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def check_streaming_status(file_id: str):
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.check_status(file_id)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def get_assembled_file(file_id: str):
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.get_file(file_id)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

def cleanup_streaming_file(file_id: str):
    assembler = get_streaming_assembler()
    if assembler:
        return assembler.cleanup(file_id)
    return {"status": "error", "msg": "Streaming assembly not initialized"}

_global_assembler = None

def initialize_streaming_assembly(temp_folder: Union[Path, str], upload_folder: Union[Path, str]):
    global _global_assembler
    _global_assembler = StreamingChunkAssembler(Path(temp_folder), Path(upload_folder))
    print("[OK] Streaming assembly initialized")

def get_streaming_assembler(temp_folder: Optional[Union[Path, str]] = None, upload_folder: Optional[Union[Path, str]] = None):
    global _global_assembler
    if _global_assembler is None:
        if temp_folder and upload_folder:
            _global_assembler = StreamingChunkAssembler(Path(temp_folder), Path(upload_folder))
        else:
            import tempfile
            temp_dir = Path(tempfile.gettempdir())
            _global_assembler = StreamingChunkAssembler(temp_dir, temp_dir)
    return _global_assembler

def shutdown_streaming_assembly():
    global _global_assembler
    if _global_assembler:
        for file_id in list(_global_assembler.streaming_files.keys()):
            _global_assembler.cleanup(file_id)
        _global_assembler = None
    print("[OK] Streaming assembly shutdown")
