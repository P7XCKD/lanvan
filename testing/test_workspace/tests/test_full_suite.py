import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://127.0.0.1"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def post_form(url, data_dict):
    encoded_data = urllib.parse.urlencode(data_dict).encode("utf-8")
    req = urllib.request.Request(url, data=encoded_data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

def get_json(url):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, {}

def upload_multipart(url, file_name, file_content_bytes, parent_path=""):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = []
    
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="parent_path"'.encode("utf-8"))
    body.append(b"")
    body.append(parent_path.encode("utf-8"))
    
    body.append(f"--{boundary}".encode("utf-8"))
    body.append(f'Content-Disposition: form-data; name="files"; filename="{file_name}"'.encode("utf-8"))
    body.append(f'Content-Type: application/octet-stream'.encode("utf-8"))
    body.append(b"")
    body.append(file_content_bytes)
    
    body.append(f"--{boundary}--".encode("utf-8"))
    body.append(b"")
    
    payload = b"\r\n".join(body)
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read().decode("utf-8")

def run_stress_test_suite():
    log("==========================================", "SUITE")
    log(" STARTING ENHANCED STRESS & EDGE-CASE SUITE", "SUITE")
    log("==========================================", "SUITE")

    # TEST 1: Folders with Spaces & Path Encoding
    folder_space = "Untitled folder test"
    folder_nested = "Sub nested"
    log(f"[TEST 1] Creating folder with spaces: '{folder_space}'")
    status, text = post_form(f"{BASE_URL}/api/files/mkdir", {"folder_name": folder_space})
    assert status == 200, f"mkdir failed: {text}"
    log(f"Created '{folder_space}' successfully", "OK")

    log(f"[TEST 1.1] Creating nested subfolder: '{folder_nested}' inside '{folder_space}'")
    status, text = post_form(f"{BASE_URL}/api/files/mkdir", {"folder_name": folder_nested, "parent_path": folder_space})
    assert status == 200, f"nested mkdir failed: {text}"
    log(f"Created '{folder_nested}' successfully", "OK")

    # TEST 2: Parallel Uploads across Root & Subfolder with spaces
    file_root = "root_stress_doc.txt"
    file_sub = "sub_stress_doc.txt"
    
    log(f"[TEST 2] Uploading '{file_root}' to Root (Home)...")
    status, text = upload_multipart(f"{BASE_URL}/upload-auto", file_root, b"Root File Content", parent_path="")
    assert status == 200, f"Root upload failed: {text}"
    
    log(f"[TEST 2.1] Uploading '{file_sub}' to Subfolder '{folder_space}'...")
    status, text = upload_multipart(f"{BASE_URL}/upload-auto", file_sub, b"Subfolder File Content", parent_path=folder_space)
    assert status == 200, f"Subfolder upload failed: {text}"

    # Verify physical file locations
    root_disk_path = Path("data") / "uploads" / file_root
    sub_disk_path = Path("data") / "uploads" / folder_space / file_sub
    assert root_disk_path.exists(), f"Root file not found on disk at {root_disk_path}"
    assert sub_disk_path.exists(), f"Subfolder file not found on disk at {sub_disk_path}"
    log("Physical file placement verified for root and subfolder with spaces", "OK")

    # TEST 3: Verify Subfolder File Listing API with URL encoding
    encoded_folder = urllib.parse.quote(folder_space)
    log(f"[TEST 3] Fetching subfolder files via /api/folders/{encoded_folder}/files...")
    status, data = get_json(f"{BASE_URL}/api/folders/{encoded_folder}/files")
    assert status == 200, f"Folder files list API failed: {data}"
    files_in_sub = [f["name"] for f in data.get("files", [])]
    assert file_sub in files_in_sub, f"{file_sub} missing from subfolder file listing"
    log(f"Folder files API returned expected files: {files_in_sub}", "OK")

    # TEST 4: Upload Cancellation Cleanup Logic
    cancel_file = "large_temp_test.bin"
    temp_disk_file = Path("data") / "uploads" / folder_space / f"{cancel_file}.tmp"
    temp_disk_file.parent.mkdir(parents=True, exist_ok=True)
    temp_disk_file.write_bytes(b"0" * 1024 * 1024) # 1MB dummy .tmp file
    assert temp_disk_file.exists()

    log(f"[TEST 4] Testing upload cancellation cleanup logic for '{cancel_file}'...")
    from app.routers.files import cleanup_temp_file_for_filename
    deleted_tmp = cleanup_temp_file_for_filename(cancel_file, folder_space)
    assert not temp_disk_file.exists(), f"Temporary file {temp_disk_file} was NOT deleted after cancellation!"
    log(f"Upload cancellation purged temporary file {temp_disk_file} (deleted count: {deleted_tmp})", "OK")

    # TEST 5: Rename & Move across subfolders
    renamed_sub = "sub_stress_renamed.txt"
    log(f"[TEST 5] Renaming '{file_sub}' -> '{renamed_sub}' in '{folder_space}'...")
    status, text = post_form(f"{BASE_URL}/api/files/rename", {"filename": file_sub, "new_name": renamed_sub})
    assert status == 200, f"Rename failed: {text}"
    
    renamed_disk_path = Path("data") / "uploads" / folder_space / renamed_sub
    assert renamed_disk_path.exists(), f"Renamed file missing on disk: {renamed_disk_path}"
    log(f"File rename confirmed on disk: {renamed_disk_path}", "OK")

    # TEST 6: File Deletion & 200 Response
    log(f"[TEST 6] Deleting file '{renamed_sub}' from '{folder_space}'...")
    status, text = post_form(f"{BASE_URL}/delete/{urllib.parse.quote(renamed_sub)}", {})
    assert status == 200, f"Delete failed: status={status}, text={text}"
    assert not renamed_disk_path.exists(), f"Deleted file still exists at {renamed_disk_path}"
    log("File deletion & JSON 200 response verified", "OK")

    # Clean up root file & test folders
    post_form(f"{BASE_URL}/delete/{urllib.parse.quote(file_root)}", {})
    post_form(f"{BASE_URL}/delete-folder/{urllib.parse.quote(folder_space)}", {})

    log("\n==========================================", "SUCCESS")
    log(" ENHANCED STRESS SUITE PASSED 100%!        ", "SUCCESS")
    log("==========================================\n", "SUCCESS")

if __name__ == "__main__":
    run_stress_test_suite()
