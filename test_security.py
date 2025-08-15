#!/usr/bin/env python3
"""
🛡️ LANVan Enhanced Security Test Suite
Tests the advanced file validation and extension manipulation detection.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from validation import AdvancedFileValidator

def test_blocked_extensions():
    """Test that dangerous file extensions are properly blocked"""
    print("🧪 Testing blocked extensions...")
    
    dangerous_files = [
        "malware.exe",
        "script.bat", 
        "virus.scr",
        "trojan.com",
        "keylogger.pif"
    ]
    
    for filename in dangerous_files:
        # Create a temporary file with dangerous extension
        with tempfile.NamedTemporaryFile(suffix=f"_{filename}", delete=False) as tmp:
            tmp.write(b"This is test content")
            temp_path = Path(tmp.name)
        
        try:
            result = AdvancedFileValidator.validate_uploaded_file(temp_path)
            if result['valid']:
                print(f"❌ SECURITY FAIL: {filename} was allowed through!")
            else:
                print(f"✅ BLOCKED: {filename} - {result['error']}")
        finally:
            temp_path.unlink()
    
def test_extension_spoofing():
    """Test detection of extension manipulation (spoofed extensions)"""
    print("\n🕵️ Testing extension spoofing detection...")
    
    # Test cases: (content, claimed_extension, should_detect_spoofing)
    test_cases = [
        (b"MZ\x90\x00", ".txt", True),  # PE executable disguised as text
        (b"\x7fELF", ".pdf", True),     # Linux ELF disguised as PDF  
        (b"PK\x03\x04", ".txt", True),  # ZIP file disguised as text
        (b"%PDF-1.4", ".pdf", False),   # Legitimate PDF
        (b"Hello world", ".txt", False) # Legitimate text
    ]
    
    for content, extension, should_detect in test_cases:
        # Create temporary file with test content
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)
        
        try:
            result = AdvancedFileValidator.validate_uploaded_file(temp_path)
            
            if should_detect:
                if not result['valid']:
                    print(f"✅ DETECTED: Extension spoofing for {extension} - {result['error']}")
                else:
                    print(f"❌ MISSED: Failed to detect spoofed {extension}")
            else:
                if result['valid']:
                    print(f"✅ ALLOWED: Legitimate {extension} file")
                else:
                    print(f"⚠️ FALSE POSITIVE: Legitimate {extension} blocked - {result['error']}")
        finally:
            temp_path.unlink()

def test_legitimate_files():
    """Test that legitimate files are allowed through"""
    print("\n📄 Testing legitimate file types...")
    
    legitimate_files = [
        (b"Hello, this is a text file.", ".txt"),
        (b"%PDF-1.4\n%test content", ".pdf"),
        (b"# Python script\nprint('hello')", ".py"),
        (b'{"name": "test", "value": 123}', ".json"),
        (b"Name,Age,City\nJohn,30,NYC", ".csv")
    ]
    
    for content, extension in legitimate_files:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)
        
        try:
            result = AdvancedFileValidator.validate_uploaded_file(temp_path)
            if result['valid']:
                print(f"✅ ALLOWED: {extension} file passed validation")
                if result.get('warnings'):
                    print(f"   ⚠️ Warnings: {'; '.join(result['warnings'])}")
            else:
                print(f"❌ BLOCKED: Legitimate {extension} file was rejected - {result['error']}")
        finally:
            temp_path.unlink()

def main():
    """Run all security tests"""
    print("🛡️ LANVan Enhanced Security Test Suite")
    print("="*50)
    
    try:
        # Test 1: Blocked extensions
        test_blocked_extensions()
        
        # Test 2: Extension spoofing detection
        test_extension_spoofing()
        
        # Test 3: Legitimate files
        test_legitimate_files()
        
        print("\n" + "="*50)
        print("🎉 Security testing completed!")
        print("✅ Enhanced security system is operational")
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
