#!/usr/bin/env python3
"""
LANVAN Cleanup Utility
Cleans up temporary files, caches, and unnecessary artifacts
"""

import os
import shutil
import glob
from pathlib import Path

def clean_python_cache():
    """Remove Python cache files and directories"""
    print("🧹 Cleaning Python cache files...")
    
    # Remove __pycache__ directories
    for pycache_dir in Path('.').rglob('__pycache__'):
        if pycache_dir.is_dir():
            print(f"   Removing {pycache_dir}")
            shutil.rmtree(pycache_dir, ignore_errors=True)
    
    # Remove .pyc files
    for pyc_file in Path('.').rglob('*.pyc'):
        print(f"   Removing {pyc_file}")
        pyc_file.unlink(missing_ok=True)

def clean_upload_temp():
    """Clean temporary upload files"""
    print("📁 Cleaning temporary upload files...")
    
    temp_dirs = [
        'app/uploads/temp_chunks',
        'app/uploads/temp_downloads'
    ]
    
    for temp_dir in temp_dirs:
        temp_path = Path(temp_dir)
        if temp_path.exists():
            for item in temp_path.iterdir():
                if item.is_file():
                    print(f"   Removing {item}")
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    print(f"   Removing directory {item}")
                    shutil.rmtree(item, ignore_errors=True)

def clean_logs():
    """Clean log files"""
    print("📋 Cleaning log files...")
    
    log_patterns = ['*.log', 'logs/*.log', 'debug.log', 'error.log']
    
    for pattern in log_patterns:
        for log_file in glob.glob(pattern, recursive=True):
            print(f"   Removing {log_file}")
            os.remove(log_file)

def clean_certificates():
    """Clean generated certificates (keep templates)"""
    print("🔒 Cleaning generated certificates...")
    
    cert_dir = Path('certs')
    if cert_dir.exists():
        cert_patterns = ['*.pem', '*.key', '*.crt', '*.cert']
        
        for pattern in cert_patterns:
            for cert_file in cert_dir.glob(pattern):
                print(f"   Removing {cert_file}")
                cert_file.unlink(missing_ok=True)

def clean_workspace_files():
    """Clean IDE and workspace files"""
    print("🛠️  Cleaning workspace and IDE files...")
    
    patterns = ['*.code-workspace', '.vscode/settings.json']
    
    for pattern in patterns:
        for workspace_file in Path('.').glob(pattern):
            print(f"   Removing {workspace_file}")
            workspace_file.unlink(missing_ok=True)

def main():
    """Run cleanup operations"""
    print("🚀 LANVAN Cleanup Utility")
    print("=" * 30)
    
    try:
        clean_python_cache()
        clean_upload_temp()
        clean_logs()
        clean_workspace_files()
        
        # Ask before cleaning certificates
        response = input("\n🔒 Clean generated certificates? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            clean_certificates()
        
        print("\n✅ Cleanup completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
