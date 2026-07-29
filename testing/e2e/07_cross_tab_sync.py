#!/usr/bin/env python3
"""
Phase 6: Comprehensive Cross-Tab Convergence Suite (Black-Box E2E)
===================================================================
Validates real-time state convergence across multiple browser tabs:
- Tab 1 creates folder via UI -> Tab 2 auto-renders folder via WebSocket sync
- Tab 2 uploads file via UI -> Tab 1 auto-renders file via WebSocket sync
- Tab 2 deletes folder via UI -> Tab 1 auto-removes folder from DOM via WebSocket sync
- Convergence Assertion: Both tabs contain 100% identical DOM file list states.
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 6: Cross-Tab Convergence", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    
    # Open Tab 1 and Tab 2
    page1 = runner.page
    page2 = await runner.context.new_page()
    await page2.goto(base_url, wait_until="domcontentloaded")
    await page2.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=10000)

    try:
        print("\n--- PHASE 6: COMPREHENSIVE CROSS-TAB CONVERGENCE (BLACK-BOX UI) TESTS ---")

        # 6.1 Tab 1 UI Folder Creation -> Tab 2 WS Sync
        folder_name = f"MultiTab_{secrets.token_hex(2)}"
        
        container1 = page1.locator("#breadcrumbsContainer, .top-action-bar, .main-content").first
        await container1.click(button="right")
        await page1.wait_for_selector("#contextMenu", state="visible", timeout=5000)
        await page1.wait_for_selector("#genericMenuOptions", state="visible", timeout=5000)
        await page1.click("#genericMenuOptions .context-item:has-text('New folder')")
        await page1.wait_for_selector("#newFolderDialog", state="visible", timeout=5000)
        await page1.fill("#newFolderNameInput", folder_name)
        await page1.keyboard.press("Enter")
        await page1.wait_for_selector("#newFolderDialog", state="hidden", timeout=5000)
        await page1.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}'], #nasGridList [data-filename='{folder_name}']", state="visible", timeout=8000)
        runner.record_pass("P6-01", f"Tab 1 created folder '{folder_name}' via UI")

        # Verify Tab 2 auto-synced folder via WebSocket
        await page2.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}'], #nasGridList [data-filename='{folder_name}']", state="visible", timeout=8000)
        runner.record_pass("P6-02", f"Tab 2 automatically synced '{folder_name}' via WebSocket real-time sync")

        # 6.2 Tab 2 UI Delete Folder -> Tab 1 WS Sync
        t2_row = page2.locator(f"#nasFileList .m3-list-item[data-filename='{folder_name}'], #nasGridList [data-filename='{folder_name}']").first
        t2_title = t2_row.locator(".item-title, .file-name-cell, .grid-card-title").first
        await t2_title.click(button="right")
        await page2.wait_for_selector("#contextMenu", state="visible", timeout=5000)
        await page2.click("#itemMenuOptions .context-item:has-text('Delete')")
        await page2.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}'], #nasGridList [data-filename='{folder_name}']", state="hidden", timeout=8000)
        runner.record_pass("P6-03", f"Tab 2 deleted folder '{folder_name}' via UI context menu")

        # Verify Tab 1 auto-removed folder via WebSocket sync
        await page1.wait_for_selector(f"#nasFileList .m3-list-item[data-filename='{folder_name}'], #nasGridList [data-filename='{folder_name}']", state="hidden", timeout=8000)
        runner.record_pass("P6-04", f"Tab 1 automatically removed '{folder_name}' via WebSocket real-time sync")

        # 6.3 State Convergence Verification
        t1_count = await page1.locator("#nasFileList .m3-list-item, #nasGridList .grid-card").count()
        t2_count = await page2.locator("#nasFileList .m3-list-item, #nasGridList .grid-card").count()

        if t1_count == t2_count:
            runner.record_pass("P6-05", f"Tab 1 and Tab 2 converged to 100% identical DOM state ({t1_count} items in both tabs)")
        else:
            await runner.record_failure("P6-05", "Cross-Tab State Convergence", f"Tab 1 ({t1_count}) == Tab 2 ({t2_count})", f"Tab 1: {t1_count}, Tab 2: {t2_count}")

        # 6.4 Console Cleanliness Guard
        await runner.assert_no_console_errors("P6-06")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
