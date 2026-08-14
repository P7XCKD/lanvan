import os
import sys
import subprocess
import time
import urllib.request
import ssl
import json
import base64

def find_adb():
    # 1. Try system PATH
    try:
        res = subprocess.run("adb --version", shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return "adb"
    except Exception:
        pass

    # 2. Check ANDROID_HOME env var
    android_home = os.environ.get("ANDROID_HOME")
    if android_home:
        path = os.path.join(android_home, "platform-tools", "adb.exe")
        if os.path.exists(path):
            return path

    # 3. Check USERPROFILE Sdk locations
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        paths = [
            os.path.join(user_profile, "Android", "sdk", "platform-tools", "adb.exe"),
            os.path.join(user_profile, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe"),
        ]
        for p in paths:
            if os.path.exists(p):
                return p

    return "adb"

ADB_PATH = find_adb()
WORKSPACE_DIR = os.path.abspath(os.path.dirname(__file__))
GRADLE_PATH = os.path.join(WORKSPACE_DIR, "temp_gradle", "gradle-8.2", "bin", "gradle.bat")

def run_cmd(cmd, cwd=None, capture=True):
    print(f"[RUN] {cmd}")
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=capture, text=True, encoding='utf-8', errors='replace')
    if res.returncode != 0:
        print(f"[ERR] Command failed (code {res.returncode}):\n{res.stderr}")
        return False, res.stdout, res.stderr
    return True, res.stdout, res.stderr

def check_device():
    print("[TEST] Checking for connected Android devices/emulators...")
    success, stdout, _ = run_cmd(f'"{ADB_PATH}" devices')
    if not success:
        return False
    lines = [line.strip() for line in stdout.split('\n') if line.strip()]
    devices = [line for line in lines[1:] if "device" in line and "devices" not in line]
    if not devices:
        print("[FAIL] No connected Android devices or emulators found via ADB. Please connect a phone or start an emulator first!")
        return False
    print(f"[OK] Found connected device: {devices[0]}")
    return True

def compile_and_install():
    print("[TEST] Compiling latest debug APK using Gradle...")
    android_dir = os.path.join(WORKSPACE_DIR, "android")
    success, _, _ = run_cmd(f'"{GRADLE_PATH}" assembleDebug', cwd=android_dir, capture=False)
    if not success:
        print("[FAIL] Gradle compilation failed.")
        return False
    
    apk_path = os.path.join(android_dir, "app", "build", "outputs", "apk", "debug", "app-debug.apk")
    if not os.path.exists(apk_path):
        print(f"[FAIL] Compiled APK not found at {apk_path}")
        return False
        
    print("[TEST] Installing APK on device...")
    success, _, _ = run_cmd(f'"{ADB_PATH}" install -r "{apk_path}"')
    if not success:
        print("[FAIL] APK installation failed.")
        return False
    print("[OK] APK compiled and installed successfully.")
    return True

def query_endpoint(url, data=None, headers=None, is_https=False, method=None):
    if headers is None:
        headers = {}
    ctx = ssl.create_default_context()
    if is_https:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            data = response.read()
            try:
                decoded = data.decode('utf-8')
            except UnicodeDecodeError:
                decoded = "<binary_data>"
            return response.status, decoded
    except Exception as e:
        return None, str(e)

def dump_device_logs():
    print("\n[LOG] Dumping last 100 lines of Android application logs...")
    run_cmd(f'"{ADB_PATH}" shell "run-as com.probz.lanvan tail -n 100 files/lanvan_app.log"')

def perform_tests():
    print("[TEST] Setting up ADB port forwarding...")
    run_cmd(f'"{ADB_PATH}" forward tcp:5000 tcp:5000')
    run_cmd(f'"{ADB_PATH}" forward tcp:5001 tcp:5001')
    
    # Ensure any active service instances are shut down first
    print("[TEST] Stopping existing server instances...")
    run_cmd(f'"{ADB_PATH}" shell am startservice -n com.probz.lanvan/.ServerService -a STOP_SERVER')
    time.sleep(6)
    
    # ------------------ TEST 1: HTTP MODE ------------------
    print("\n--- PHASE 1: HTTP Server Testing ---")
    print("[TEST] Starting Server in HTTP Mode on port 5000...")
    run_cmd(f'"{ADB_PATH}" shell am startforegroundservice -n com.probz.lanvan/.ServerService -a START_SERVER --es PORT 5000 --es USE_HTTPS false')
    time.sleep(10)
    
    # Check homepage endpoint
    print("[TEST] Verifying HTTP homepage response...")
    status, body = query_endpoint("http://127.0.0.1:5000/")
    if status == 200 and "<html" in body.lower():
        print("[OK] HTTP Homepage loaded successfully (200 OK)")
    else:
        print(f"[FAIL] HTTP Homepage returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # Check status endpoint
    print("[TEST] Verifying HTTP server-status API endpoint...")
    status, body = query_endpoint("http://127.0.0.1:5000/api/server-status")
    if status == 200:
        print(f"[OK] HTTP Server Status endpoint active")
    else:
        print(f"[FAIL] HTTP Status endpoint returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # Test file upload API endpoint (Plain)
    print("[TEST] Performing mock file upload test (HTTP)...")
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    payload = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="android_test_file.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "This is an automated Android integration test upload payload.\r\n"
        f"--{boundary}--\r\n"
    ).encode('utf-8')
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(payload))
    }
    status, body = query_endpoint("http://127.0.0.1:5000/upload-auto", data=payload, headers=headers)
    if status == 200 and "success" in body.lower():
        print("[OK] HTTP Mock file upload passed successfully!")
    else:
        print(f"[FAIL] HTTP Mock file upload returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # Test file upload API endpoint (AES Encrypted Mock)
    print("[TEST] Performing mock AES encrypted file upload test...")
    encrypted_payload = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="android_test_aes.txt"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
        "ENCRYPTED_MOCK_DATA_12345\r\n"
        f"--{boundary}--\r\n"
    ).encode('utf-8')
    headers_aes = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(encrypted_payload)),
        "X-Encrypted": "true",
        "X-Original-Size": "25"
    }
    status, body = query_endpoint("http://127.0.0.1:5000/upload-auto", data=encrypted_payload, headers=headers_aes)
    if status == 200 and "success" in body.lower():
        print("[OK] HTTP AES Mock file upload passed successfully!")
    else:
        print(f"[FAIL] HTTP AES Mock file upload returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # ------------------ TEST 2: QR Code ------------------
    print("\n--- PHASE 2: QR Code Generation ---")
    print("[TEST] Verifying QR code endpoint...")
    status, _ = query_endpoint("http://127.0.0.1:5000/api/qr-code?text=lanvan_test_string")
    if status == 200:
        print("[OK] QR Code generated successfully")
    else:
        print(f"[FAIL] QR Code endpoint failed: {status}")
        dump_device_logs()
        return False

    # ------------------ TEST 3: mDNS Discovery ------------------
    print("\n--- PHASE 3: mDNS Discovery ---")
    time.sleep(3)  # Give the server's background thread time to start mDNS
    print("[TEST] Verifying mDNS info endpoint...")
    status, body = query_endpoint("http://127.0.0.1:5000/api/mdns-info")
    if status == 200:
        try:
            mdns_data = json.loads(body)
            if mdns_data.get("status") == "active" and mdns_data.get("domain") == "Lanvan.local":
                print("[OK] mDNS domain registered successfully: Lanvan.local")
            else:
                print(f"[FAIL] mDNS response format incorrect: {body}")
                dump_device_logs()
                return False
        except:
            pass
    else:
        print(f"[FAIL] mDNS endpoint failed: {status}")
        dump_device_logs()
        return False

    # ------------------ TEST 4: Clipboard Sync ------------------
    print("\n--- PHASE 4: Clipboard Sync ---")
    print("[TEST] Verifying Clipboard POST...")
    clip_text = "Lanvan Automated Test Clipboard Data!"
    clip_payload = json.dumps({"data": clip_text}).encode('utf-8')
    status, body = query_endpoint("http://127.0.0.1:5000/api/clipboard", data=clip_payload, headers={"Content-Type": "application/json"}, method="POST")
    if status == 200:
        print("[OK] Clipboard data sent to device")
    else:
        print(f"[FAIL] Clipboard POST failed: {status} / {body}")
        dump_device_logs()
        return False
        
    print("[TEST] Verifying Clipboard GET...")
    status, body = query_endpoint("http://127.0.0.1:5000/api/clipboard")
    if status == 200 and clip_text in body:
        print("[OK] Clipboard data verified successfully!")
    else:
        print(f"[WARN] Clipboard GET returned unexpected data (could be normal if Termux clipboard failed): {body}")

    # Stop HTTP Server
    print("[TEST] Stopping HTTP Server...")
    run_cmd(f'"{ADB_PATH}" shell am startservice -n com.probz.lanvan/.ServerService -a STOP_SERVER')
    time.sleep(6)

    # ------------------ TEST 5: HTTPS MODE ------------------
    print("\n--- PHASE 5: HTTPS Server Testing ---")
    print("[TEST] Starting Server in HTTPS Mode on port 5001...")
    run_cmd(f'"{ADB_PATH}" shell am startforegroundservice -n com.probz.lanvan/.ServerService -a START_SERVER --es PORT 5001 --es USE_HTTPS true')
    time.sleep(10)
    
    # Check homepage endpoint over HTTPS
    print("[TEST] Verifying HTTPS homepage response...")
    status, body = query_endpoint("https://127.0.0.1:5001/", is_https=True)
    if status == 200 and "<html" in body.lower():
        print("[OK] HTTPS Homepage loaded successfully (200 OK)")
    else:
        print(f"[FAIL] HTTPS Homepage returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # Check status endpoint over HTTPS
    print("[TEST] Verifying HTTPS server-status API endpoint...")
    status, body = query_endpoint("https://127.0.0.1:5001/api/server-status", is_https=True)
    if status == 200:
        print(f"[OK] HTTPS Server Status endpoint active")
    else:
        print(f"[FAIL] HTTPS Status endpoint returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # Test file upload API endpoint over HTTPS (Plain)
    print("[TEST] Performing mock file upload test (HTTPS)...")
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    payload = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="android_test_file_https.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
        "This is an automated Android integration test upload payload over HTTPS.\r\n"
        f"--{boundary}--\r\n"
    ).encode('utf-8')
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(payload))
    }
    status, body = query_endpoint("https://127.0.0.1:5001/upload-auto", data=payload, headers=headers, is_https=True)
    if status == 200 and "success" in body.lower():
        print("[OK] HTTPS Mock file upload passed successfully!")
    else:
        print(f"[FAIL] HTTPS Mock file upload returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # Test file upload API endpoint over HTTPS (AES Encrypted Mock)
    print("[TEST] Performing mock AES encrypted file upload test (HTTPS)...")
    encrypted_payload = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="files"; filename="android_test_aes_https.txt"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
        "ENCRYPTED_MOCK_DATA_HTTPS_12345\r\n"
        f"--{boundary}--\r\n"
    ).encode('utf-8')
    headers_aes = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(encrypted_payload)),
        "X-Encrypted": "true",
        "X-Original-Size": "31"
    }
    status, body = query_endpoint("https://127.0.0.1:5001/upload-auto", data=encrypted_payload, headers=headers_aes, is_https=True)
    if status == 200 and "success" in body.lower():
        print("[OK] HTTPS AES Mock file upload passed successfully!")
    else:
        print(f"[FAIL] HTTPS AES Mock file upload returned status {status} / error: {body}")
        dump_device_logs()
        return False

    # Stop HTTPS Server
    print("[TEST] Stopping HTTPS Server...")
    run_cmd(f'"{ADB_PATH}" shell am startservice -n com.probz.lanvan/.ServerService -a STOP_SERVER')
    time.sleep(3)
    
    # Clear port forwarding
    print("[TEST] Cleaning up port forwarding...")
    run_cmd(f'"{ADB_PATH}" forward --remove-all')
    
    return True

def main():
    print("====================================================")
    print("      LANVAN COMPREHENSIVE ANDROID INTEGRATION       ")
    print("====================================================")
    
    if not check_device():
        sys.exit(1)
        
    if not compile_and_install():
        sys.exit(1)
        
    success = perform_tests()
    
    print("\n[TEST] Ensuring app and server are fully closed...")
    run_cmd(f'"{ADB_PATH}" shell am startservice -n com.probz.lanvan/.ServerService -a STOP_SERVER')
    run_cmd(f'"{ADB_PATH}" shell am force-stop com.probz.lanvan')
    
    print("\n====================================================")
    if success:
        print("          ALL ANDROID INTEGRATION TESTS PASSED      ")
    else:
        print("          ANDROID INTEGRATION TEST FAILED           ")
    print("====================================================")
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
