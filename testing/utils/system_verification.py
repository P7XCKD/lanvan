#!/usr/bin/env python3
"""
[SEARCH] LANVAN System Verification Script
Tests all components before P2P implementation
"""

import sys
import importlib
import os

# Add project root to Python path for app imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_import(module_name, description):
    try:
        importlib.import_module(module_name)
        print(f"[OK] {description}: OK")
        return True
    except Exception as e:
        print(f"[ERR] {description}: FAILED - {e}")
        return False

def main():
    print("[SEARCH] LANVAN System Verification")
    print("=" * 50)
    print(f"Python Version: {sys.version}")
    print()
    
    # Test core dependencies
    tests = [
        ("fastapi", "FastAPI Framework"),
        ("uvicorn", "ASGI Server"),
        ("aiofiles", "Async File Operations"),
        ("pyperclip", "Clipboard Support"),
        ("aiortc", "WebRTC for P2P"),
        ("cryptography", "AES Encryption"),
        ("zeroconf", "mDNS Discovery"),
        ("psutil", "System Monitoring"),
        ("qrcode", "QR Code Generation"),
    ]
    
    results = []
    for module, desc in tests:
        results.append(test_import(module, desc))
    
    print()
    
    # Test LANVAN modules
    lanvan_tests = [
        ("app.main", "LANVAN Core"),
        ("app.routes", "API Routes"),
        ("app.config", "Configuration"),
        ("app.aes_utils", "Encryption Utils"),
        ("app.mdns_manager", "mDNS Manager"),
    ]
    
    for module, desc in lanvan_tests:
        results.append(test_import(module, desc))
    
    print()
    
    if all(results):
        print("[DONE] SYSTEM STATUS: ALL GREEN!")
        print("[START] Ready for P2P Implementation!")
        return True
    else:
        print("[WARN]  SYSTEM STATUS: Issues detected")
        print("[ERR] Fix issues before proceeding")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
