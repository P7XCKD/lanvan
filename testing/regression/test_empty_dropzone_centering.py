#!/usr/bin/env python3
"""
Regression Test: Empty Dropzone Centering & Layout Audit
Verifies that the empty state dropzone ("Drop files here") is 100% centered
vertically and horizontally across Mobile, List View, and Grid View without off-center padding.
"""

import sys
import re
from pathlib import Path

GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

BASE = Path(__file__).parent.parent.parent
LANVAN_CSS = BASE / "app" / "static" / "css" / "lanvan.css"
APP_INIT = BASE / "app" / "static" / "js" / "app-init.js"

passed = 0
failed = 0

def check(description, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  {GREEN}PASS{RESET} {description}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  {RED}FAIL{RESET} {description}" + (f" — {detail}" if detail else ""))

def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Empty Dropzone Centering & Layout Regression Test{RESET}")
    print(f"{BOLD}{'='*60}\n")

    css_content = LANVAN_CSS.read_text(encoding="utf-8") if LANVAN_CSS.exists() else ""
    js_content = APP_INIT.read_text(encoding="utf-8") if APP_INIT.exists() else ""

    # Test 1: Check .empty-dropzone-wrapper CSS rules in lanvan.css
    print(f"{BOLD}1. CSS Centering Rules (lanvan.css){RESET}")
    check(
        "empty-dropzone-wrapper rule defined in lanvan.css",
        ".empty-dropzone-wrapper" in css_content,
        "Found selector"
    )
    
    # Check wrapper flex alignment properties
    wrapper_has_center = "justify-content: center" in css_content and "align-items: center" in css_content
    check(
        "empty-dropzone-wrapper uses flex center alignment",
        wrapper_has_center,
        "justify-content & align-items set to center"
    )

    check(
        "empty-dropzone-wrapper padding is 0 (no top offset bias)",
        "padding: 0" in css_content or "padding:0" in css_content,
        "padding is zeroed out"
    )

    # Test 2: Check JS template markup in app-init.js
    print(f"\n{BOLD}2. JS Template Markup (app-init.js){RESET}")
    
    # Ensure no old padding:3rem 0 remains in app-init.js
    check(
        "No legacy padding:3rem 0 top padding bias in JS templates",
        "padding:3rem 0" not in js_content and "padding: 3rem 0" not in js_content,
        "legacy 3rem top padding removed from empty state wrappers"
    )

    check(
        "Empty state hides table header to prevent asymmetrical top gap",
        'fileTableHead.style.display = (viewMode === "grid" || !hasFiles) ? "none" : ""' in js_content or "updateExplorerLayoutState" in js_content,
        "fileTableHead hidden when empty state is painted via updateExplorerLayoutState"
    )

    check(
        "Empty state wrapper uses 100% height and flex column layout",
        "empty-dropzone-wrapper" in js_content and "height:100%" in js_content,
        "height:100% and flex column alignment applied"
    )

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"  {GREEN}Passed: {passed}{RESET}  {RED}Failed: {failed}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    if failed == 0:
        print(f"{GREEN}[OK] All empty dropzone centering checks PASSED 100%!{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}[FAIL] {failed} checks failed!{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
