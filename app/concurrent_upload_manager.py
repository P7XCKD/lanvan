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
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import UploadFile
from concurrent.futures import ThreadPoolExecutor
import threading

from .android_optimizer import universal_optimizer


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
            # 📊 Get file size for optimization
            upload_file.file.seek(0, 2)
            file_size = upload_file.file.tell()
            upload_file.file.seek(0)
            
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
            
            # 📝 Process file with streaming
            result = await self._stream_upload_async(
                upload_file, destination, encrypt, chunk_size, upload_id
            )
            
            # Update final status
            elapsed = time.time() - start_time
            with self.upload_lock:
                self.active_uploads[upload_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'elapsed_time': elapsed
                })
            
            print(f"✅ [{upload_id}] Upload completed: {upload_file.filename} in {elapsed:.1f}s")
            return result
            
        except Exception as e:
            # Update error status
            with self.upload_lock:
                self.active_uploads[upload_id].update({
                    'status': 'error',
                    'error': str(e)
                })
            
            print(f"❌ [{upload_id}] Upload failed: {upload_file.filename} - {str(e)}")
            raise e
        
        finally:
            # Cleanup upload tracking after delay
            asyncio.create_task(self._cleanup_upload_tracking(upload_id, delay=30))
            
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
        🌊 Stream upload with adaptive chunk processing
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        total_written = 0
        hash_calculator = hashlib.sha256()
        
        # Use executor for I/O operations to avoid blocking
        def write_chunk_sync(chunk_data: bytes, file_path: Path, mode: str):
            with open(file_path, mode) as f:
                f.write(chunk_data)
        
        try:
            with open(destination, 'wb') as dest_file:
                while True:
                    # Read chunk asynchronously
                    chunk = await asyncio.get_event_loop().run_in_executor(
                        self.executor, upload_file.file.read, chunk_size
                    )
                    
                    if not chunk:
                        break
                    
                    # Process chunk
                    if encrypt:
                        # Add encryption logic here if needed
                        pass
                    
                    # Write chunk asynchronously
                    await asyncio.get_event_loop().run_in_executor(
                        self.executor, dest_file.write, chunk
                    )
                    
                    total_written += len(chunk)
                    hash_calculator.update(chunk)
                    
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
                    
                    # Yield control to allow other uploads to progress
                    await asyncio.sleep(0)
        
        except Exception as e:
            # Clean up partial file
            if destination.exists():
                destination.unlink()
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
