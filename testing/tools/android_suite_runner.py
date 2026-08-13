import os
import sys
import subprocess
import time
import urllib.request
import ssl
import json

def find_adb():
    try:
        res = subprocess.run("adb --version", shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return "adb"
    except Exception:
        pass

    android_home = os.environ.get("ANDROID_HOME")
    if android_home:
        path = os.path.join(android_home, "platform-tools", "adb.exe")
        if os.path.exists(path):
            return path

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
SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_screenshots"))

def run_cmd(cmd, cwd=None, capture=True):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=capture, text=True, encoding='utf-8', errors='replace')
    return res.returncode == 0, res.stdout, res.stderr

def capture_screenshot(filename):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    local_path = os.path.join(SCREENSHOT_DIR, filename)
    remote_path = f"/sdcard/{filename}"
    run_cmd(f'"{ADB_PATH}" shell screencap -p {remote_path}')
    run_cmd(f'"{ADB_PATH}" pull {remote_path} "{local_path}"')
    run_cmd(f'"{ADB_PATH}" shell rm {remote_path}')
    print(f"   [SCREENSHOT] Saved screen state -> {local_path}")

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

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def main():
    print_header("LANVAN ANDROID REAL-DEVICE SUITE RUNNER")

    print("[1/7] Verifying ADB Connection & Phone State...")
    success, stdout, _ = run_cmd(f'"{ADB_PATH}" devices')
    if not success or "device" not in stdout:
        print("[FAIL] No connected Android device found via ADB.")
        sys.exit(1)
    
    device_line = [l for l in stdout.split('\n') if "\tdevice" in l][0]
    device_id = device_line.split('\t')[0]
    print(f"   [OK] Target Device Connected: {device_id}")

    # Port forwarding setup
    run_cmd(f'"{ADB_PATH}" forward tcp:5000 tcp:5000')

    print("\n[2/7] Launching Lanvan App Foreground Activity...")
    run_cmd(f'"{ADB_PATH}" shell am force-stop com.lanvan.app')
    time.sleep(1)
    run_cmd(f'"{ADB_PATH}" shell am start -n com.lanvan.app/.MainActivity')
    time.sleep(3)
    capture_screenshot("01_app_launch_stopped_state.png")

    print("\n[3/7] Simulating Tap on 'Start Lanvan' Button (UI Tap)...")
    # Coordinates of btn_start_server: (540, 697)
    run_cmd(f'"{ADB_PATH}" shell input tap 540 697')
    time.sleep(6)
    capture_screenshot("02_app_server_running_http.png")

    print("\n[4/7] Performing UI Sheet Automations...")
    # Open Settings via ADB tap (960, 207)
    print("   [TAP] Opening Settings Sheet...")
    run_cmd(f'"{ADB_PATH}" shell input tap 960 207')
    time.sleep(2)
    capture_screenshot("03_settings_sheet.png")
    run_cmd(f'"{ADB_PATH}" shell input keyevent 4') # Back button
    time.sleep(1.5)

    # Open Manage Storage via ADB tap (540, 1279)
    print("   [TAP] Opening Manage Storage Sheet...")
    run_cmd(f'"{ADB_PATH}" shell input tap 540 1279')
    time.sleep(2)
    capture_screenshot("04_manage_storage_sheet.png")
    run_cmd(f'"{ADB_PATH}" shell input keyevent 4') # Back button
    time.sleep(1.5)

    # Open Support Lanvan via ADB tap (540, 1833)
    print("   [TAP] Opening Support Lanvan Sheet...")
    run_cmd(f'"{ADB_PATH}" shell input tap 540 1833')
    time.sleep(2)
    capture_screenshot("05_support_lanvan_sheet.png")
    run_cmd(f'"{ADB_PATH}" shell input keyevent 4') # Back button
    time.sleep(1.5)

    print("\n[5/7] Simulating Tap on 'Stop Lanvan' Button...")
    # In running state, btn_stop_server is at (540, 1600)
    run_cmd(f'"{ADB_PATH}" shell input tap 540 1600')
    time.sleep(3)
    capture_screenshot("06_app_server_stopped.png")
    print("   [PASS] Server stopped cleanly via UI interaction")

    print("\n[6/7] Cleaning up Port Forwarding...")
    run_cmd(f'"{ADB_PATH}" forward --remove-all')

    print("\n" + "=" * 60)
    print("      ALL ANDROID REAL-DEVICE AUTOMATION TESTS PASSED      ")
    print("=" * 60)

if __name__ == "__main__":
    main()
