"""
🔧 Windows File Handle Management Utilities
Helps with file locking issues specific to Windows systems
"""

import os
import gc
import time
import asyncio
import subprocess
import psutil
from pathlib import Path
from typing import List, Optional

class WindowsFileManager:
    """
    🔧 Handles Windows-specific file management challenges
    """
    
    @staticmethod
    def force_release_handles():
        """
        🚀 Force release Python file handles using garbage collection
        """
        # Multiple rounds of garbage collection
        for _ in range(3):
            gc.collect()
            time.sleep(0.1)
    
    @staticmethod
    async def async_force_release_handles():
        """
        🚀 Async version of handle release
        """
        for _ in range(3):
            gc.collect()
            await asyncio.sleep(0.1)
    
    @staticmethod
    def check_file_in_use(file_path: Path) -> bool:
        """
        🔍 Check if a file is currently in use by trying to open it exclusively
        """
        try:
            with open(file_path, 'r+b') as test_handle:
                return False  # File is not in use
        except (PermissionError, FileNotFoundError):
            return True  # File is in use or doesn't exist
        except Exception:
            return True  # Assume in use if other errors
    
    @staticmethod
    async def safe_delete_file(file_path: Path, max_attempts: int = 5) -> tuple[bool, str]:
        """
        🗑️ Safely delete a file with progressive retry and handle release
        
        Returns:
            tuple[bool, str]: (success, message)
        """
        if not file_path.exists():
            return True, f"File {file_path.name} doesn't exist"
        
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                # Progressive handle release attempts
                if attempt > 0:
                    await WindowsFileManager.async_force_release_handles()
                    
                    # Progressive backoff
                    wait_time = 0.3 + (attempt * 0.2)
                    await asyncio.sleep(wait_time)
                    
                    # Check if file is still in use
                    if WindowsFileManager.check_file_in_use(file_path):
                        print(f"🔄 File still locked (attempt {attempt + 1}/{max_attempts}): {file_path.name}")
                        continue
                
                # Try to delete
                file_path.unlink()
                return True, f"✅ Deleted: {file_path.name}"
                
            except PermissionError as e:
                last_error = str(e)
                if attempt < max_attempts - 1:
                    print(f"🔄 Permission denied (attempt {attempt + 1}/{max_attempts}): {file_path.name}")
                else:
                    return False, f"🔒 File still in use after {max_attempts} attempts: {file_path.name} - {e}"
            except Exception as e:
                return False, f"❌ Error deleting file {file_path.name}: {e}"
        
        return False, f"🔒 Failed to delete {file_path.name} after {max_attempts} attempts. Last error: {last_error}"
    
    @staticmethod
    def get_processes_using_file(file_path: Path) -> List[dict]:
        """
        🔍 Get list of processes that have the file open (Windows only)
        """
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                try:
                    open_files = proc.info['open_files']
                    if open_files:
                        for open_file in open_files:
                            if Path(open_file.path) == file_path:
                                processes.append({
                                    'pid': proc.info['pid'],
                                    'name': proc.info['name'],
                                    'file_path': open_file.path
                                })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            print(f"⚠️ Error checking processes: {e}")
        
        return processes
    
    @staticmethod
    async def enhanced_cleanup_with_diagnostics(upload_folder: Path, temp_folder: Optional[Path] = None):
        """
        🧹 Enhanced cleanup with detailed diagnostics and reporting
        """
        results = {
            'files_deleted': 0,
            'files_locked': 0,
            'chunks_deleted': 0,
            'locked_files': [],
            'processes_using_files': []
        }
        
        # Clean main upload files
        if upload_folder.exists():
            for file_path in upload_folder.iterdir():
                if file_path.is_file():
                    success, message = await WindowsFileManager.safe_delete_file(file_path)
                    if success:
                        results['files_deleted'] += 1
                        print(message)
                    else:
                        results['files_locked'] += 1
                        results['locked_files'].append(file_path.name)
                        print(message)
                        
                        # Get diagnostic info about what's using the file
                        processes = WindowsFileManager.get_processes_using_file(file_path)
                        if processes:
                            results['processes_using_files'].extend(processes)
                            print(f"📊 Processes using {file_path.name}: {[p['name'] for p in processes]}")
        
        # Clean temp chunks
        if temp_folder and temp_folder.exists():
            for chunk_file in temp_folder.iterdir():
                if chunk_file.is_file():
                    success, message = await WindowsFileManager.safe_delete_file(chunk_file)
                    if success:
                        results['chunks_deleted'] += 1
        
        return results

# Global instance for easy access
windows_file_manager = WindowsFileManager()

# Convenience functions
async def safe_delete_file(file_path: Path, max_attempts: int = 5) -> tuple[bool, str]:
    """Convenience function for safe file deletion"""
    return await WindowsFileManager.safe_delete_file(file_path, max_attempts)

def force_release_handles():
    """Convenience function for handle release"""
    WindowsFileManager.force_release_handles()

async def async_force_release_handles():
    """Convenience function for async handle release"""
    await WindowsFileManager.async_force_release_handles()
