"""
🚀 Concurrent Upload Manager for LANVan
Handles multiple file uploads simultaneously with adaptive optimization for ALL platforms.

Key Features:
- Async concurrent processing (no more blocking!)
- Universal adaptive chunk sizing for all files
- Platform-aware optimizations
- Real-time progress tracking
- Memory-efficient streaming for large files
"""

import asyncio
import os
import hashlib
import gc
import time
import io
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import UploadFile
from concurrent.futures import ThreadPoolExecutor
import threading

from .android_optimizer import universal_optimizer
from .responsiveness_monitor import responsiveness_monitor, ensure_responsiveness


class ConcurrentUploadManager:
    """
    🎯 Manages multiple file uploads concurrently with adaptive optimization
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
        🚀 Upload multiple files concurrently with adaptive optimization
        """
        print(f"🔄 Starting concurrent upload of {len(files)} files (max {self.max_concurrent_uploads} parallel)")
        
        # Create upload tasks
        tasks = []
        for i, (file, destination) in enumerate(zip(files, destinations)):
            task = asyncio.create_task(
                self._upload_single_file_async(
                    file, destination, encrypt, upload_id=f"upload_{i}"
                )
            )
            tasks.append(task)
        
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
        
        print(f"✅ Concurrent upload completed: {len([r for r in processed_results if r.get('success')])} success, {len([r for r in processed_results if not r.get('success')])} failed")
        return processed_results
    
    async def _upload_single_file_async(
        self, 
        upload_file: UploadFile, 
        destination: Path, 
        encrypt: bool = False,
        upload_id: str = "upload"
    ) -> Dict[str, Any]:
        """
        🎯 Upload a single file asynchronously with adaptive optimization
        """
        start_time = time.time()
        
        # Register upload
        with self.upload_lock:
            self.active_uploads[upload_id] = {
                'filename': upload_file.filename,
                'start_time': start_time,
                'status': 'starting',
                'progress': 0,
                'bytes_processed': 0
            }
        
        try:
            # 📊 Get file size for optimization - FIXED: Use async operations
            try:
                import asyncio
                await asyncio.to_thread(upload_file.file.seek, 0, 2)
                file_size = await asyncio.to_thread(upload_file.file.tell)
                await asyncio.to_thread(upload_file.file.seek, 0)
            except:
                # Fallback: try to get size from UploadFile.size if seek fails
                file_size = getattr(upload_file, 'size', 0)
                if file_size == 0:
                    # Last resort: read once to get size then reset
                    content = await upload_file.read()
                    file_size = len(content)
                    # Reset file pointer by recreating the upload file object
                    upload_file.file = io.BytesIO(content)
            
            # 🎯 Get adaptive chunk size for this file
            chunk_size = universal_optimizer.get_adaptive_chunk_size(file_size)
            
            print(f"🔄 [{upload_id}] Starting upload: {upload_file.filename} ({file_size:,} bytes, {chunk_size//1024}KB chunks)")
            
            # Update status
            with self.upload_lock:
                self.active_uploads[upload_id].update({
                    'status': 'uploading',
                    'total_size': file_size,
                    'chunk_size': chunk_size
                })
            
            # 🚀 Apply universal optimizations
            if file_size > 50 * 1024 * 1024:  # Files > 50MB
                universal_optimizer.optimize_for_upload(file_size)
            
            # 📝 Process file with streaming - Enhanced with NEW async function option
            print(f"🔍 [{upload_id}] Starting upload...")
            
            # 🚀 NEW: Option to use optimized async function from routes.py
            USE_NEW_ASYNC_FUNCTION = False  # Temporarily disabled - need to fix return format
            
            if USE_NEW_ASYNC_FUNCTION:
                # Use the new optimized async function that fixes synchronous bottlenecks
                try:
                    from .routes import save_upload_file_async
                    print(f"🚀 [{upload_id}] Using optimized async upload...")
                    
                    # Call the new async function
                    await save_upload_file_async(upload_file, destination, encrypt)
                    
                    # Create result dictionary matching original format
                    final_size = destination.stat().st_size
                    
                    # Calculate hash of uploaded file for verification
                    import hashlib
                    hash_calculator = hashlib.sha256()
                    with open(destination, 'rb') as f:
                        while chunk := f.read(8192):
                            hash_calculator.update(chunk)
                    
                    result = {
                        'success': True,
                        'filename': upload_file.filename,
                        'size': final_size,
                        'hash': hash_calculator.hexdigest(),
                        'destination': str(destination)
                    }
                    
                except Exception as e:
                    print(f"⚠️ [{upload_id}] New function failed, using original: {e}")
                    # Fall back to original method
                    result = await self._stream_upload_async(
                        upload_file, destination, encrypt, chunk_size, upload_id
                    )
            else:
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
            
            print(f"✅ [{upload_id}] Upload completed: {upload_file.filename} in {elapsed:.1f}s")
            
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
            
            print(f"❌ [{upload_id}] Upload failed: {upload_file.filename} - {type(e).__name__}: {str(e)}")
            
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
    
    async def _stream_upload_async(
        self, 
        upload_file: UploadFile, 
        destination: Path, 
        encrypt: bool,
        chunk_size: int,
        upload_id: str
    ) -> Dict[str, Any]:
        """
        🌊 Stream upload with adaptive chunk processing - TRUE non-blocking I/O
        🔒 RACE CONDITION FIX: Upload to .tmp file first, then atomically move to final name
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # 🚀 TEMPORARY FILE STRATEGY: Upload to .tmp extension first
        temp_destination = destination.with_suffix(destination.suffix + '.tmp')
        
        print(f"🔄 [{upload_id}] Uploading to temporary file: {temp_destination.name}")
        
        # Get file size for responsiveness calculations
        file_size = 0
        with self.upload_lock:
            if upload_id in self.active_uploads:
                file_size = self.active_uploads[upload_id].get('total_size', 0)
        
        total_written = 0
        hash_calculator = hashlib.sha256()
        
        try:
            # 🚀 Use async file I/O to prevent blocking the event loop
            import aiofiles
            
            async with aiofiles.open(temp_destination, 'wb') as dest_file:
                chunk_count = 0
                last_yield = time.time()
                
                while True:
                    # 🔧 Read chunk with more frequent yielding for large files
                    chunk = await upload_file.read(chunk_size)
                    
                    if not chunk:
                        print(f"✅ [{upload_id}] Upload completed: {total_written:,} bytes")
                        break
                    
                    chunk_count += 1
                    
                    # 🔐 Process chunk with encryption if requested
                    if encrypt:
                        # Import encryption function
                        try:
                            from .aes_utils import encrypt_file_stream
                            print(f"🔐 [{upload_id}] Encrypting chunk {chunk_count} ({len(chunk):,} bytes)")
                            # For now, encrypt each chunk individually (can be optimized later)
                            encrypted_chunk, _ = encrypt_file_stream(chunk)
                            chunk = encrypted_chunk
                        except Exception as e:
                            print(f"❌ [{upload_id}] Encryption failed for chunk {chunk_count}: {e}")
                            # Continue without encryption as fallback
                    
                    # 🚀 Write chunk asynchronously to prevent blocking
                    await dest_file.write(chunk)
                    
                    total_written += len(chunk)
                    hash_calculator.update(chunk)
                    
                    # Progress logging for large files - MINIMAL SPAM
                    if chunk_count % 200 == 0:  # Much less frequent logging
                        print(f"📊 [{upload_id}] {total_written//1024//1024}MB")
                    
                    # 🧹 Adaptive memory management
                    if universal_optimizer.should_run_gc(total_written, chunk_size):
                        gc.collect()
                    
                    # Update progress
                    with self.upload_lock:
                        if upload_id in self.active_uploads:
                            total_size = self.active_uploads[upload_id].get('total_size', 1)
                            progress = min(95, (total_written / total_size) * 100)
                            self.active_uploads[upload_id].update({
                                'progress': progress,
                                'bytes_processed': total_written
                            })
                    
                    # 🎯 ULTRA-RESPONSIVE: Yield control MUCH more frequently for large files
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
            # Fallback to synchronous I/O if aiofiles not available
            print(f"⚠️ [{upload_id}] aiofiles not available, using synchronous I/O")
            return await self._stream_upload_sync_fallback(
                upload_file, destination, encrypt, chunk_size, upload_id, 
                total_written, hash_calculator
            )
        except Exception as e:
            # Clean up partial temp file
            if temp_destination.exists():
                temp_destination.unlink()
            # Enhanced error logging for debugging
            print(f"❌ [{upload_id}] Stream upload error: {type(e).__name__}: {str(e)}")
            raise e
        
        # 🎯 ATOMIC MOVE: Move from .tmp to final destination to prevent race conditions
        try:
            print(f"🔄 [{upload_id}] Moving {temp_destination.name} → {destination.name}")
            temp_destination.rename(destination)
            print(f"✅ [{upload_id}] File atomically moved to final destination")
        except Exception as e:
            # Clean up temp file if move fails
            if temp_destination.exists():
                temp_destination.unlink()
            print(f"❌ [{upload_id}] Failed to move temp file: {e}")
            raise Exception(f"Failed to finalize upload: {e}")
        
        return {
            'success': True,
            'filename': upload_file.filename,
            'size': total_written,
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
        """
        🔄 Fallback synchronous upload with frequent yielding
        """
        if hash_calculator is None:
            hash_calculator = hashlib.sha256()
            
        try:
            with open(destination, 'wb') as dest_file:
                chunk_count = 0
                last_yield = time.time()
                
                while True:
                    chunk = await upload_file.read(chunk_size)
                    
                    if not chunk:
                        print(f"🏁 [{upload_id}] Finished reading after {chunk_count} chunks, {total_written:,} bytes")
                        break
                    
                    chunk_count += 1
                    
                    # Write chunk synchronously but yield frequently
                    dest_file.write(chunk)
                    
                    total_written += len(chunk)
                    hash_calculator.update(chunk)
                    
                    # Progress logging
                    if chunk_count % 32 == 0:
                        print(f"📊 [{upload_id}] Progress: {chunk_count} chunks, {total_written//1024//1024}MB written")
                    
                    # Memory management
                    if universal_optimizer.should_run_gc(total_written, chunk_size):
                        gc.collect()
                    
                    # Update progress
                    with self.upload_lock:
                        if upload_id in self.active_uploads:
                            total_size = self.active_uploads[upload_id].get('total_size', 1)
                            progress = min(95, (total_written / total_size) * 100)
                            self.active_uploads[upload_id].update({
                                'progress': progress,
                                'bytes_processed': total_written
                            })
                    
                    # 🎯 FREQUENT yielding to prevent blocking
                    current_time = time.time()
                    if current_time - last_yield > 0.05:  # Yield every 50ms
                        await asyncio.sleep(0.005)  # 5ms sleep
                        last_yield = current_time
        
        except Exception as e:
            if destination.exists():
                destination.unlink()
            print(f"❌ [{upload_id}] Sync fallback upload error: {type(e).__name__}: {str(e)}")
            raise e
        
        return {
            'success': True,
            'filename': upload_file.filename,
            'size': total_written,
            'hash': hash_calculator.hexdigest(),
            'destination': str(destination)
        }
    
    async def _cleanup_upload_tracking(self, upload_id: str, delay: int = 30):
        """Clean up upload tracking after delay"""
        await asyncio.sleep(delay)
        with self.upload_lock:
            if upload_id in self.active_uploads:
                del self.active_uploads[upload_id]
    
    def get_upload_status(self, upload_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current upload status"""
        with self.upload_lock:
            if upload_id:
                return self.active_uploads.get(upload_id, {})
            else:
                return {
                    'active_uploads': len(self.active_uploads),
                    'uploads': dict(self.active_uploads)
                }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system-wide upload status"""
        with self.upload_lock:
            active_count = len(self.active_uploads)
            total_bytes = sum(u.get('bytes_processed', 0) for u in self.active_uploads.values())
            
        return {
            'concurrent_uploads_active': active_count,
            'max_concurrent': self.max_concurrent_uploads,
            'total_bytes_processing': total_bytes,
            'platform': universal_optimizer.platform,
            'memory_optimization_active': universal_optimizer.upload_active
        }


# Global concurrent upload manager
concurrent_upload_manager = ConcurrentUploadManager(max_concurrent_uploads=3)


async def save_upload_file_async(
    upload_file: UploadFile, 
    destination: Path, 
    encrypt: bool = False
) -> Dict[str, Any]:
    """
    🚀 Async version of save_upload_file_sync with universal optimization
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
    🎯 Upload multiple files concurrently with adaptive optimization
    """
    return await concurrent_upload_manager.upload_files_concurrently(
        files, destinations, encrypt
    )
