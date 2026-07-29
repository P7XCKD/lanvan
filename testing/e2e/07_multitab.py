#!/usr/bin/env python3
"""
Level 7: Multi-Tab Real-Time Cross-Tab WebSocket Sync Playwright Suite
========================================================================
Tests real-time cross-tab synchronization:
- Tab 1 creates a folder via UI -> Tab 2 receives WebSocket mutation & renders row instantly
- Tab 2 deletes folder via UI -> Tab 1 receives WebSocket mutation & removes row instantly
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Level 7: Multi-Tab Real-Time Sync", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page1 = runner.page
    context = runner.context

    try:
        print("\n--- LEVEL 7: MULTI-TAB REAL-TIME SYNC TESTS ---")

        # Open Tab 2
        page2 = await context.new_page()
        await page2.goto(base_url, wait_until="domcontentloaded")
        await page2.wait_for_timeout(1000)

        # 7.1 Tab 1 UI Folder Creation
        folder_name = f"MultiTab_{secrets.token_hex(2)}"
        
        container = page1.locator("#breadcrumbsContainer, .top-action-bar, .main-content").first
        await container.click(button="right")
        await page1.wait_for_selector("#contextMenu", state="visible", timeout=3000)
        await page1.wait_for_selector("#genericMenuOptions", state="visible", timeout=3000)
        await page1.click("#genericMenuOptions .context-item:has-text('New folder')")
        await page1.wait_for_selector("#newFolderDialog", state="visible", timeout=3000)
        await page1.fill("#newFolderNameInput", folder_name)
        await page1.keyboard.press("Enter")
        await page1.wait_for_selector("#newFolderDialog", state="hidden", timeout=3000)
        await page1.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}']", state="visible", timeout=8000)
        runner.record_pass("L7-01", f"Tab 1 created folder '{folder_name}' via UI")

        # 7.2 Verify Tab 2 rendered folder automatically via WebSocket real-time sync
        t2_row = page2.locator(f"#nasFileList .m3-list-item[data-filename='{folder_name}']").first
        try:
            await page2.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}']", state="visible", timeout=4000)
            runner.record_pass("L7-02", f"Tab 2 automatically synced '{folder_name}' via WebSocket without page refresh")
        except Exception as e:
            await runner.record_failure("L7-02", "Cross-Tab Real-Time Sync", f"'{folder_name}' auto-rendered in Tab 2", str(e))

        # 7.3 Tab 2 UI Delete Folder
        if await t2_row.is_visible():
            t2_title_el = t2_row.locator(".item-title, .file-name-cell").first
            await t2_title_el.click(button="right")
            await page2.wait_for_selector("#contextMenu", state="visible", timeout=3000)
            await page2.click("#itemMenuOptions .context-item:has-text('Delete')")
            await page2.wait_for_timeout(1500)
            await page2.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}']", state="hidden", timeout=8000)
            runner.record_pass("L7-03", f"Tab 2 deleted folder '{folder_name}' via UI")

        # 7.4 Verify Tab 1 auto-removed folder via WebSocket sync
        try:
            await page1.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}']", state="hidden", timeout=8000)
            runner.record_pass("L7-04", f"Tab 1 automatically removed '{folder_name}' via WebSocket sync")
        except Exception as e:
            await runner.record_failure("L7-04", "Cross-Tab Real-Time Delete Sync", f"'{folder_name}' auto-removed in Tab 1", str(e))

        # Close Tab 2
        await page2.close()

        # 7.5 Console Exception Guard
        await runner.assert_no_console_errors("L7-05")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
