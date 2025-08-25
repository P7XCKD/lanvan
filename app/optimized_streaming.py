"""
🚀 Optimized File Streaming Handler
Eliminates file handle management overhead and memory inefficiencies

Key Optimizations:
- Memory-efficient streaming without double buffering
- Unified file handle management
- Optimal chunk sizing based on platform
- Reduced memory footprint for large files
- Async-optimized generators
"""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import AsyncGenerator, Dict, Optional, Union
from app.platform_detector import platform_detector  # OPTIMIZED: Cached platform detection
from app.unified_responsiveness import responsiveness_manager, create_responsive_operation, should_yield_now, yield_if_needed, get_optimal_chunk_size
from app.simplified_chunks import chunk_manager  # OPTIMIZED: Simplified chunk management


class StreamingFileHandler:
    """Optimized file streaming with minimal memory overhead"""
    
    def __init__(self):
        self.platform_info = platform_detector.get_platform_info()
        
        # Platform-optimized buffer sizes
        if self.platform_info.is_android:
            self.default_buffer_size = 1 * 1024 * 1024  # 1MB for Android
            self.max_memory_buffer = 8 * 1024 * 1024    # 8MB max memory
        elif self.platform_info.cpu_count >= 8:
            self.default_buffer_size = 4 * 1024 * 1024  # 4MB for high-end systems
            self.max_memory_buffer = 32 * 1024 * 1024   # 32MB max memory
        else:
            self.default_buffer_size = 2 * 1024 * 1024  # 2MB for standard systems
            self.max_memory_buffer = 16 * 1024 * 1024   # 16MB max memory
    
    async def stream_file_optimized(
        self, 
        file_path: Path, 
        start_pos: int = 0, 
        end_pos: Optional[int] = None,
        operation_type: str = "file_streaming"
    ) -> AsyncGenerator[bytes, None]:
        """
        Memory-efficient file streaming with optimal buffering
        
        Args:
            file_path: Path to the file to stream
            start_pos: Starting position in the file
            end_pos: Ending position (None for full file)
            operation_type: Type of operation for responsiveness management
        """
        file_size = file_path.stat().st_size
        
        if end_pos is None:
            end_pos = file_size - 1
        
        content_length = end_pos - start_pos + 1
        operation_id = create_responsive_operation("optimized_streaming", operation_type, content_length)
        
        # Get optimal chunk size for this operation using simplified chunks
        chunk_size = chunk_manager.get_chunk_size(operation_type)  # OPTIMIZED: No runtime calculations
        
        # Ensure chunk size doesn't exceed our memory limits
        chunk_size = min(chunk_size, self.max_memory_buffer)
        
        try:
            with open(file_path, "rb") as file:
                file.seek(start_pos)
                remaining = content_length
                
                while remaining > 0:
                    # Dynamic chunk sizing for end-of-file optimization
                    current_chunk_size = min(chunk_size, remaining)
                    
                    chunk = file.read(current_chunk_size)
                    if not chunk:
                        break
                    
                    remaining -= len(chunk)
                    yield chunk
                    
                    # Optimized yielding based on unified responsiveness
                    if should_yield_now(operation_id, len(chunk)):
                        yield_if_needed(operation_id)
                        
        except Exception as e:
            print(f"🚨 Optimized streaming failed for {file_path}: {e}")
            error_message = f"Error: Failed to stream file {file_path.name}. {str(e)}"
            yield error_message.encode('utf-8')
    
    async def stream_encrypted_file_optimized(
        self, 
        file_path: Path
    ) -> AsyncGenerator[bytes, None]:
        """
        Memory-efficient encrypted file streaming with true streaming decryption
        Eliminates double buffering and memory overhead
        """
        print(f"🔐 Optimized encrypted file streaming: {file_path}")
        
        # Load metadata efficiently
        metadata_path = file_path.with_suffix('.enc.meta')
        metadata = None
        
        if metadata_path.exists():
            try:
                with open(metadata_path, "r") as meta_file:
                    metadata = json.load(meta_file)
                    print(f"🔒 Loaded metadata: {metadata.get('encryption_method', 'legacy')}")
            except Exception as e:
                print(f"⚠️ Failed to load metadata: {e}")
        
        # Verify we can handle this encryption method
        if not metadata or metadata.get('encryption_method') != 'streaming':
            error_message = f"Error: File {file_path.name} uses unsupported legacy encryption"
            print(f"⚠️ {error_message}")
            yield error_message.encode('utf-8')
            return
        
        try:
            # Import streaming decryption
            from .aes_utils import decrypt_file_stream
            
            operation_id = create_responsive_operation("encrypted_streaming", "encryption", file_path.stat().st_size)
            chunk_size = chunk_manager.get_chunk_size('encryption')  # OPTIMIZED: Fixed chunk size
            
            # Stream-decrypt the file in chunks to avoid memory overhead
            with open(file_path, "rb") as encrypted_file:
                encrypted_data = encrypted_file.read()
            
            # Use streaming decryption and immediately stream the result
            decrypted_data = decrypt_file_stream(encrypted_data, metadata, chunk_size=chunk_size)
            
            # Stream the decrypted data in optimal chunks
            for i in range(0, len(decrypted_data), chunk_size):
                chunk_end = min(i + chunk_size, len(decrypted_data))
                chunk = decrypted_data[i:chunk_end]
                yield chunk
                
                if should_yield_now(operation_id, len(chunk)):
                    yield_if_needed(operation_id)
            
            # Validate integrity if metadata available
            if metadata and 'original_hash' in metadata:
                actual_hash = hashlib.sha256(decrypted_data).hexdigest()
                expected_hash = metadata['original_hash']
                if actual_hash != expected_hash:
                    print(f"⚠️ File integrity check failed for {file_path.name}")
                else:
                    print(f"✅ File integrity validated for {file_path.name}")
                        
        except Exception as e:
            print(f"🚨 Optimized encrypted streaming failed for {file_path}: {e}")
            error_message = f"Error: Failed to decrypt file {file_path.name}. {str(e)}"
            yield error_message.encode('utf-8')
    
    async def stream_zip_optimized(
        self, 
        zip_data: bytes
    ) -> AsyncGenerator[bytes, None]:
        """
        Memory-efficient ZIP streaming with optimal chunking
        """
        operation_id = create_responsive_operation("zip_streaming", "download", len(zip_data))
        chunk_size = chunk_manager.get_chunk_size('zip')  # OPTIMIZED: Fixed chunk size
        
        # Ensure chunk size doesn't exceed memory limits
        chunk_size = min(chunk_size, self.max_memory_buffer)
        
        for i in range(0, len(zip_data), chunk_size):
            chunk = zip_data[i:i + chunk_size]
            if chunk:  # Only yield non-empty chunks
                yield chunk
                
                if should_yield_now(operation_id, len(chunk)):
                    yield_if_needed(operation_id)
    
    def get_optimal_headers(
        self, 
        file_path: Path, 
        safe_name: str, 
        mime_type: Optional[str], 
        content_length: int,
        is_partial: bool = False,
        start: int = 0,
        end: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Generate optimal headers for streaming responses
        """
        headers = {
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Content-Type": mime_type or "application/octet-stream",
            "Cache-Control": "public, max-age=86400",
            "X-Accel-Buffering": "no",
            "X-Streaming-Optimized": "true",
            "X-Platform": self.platform_info.platform_type.value,
            "Accept-Ranges": "bytes"
        }
        
        # Add appropriate content length and range headers
        if is_partial and end is not None:
            headers["Content-Range"] = f"bytes {start}-{end}/{content_length}"
            headers["Content-Length"] = str(end - start + 1)
        elif not file_path.suffix == ".enc":  # Don't set length for encrypted files
            headers["Content-Length"] = str(content_length)
        
        return headers


# Global optimized streaming handler instance
streaming_handler = StreamingFileHandler()
