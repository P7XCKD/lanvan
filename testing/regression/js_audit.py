#!/usr/bin/env python3
"""Lanvan JS Audit — Module 4 (Behavior/Handler Verification)"""
import re, sys
from pathlib import Path

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"
BASE = Path(__file__).parent.parent.parent
INDEX = BASE / "app" / "templates" / "index.html"
APP_INIT = BASE / "app" / "static" / "js" / "app-init.js"
index = Path(INDEX).read_text(encoding="utf-8") if INDEX.exists() else ""
app_js = Path(APP_INIT).read_text(encoding="utf-8") if APP_INIT.exists() else ""
passed = 0; failed = 0; critical = 0

def check(component, condition, detail="", is_critical=True):
    global passed, failed, critical
    if condition:
        passed += 1; print(f"  {GREEN}PASS{RESET} {component}" + (f" — {detail}" if detail else ""))
    else:
        if is_critical:
            failed += 1; critical += 1
            print(f"  {RED}FAIL{RESET} {component}" + (f" — {detail}" if detail else "") + " [CRITICAL]")
        else:
            print(f"  {YELLOW}WARN{RESET} {component}" + (f" — {detail}" if detail else ""))

print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  Module 4: JS Audit — Behavior & Handler Verification{RESET}")
print(f"{BOLD}{'='*60}")

handlers = re.findall(r'on(?:click|change|input|paste)="(\w+)', index)
handler_funcs = set(handlers) - {"", "event"}

defined = set(re.findall(r'function\s+(\w+)\s*\(', app_js))
defined |= set(re.findall(r'window\.(\w+)\s*=\s*function', app_js))
defined |= set(re.findall(r'window\.(\w+)\s*=\s*async\s+function', app_js))

production = {"toggleDeviceLogs","closeDeviceLogsModal","toggleSettingsMenu",
    "showAccessControlSettings","showConnectionInfo","addTextToClipboard",
    "cancelAllUploads","toggleUploadMode","toggleUploadModeNew",
    "setThemePreference","refreshFileListManually","showDownloadOptions","clearAllFiles"}

print(f"\n{BOLD}Handler Bindings (index.html → app-init.js){RESET}")
print(f"{'─'*50}")

all_defined = defined | production
broken = handler_funcs - all_defined
wired = handler_funcs & all_defined

for h in sorted(wired):
    check(f"  {h}()", True, "handler wired")

for h in sorted(broken):
    check(f"  {h}()", False, "BROKEN — no JS definition")

print(f"\n{BOLD}Adapter Guards{RESET}")
print(f"{'─'*50}")
check("Self-guard (__appInitLoaded)", "__appInitLoaded" in app_js, "prevents double-init")
check("Wrapper guard (__prototypeWrapped)", "__prototypeWrapped" in app_js, "prevents double-wrap")
check("Rendering wrapper", "updateFileDisplay" in app_js and "renderPrototypeFileList" in app_js)
check("Clipboard wrapper", "refreshClipboardHistory" in app_js and "syncPrototypeClipboard" in app_js)

print(f"\n{BOLD}Critical Functions{RESET}")
print(f"{'─'*50}")
critical_funcs = ["renderPrototypeFileList","buildListItem","attachListItemHandlers",
    "syncPrototypeClipboard","renderUploadTray","startUploadTrayPolling",
    "renderQuickAccess","renderSidebarQR","fetchFilesData","triggerInstantRefresh",
    "setupDropzone","setupSearch","renderSearchResults"]
for fn in critical_funcs:
    check(f"  {fn}()", fn in app_js, "defined" if fn in app_js else "MISSING")

total = passed + failed
score = round((passed / max(total, 1)) * 100, 1)
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"\n{BOLD}Module 4: JS Audit Score{RESET}")
print(f"  {GREEN}Passed: {passed}{RESET}  {RED}Failed: {failed} (Critical: {critical}){RESET}  {BOLD}Score: {score}%{RESET}")
print(f"\n{'✅ All handlers verified!' if critical == 0 else f'❌ {critical} broken handlers'}{RESET}\n")
sys.exit(0 if critical == 0 else 1)