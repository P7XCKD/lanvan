import os
import test_android

adb = test_android.find_adb()
print(f"[ADB] Found ADB at: {adb}")

apk_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../android/app/build/outputs/apk/debug/app-debug.apk"))
print(f"[APK] Installing {apk_path}...")

ok, out, err = test_android.run_cmd(f'"{adb}" install -r "{apk_path}"')
print(f"[INSTALL OUTPUT]\n{out}\n{err}")

print("[LAUNCH] Starting Lanvan app on physical phone...")
ok, out, err = test_android.run_cmd(f'"{adb}" shell am start -n com.lanvan.app/.MainActivity')
print(f"[LAUNCH OUTPUT]\n{out}\n{err}")

print("[SUCCESS] Lanvan APK successfully installed and launched on your physical phone!")
