#!/usr/bin/env python3
"""
Certificate Cleanup Script
==========================
This script removes existing certificate files so they can be auto-generated fresh.
Run this before uploading to GitHub to ensure no private keys are committed.
"""

import os
import sys
from pathlib import Path

def cleanup_certificates():
    """Remove existing certificate files"""
    certs_dir = Path(__file__).parent
    cert_files = [
        certs_dir / "cert.pem",
        certs_dir / "key.pem",
        certs_dir / "cert.crt",
        certs_dir / "private.key"
    ]
    
    removed_count = 0
    for cert_file in cert_files:
        if cert_file.exists():
            try:
                cert_file.unlink()
                print(f"[OK] Removed: {cert_file.name}")
                removed_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to remove {cert_file.name}: {e}")
    
    if removed_count == 0:
        print("[INFO] No certificate files found to remove")
    else:
        print(f"[INFO] Cleaned up {removed_count} certificate file(s)")
        print("[INFO] Certificates will be auto-generated when needed")

if __name__ == "__main__":
    print("[INFO] Certificate Cleanup")
    print("=" * 30)
    cleanup_certificates()
