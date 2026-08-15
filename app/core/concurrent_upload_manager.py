"""
[START] Concurrent Upload Manager for Lanvan
Handles multiple file uploads simultaneously with adaptive optimization for ALL platforms.

Key Features:
- Async concurrent processing (no more blocking!)
- Universal adaptive chunk sizing for all files
- Platform-aware optimizations
- Real-time progress tracking
- Memory-efficient streaming for large files
- Advanced file locking to prevent race conditions
"""

import asyncio
import os
import json
import hashlib
import gc
import time
import io
import shutil
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import UploadFile
from concurrent.futures import ThreadPoolExecutor
import threading
from app.utils.termux_compat import is_android_environment
from app.core.logger import logger

# Import universal optimizer with fallback
try:
    from app.utils.universal_optimizer import universal_optimizer
except ImportError:
    try:
        from universal_optimizer import universal_optimizer
    except ImportError:
        # Fallback to a basic optimizer if not available
        class BasicOptimizer:
            platform_type = "unknown"
            def get_adaptive_chunk_size(self, file_size): return 64 * 1024
            def should_run_gc(self, bytes_written, chunk_size): return bytes_written % (50 * 1024 * 1024) == 0
            def memory_cleanup(self, force=False): pass
            def optimize_for_large_files(self, operation_type="upload"): return {"warnings": [], "recommendations": []}
        universal_optimizer = BasicOptimizer()

# Import responsiveness monitor with fallback
try:
    from app.utils.responsiveness_manager import responsiveness_monitor, ensure_responsiveness
except ImportError:
    try:
        from app.utils.responsiveness_manager import responsiveness_monitor, ensure_responsiveness  
    except ImportError:
        # Fallback responsiveness function
        async def ensure_responsiveness(): 
            await asyncio.sleep(0.001)

# Import file locking with fallback
try:
    from app.core.file_locking import get_file_lock_manager
except ImportError:
    try:
        from file_locking import get_file_lock_manager
    except ImportError:
        # Fallback file lock manager
        class BasicFileLockManager:
            def __init__(self, base_path): 
                self.base_path = base_path
            def upload_lock(self, filename, timeout=30.0):
                import contextlib
                class DummyLock:
                    async def __aenter__(self): return self
                    async def __aexit__(self, *args): pass
                return contextlib.asynccontextmanager(lambda: DummyLock())()
        def get_file_lock_manager(upload_folder): 
            return BasicFileLockManager(upload_folder)


class ConcurrentUploadManager:
    """
    [TARGET] Manages multiple file uploads concurrently with adaptive optimization
    """
    
    def __init__(self, max_concurrent_uploads: int = 3):
        self.max_concurrent_uploads = max_concurrent_uploads
        self.active_uploads: Dict[str, Dict[str, Any]] = {}
        self.upload_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_uploads)
        
    async def upload_files_concurrently(
        self, 
        files: List[UploadFile], 
        destinations: List[Path], 
        encrypt: bool = False
    ) -> List[Dict[str, Any]]:
        """
        [START] Upload multiple files concurrently with adaptive optimization
        """
        logger.info("UPLOAD", "Processing uploads", details={"Count": len(files)})
        
        semaphore = asyncio.Semaphore(max(1, self.max_concurrent_uploads))

        async def run_upload(file: UploadFile, destination: Path, upload_id: str):
            async with semaphore:
                return await self._upload_single_file_async(
                    file, destination, encrypt, upload_id=upload_id
                )

        # Create bounded upload tasks
        tasks = []
        for i, (file, destination) in enumerate(zip(files, destinations)):
            tasks.append(asyncio.create_task(run_upload(file, destination, f"upload_{i}")))
        
        # Execute uploads concurrently with progress tracking
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'filename': files[i].filename,
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        logger.info("UPLOAD", "Upload batch completed", details={"SuccessCount": len([r for r in processed_results if r.get('success')]), "FailedCount": len([r for r in processed_results if not r.get('success')])})
        return processed_results
    
    async def _upload_single_file_async(
        self, 
        upload_file: UploadFile, 
        destination: Path, 
        encrypt: bool = False,
        chunk_size: int = 512 * 1024,
        upload_id: str = "default"
    ) -> Dict[str, Any]:
        """
        [TARGET] Upload a single file asynchronously with adaptive optimization
        """
        start_time = time.time()
        
        # Register upload
        with self.upload_lock:
            self.active_uploads[upload_id] = {
                'status': 'starting',
                'progress': 0,
                'start_time': start_time,
                'filename': upload_file.filename
            }
        
        try:
            try:
                await asyncio.to_thread(upload_file.file.seek, 0, 2)
                file_size = await asyncio.to_thread(upload_file.file.tell)
                await asyncio.to_thread(upload_file.file.seek, 0)
            except Exception:
                file_size = getattr(upload_file, 'size', 0) or 0
            
            logger.info("UPLOAD", "Upload started", op_id=upload_id, details={"Type": upload_file.content_type or "unknown", "Size": file_size})
            
            # Update status
            with self.upload_lock:
                self.active_uploads[upload_id].update({
                    'status': 'uploading',
                    'total_size': file_size,
                    'chunk_size': chunk_size
                })
            
            # [START] Apply universal optimizations
            if file_size > 50 * 1024 * 1024:  # Files > 50MB
                universal_optimizer.optimize_for_large_files("upload")
            
            # Use original streaming method
            result = await self._stream_upload_async(
                upload_file, destination, encrypt, chunk_size, upload_id
            )
            
            # Update final status BEFORE cleanup
            elapsed = time.time() - start_time
            with self.upload_lock:
                if upload_id in self.active_uploads:
                    self.active_uploads[upload_id].update({
                        'status': 'completed',
                        'progress': 100,
                        'elapsed_time': elapsed
                    })
            
            logger.info("UPLOAD", "Upload completed", op_id=upload_id, details={"Size": file_size, "DurationSec": round(elapsed, 2), "Status": "SUCCESS"})
            
            # Schedule cleanup AFTER successful completion
            import asyncio
            asyncio.create_task(self._cleanup_upload_tracking(upload_id, delay=30))
            
            return result
            
        except Exception as e:
            # Update error status (with safety check)
            with self.upload_lock:
                if upload_id in self.active_uploads:
                    self.active_uploads[upload_id].update({
                        'status': 'error',
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
            
            logger.error("UPLOAD", "Upload failed", op_id=upload_id, details={"Reason": str(e)})
            
            # Return detailed error info instead of raising
            result = {
                'success': False,
                'filename': upload_file.filename,
                'error': str(e),
                'error_type': type(e).__name__,
                'upload_id': upload_id
            }
            
            # Schedule cleanup for failed uploads too
            import asyncio
            asyncio.create_task(self._cleanup_upload_tracking(upload_id, delay=30))
            
            return result
        
        finally:
            # Stop optimizations
            universal_optimizer.upload_active = False
            universal_optimizer.memory_cleanup(force=True)
            try:
                from app.utils.android_compat import update_android_progress
                update_android_progress(-1)
            except Exception:
                pass
    
    async def _stream_upload_async(
        self, 
        upload_file: UploadFile, 
        destination: Path, 
        encrypt: bool,
        chunk_size: int,
        upload_id: str
    ) -> Dict[str, Any]:
        """
        [STREAM] Stream upload with adaptive chunk processing - TRUE non-blocking I/O
        [LOCK] RACE CONDITION FIX: Upload to .tmp file first, then atomically move to final name
        """
        destination.parent.mkdir(parents=True, exist_ok=True)

        # [START] TEMPORARY FILE STRATEGY: Keep plaintext staging outside the uploads folder when encrypting
        if encrypt:
            temp_plaintext_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp', prefix=f"{upload_id}_")
            temp_destination = Path(temp_plaintext_file.name)
            temp_plaintext_file.close()
        else:
            temp_destination = destination.with_suffix(destination.suffix + '.tmp')

        encrypted_temp_destination = None
        encrypted_metadata_path = None
        
        # Get file size for responsiveness calculations
        file_size = 0
        with self.upload_lock:
            if upload_id in self.active_uploads:
                file_size = self.active_uploads[upload_id].get('total_size', 0)
        
        total_written = 0
        hash_calculator = hashlib.sha256()
        
        try:
            # [START] Use async file I/O to prevent blocking the event loop
            import aiofiles
            
            async with aiofiles.open(temp_destination, 'wb') as dest_file:
                chunk_count = 0
                last_yield = time.time()
                
                while True:
                    # [CFG] Read chunk with more frequent yielding for large files
                    chunk = await upload_file.read(chunk_size)
                    
                    if not chunk:
                        logger.log_upload("Upload streaming completed", op_id=upload_id, size_bytes=total_written, status="SUCCESS")
                        break
                    
                    chunk_count += 1
                    
                    # [START] Write chunk asynchronously to prevent blocking
                    await dest_file.write(chunk)
                    
                    total_written += len(chunk)
                    hash_calculator.update(chunk)
                    
                    # [CLEAN] Adaptive memory management
                    if universal_optimizer.should_run_gc(total_written, chunk_size):
                        gc.collect()
                    
                    # Broadcast upload progress to Android notification
                    if file_size:
                        percent = int((total_written / file_size) * 100)
                        if chunk_count % 10 == 0:  # Throttled progress updates
                            from app.utils.android_compat import update_android_progress
                            update_android_progress(percent, f"Uploading {upload_file.filename}...")
                    
                    # Update progress
                    with self.upload_lock:
                        if upload_id in self.active_uploads:
                            total_size = self.active_uploads[upload_id].get('total_size', 1)
                            progress = min(95, (total_written / total_size) * 100)
                            self.active_uploads[upload_id].update({
                                'progress': progress,
                                'bytes_processed': total_written
                            })
                    
                    # [TARGET] ULTRA-RESPONSIVE: Yield control MUCH more frequently for large files
                    current_time = time.time()
                    
                    # Adaptive yielding based on file size and chunk size
                    if file_size > 1024 * 1024 * 1024:  # Files > 1GB
                        yield_interval = 0.05  # 50ms - very frequent yielding
                    elif file_size > 100 * 1024 * 1024:  # Files > 100MB
                        yield_interval = 0.08  # 80ms - frequent yielding
                    else:
                        yield_interval = 0.1   # 100ms - normal yielding
                    
                    if current_time - last_yield > yield_interval:
                        # Use adaptive yielding based on system responsiveness
                        await ensure_responsiveness()
                        last_yield = current_time
                    
                    # Additional micro-yielding for very large chunks to prevent blocking
                    if chunk_size > 4 * 1024 * 1024:  # Chunks > 4MB
                        await asyncio.sleep(0.001)  # 1ms micro-sleep
                    
                    # Force yielding every 10 chunks for large files to prevent ANY blocking
                    if file_size > 500 * 1024 * 1024 and chunk_count % 10 == 0:
                        await asyncio.sleep(0.005)  # 5ms forced yield every 10 chunks
        
        except ImportError:
            logger.warn("UPLOAD", "aiofiles not available, using fallback", op_id=upload_id)
            return await self._stream_upload_sync_fallback(
                upload_file, destination, encrypt, chunk_size, upload_id, 
                total_written, hash_calculator
            )
        except Exception as e:
            if temp_destination.exists():
                temp_destination.unlink()
            logger.error("UPLOAD", "Stream upload error", op_id=upload_id, details={"Reason": str(e)})
            raise e
        
        final_source = temp_destination
        if encrypt:
            try:
                try:
                    from app.core.aes_utils import encrypt_file_to_file_streaming
                except ImportError:
                    from aes_utils import encrypt_file_to_file_streaming

                encrypted_temp_destination = temp_destination.with_suffix('.enc')
                metadata = await asyncio.to_thread(
                    encrypt_file_to_file_streaming,
                    str(temp_destination),
                    str(encrypted_temp_destination),
                    None,
                    chunk_size
                )

                metadata_path = encrypted_temp_destination.with_suffix('.enc.meta')
                metadata_payload = {
                    'encryption_method': 'streaming',
                    'algorithm': metadata.get('algorithm', 'AES-256-CBC-Stream-V2'),
                    'original_size': metadata.get('original_size', str(total_written)),
                    'encrypted_size': metadata.get('encrypted_size', '0'),
                    'chunk_size': str(chunk_size)
                }
                metadata_path.write_text(json.dumps(metadata_payload), encoding='utf-8')
                encrypted_metadata_path = metadata_path

                if temp_destination.exists():
                    temp_destination.unlink()
                final_source = encrypted_temp_destination
                logger.info("UPLOAD", "Encryption complete", op_id=upload_id, details={"Algorithm": metadata_payload['algorithm']})
            except Exception as e:
                if encrypted_temp_destination and encrypted_temp_destination.exists():
                    encrypted_temp_destination.unlink()
                if temp_destination.exists():
                    temp_destination.unlink()
                logger.error("UPLOAD", "Final encryption failed", op_id=upload_id, details={"Reason": str(e)})
                raise e

        await self._perform_atomic_move(
            final_source, destination, upload_id
        )

        if encrypt and encrypted_metadata_path:
            final_metadata_destination = destination.with_suffix('.enc.meta')
            try:
                await self._perform_atomic_move(
                    encrypted_metadata_path,
                    final_metadata_destination,
                    upload_id
                )
            except Exception:
                if destination.exists():
                    destination.unlink()
                raise
        
        return {
            'success': True,
            'filename': upload_file.filename,
            'size': destination.stat().st_size if destination.exists() else total_written,
            'hash': hash_calculator.hexdigest(),
            'destination': str(destination)
        }
    
    async def _stream_upload_sync_fallback(
        self, 
        upload_file: UploadFile, 
        destination: Path, 
        encrypt: bool,
        chunk_size: int,
        upload_id: str,
        total_written: int = 0,
        hash_calculator = None
    ) -> Dict[str, Any]:
        if hash_calculator is None:
            hash_calculator = hashlib.sha256()
        
        temp_destination = destination.with_suffix(destination.suffix + '.tmp')
        logger.debug("UPLOAD", "Sync fallback temporary upload started", op_id=upload_id)
            
        try:
            with open(temp_destination, 'wb') as dest_file:
                chunk_count = 0
                last_yield = time.time()
                
                while True:
                    chunk = await upload_file.read(chunk_size)
                    
                    if not chunk:
                        logger.debug("UPLOAD", "Sync fallback read complete", op_id=upload_id, details={"Chunks": chunk_count, "Size": total_written})
                        break
                    
                    chunk_count += 1
                    dest_file.write(chunk)
                    
                    total_written += len(chunk)
                    hash_calculator.update(chunk)
                    
                    if universal_optimizer.should_run_gc(total_written, chunk_size):
                        gc.collect()
                    
                    with self.upload_lock:
                        if upload_id in self.active_uploads:
                            total_size = self.active_uploads[upload_id].get('total_size', 1)
                            progress = min(95, (total_written / total_size) * 100)
                            self.active_uploads[upload_id].update({
                                'progress': progress,
                                'bytes_processed': total_written
                            })
                    
                    current_time = time.time()
                    if current_time - last_yield > 0.05:
                        await asyncio.sleep(0.005)
                        last_yield = current_time
        
        except Exception as e:
            if temp_destination.exists():
                temp_destination.unlink()
            logger.error("UPLOAD", "Sync fallback upload error", op_id=upload_id, details={"Reason": str(e)})
            raise e
        
        final_source = temp_destination
        if encrypt:
            encrypted_temp_destination = None
            encrypted_metadata_path = None
            try:
                try:
                    from app.core.aes_utils import encrypt_file_to_file_streaming
                except ImportError:
                    from aes_utils import encrypt_file_to_file_streaming

                encrypted_temp_destination = temp_destination.with_suffix('.enc')
                metadata = await asyncio.to_thread(
                    encrypt_file_to_file_streaming,
                    str(temp_destination),
                    str(encrypted_temp_destination),
                    None,
                    chunk_size
                )

                metadata_path = encrypted_temp_destination.with_suffix('.enc.meta')
                metadata_payload = {
                    'encryption_method': 'streaming',
                    'algorithm': metadata.get('algorithm', 'AES-256-CBC-Stream-V2'),
                    'original_size': metadata.get('original_size', str(total_written)),
                    'encrypted_size': metadata.get('encrypted_size', '0'),
                    'chunk_size': str(chunk_size)
                }
                metadata_path.write_text(json.dumps(metadata_payload), encoding='utf-8')
                encrypted_metadata_path = metadata_path

                if temp_destination.exists():
                    temp_destination.unlink()
                final_source = encrypted_temp_destination
                logger.info("UPLOAD", "Encryption complete", op_id=upload_id, details={"Algorithm": metadata_payload['algorithm']})
            except Exception as e:
                if encrypted_temp_destination and encrypted_temp_destination.exists():
                    encrypted_temp_destination.unlink()
                if temp_destination.exists():
                    temp_destination.unlink()
                logger.error("UPLOAD", "Final encryption failed", op_id=upload_id, details={"Reason": str(e)})
                raise e

        await self._perform_atomic_move(
            final_source, destination, upload_id
        )

        if encrypt and encrypted_metadata_path:
            final_metadata_destination = destination.with_suffix('.enc.meta')
            try:
                await self._perform_atomic_move(
                    encrypted_metadata_path,
                    final_metadata_destination,
                    upload_id
                )
            except Exception:
                if destination.exists():
                    destination.unlink()
                raise
        
        return {
            'success': True,
            'filename': upload_file.filename,
            'size': destination.stat().st_size if destination.exists() else total_written,
            'hash': hash_calculator.hexdigest(),
            'destination': str(destination)
        }
    
    async def _cleanup_upload_tracking(self, upload_id: str, delay: int = 30):
        await asyncio.sleep(delay)
        with self.upload_lock:
            if upload_id in self.active_uploads:
                del self.active_uploads[upload_id]
    
    def get_upload_status(self, upload_id: Optional[str] = None) -> Dict[str, Any]:
        with self.upload_lock:
            if upload_id:
                return self.active_uploads.get(upload_id, {})
            else:
                return {
                    'active_uploads': len(self.active_uploads),
                    'uploads': dict(self.active_uploads)
                }
    
    def get_system_status(self) -> Dict[str, Any]:
        with self.upload_lock:
            active_count = len(self.active_uploads)
            total_bytes = sum(u.get('bytes_processed', 0) for u in self.active_uploads.values())
            
        return {
            'concurrent_uploads_active': active_count,
            'max_concurrent': self.max_concurrent_uploads,
            'total_bytes_processing': total_bytes,
            'platform': universal_optimizer.platform_type,
            'memory_optimization_active': getattr(universal_optimizer, 'keep_alive_active', False)
        }

    async def _perform_atomic_move(
        self, 
        temp_destination: Path, 
        destination: Path, 
        upload_id: str
    ) -> None:
        import os
        import shutil
        import asyncio
        
        is_windows = os.name == 'nt'
        is_android = is_android_environment()
        
        platform_name = "Windows" if is_windows else "Android/Termux" if is_android else "Linux/Unix"
        
        max_retries = 3 if is_windows else 1
        retry_delay = 0.3 if is_windows else 0.1
        
        if is_windows:
            await asyncio.sleep(0.2)
            
        logger.debug("UPLOAD", "Performing atomic move", op_id=upload_id, details={"Platform": platform_name})
        
        for attempt in range(max_retries):
            try:
                if is_windows:
                    await asyncio.to_thread(shutil.move, str(temp_destination), str(destination))
                else:
                    temp_destination.rename(destination)
                
                logger.debug("UPLOAD", "Atomic move completed", op_id=upload_id)
                return
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warn("UPLOAD", "Move attempt failed, retrying", op_id=upload_id, details={"Attempt": attempt + 1, "Reason": str(e)})
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    if temp_destination.exists():
                        try:
                            temp_destination.unlink()
                            logger.debug("UPLOAD", "Cleaned up temp file after failed move", op_id=upload_id)
                        except Exception:
                            pass
                    
                    error_msg = f"Failed to finalize upload after {max_retries} attempts on {platform_name}: {e}"
                    logger.error("UPLOAD", "Atomic move failed", op_id=upload_id, details={"Reason": error_msg})
                    raise Exception(error_msg)


# Global concurrent upload manager
concurrent_upload_manager = ConcurrentUploadManager(max_concurrent_uploads=3)


async def save_upload_file_async(
    upload_file: UploadFile, 
    destination: Path, 
    encrypt: bool = False
) -> Dict[str, Any]:
    """
    [START] Async version of save_upload_file_sync with universal optimization
    """
    return await concurrent_upload_manager._upload_single_file_async(
        upload_file, destination, encrypt, upload_id=f"single_{time.time()}"
    )


async def upload_multiple_files_concurrent(
    files: List[UploadFile], 
    destinations: List[Path], 
    encrypt: bool = False
) -> List[Dict[str, Any]]:
    """
    [TARGET] Upload multiple files concurrently with adaptive optimization
    """
    return await concurrent_upload_manager.upload_files_concurrently(
        files, destinations, encrypt
    )
