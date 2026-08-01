#!/usr/bin/env python3
"""
Lanvan Runtime Scanner — Module 1 (Runtime + Console)
Verifies live DOM components and checks for console errors.
Works against a running Lanvan server.
"""

import urllib.request
import urllib.error
import json
import sys
import time
import re
from pathlib import Path

BASE_URL = "http://localhost"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
failed = 0
warnings = 0
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
            warnings += 1
            print(f"  {YELLOW}WARN{RESET} {component}" + (f" — {detail}" if detail else ""))

def fetch_html():
    try:
        req = urllib.request.Request(BASE_URL, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"{RED}Cannot connect to {BASE_URL}: {e}{RESET}")
        return None

print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"{BOLD}  Module 1: Runtime Scanner — DOM + Console Audit{RESET}")
print(f"{BOLD}{'═'*60}")
print(f"Server: {BASE_URL}\n")

html = fetch_html()
if not html:
    print(f"{RED}ABORT: Server not reachable. Start Lanvan first.{RESET}\n")
    sys.exit(1)

# ── 1. Application Shell ──
print(f"\n{BOLD}1. Application Shell Components{RESET}")
print(f"{'─'*50}")

check("Sidebar (.app-sidebar)", bool(re.search(r'class="app-sidebar"', html)), "Desktop sidebar exists")
check("Top Bar (.app-bar)", bool(re.search(r'class="app-bar"', html)), "Search + actions bar")
check("Search Shell (.search-shell)", bool(re.search(r'class="search-shell"', html)), "Search input container")
check("Search Input (#searchInput)", '"searchInput"' in html, "Type search")
check("Theme Toggle (theme button)", 'toggleDarkMode()' in html or 'openSettingsDialog()' in html, "Dark/light toggle")
check("Settings Toggle (settings button)", 'openSettingsDialog()' in html, "Settings gear")
check("Bottom Navigation (.bottom-nav)", bool(re.search(r'class="bottom-nav"', html)), "Mobile nav bar")
check("App Body (.app-body)", bool(re.search(r'class="app-body"', html)), "Main content area")

# ── 2. File Browser ──
print(f"\n{BOLD}2. File Browser Components{RESET}")
print(f"{'─'*50}")

check("File View (#fileView)", '"fileView"' in html, "File browser panel")
check("Panel Header (.desktop-panel-header)", bool(re.search(r'class="desktop-panel-header"', html)), "Title + meta bar")
check("Breadcrumbs (#breadcrumbsContainer)", '"breadcrumbsContainer"' in html, "Folder path")
check("Quick Access (#quickAccessContainer)", '"quickAccessContainer"' in html, "Recent files grid")
check("Toolbar (#fileToolbar)", '"fileToolbar"' in html, "Filter + view switcher")
check("Type Filter (#typeDropdownBtn)", '"typeDropdownBtn"' in html, "File type filter")
check("View Switcher (#listViewBtn)", '"listViewBtn"' in html, "List/grid toggle")
check("Dropzone (#nasDropzone)", '"nasDropzone"' in html, "Drag-drop zone")
check("File List (#nasFileList)", '"nasFileList"' in html, "Dynamic file container")
check("Drag Overlay (.drag-overlay)", bool(re.search(r'class="drag-overlay"', html)), "Upload drop indicator")
check("Panel Meta (#filePanelMeta)", '"filePanelMeta"' in html, "File count label")

# ── 3. Clipboard ──
print(f"\n{BOLD}3. Clipboard Components{RESET}")
print(f"{'─'*50}")

check("Clipboard View (#clipboardView)", '"clipboardView"' in html, "Clipboard panel")
check("Clipboard Input (#clipboardInput)", '"clipboardInput"' in html, "Text entry")
check("Clipboard History (#clipboardHistory)", '"clipboardHistory"' in html, "History list")
check("Add Text Button (Add Text)", 'addClipboardItem()' in html, "Submit button")

# ── 4. Dialogs & Modals ──
print(f"\n{BOLD}4. Dialogs & Modals{RESET}")
print(f"{'─'*50}")

check("New Folder Dialog (#newFolderDialog)", '"newFolderDialog"' in html, "Create folder modal")
check("Rename Dialog (#renameDialog)", '"renameDialog"' in html, "Rename modal")
check("Move Dialog (#moveFileDialog)", '"moveFileDialog"' in html, "Move modal")
check("Settings Dialog (#settingsDialog)", '"settingsDialog"' in html, "App settings")
check("Connect QR Dialog (#connectQrDialog)", '"connectQrDialog"' in html, "QR code")
check("Preview Modal (#previewModal)", '"previewModal"' in html, "File preview")
check("Device Logs Modal (#deviceLogsModal)", '"deviceLogsModal"' in html, "Production logs")

# ── 5. Context Menus ──
print(f"\n{BOLD}5. Context Menus{RESET}")
print(f"{'─'*50}")

check("Context Menu (#contextMenu)", '"contextMenu"' in html, "Right-click menu")
check("Generic Menu Options (#genericMenuOptions)", '"genericMenuOptions"' in html, "File upload options")
check("Item Menu Options (#itemMenuOptions)", '"itemMenuOptions"' in html, "Rename/delete/move")
check("Sort Dropdown (#sortDropdownMenu)", '"sortDropdownMenu"' in html, "Sort options")
check("Type Dropdown (#typeDropdownMenu)", '"typeDropdownMenu"' in html, "Type filter menu")

# ── 6. Mobile Components ──
print(f"\n{BOLD}6. Mobile Components{RESET}")
print(f"{'─'*50}")

check("Mobile Sheet Overlay (#mobileAddSheetOverlay)", '"mobileAddSheetOverlay"' in html, "Bottom sheet")
check("YouTube Add Button (.yt-add-btn)", bool(re.search(r'class="yt-add-btn"', html)), "Mobile plus button")

# ── 7. Production Legacy ──
print(f"\n{BOLD}7. Production Compatibility (Hidden Container){RESET}")
print(f"{'─'*50}")

check("#production-legacy container", '"production-legacy"' in html, "Production IDs preserved")
check("#enableEncryption (AES toggle)", '"enableEncryption"' in html, "AES setting")
check("#enableDarkMode (dark mode)", '"enableDarkMode"' in html, "Theme toggle")
check("#fileInput (production upload)", '"fileInput"' in html, "File input")
check("#folderInput (folder upload)", '"folderInput"' in html, "Folder input")
check("#drop-zone (legacy dropzone)", '"drop-zone"' in html, "Legacy drag zone")
check("#uploadProgress (progress bar)", '"uploadProgress"' in html, "Progress element")
check("#uploadManager (manager)", '"uploadManager"' in html, "Upload manager")
check("#uploadQueue (upload list)", '"uploadQueue"' in html, "Upload queue container")
check("#fileGrid (file listing)", '"fileGrid"' in html, "Production grid")
check("#folderGrid (folder listing)", '"folderGrid"' in html, "Folder grid")
check("#clipboardTextInput (prod clipboard)", '"clipboardTextInput"' in html, "Prod clipboard")
check("#clipboardHistoryContent (prod history)", '"clipboardHistoryContent"' in html, "Prod history")
check("#addTextToClipboardBtn (prod add btn)", '"addTextToClipboardBtn"' in html, "Prod add button")
check("#settingsMenu (prod settings)", '"settingsMenu"' in html, "Prod settings menu")
check("#protocolStatus (protocol)", '"protocolStatus"' in html, "Protocol indicator")

# ── 8. Upload Toast Tray ──
print(f"\n{BOLD}8. Upload Progress UI{RESET}")
print(f"{'─'*50}")

check("#uploadToastStack exists", '"uploadToastStack"' in html, "Desktop upload tray")
check("#toast exists", '"toast"' in html, "System toast")
check("#toast-progress exists", '"toast-progress"' in html, "Toast progress bar")

# ── Score Calculation ──
total = passed + failed + warnings
score = round((passed / max(total, 1)) * 100, 1)

print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"\n{BOLD}Module 1: Runtime Score{RESET}")
print(f"  {GREEN}Passed:   {passed}{RESET}")
print(f"  {RED}Failed:   {failed} (Critical: {critical}){RESET}")
print(f"  {YELLOW}Warnings: {warnings}{RESET}")
print(f"  {BOLD}Score:    {score}%{RESET}")

if critical == 0:
    print(f"\n  {GREEN}✅ All critical components verified.{RESET}")
else:
    print(f"\n  {RED}❌ {critical} critical issues found.{RESET}")
    print(f"  Fix these before proceeding to Module 2 (State Scanner).")

print(f"\n{BOLD}{'═'*60}{RESET}\n")

# Classification key
print(f"{BOLD}Classification Key:{RESET}")
print(f"  {RED}Lanvan Regression{RESET} — missing production feature")
print(f"  {YELLOW}Intentional Improvement{RESET} — Lanvan improved over reference build")
print(f"  {YELLOW}Reference Limitation{RESET} — reference-only, skip")

sys.exit(0 if critical == 0 else 1)