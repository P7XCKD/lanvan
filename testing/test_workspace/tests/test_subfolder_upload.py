"""
Automated Test for Subfolder Uploads in Lanvan
Verifies that files uploaded while inside a subfolder are saved into that subfolder and not in Home root.
"""

import os
import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://127.0.0.1"

def run_subfolder_upload_test():
    print("[TEST] Starting Subfolder Upload Test...")
    
    subfolder_name = "TestSubfolder_AutoTest"
    test_filename = "subfolder_test_sample.txt"
    test_content = b"Subfolder upload automated test payload."
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    print(f"[TEST] Creating folder: {subfolder_name}")
    
    body_mkdir = [
        f"--{boundary}".encode("utf-8"),
        f'Content-Disposition: form-data; name="folder_name"'.encode("utf-8"),
        b"",
        subfolder_name.encode("utf-8"),
        f"--{boundary}--".encode("utf-8"),
        b""
    ]
    payload_mkdir = b"\r\n".join(body_mkdir)
    req = urllib.request.Request(
        f"{BASE_URL}/api/files/mkdir",
        data=payload_mkdir,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req) as response:
        print(f"[TEST] Create folder status: {response.status}, text: {response.read().decode('utf-8')}")

    # Upload a test file into TestSubfolder_AutoTest using multipart/form-data
    test_filename = "subfolder_test_sample.txt"
    test_content = b"Subfolder upload automated test payload."
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    body = []
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="parent_path"'.encode("utf-8"))
    body.append(b"")
    body.append(subfolder_name.encode("utf-8"))
    
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="files"; filename="{test_filename}"'.encode("utf-8"))
    body.append(b"Content-Type: text/plain")
    body.append(b"")
    body.append(test_content)
    body.append(f"--{boundary}--".encode("utf-8"))
    body.append(b"")

    payload = b"\r\n".join(body)
    
    upload_req = urllib.request.Request(
        f"{BASE_URL}/upload-auto",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    
    with urllib.request.urlopen(upload_req) as response:
        print(f"[TEST] Upload status: {response.status}, text: {response.read().decode('utf-8')}")

    # Check physical disk placement
    expected_path = Path("data/uploads") / subfolder_name / test_filename
    root_path = Path("data/uploads") / test_filename

    print(f"[TEST] Checking physical disk path: {expected_path}")
    assert expected_path.exists(), f"ERROR: File was NOT saved into subfolder! Path '{expected_path}' does not exist."
    assert not root_path.exists(), f"ERROR: File was mistakenly saved into root Home folder!"
    
    print("\n[SUCCESS] Subfolder upload test passed completely! Files are saved into subfolders accurately.\n")

if __name__ == "__main__":
    run_subfolder_upload_test()
