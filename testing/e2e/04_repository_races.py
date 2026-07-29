#!/usr/bin/env python3
"""
Phase 4: Controlled Repository Network Race Suite (Black-Box E2E)
===================================================================
Validates that delayed out-of-order backend responses never corrupt active viewports:
- Intercepts network responses and artificially delays Folder A fetch by 3000ms.
- User rapidly navigates to Folder B (fetches in 50ms).
- Delayed Folder A payload arrives while Folder B is active.
- ASSERTION: Visible viewport content MUST remain 100% Folder B without stale data pollution.
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 4: Controlled Repository Network Races", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- PHASE 4: CONTROLLED REPOSITORY NETWORK RACES (BLACK-BOX UI) TESTS ---")

        # 4.1 Create RaceFolder_A and RaceFolder_B via UI
        folder_a = f"Race_A_{secrets.token_hex(2)}"
        folder_b = f"Race_B_{secrets.token_hex(2)}"

        await runner.trigger_ui_folder_create(folder_a)
        await runner.trigger_ui_folder_create(folder_b)
        runner.record_pass("P4-01", f"Created test folders '{folder_a}' and '{folder_b}' via UI")

        # 4.2 Upload unique test file into Folder A and Folder B
        await runner.trigger_ui_folder_navigate(folder_a)
        file_a_name = f"file_in_{folder_a}.txt"
        file_a_path = create_dummy_file(file_a_name, "Content inside Folder A")
        file_input = page.locator("#fileInput").first
        await file_input.set_input_files(file_a_path)
        await page.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{file_a_name}'], #nasGridList [data-filename='{file_a_name}']", state="visible", timeout=8000)

        # Return to Home
        home_crumb = page.locator("#breadcrumbsContainer .breadcrumb-item:has-text('Home')").first
        await home_crumb.click()
        await page.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_b}'], #nasGridList [data-filename='{folder_b}']", state="visible", timeout=8000)

        await runner.trigger_ui_folder_navigate(folder_b)
        file_b_name = f"file_in_{folder_b}.txt"
        file_b_path = create_dummy_file(file_b_name, "Content inside Folder B")
        await file_input.set_input_files(file_b_path)
        await page.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{file_b_name}'], #nasGridList [data-filename='{file_b_name}']", state="visible", timeout=8000)

        # Return to Home
        await home_crumb.click()
        await page.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_a}'], #nasGridList [data-filename='{folder_a}']", state="visible", timeout=8000)

        # 4.3 Setup Controlled Network Race: Delay requests for Folder A by 2500ms
        async def delay_folder_a_fetch(route):
            url = route.request.url
            if folder_a in url:
                await asyncio.sleep(2.5)
            await route.continue_()

        await page.route("**/api/files*", delay_folder_a_fetch)

        # 4.4 Trigger Rapid Navigation: Click Folder A, then Home, then enter Folder B
        row_a = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_a}'], #nasGridList [data-filename='{folder_a}']").first
        title_a = row_a.locator(".item-title, .file-name-cell, .grid-card-title").first
        await title_a.dblclick()

        # Click Home and wait 450ms for nav throttle window to clear
        await page.wait_for_timeout(450)
        await home_crumb.click()
        await page.wait_for_timeout(450)

        # Double click into Folder B
        row_b = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_b}'], #nasGridList [data-filename='{folder_b}']").first
        title_b = row_b.locator(".item-title, .file-name-cell, .grid-card-title").first
        await title_b.dblclick()
        await page.wait_for_selector(f"#breadcrumbsContainer .breadcrumb-item:has-text('{folder_b}')", state="visible", timeout=8000)

        # 4.5 Wait 3000ms for delayed Folder A payload to arrive while viewport is in Folder B
        await page.wait_for_timeout(3000)

        # ASSERTION: Active viewport must render file_b_name and NOT file_a_name
        is_file_b_visible = await page.is_visible(f"#nasFileList .m3-list-item[data-filename='{file_b_name}'], #nasGridList [data-filename='{file_b_name}']")
        is_file_a_visible = await page.is_visible(f"#nasFileList .m3-list-item[data-filename='{file_a_name}'], #nasGridList [data-filename='{file_a_name}']")

        if is_file_b_visible and not is_file_a_visible:
            runner.record_pass("P4-02", f"Delayed out-of-order payload for '{folder_a}' was correctly REJECTED by active '{folder_b}' viewport")
        else:
            await runner.record_failure("P4-02", "Network Race Protection", f"Only '{file_b_name}' visible", f"File B: {is_file_b_visible}, File A Leak: {is_file_a_visible}")

        await page.unroute("**/api/files*")

        # 4.6 Console Cleanliness Guard
        await runner.assert_no_console_errors("P4-03")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
