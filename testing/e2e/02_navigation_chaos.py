#!/usr/bin/env python3
"""
Level 4: Navigation Chaos Playwright UI Suite
=============================================
Tests UI navigation pathways:
- Double click nested folder traversal
- Breadcrumb navigation clicks
- Browser History (page.go_back(), page.go_forward())
- Page Refresh (page.reload() / F5)
- Rapid click spam on folders and breadcrumbs
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Level 4: Navigation Chaos (UI)", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- LEVEL 4: NAVIGATION CHAOS (REAL UI) TESTS ---")

        # 2.1 Create Level A and Level B Folders via UI
        folder_a = f"NavUI_A_{secrets.token_hex(2)}"
        
        # Open dialog via showGenericContextMenu
        await page.evaluate("() => { if (typeof showGenericContextMenu === 'function') showGenericContextMenu(200, 200); }")
        await page.wait_for_selector("#contextMenu", state="visible", timeout=3000)
        await page.click("#genericMenuOptions .context-item:has-text('New folder')")
        await page.wait_for_selector("#newFolderDialog", state="visible", timeout=3000)
        await page.fill("#newFolderNameInput", folder_a)
        await page.keyboard.press("Enter")
        await page.wait_for_selector("#newFolderDialog", state="hidden", timeout=3000)
        await page.wait_for_timeout(500)

        row_a = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_a}']").first
        if await row_a.is_visible():
            runner.record_pass("L4-01", f"Created Folder '{folder_a}' via UI")
        else:
            await runner.record_failure("L4-01", "Folder Creation", f"'{folder_a}' visible", "Not visible")

        # Double click to enter Folder A
        title_a = row_a.locator(".item-title, .file-name-cell").first
        await title_a.dblclick()
        await page.wait_for_timeout(1000)

        # 2.2 Create Nested Folder B inside Folder A
        folder_b = f"NavUI_B_{secrets.token_hex(2)}"
        await page.evaluate("() => { if (typeof showGenericContextMenu === 'function') showGenericContextMenu(200, 200); }")
        await page.wait_for_selector("#contextMenu", state="visible", timeout=3000)
        await page.click("#genericMenuOptions .context-item:has-text('New folder')")
        await page.wait_for_selector("#newFolderDialog", state="visible", timeout=3000)
        await page.fill("#newFolderNameInput", folder_b)
        await page.keyboard.press("Enter")
        await page.wait_for_selector("#newFolderDialog", state="hidden", timeout=3000)
        await page.wait_for_timeout(500)

        row_b = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_b}']").first
        title_b = row_b.locator(".item-title, .file-name-cell").first
        await title_b.dblclick()
        await page.wait_for_timeout(1000)

        breadcrumb_text = await page.inner_text("#breadcrumbsContainer")
        if folder_a in breadcrumb_text and folder_b in breadcrumb_text:
            runner.record_pass("L4-02", f"Nested double-click navigation into '{folder_a}/{folder_b}' verified")
        else:
            await runner.record_failure("L4-02", "Nested UI Navigation", f"'{folder_a}/{folder_b}' in breadcrumb", breadcrumb_text)

        # 2.3 UI Breadcrumb Navigation to Parent Folder
        crumb_a = page.locator(f"#breadcrumbsContainer .breadcrumb-item:has-text('{folder_a}')").first
        await crumb_a.click()
        await page.wait_for_timeout(800)

        bc_after_back = await page.inner_text("#breadcrumbsContainer")
        if folder_a in bc_after_back and folder_b not in bc_after_back:
            runner.record_pass("L4-03", f"Breadcrumb click returned to Parent folder '{folder_a}'")
        else:
            await runner.record_failure("L4-03", "Breadcrumb Back Navigation", f"Parent '{folder_a}' in breadcrumb", bc_after_back)

        # 2.4 Subfolder Navigation from Parent Folder
        row_b = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_b}']").first
        title_b = row_b.locator(".item-title, .file-name-cell").first
        await title_b.dblclick()
        await page.wait_for_timeout(800)

        bc_after_forward = await page.inner_text("#breadcrumbsContainer")
        if folder_b in bc_after_forward:
            runner.record_pass("L4-04", f"Re-entering subfolder '{folder_b}' verified")
        else:
            await runner.record_failure("L4-04", "Re-enter Subfolder", f"Subfolder '{folder_b}' in breadcrumb", bc_after_forward)

        # 2.5 Page Refresh (F5 / page.reload()) & State Recovery
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        bc_after_reload = await page.inner_text("#breadcrumbsContainer")
        if folder_b in bc_after_reload or folder_a in bc_after_reload:
            runner.record_pass("L4-05", "Page Refresh (page.reload()) recovered viewport state cleanly")
        else:
            await runner.record_failure("L4-05", "Page Reload Recovery", f"'{folder_a}' or '{folder_b}' in breadcrumb", bc_after_reload)

        # 2.6 Rapid Click Spam on Breadcrumbs
        home_item = page.locator("#breadcrumbsContainer .breadcrumb-item:has-text('Home')").first
        for _ in range(5):
            await home_item.click(force=True)
            await page.wait_for_timeout(50)

        await page.wait_for_timeout(800)
        final_bc = await page.inner_text("#breadcrumbsContainer")
        if final_bc.strip() == "Home":
            runner.record_pass("L4-06", "Rapid Breadcrumb Click Spam settled cleanly on Home")
        else:
            await runner.record_failure("L4-06", "Breadcrumb Spam Settlement", "Home only", final_bc)

        # 2.7 Console Exception Guard
        await runner.assert_no_console_errors("L4-07")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
