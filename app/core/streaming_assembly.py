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

from app.core.logger import logger

_TERMUX_MODE = False

try:
    if is_android_environment():
        logger.info("ANDROID", "Termux environment detected, using safe mode")
        _TERMUX_MODE = True
except Exception as e:
    logger.warn("ANDROID", "Critical import fallback", details={"Reason": str(e)})
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
        logger.info("STORAGE", "Streaming assembly initialized", details={"Mode": "Termux" if _TERMUX_MODE else "Full"})

    def register_file(self, file_id: str, expected_parts: int, filename: str, total_size: int):
        """Register a file for streaming assembly"""
        streaming_file = StreamingFile(
            filename=filename,
            expected_parts=expected_parts,
            total_size=total_size
        )
        self.streaming_files[file_id] = streaming_file
        logger.info("UPLOAD", "File registered for streaming", details={"FileID": file_id, "Parts": expected_parts, "Size": total_size})
        return {"status": "registered", "file_id": file_id}

    def _cleanup_stale_sessions(self):
        now = time.time()
        stale_ids = []
        for file_id, sf in self.streaming_files.items():
            age = now - sf.start_time
            if age > self._max_session_age_seconds and not sf.completed:
                stale_ids.append(file_id)
        
        for file_id in stale_ids:
            self.cleanup(file_id)
        
        if stale_ids:
            logger.info("STORAGE", "Evicted stale streaming sessions", details={"EvictedCount": len(stale_ids)})

    def add_chunk(self, file_id: str, chunk_number: int, chunk_data: bytes):
        """Add a chunk to the streaming file and attempt real-time assembly"""
        if file_id not in self.streaming_files:
            return {"status": "error", "msg": "File not registered"}
        
        streaming_file = self.streaming_files[file_id]
        
        chunk_len = len(chunk_data)
        if getattr(streaming_file, 'disabled', False) or (self._current_chunks_memory + chunk_len > self._max_total_chunks_memory):
            logger.warn("STORAGE", "Memory cap exceeded, using disk chunk storage", details={"FileID": file_id})
            streaming_file.disabled = True
            freed_bytes = sum(len(d) for d in streaming_file.chunk_data.values())
            self._current_chunks_memory = max(0, self._current_chunks_memory - freed_bytes)
            streaming_file.chunk_data.clear()
            if streaming_file.temp_path and streaming_file.temp_path.exists():
                try:
                    streaming_file.temp_path.unlink()
                except Exception as e:
                    logger.warn("STORAGE", "Failed to remove partial streaming temp file", details={"Reason": str(e)})
            return {"status": "fallback_to_disk", "msg": "Server RAM limit reached — using disk chunk storage"}
        
        now = time.time()
        if now - self._last_cleanup_time > 60:
            self._cleanup_stale_sessions()
            self._last_cleanup_time = now
        
        streaming_file.chunk_data[chunk_number] = chunk_data
        streaming_file.received_parts.add(chunk_number)
        streaming_file.assembled_size += len(chunk_data)
        self._current_chunks_memory += len(chunk_data)
        
        expected = streaming_file.expected_parts
        if chunk_number == 1 or chunk_number == expected or (expected > 10 and chunk_number % max(1, expected // 10) == 0):
            logger.debug("UPLOAD", "Added chunk", details={"Chunk": chunk_number, "Total": expected, "Size": len(chunk_data)})
        
        self._try_real_time_assembly(file_id)
        
        if len(streaming_file.received_parts) == streaming_file.expected_parts:
            return self._finalize_assembly(file_id)
        
        progress = len(streaming_file.received_parts) / streaming_file.expected_parts * 100
        return {"status": "chunk_added", "progress": progress}

    def _try_real_time_assembly(self, file_id: str):
        streaming_file = self.streaming_files[file_id]
        if _TERMUX_MODE:
            self._assemble_available_chunks(file_id)
        elif len(streaming_file.chunk_data) >= 5:
            self._assemble_available_chunks(file_id)

    def _assemble_available_chunks(self, file_id: str):
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
            streaming_file.temp_path.parent.mkdir(parents=True, exist_ok=True)

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
                logger.debug("UPLOAD", "Real-time assembled chunks", details={"FileID": file_id, "Start": consecutive_chunks[0], "End": consecutive_chunks[-1]})
                streaming_file.last_assembled_chunk = consecutive_chunks[-1]
                streaming_file.processing_started = True
                
            except Exception as e:
                streaming_file.error = f"Assembly error: {str(e)}"
                logger.error("UPLOAD", "Real-time assembly failed", details={"FileID": file_id, "Reason": str(e)})

    def _finalize_assembly(self, file_id: str):
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
                streaming_file.temp_path.parent.mkdir(parents=True, exist_ok=True)

            if streaming_file.chunk_data:
                mode = 'ab' if streaming_file.temp_path.exists() else 'wb'
                with open(streaming_file.temp_path, mode) as f:
                    for chunk_num in sorted(streaming_file.chunk_data.keys()):
                        chunk_data = streaming_file.chunk_data[chunk_num]
                        f.write(chunk_data)

            freed_bytes = sum(len(d) for d in streaming_file.chunk_data.values())
            self._current_chunks_memory = max(0, self._current_chunks_memory - freed_bytes)
            streaming_file.chunk_data.clear()
            
            import shutil
            from pathlib import PurePosixPath
            from app.core.version_manager import VersionManager
            
            rel_p = PurePosixPath(streaming_file.filename)
            target_dir_str = str(rel_p.parent) if rel_p.parent != PurePosixPath(".") else ""
            bare_filename_str = rel_p.name

            success, lf = VersionManager.create_version_transaction(
                target_dir=target_dir_str,
                filename=bare_filename_str,
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
            
            logger.info("UPLOAD", "Streaming assembly completed", details={"FileID": file_id, "Size": actual_size, "DurationSec": round(duration, 2), "Status": "SUCCESS"})
            
            return {
                "status": "completed", 
                "path": streaming_file.final_path,
                "filename": streaming_file.filename,
                "size": actual_size
            }
            
        except Exception as e:
            streaming_file.error = f"Finalization error: {str(e)}"
            streaming_file.completed = False
            logger.error("UPLOAD", "Assembly finalization failed", details={"FileID": file_id, "Reason": str(e)})
            return {"status": "error", "msg": str(e)}

    def assemble_file(self, file_id: str):
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
        if file_id in self.streaming_files:
            streaming_file = self.streaming_files[file_id]
            
            freed_bytes = sum(len(d) for d in streaming_file.chunk_data.values())
            self._current_chunks_memory = max(0, self._current_chunks_memory - freed_bytes)
            streaming_file.chunk_data.clear()
            
            try:
                pattern = f"{streaming_file.filename.replace('/', '__')}.part*"
                for chunk_file in self.temp_folder.glob(pattern):
                    chunk_file.unlink()
                    logger.debug("STORAGE", "Cleaned up chunk file", details={"FileID": file_id})
            except Exception as e:
                logger.warn("STORAGE", "Cleanup warning for chunk file", details={"FileID": file_id, "Reason": str(e)})

    def get_memory_usage(self):
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
            streaming_file = self.streaming_files[file_id]
            self.cleanup_chunks(file_id)
            if streaming_file.temp_path and streaming_file.temp_path.exists():
                try:
                    streaming_file.temp_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.warn("STORAGE", "Failed to delete temp file in cleanup", details={"FileID": file_id, "Reason": str(e)})
            del self.streaming_files[file_id]
            logger.debug("STORAGE", "Cleaned up streaming session", details={"FileID": file_id})

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
    logger.info("STORAGE", "Streaming assembly system initialized")

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
    logger.info("STORAGE", "Streaming assembly system shutdown")
