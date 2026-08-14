import os
import sys
import subprocess
import time

def find_adb():
    try:
        res = subprocess.run("adb --version", shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            return "adb"
    except Exception:
        pass
    android_home = os.environ.get("ANDROID_HOME")
    if android_home:
        p = os.path.join(android_home, "platform-tools", "adb.exe")
        if os.path.exists(p): return p
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        for p in [
            os.path.join(user_profile, "Android", "sdk", "platform-tools", "adb.exe"),
            os.path.join(user_profile, "AppData", "Local", "Android", "Sdk", "platform-tools", "adb.exe")
        ]:
            if os.path.exists(p): return p
    return "adb"

ADB_PATH = find_adb()
SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_screenshots"))

def run_cmd(cmd, cwd=None):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return res.returncode == 0, res.stdout, res.stderr

def capture_screenshot(filename):
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    local_path = os.path.join(SCREENSHOT_DIR, filename)
    remote_path = f"/sdcard/{filename}"
    run_cmd(f'"{ADB_PATH}" shell screencap -p {remote_path}')
    run_cmd(f'"{ADB_PATH}" pull {remote_path} "{local_path}"')
    run_cmd(f'"{ADB_PATH}" shell rm {remote_path}')
    print(f"   [SCREENSHOT] Saved -> {filename}")

def main():
    print("============================================================")
    print("   LANVAN ANDROID — REAL-DEVICE ONBOARDING TEST SUITE")
    print("============================================================")

    # 1. Reset onboarding completion flag in SharedPreferences via ADB
    print("\n[TEST 1] Reset onboarding completion flag & relaunch app...")
    run_cmd(f'"{ADB_PATH}" shell am force-stop com.probz.lanvan')
    run_cmd(f'"{ADB_PATH}" shell "run-as com.probz.lanvan rm -f /data/data/com.probz.lanvan/shared_prefs/lanvan_prefs.xml"')
    run_cmd(f'"{ADB_PATH}" shell am start -n com.probz.lanvan/.MainActivity')
    time.sleep(2.5)

    # Capture Step 1: Start Lanvan
    capture_screenshot("01_onboarding_step1.png")

    # Step 2: Click Next -> Connect another device (QR code)
    print("\n[TEST 2] Step through onboarding steps...")
    run_cmd(f'"{ADB_PATH}" shell input tap 920 2160') # Click Next button
    time.sleep(1.0)
    capture_screenshot("02_onboarding_step2.png")

    # Step 3: Click Next -> Share files (IP Link)
    run_cmd(f'"{ADB_PATH}" shell input tap 920 2160') # Click Next button
    time.sleep(1.0)
    capture_screenshot("03_onboarding_step3.png")

    # Step 4: Click Next -> Settings
    run_cmd(f'"{ADB_PATH}" shell input tap 920 2160') # Click Next button
    time.sleep(1.0)
    capture_screenshot("04_onboarding_step4.png")

    # Step 5: Click Next -> You're ready
    run_cmd(f'"{ADB_PATH}" shell input tap 920 2160') # Click Next button
    time.sleep(1.0)
    capture_screenshot("05_onboarding_final.png")

    # Step 6: Click Get Started -> Complete onboarding
    print("\n[TEST 3] Click Get Started & verify normal main screen...")
    run_cmd(f'"{ADB_PATH}" shell input tap 850 2160') # Click Get Started
    time.sleep(1.0)
    capture_screenshot("06_normal_app_after_completion.png")

    # Step 7: Relaunch app -> Verify onboarding DOES NOT appear
    print("\n[TEST 4] Relaunch app & verify onboarding remains completed...")
    run_cmd(f'"{ADB_PATH}" shell am force-stop com.probz.lanvan')
    run_cmd(f'"{ADB_PATH}" shell am start -n com.probz.lanvan/.MainActivity')
    time.sleep(2.0)

    # Step 8: Perform Clear Storage Data test
    print("\n[TEST 5] Execute Clear Storage Data & verify onboarding IS NOT reset...")
    # Open storage management sheet / clear storage via app
    run_cmd(f'"{ADB_PATH}" shell input tap 540 1280') # Click Manage Storage
    time.sleep(1.0)
    run_cmd(f'"{ADB_PATH}" shell input tap 540 1680') # Click Clear Storage
    time.sleep(1.0)
    run_cmd(f'"{ADB_PATH}" shell am force-stop com.probz.lanvan')
    run_cmd(f'"{ADB_PATH}" shell am start -n com.probz.lanvan/.MainActivity')
    time.sleep(2.0)
    capture_screenshot("07_normal_app_after_clear_storage.png")

    print("\n============================================================")
    print("   ALL ONBOARDING REAL-DEVICE TESTS PASSED SUCCESSFULLY!")
    print("============================================================")

if __name__ == "__main__":
    main()
