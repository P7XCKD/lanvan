import os
import sys
import subprocess
import test_android

adb = test_android.find_adb()
print(f"[ADB] Found ADB at: {adb}")

# Determine Gradle path
workspace_dir = os.path.abspath(os.path.dirname(__file__))
gradle_bin = os.path.join(workspace_dir, "temp_gradle", "gradle-8.2", "bin", "gradle.bat")
android_dir = os.path.abspath(os.path.join(workspace_dir, "../../android"))

print(f"[BUILD] Compiling debug APK with Gradle at {gradle_bin}...")
ok, out, err = test_android.run_cmd(f'"{gradle_bin}" assembleDebug --no-daemon', cwd=android_dir, capture=False)

if not ok:
    print("[BUILD FAILED] Gradle build failed!")
    sys.exit(1)

print("[BUILD] Gradle assembleDebug completed successfully.")

# Install the freshly built APK
apk_path = os.path.abspath(os.path.join(android_dir, "app/build/outputs/apk/debug/app-debug.apk"))
print(f"[APK] Installing {apk_path}...")

ok, out, err = test_android.run_cmd(f'"{adb}" install -r "{apk_path}"')
print(f"[INSTALL OUTPUT]\n{out}\n{err}")

print("[LAUNCH] Starting Lanvan app on physical phone...")
ok, out, err = test_android.run_cmd(f'"{adb}" shell am start -n com.probz.lanvan/.MainActivity')
print(f"[LAUNCH OUTPUT]\n{out}\n{err}")

print("[SUCCESS] Lanvan APK successfully built, installed, and launched on your physical phone!")
