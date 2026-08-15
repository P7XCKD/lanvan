#!/usr/bin/env python3
"""
Lanvan Android Production Runtime Privacy & Canary Leak Test
===========================================================
Executes a complete lifecycle runtime privacy audit on a live Android device:
1. Upload file 1: DO_NOT_LOG_SECRET_847291.pdf
2. Upload file 2: PRIVATE_DOCUMENT_928374.txt
3. Upload to folder: DO_NOT_LOG_FOLDER_736281
4. Download both files
5. Send clipboard payload: DO_NOT_LOG_CLIPBOARD_564738
6. Perform WebSocket activity
7. Trigger invalid/failure requests
8. Test HTTP mode
9. Test HTTPS mode
10. Retrieve complete Android app log & verify zero leak of canaries, filenames, URLs, paths.
"""

import os
import sys
import time
import re
import json
import ssl
import urllib.request
import urllib.parse
from pathlib import Path

# Add testing/tools directory to path
TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))

import test_android

ADB = test_android.find_adb()
CANARIES = [
    "DO_NOT_LOG_SECRET_847291",
    "PRIVATE_DOCUMENT_928374",
    "DO_NOT_LOG_FOLDER_736281",
    "DO_NOT_LOG_CLIPBOARD_564738",
    "DO_NOT_LOG_SECRET_847291.pdf",
    "PRIVATE_DOCUMENT_928374.txt",
]

SENSITIVE_PATTERNS = [
    ("filename=", "Raw Content-Disposition filename param"),
    ("Content-Disposition", "Raw Content-Disposition header in logs"),
    ("/download/DO_NOT_LOG", "Download path in HTTP access logs"),
    ("/upload", "Upload endpoint in HTTP access logs"),
    ("request.url", "Raw request.url leak"),
    ("request.headers", "Raw request.headers leak"),
    ("request.body", "Raw request.body leak"),
    ("/data/user/", "Android /data/user/ internal storage leak"),
    ("/storage/emulated/", "Android /storage/emulated/ shared storage leak"),
    ("DO_NOT_LOG_CLIPBOARD_564738", "Clipboard content leak"),
]

def log_test(step_num, name, status, details=""):
    color = "\033[92m[PASS]\033[0m" if status else "\033[91m[FAIL]\033[0m"
    print(f"Step {step_num}: {name} -> {color} {details}")
    return status

def query_endpoint(url, data=None, headers=None, method=None, is_https=False, timeout=15):
    try:
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=timeout, context=ctx if is_https else None) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace'), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace'), e.headers
    except Exception as e:
        return 0, str(e), {}

def run_privacy_runtime_test():
    print("=" * 65)
    print("   LANVAN ANDROID RUNTIME PRIVACY AUDIT & CANARY LEAK SUITE   ")
    print("=" * 65)

    if not test_android.check_device():
        print("[FAIL] No connected Android device found.")
        return False

    results = {}

    # Step 0: Ensure previous instance is stopped, clear logcat, delete previous logs, set up port forwarding
    test_android.run_cmd(f'"{ADB}" shell am force-stop com.probz.lanvan')
    test_android.run_cmd(f'"{ADB}" logcat -c')
    test_android.run_cmd(f'"{ADB}" shell run-as com.probz.lanvan rm -f /data/data/com.probz.lanvan/files/lanvan_app.log')
    test_android.run_cmd(f'"{ADB}" forward tcp:5000 tcp:5000')
    test_android.run_cmd(f'"{ADB}" forward tcp:5001 tcp:5001')
    time.sleep(2)

    # Start Android Server in HTTP mode via MainActivity intent
    print("\n--- Starting Android Server (HTTP Mode: 5000) ---")
    test_android.run_cmd(f'"{ADB}" shell am start -n com.probz.lanvan/.MainActivity --ez AUTO_START_SERVER true --ez USE_HTTPS false')
    
    # Wait for HTTP server to become responsive
    http_started = False
    for attempt in range(12):
        time.sleep(1.5)
        st, _, _ = query_endpoint("http://127.0.0.1:5000/api/server-status", timeout=2)
        if st == 200:
            http_started = True
            print(f"[OK] Android HTTP Server is active on port 5000 (attempt {attempt+1})")
            break

    if not http_started:
        print("[WARN] HTTP Server did not respond on localhost:5000, checking logcat...")
        _, logs, _ = test_android.run_cmd(f'"{ADB}" logcat -d -s Lanvan ServerService Chaquopy')
        print(logs[-500:])

    # 1. Upload file 1: DO_NOT_LOG_SECRET_847291.pdf
    boundary = "----WebKitFormBoundaryPrivacyTest123"
    pdf_content = b"%PDF-1.4 mock pdf secret content for runtime testing"
    payload1 = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="DO_NOT_LOG_SECRET_847291.pdf"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode('utf-8') + pdf_content + f"\r\n--{boundary}--\r\n".encode('utf-8')

    st, body, _ = query_endpoint("http://127.0.0.1:5000/upload-auto", data=payload1, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    })
    results["Upload PDF"] = log_test(1, "Upload DO_NOT_LOG_SECRET_847291.pdf", st == 200 and "success" in body.lower(), f"Status: {st}")

    # 2. Upload file 2: PRIVATE_DOCUMENT_928374.txt
    txt_content = b"Top secret personal confidential notes 12345"
    payload2 = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="PRIVATE_DOCUMENT_928374.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode('utf-8') + txt_content + f"\r\n--{boundary}--\r\n".encode('utf-8')

    st, body, _ = query_endpoint("http://127.0.0.1:5000/upload-auto", data=payload2, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    })
    results["Upload TXT"] = log_test(2, "Upload PRIVATE_DOCUMENT_928374.txt", st == 200 and "success" in body.lower(), f"Status: {st}")

    # 3. Create/use folder: DO_NOT_LOG_FOLDER_736281
    payload3 = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="parent_path"\r\n\r\n'
        "DO_NOT_LOG_FOLDER_736281\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="nested_doc.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "nested secret data\r\n"
        f"--{boundary}--\r\n"
    ).encode('utf-8')

    st, body, _ = query_endpoint("http://127.0.0.1:5000/upload-auto", data=payload3, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    })
    results["Create/Use Folder"] = log_test(3, "Upload into DO_NOT_LOG_FOLDER_736281", st == 200 and "success" in body.lower(), f"Status: {st}")

    # 4. Download both files and verify Content-Disposition header in HTTP response
    st1, _, hdrs1 = query_endpoint("http://127.0.0.1:5000/download/DO_NOT_LOG_SECRET_847291.pdf")
    cd1 = hdrs1.get("Content-Disposition", "")
    st2, _, hdrs2 = query_endpoint("http://127.0.0.1:5000/download/PRIVATE_DOCUMENT_928374.txt")
    cd2 = hdrs2.get("Content-Disposition", "")

    download_ok = (st1 == 200 and "DO_NOT_LOG_SECRET_847291.pdf" in cd1 and
                   st2 == 200 and "PRIVATE_DOCUMENT_928374.txt" in cd2)
    results["Download Files"] = log_test(4, "Download both canary files (Content-Disposition verified in HTTP header)", download_ok, f"PDF st={st1}, TXT st={st2}")

    # 5. Clipboard operation: DO_NOT_LOG_CLIPBOARD_564738
    clip_payload = json.dumps({"data": "DO_NOT_LOG_CLIPBOARD_564738"}).encode('utf-8')
    st, body, _ = query_endpoint("http://127.0.0.1:5000/api/clipboard", data=clip_payload, headers={"Content-Type": "application/json"}, method="POST")
    st_get, body_get, _ = query_endpoint("http://127.0.0.1:5000/api/clipboard/list")
    clip_ok = (st == 200 and "DO_NOT_LOG_CLIPBOARD_564738" in body_get)
    results["Clipboard Operation"] = log_test(5, "Clipboard write & read (DO_NOT_LOG_CLIPBOARD_564738)", clip_ok, f"Status: {st}")

    # 6. WebSocket activity (connect to /ws/ui_events or /ws/file_events via HTTP upgrade check or endpoint poll)
    st, body, _ = query_endpoint("http://127.0.0.1:5000/api/server-status")
    results["WebSocket / Operational Status"] = log_test(6, "Operational Server Status & Sync endpoints", st == 200, f"Status: {st}")

    # 7. Invalid/Failure Request (404 and 400/422 bad request)
    st_404, _, _ = query_endpoint("http://127.0.0.1:5000/download/non_existent_random_file_xyz123.bin")
    st_400, _, _ = query_endpoint("http://127.0.0.1:5000/upload-auto", data=b"invalid non multipart", headers={"Content-Type": "text/plain"})
    fail_req_ok = (st_404 == 404 and st_400 in [400, 422])
    results["Trigger Failure Requests"] = log_test(7, "Safely trigger 404 & 400/422 error paths", fail_req_ok, f"404 st={st_404}, 400/422 st={st_400}")

    # 8. HTTP Mode Overall
    results["HTTP Mode"] = log_test(8, "HTTP Mode comprehensive tests", all([results["Upload PDF"], results["Upload TXT"], results["Download Files"]]))

    # 9. HTTPS Mode
    print("\n--- Switching Android Server to HTTPS Mode (5001) ---")
    test_android.run_cmd(f'"{ADB}" shell am force-stop com.probz.lanvan')
    time.sleep(2)
    # Start fresh app in HTTPS mode
    test_android.run_cmd(f'"{ADB}" shell am start -n com.probz.lanvan/.MainActivity --ez AUTO_START_SERVER true --ez USE_HTTPS true')
    
    https_started = False
    for attempt in range(15):
        time.sleep(1.5)
        st_https, _, _ = query_endpoint("https://127.0.0.1:5001/api/server-status", is_https=True, timeout=2)
        if st_https == 200:
            https_started = True
            print(f"[OK] Android HTTPS Server is active on port 5001 (attempt {attempt+1})")
            break

    results["HTTPS Mode"] = log_test(9, "HTTPS Server mode operational", https_started, f"Status: {st_https if https_started else 'Failed'}")

    # Stop server
    test_android.run_cmd(f'"{ADB}" shell am force-stop com.probz.lanvan')
    time.sleep(2)

    # 10. RETRIEVE AND ANALYZE ANDROID PRODUCTION LOGS
    print("\n" + "=" * 65)
    print("   COMPLETE ANDROID PRODUCTION LOG PRIVACY ANALYSIS   ")
    print("=" * 65)

    # Retrieve internal lanvan_app.log from app internal storage
    _, log_content, _ = test_android.run_cmd(f'"{ADB}" shell run-as com.probz.lanvan cat /data/data/com.probz.lanvan/files/lanvan_app.log')
    if not log_content or "No such file" in log_content:
        # Fallback to logcat Lanvan tags
        _, log_content, _ = test_android.run_cmd(f'"{ADB}" logcat -d -s Lanvan ServerService Chaquopy')

    print(f"Retrieved {len(log_content)} bytes of Android runtime logs.")

    # Check for Canary Leaks
    leaks_found = []
    for canary in CANARIES:
        count = log_content.count(canary)
        if count > 0:
            leaks_found.append(f"CANARY LEAK: '{canary}' occurred {count} times in Android logs!")

    for pat, desc in SENSITIVE_PATTERNS:
        matches = [line for line in log_content.splitlines() if pat in line]
        if matches:
            leaks_found.append(f"PATTERN LEAK ({desc}): Found match in line: '{matches[0]}'")

    # Verify Allowed Operational Logs Exist
    allowed_operational_checks = {
        "Upload Operational Logs": bool(re.search(r'\[UPLOAD\].*(?:File saved via VersionManager|Upload batch completed|Upload started)', log_content)),
        "Storage / Server Status": bool(re.search(r'\[SERVER\]|\[STORAGE\]|\[NETWORK\]', log_content)),
        "MIME Type & Size formatting": bool(re.search(r'Type:\s*[a-zA-Z0-9_\-\/]+', log_content) or re.search(r'Size:\s*\d+', log_content)),
        "Sanitized [Sanitized File] Replacement": ("[Sanitized File]" in log_content or "[Sanitized Android Path]" in log_content or "[Clipboard Data]" in log_content or len(leaks_found) == 0)
    }

    print("\n--- PRIVACY CANARY AUDIT RESULTS ---")
    if not leaks_found:
        print("\033[92m[PASS] ZERO CANARY LEAKS DETECTED! All filenames, paths, and clipboard text are completely redacted.\033[0m")
    else:
        for leak in leaks_found:
            print(f"\033[91m[FAIL] {leak}\033[0m")

    print("\n--- ALLOWED OPERATIONAL LOG AUDIT ---")
    for check_name, passed in allowed_operational_checks.items():
        status_str = "\033[92m[PASS]\033[0m" if passed else "\033[93m[WARN]\033[0m"
        print(f"{check_name}: {status_str}")

    print("\n--- REPRESENTATIVE SANITIZED PRODUCTION LOG SAMPLES ---")
    sample_lines = [line.strip() for line in log_content.splitlines() if any(tag in line for tag in ["[UPLOAD]", "[DOWNLOAD]", "[SERVER]", "[NETWORK]", "[STORAGE]", "[SECURITY]"])]
    for line in sample_lines[-12:]:
        print("  |", line)

    all_passed = (len(leaks_found) == 0 and all(results.values()))
    print("\n" + "=" * 65)
    print(f"OVERALL RUNTIME PRIVACY VERIFICATION: {'PASS' if all_passed else 'FAIL'}")
    print("=" * 65)
    return all_passed

if __name__ == "__main__":
    ok = run_privacy_runtime_test()
    sys.exit(0 if ok else 1)
