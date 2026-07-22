#!/usr/bin/env python3
"""Lanvan DOM Audit — Module 3 (Semantic Component Comparison)"""
import re, sys
from pathlib import Path

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"
BASE = Path(__file__).parent.parent.parent
INDEX = BASE / "app" / "templates" / "index.html"
index = Path(INDEX).read_text(encoding="utf-8") if INDEX.exists() else ""
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
print(f"{BOLD}  Module 3: DOM Audit — Semantic Component Comparison{RESET}")
print(f"{BOLD}{'='*60}")

components = {
    "Sidebar": ["app-sidebar","sidebar-brand","sidebar-menu","sideItemFile","sideItemClipboard"],
    "SearchBar": ["app-bar","search-shell","app-actions","searchInput","clearSearchBtn"],
    "Toolbar": ["file-toolbar","filter-chip","view-switcher-pill","fileToolbar","listViewBtn","gridViewBtn"],
    "QuickAccess": ["quick-access","quickAccessContainer"],
    "FileList": ["m3-card","m3-list","drag-overlay","nasDropzone","nasFileList","fileTableHead","breadcrumbsContainer"],
    "Clipboard": ["clipboard-composer-card","clipboard-input-wrapper","clipboardView","clipboardInput","clipboardHistory"],
    "DialogSet": ["m3-dialog-overlay","renameDialog","newFolderDialog","moveFileDialog","settingsDialog","connectQrDialog","previewModal"],
    "ContextMenu": ["custom-context-menu","context-item","contextMenu","sortDropdownMenu","typeDropdownMenu"],
    "QRPanel": ["connection-card","qr-box","connect-tabs","qrBox","connectAddress"],
    "SettingsDialog": ["m3-dialog","m3-switch","aesSettingToggle"],
    "MobileNav": ["bottom-nav","nav-item","yt-nav-add","navItemFile","mobileAddSheetOverlay"],
    "UploadTray": ["upload-toast-stack","uploadToastStack"],
}

for comp_name, required in components.items():
    print(f"\n{BOLD}{comp_name}{RESET}")
    for item in required:
        check(f"  {item}", item in index, "present" if item in index else "MISSING")

print(f"\n{BOLD}Production Legacy — Hidden Container IDs{RESET}")
prod_ids = ["production-legacy","fileInput","folderInput","drop-zone","uploadProgress",
    "uploadManager","uploadQueue","fileGrid","folderGrid","fileCount","folderCount",
    "enableEncryption","enableDarkMode","protocolStatus","settingsBtn","settingsMenu",
    "clipboardTextInput","clipboardHistoryContent","addTextToClipboardBtn","clipboardSection"]
for pid in prod_ids:
    check(f"  #{pid}", f'"{pid}"' in index, "preserved" if f'"{pid}"' in index else "MISSING")

total = passed + failed
score = round((passed / max(total, 1)) * 100, 1)
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"\n{BOLD}Module 3: DOM Audit Score{RESET}")
print(f"  {GREEN}Passed: {passed}{RESET}  {RED}Failed: {failed} (Critical: {critical}){RESET}  {BOLD}Score: {score}%{RESET}")
print(f"\n{'✅ All components verified!' if critical == 0 else f'❌ {critical} critical issues'}{RESET}\n")
sys.exit(0 if critical == 0 else 1)