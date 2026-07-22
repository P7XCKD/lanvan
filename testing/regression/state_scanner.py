#!/usr/bin/env python3
"""
Lanvan State Scanner — Module 2 (State Audit)
Verifies UI states: Loading, Empty, Uploading, Error, Selected.
Checks correct elements show/hide for each state.
"""

import urllib.request
import urllib.error
import json
import sys
import re
import time
from pathlib import Path

BASE_URL = "http://localhost"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
failed = 0
critical = 0
score = 0

def check(component, condition, detail="", is_critical=True):
    global passed, failed, critical
    if condition:
        passed += 1
        print(f"  {GREEN}PASS{RESET} {component}" + (f" — {detail}" if detail else ""))
    else:
        if is_critical:
            failed += 1
            critical += 1
            print(f"  {RED}FAIL{RESET} {component}" + (f" — {detail}" if detail else "") + " [CRITICAL]")
        else:
            print(f"  {YELLOW}WARN{RESET} {component}" + (f" — {detail}" if detail else ""))

def fetch(url):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except:
        return ""

def api_fetch(url):
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except:
        return {}

print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"{BOLD}  Module 2: State Scanner — UI State Audit{RESET}")
print(f"{BOLD}{'═'*60}")

# ── Loading State ──
print(f"\n{BOLD}1. Loading State (initial page load){RESET}")
print(f"{'─'*50}")

html = fetch(BASE_URL)
check("Loading spinner CSS keyframes exist",
      "@keyframes spin" in fetch(BASE_URL) or 'animation:spin' in html,
      "Spinner animation defined")

check("nasFileList container exists",
      '"nasFileList"' in html,
      "File list target")

check("Drop zone exists",
      '"nasDropzone"' in html,
      "Upload target for empty state")

# ── Empty State ──
print(f"\n{BOLD}2. Empty State (no files uploaded){RESET}")
print(f"{'─'*50}")

data = api_fetch(f"{BASE_URL}/api/files")
files = data.get("files", [])
files_data = data.get("files_data", [])

check("API /api/files returns valid response",
      "status" in data,
      f"status={data.get('status', 'unknown')}")

if len(files) == 0:
    check("Empty state: Drop files here message",
          "Drop files here" in html or "Files will appear here" in html,
          "Empty state visible when no files")
    check("Empty state: Upload prompt exists",
          "Drop files here" in html or "upload" in html.lower(),
          "User can see upload ability")
else:
    check("Files listed when data exists",
          len(files) > 0,
          f"{len(files)} files found")

# ── File Data (Metadata) ──
print(f"\n{BOLD}3. File Data (Metadata){RESET}")
print(f"{'─'*50}")

check("API returns files_data with metadata",
      len(files_data) > 0 if files else True,
      f"{len(files_data)} files with metadata")

if files_data:
    sample = files_data[0]
    check("File metadata: name present",
          "name" in sample,
          f"name={sample.get('name', 'MISSING')}")
    check("File metadata: size present",
          "size" in sample,
          f"size={sample.get('size', 'MISSING')}")
    check("File metadata: mtime present",
          "mtime" in sample,
          f"mtime={sample.get('mtime', 'MISSING')}")

# ── Upload State ──
print(f"\n{BOLD}4. Upload State Check{RESET}")
print(f"{'─'*50}")

check("Upload toast stack exists",
      '"uploadToastStack"' in html,
      "Desktop upload progress tray")

check("System toast exists",
      '"toast"' in html,
      "Toast notification system")

check("Upload progress bar exists",
      '"upload-progress-fill"' in html or '"uploadProgress"' in html,
      "Progress indicator")

check("Production file input accessible",
      '"fileInput"' in html,
      "Hidden file input for uploads")

check("Production folder input accessible",
      '"folderInput"' in html,
      "Hidden folder input for uploads")

# ── Selected State ──
print(f"\n{BOLD}5. Selection State{RESET}")
print(f"{'─'*50}")

check("Toolbar default content exists",
      '"toolbarDefaultContent"' in html,
      "Default toolbar (filter + view switcher)")

check("Toolbar selection content exists",
      '"toolbarSelectionContent"' in html,
      "Selection toolbar (rename/download/move/delete)")

check("Clear selection function defined",
      'clearSelection' in html or 'clearSelection' in fetch(BASE_URL),
      "Clear selection handler")

check("Rename modal opener exists",
      'openRenameModal()' in html,
      "Rename dialog trigger")

check("Move modal opener exists",
      'openMoveModal()' in html,
      "Move dialog trigger")

check("Download action exists",
      'downloadSelected()' in html,
      "Download selected trigger")

check("Delete action exists",
      'deleteSelected()' in html,
      "Delete selected trigger")

# ── Error States ──
print(f"\n{BOLD}6. Error Handling{RESET}")
print(f"{'─'*50}")

# Test that the server responds to invalid requests with errors
invalid_data = api_fetch(f"{BASE_URL}/api/files/rename")
check("Invalid API returns error (not crash)",
      invalid_data.get("status") != "success" or "error" in str(invalid_data).lower(),
      "Server handles invalid requests gracefully")

# ── Dialog States ──
print(f"\n{BOLD}7. Dialog Availability{RESET}")
print(f"{'─'*50}")

check("Settings dialog has AES toggle",
      '"aesSettingToggle"' in html,
      "AES encryption setting")

check("Settings dialog has dark theme toggle",
      '"darkThemeSettingToggle"' in html,
      "Dark theme setting")

check("Rename dialog has input",
      '"renameInput"' in html,
      "Rename input field")

check("New folder dialog has input",
      '"newFolderNameInput"' in html,
      "Folder name input")

check("Move dialog has folder options",
      '"moveFolderOptions"' in html,
      "Move target list")

check("QR dialog has connect tabs",
      '"connectQrLanIpTab"' in html,
      "LAN IP / mDNS tabs")

# ── Dark Mode State ──
print(f"\n{BOLD}8. Dark Mode State{RESET}")
print(f"{'─'*50}")

check("data-theme attribute handler",
      'data-theme' in html or 'toggleDarkMode' in html,
      "Theme switching supported")

check("Dark mode inline script for flash prevention",
      'dark_mode_enabled' in html or 'enableDarkMode' in html,
      "Dark mode persisted in localStorage")

check("Light logo element exists",
      '"light-logo"' in html,
      "White logo for dark mode")

check("Dark logo element exists",
      '"dark-logo"' in html,
      "Black/colored logo for light mode")

# ── Score ──
total = passed + failed
score = round((passed / max(total, 1)) * 100, 1)

print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"\n{BOLD}Module 2: State Score{RESET}")
print(f"  {GREEN}Passed:   {passed}{RESET}")
print(f"  {RED}Failed:   {failed} (Critical: {critical}){RESET}")
print(f"  {BOLD}Score:    {score}%{RESET}")

if critical == 0:
    print(f"\n  {GREEN}✅ State verification complete. Proceed to Module 3 (DOM Audit).{RESET}")
else:
    print(f"\n  {RED}❌ {critical} critical issues found.{RESET}")

print(f"\n{BOLD}{'═'*60}{RESET}\n")
sys.exit(0 if critical == 0 else 1)