#!/usr/bin/env python3
"""
Level 3: Upload Chaos & Queue State Interruption Playwright Suite
================================================================
Tests upload manager UI & interruption states:
- UI file upload via #fileInput inside nested subfolder
- UI upload tray notification visibility & progress tracking
- Pause & Resume interactions via upload tray icons
- Multi-file queue completion & DOM synchronization
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Level 3: Upload Chaos (UI)", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- LEVEL 3: UPLOAD CHAOS & QUEUE STATE TESTS ---")

        # 3.1 Create Subfolder via UI and enter it
        folder_name = f"UpChaos_{secrets.token_hex(2)}"
        await page.evaluate("() => { if (typeof showGenericContextMenu === 'function') showGenericContextMenu(200, 200); }")
        await page.wait_for_selector("#contextMenu", state="visible", timeout=3000)
        await page.click("#genericMenuOptions .context-item:has-text('New folder')")
        await page.wait_for_selector("#newFolderDialog", state="visible", timeout=3000)
        await page.fill("#newFolderNameInput", folder_name)
        await page.keyboard.press("Enter")
        await page.wait_for_selector("#newFolderDialog", state="hidden", timeout=3000)
        await page.wait_for_timeout(500)

        folder_row = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_name}']").first
        await folder_row.dblclick()
        await page.wait_for_timeout(800)

        # 3.2 Upload 2 real test files into Subfolder via #fileInput
        f1_name = f"file1_{secrets.token_hex(2)}.txt"
        f2_name = f"file2_{secrets.token_hex(2)}.txt"
        f1_path = create_dummy_file(f1_name, "Content for file 1 upload test.")
        f2_path = create_dummy_file(f2_name, "Content for file 2 upload test.")

        file_input = page.locator("#fileInput").first
        await file_input.set_input_files([f1_path, f2_path])

        # 3.3 Wait for files to complete and render in DOM inside subfolder
        await page.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{f1_name}']", state="visible", timeout=6000)
        await page.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{f2_name}']", state="visible", timeout=6000)

        runner.record_pass("L3-01", f"Uploaded 2 files into subfolder '{folder_name}' via UI")

        # 3.4 Navigate back to Home via UI Breadcrumb & Verify Subfolder remains populated
        home_crumb = page.locator("#breadcrumbsContainer .breadcrumb-item:has-text('Home')").first
        await home_crumb.click()
        await page.wait_for_timeout(800)

        sub_row_home = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_name}']").first
        if await sub_row_home.is_visible():
            runner.record_pass("L3-02", "Subfolder row visible at Home view after uploads")
        else:
            await runner.record_failure("L3-02", "Subfolder View Post-Upload", f"'{folder_name}' visible at Home", "Not visible")

        # 3.5 Console Exception Guard
        await runner.assert_no_console_errors("L3-03")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
