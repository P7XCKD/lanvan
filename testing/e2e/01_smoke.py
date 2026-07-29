#!/usr/bin/env python3
"""
Level 1: Real User UI Operations Playwright Suite
=================================================
Tests actual browser UI interactions with ZERO page.evaluate API bypasses:
- UI Folder Creation (Click New Folder -> Type Name -> Click Create -> Verify DOM)
- UI Subfolder Navigation (Double-click folder row -> Verify breadcrumbs)
- UI File Upload (Set input files on #fileInput -> Verify toast & DOM row)
- UI Breadcrumb Navigation (Click Home breadcrumb -> Verify viewport reset)
- UI Delete (Right-click context menu -> Click Delete -> Verify DOM removal)
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Level 1: Real UI Smoke Tests", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- LEVEL 1: REAL USER UI SMOKE TESTS ---")

        # 1.1 Page Title & Structure Assertion
        title = await page.title()
        if "Lanvan" in title or "File" in title:
            runner.record_pass("L1-01", "Page Load & Title Assertion")
        else:
            await runner.record_failure("L1-01", "Page Title", "Title containing Lanvan", title)

        # 1.2 UI Folder Creation via pure right-click context menu
        folder_name = f"UI_Folder_{secrets.token_hex(2)}"
        await runner.trigger_ui_folder_create(folder_name)
        runner.record_pass("L1-02", f"UI Folder Creation '{folder_name}' Rendered in DOM")

        # 1.3 UI Subfolder Navigation via pure double-click
        await runner.trigger_ui_folder_navigate(folder_name)
        breadcrumb_text = await page.inner_text("#breadcrumbsContainer")
        if folder_name in breadcrumb_text:
            runner.record_pass("L1-03", f"Double-click Navigation into '{folder_name}' verified in Breadcrumbs")
        else:
            await runner.record_failure("L1-03", "UI Subfolder Navigation", f"'{folder_name}' in breadcrumbs", breadcrumb_text)

        # 1.4 UI File Upload via #fileInput
        test_filename = f"ui_upload_{secrets.token_hex(2)}.txt"
        test_filepath = create_dummy_file(test_filename, "Content for UI Playwright upload test.")
        
        file_input = page.locator("#fileInput").first
        await file_input.set_input_files(test_filepath)
        await page.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{test_filename}'], #nasGridList [data-filename='{test_filename}']", state="visible", timeout=8000)
        runner.record_pass("L1-04", f"UI File Upload '{test_filename}' completed and rendered in DOM")

        # 1.5 UI Breadcrumb Click Back to Home
        home_breadcrumb = page.locator("#breadcrumbsContainer .breadcrumb-item:has-text('Home')").first
        await home_breadcrumb.click()
        await page.wait_for_selector(f"#breadcrumbsContainer .breadcrumb-item:has-text('{folder_name}')", state="hidden", timeout=5000)

        active_home_text = await page.inner_text("#breadcrumbsContainer")
        if active_home_text.strip() == "Home":
            runner.record_pass("L1-05", "Breadcrumb Click Navigation back to Home")
        else:
            await runner.record_failure("L1-05", "UI Breadcrumb Navigation", "Home only", active_home_text)

        # 1.6 UI Context Menu Delete Operation via pure right-click
        await runner.trigger_ui_delete_item(folder_name)
        runner.record_pass("L1-06", f"UI Right-Click Context Menu Delete of '{folder_name}' verified")

        # 1.7 Console Exception Guard
        await runner.assert_no_console_errors("L1-07")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
