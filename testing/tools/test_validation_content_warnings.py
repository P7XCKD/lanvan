"""
Regression test for FileValidator.validate_uploaded_file uninitialized content_warnings bug.
Verifies file validation succeeds in HTTP mode (is_https=False) where dangerous blocking is disabled.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.validation import FileValidator

def test_validate_uploaded_file_http_mode():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF-1.4\n%EOF\n")
        tmp_path = Path(tmp.name)
    
    try:
        # Test 1: HTTP mode (is_https=False) - dangerous blocking disabled by default
        res_http = FileValidator.validate_uploaded_file(tmp_path, "test_document.pdf", is_https=False)
        assert res_http["valid"] == True, f"HTTP mode validation failed: {res_http}"
        assert res_http["warnings"] == [], f"Unexpected warnings in HTTP mode: {res_http['warnings']}"
        assert res_http["extension_check"] is None, f"Extension check should be None in HTTP mode: {res_http['extension_check']}"
        print("[PASS] Test 1: HTTP mode (is_https=False) validation passed without UnboundLocalError.")

        # Test 2: HTTPS mode (is_https=True) - dangerous blocking enabled by default
        res_https = FileValidator.validate_uploaded_file(tmp_path, "test_document.pdf", is_https=True)
        assert res_https["valid"] == True, f"HTTPS mode validation failed: {res_https}"
        print("[PASS] Test 2: HTTPS mode (is_https=True) validation passed.")

        # Test 3: Malicious file (executable disguised as txt) in HTTPS mode should be blocked
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_exe:
            tmp_exe.write(b"MZ\x90\x00\x03\x00\x00\x00")
            tmp_exe_path = Path(tmp_exe.name)
        
        try:
            res_malicious = FileValidator.validate_uploaded_file(tmp_exe_path, "malware.txt", is_https=True)
            assert res_malicious["valid"] == False, f"Malicious file should be blocked in HTTPS mode: {res_malicious}"
            print("[PASS] Test 3: Malicious file correctly blocked in HTTPS mode.")
        finally:
            if tmp_exe_path.exists():
                tmp_exe_path.unlink()

    finally:
        if tmp_path.exists():
            tmp_path.unlink()

if __name__ == "__main__":
    test_validate_uploaded_file_http_mode()
    print("ALL VALIDATION CONTENT_WARNINGS TESTS PASSED 100%!")
