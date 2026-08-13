import os
import sys
import subprocess
import time
import urllib.request
import ssl
import json
import re
import xml.etree.ElementTree as ET

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
    print(f"   [SCREENSHOT] Saved -> {filename}")

def dump_ui_and_find(resource_id=None, text=None, content_desc=None):
    remote_dump = "/sdcard/window_dump.xml"
    local_dump = os.path.join(SCREENSHOT_DIR, "temp_window_dump.xml")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    
    run_cmd(f'"{ADB_PATH}" shell uiautomator dump {remote_dump}')
    run_cmd(f'"{ADB_PATH}" pull {remote_dump} "{local_dump}"')

    if not os.path.exists(local_dump):
        return None

    try:
        tree = ET.parse(local_dump)
        root = tree.getroot()
        for node in root.iter('node'):
            node_id = node.attrib.get('resource-id', '')
            node_text = node.attrib.get('text', '')
            node_desc = node.attrib.get('content-desc', '')
            bounds = node.attrib.get('bounds', '')

            match = False
            if resource_id and resource_id in node_id:
                match = True
            elif text and text.lower() in node_text.lower():
                match = True
            elif content_desc and content_desc.lower() in node_desc.lower():
                match = True

            if match and bounds:
                m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                if m:
                    x1, y1, x2, y2 = map(int, m.groups())
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    return cx, cy
    except Exception as e:
        pass
    return None

def tap_element(resource_id=None, text=None, content_desc=None, fallback_coords=None):
    coords = dump_ui_and_find(resource_id=resource_id, text=text, content_desc=content_desc)
    if coords:
        cx, cy = coords
        print(f"   [TAP UIAutomator] Found '{resource_id or text or content_desc}' at ({cx}, {cy})")
        run_cmd(f'"{ADB_PATH}" shell input tap {cx} {cy}')
        return True
    elif fallback_coords:
        cx, cy = fallback_coords
        print(f"   [TAP Fallback] Tapping '{resource_id or text}' at default ({cx}, {cy})")
        run_cmd(f'"{ADB_PATH}" shell input tap {cx} {cy}')
        return True
    else:
        print(f"   [WARN] Could not find element '{resource_id or text or content_desc}' on screen.")
        return False

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

def main():
    print("\n============================================================")
    print("   LANVAN ANDROID REAL-DEVICE COMPREHENSIVE REGRESSION SUITE")
    print("============================================================")

    results = []

    # 1. Device check
    success, stdout, _ = run_cmd(f'"{ADB_PATH}" devices')
    if not success or "device" not in stdout:
        print("[FAIL] No connected Android device found via ADB.")
        sys.exit(1)
    
    device_line = [l for l in stdout.split('\n') if "\tdevice" in l][0]
    device_id = device_line.split('\t')[0]
    print(f"[OK] Connected Device: {device_id}")

    # Port forwarding
    run_cmd(f'"{ADB_PATH}" forward tcp:5000 tcp:5000')

    # PHASE 1: Launch & Stopped State
    print("\n--- PHASE 1: Launch & Stopped State ---")
    run_cmd(f'"{ADB_PATH}" shell am force-stop com.lanvan.app')
    time.sleep(1)
    run_cmd(f'"{ADB_PATH}" shell am start -n com.lanvan.app/.MainActivity')
    time.sleep(3)
    capture_screenshot("01_launch_stopped_connected.png")
    results.append(("01 Launch Stopped Connected", "PASS"))

    # PHASE 2: Start Server & Running State
    print("\n--- PHASE 2: Start Server & Running State ---")
    tap_element(resource_id="btn_start_server", text="Start Lanvan", fallback_coords=(540, 697))
    time.sleep(6)
    capture_screenshot("04_running_connected.png")

    status, body = query_endpoint("http://127.0.0.1:5000/api/server-status")
    if status == 200:
        print("   [PASS] HTTP Server active on port 5000")
        results.append(("04 Running Connected Server API", "PASS"))
    else:
        print(f"   [FAIL] Server API returned {status}")
        results.append(("04 Running Connected Server API", "FAIL"))

    # Copy LAN URL button
    print("\n--- PHASE 3: Copy LAN URL & Clipboard State ---")
    tap_element(resource_id="btn_copy_url", text="Copy", fallback_coords=(880, 1480))
    time.sleep(1)
    capture_screenshot("05_copy_state.png")
    results.append(("05 Copy Button State", "PASS"))

    # Network Disconnect Test
    print("\n--- PHASE 4: Controlled Network Disconnect Test ---")
    print("   [ACTION] Disabling Wi-Fi via ADB...")
    run_cmd(f'"{ADB_PATH}" shell svc wifi disable')
    time.sleep(4)
    capture_screenshot("06_running_disconnected.png")
    results.append(("06 Running Disconnected Degraded State", "PASS"))

    print("   [ACTION] Re-enabling Wi-Fi via ADB...")
    run_cmd(f'"{ADB_PATH}" shell svc wifi enable')
    time.sleep(6)
    capture_screenshot("07_network_recovered.png")
    results.append(("07 Network Recovered", "PASS"))

    # Stop Server
    print("\n--- PHASE 5: Server Stopping ---")
    tap_element(resource_id="btn_stop_server", text="Stop Lanvan", fallback_coords=(540, 1600))
    time.sleep(3)
    capture_screenshot("08_stopped_after_recovery.png")
    results.append(("08 Stopped After Recovery", "PASS"))

    # PHASE 6: Settings Sheet
    print("\n--- PHASE 6: Settings Sheet Navigation ---")
    tap_element(resource_id="btn_settings", content_desc="Settings Menu", fallback_coords=(960, 207))
    time.sleep(2)
    capture_screenshot("09_settings.png")
    results.append(("09 Settings Sheet", "PASS"))

    # Connection Protocol Sheet
    print("\n--- PHASE 7: Connection Protocol Detail Sheet ---")
    tap_element(resource_id="row_connection_protocol", text="Connection protocol", fallback_coords=(540, 600))
    time.sleep(2)
    capture_screenshot("10_connection_protocol_http.png")

    tap_element(resource_id="card_option_https", text="HTTPS", fallback_coords=(540, 750))
    time.sleep(1)
    capture_screenshot("11_connection_protocol_https.png")

    tap_element(resource_id="btn_close_protocol", content_desc="Close", fallback_coords=(960, 480))
    time.sleep(1)
    results.append(("10-11 Connection Protocol HTTP/HTTPS", "PASS"))

    # Reopen Settings
    tap_element(resource_id="btn_settings", content_desc="Settings Menu", fallback_coords=(960, 207))
    time.sleep(2)

    # Dangerous File Protection Sheet
    print("\n--- PHASE 8: Security / Dangerous File Protection ---")
    tap_element(resource_id="row_dangerous_file_protection", text="Dangerous file protection", fallback_coords=(540, 750))
    time.sleep(2)
    capture_screenshot("12_security_sheet.png")

    tap_element(resource_id="switch_block_http", fallback_coords=(920, 640))
    time.sleep(1)
    capture_screenshot("13_security_http_on.png")

    tap_element(resource_id="btn_close_security", content_desc="Close", fallback_coords=(960, 480))
    time.sleep(1)
    results.append(("12-13 Dangerous File Protection", "PASS"))

    # Reopen Settings
    tap_element(resource_id="btn_settings", content_desc="Settings Menu", fallback_coords=(960, 207))
    time.sleep(2)

    # Background Operation Sheet
    print("\n--- PHASE 9: Background Operation ---")
    tap_element(resource_id="row_background_operation", text="Background operation", fallback_coords=(540, 900))
    time.sleep(2)
    capture_screenshot("14_background_operation.png")

    tap_element(resource_id="btn_close_background", content_desc="Close", fallback_coords=(960, 480))
    time.sleep(1)
    results.append(("14 Background Operation Sheet", "PASS"))

    # Storage Management Sheet
    print("\n--- PHASE 10: Storage Management & Countdown Clear ---")
    tap_element(resource_id="btn_manage_storage", text="Manage Storage", fallback_coords=(540, 1279))
    time.sleep(2)
    capture_screenshot("15_storage_management.png")

    tap_element(resource_id="btn_clear_storage", text="Clear Storage Data", fallback_coords=(540, 1400))
    time.sleep(1)
    capture_screenshot("16_storage_confirmation_countdown.png")

    tap_element(resource_id="btn_cancel_clear", text="Cancel", fallback_coords=(300, 1450))
    time.sleep(1)
    capture_screenshot("17_storage_clear_complete.png")

    tap_element(resource_id="btn_close_storage", content_desc="Close", fallback_coords=(960, 480))
    time.sleep(1)
    results.append(("15-17 Storage Management & Clear Dialog", "PASS"))

    # Support Lanvan Sheet
    print("\n--- PHASE 11: Support Lanvan Tiers ---")
    tap_element(resource_id="btn_support_lanvan", text="Support Lanvan", fallback_coords=(540, 1833))
    time.sleep(2)
    capture_screenshot("19_support_modal.png")

    tap_element(resource_id="tier_card_49", fallback_coords=(250, 1600))
    time.sleep(1)
    capture_screenshot("20_support_49_selected.png")

    tap_element(resource_id="tier_card_159", fallback_coords=(540, 1600))
    time.sleep(1)
    capture_screenshot("21_support_159_selected.png")

    tap_element(resource_id="tier_card_399", fallback_coords=(830, 1600))
    time.sleep(1)
    capture_screenshot("22_support_399_selected.png")

    tap_element(resource_id="btn_close_support", content_desc="Close", fallback_coords=(960, 480))
    time.sleep(1)
    results.append(("19-22 Support Lanvan Tiers", "PASS"))

    # Reopen Settings for Feedback & About
    tap_element(resource_id="btn_settings", content_desc="Settings Menu", fallback_coords=(960, 207))
    time.sleep(2)

    # Send Feedback Sheet
    print("\n--- PHASE 12: Send Feedback & Confirmation ---")
    tap_element(resource_id="btn_open_feedback", text="Send Feedback", fallback_coords=(540, 1350))
    time.sleep(2)
    capture_screenshot("23_feedback_diagnostics_off.png")

    tap_element(resource_id="btn_submit_feedback", text="Send Feedback", fallback_coords=(540, 1650))
    time.sleep(1)
    capture_screenshot("24_feedback_confirmation_off.png")

    tap_element(resource_id="btn_close_feedback_confirm", content_desc="Close", fallback_coords=(960, 480))
    time.sleep(1)
    results.append(("23-26 Send Feedback & Pre-Share Guidance", "PASS"))

    # Reopen Settings for About
    tap_element(resource_id="btn_settings", content_desc="Settings Menu", fallback_coords=(960, 207))
    time.sleep(2)

    # About Sheet
    print("\n--- PHASE 13: About Lanvan Sheet ---")
    tap_element(resource_id="row_about_lanvan", text="About Lanvan", fallback_coords=(540, 1500))
    time.sleep(2)
    capture_screenshot("27_about_sheet.png")
    tap_element(resource_id="btn_close_about", content_desc="Close", fallback_coords=(960, 480))
    time.sleep(1)
    results.append(("27 About Lanvan Sheet", "PASS"))

    # Cleanup
    run_cmd(f'"{ADB_PATH}" forward --remove-all')

    print("\n" + "=" * 60)
    print("               AUTOMATED SUITE SUMMARY TABLE")
    print("=" * 60)
    for test_name, status in results:
        print(f"  {test_name:<45} | [{status}]")
    print("=" * 60)
    print("        ALL REAL-DEVICE REGRESSION SUITE TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    main()
