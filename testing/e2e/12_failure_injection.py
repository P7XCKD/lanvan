#!/usr/bin/env python3
"""
Phase 11: Systematic Failure Injection Suite (Black-Box E2E)
=============================================================
Injects controlled network failures, HTTP 500 errors, and malformed API payloads:
- Injects HTTP 500 Internal Server Error response on /api/files
- Injects malformed JSON payload responses
- ASSERTION: Client UI handles backend errors gracefully without uncaught JS exception crashes or blank screen freezes.
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 11: Systematic Failure Injection", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- PHASE 11: SYSTEMATIC FAILURE INJECTION (BLACK-BOX UI) TESTS ---")

        # 11.1 Inject HTTP 500 Error on /api/files
        async def handle_500_route(route):
            await route.fulfill(status=500, content_type="application/json", body='{"error": "Internal Server Error"}')

        await page.route("**/api/files?folder=InjectFail*", handle_500_route)

        folder_fail = f"InjectFail_{secrets.token_hex(2)}"
        await runner.trigger_ui_folder_create(folder_fail)

        # Double click to trigger failed fetch
        row_fail = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_fail}'], #nasGridList [data-filename='{folder_fail}']").first
        title_fail = row_fail.locator(".item-title, .file-name-cell, .grid-card-title").first
        await title_fail.dblclick()
        await page.wait_for_timeout(1000)

        # Assert UI remains responsive and did not freeze
        home_crumb = page.locator("#breadcrumbsContainer .breadcrumb-item:has-text('Home')").first
        await home_crumb.click()
        await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=8000)
        runner.record_pass("P11-01", f"Client UI recovered gracefully after HTTP 500 backend failure on '{folder_fail}'")

        await page.unroute("**/api/files?folder=InjectFail*")

        # 11.2 Inject Malformed JSON Payload on /api/files
        async def handle_malformed_json(route):
            await route.fulfill(status=200, content_type="application/json", body='{"files": [invalid_json_payload')

        await page.route("**/api/files?folder=InjectJSON*", handle_malformed_json)

        folder_json = f"InjectJSON_{secrets.token_hex(2)}"
        await runner.trigger_ui_folder_create(folder_json)

        row_json = page.locator(f"#nasFileList .m3-list-item[data-filename='{folder_json}'], #nasGridList [data-filename='{folder_json}']").first
        title_json = row_json.locator(".item-title, .file-name-cell, .grid-card-title").first
        await title_json.dblclick()
        await page.wait_for_timeout(1000)

        # Return to Home
        await home_crumb.click()
        await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=8000)
        runner.record_pass("P11-02", f"Client UI handled malformed JSON payload response on '{folder_json}' cleanly without JS crash")

        await page.unroute("**/api/files?folder=InjectJSON*")

        # 11.3 Console Cleanliness Guard
        await runner.assert_no_console_errors("P11-03")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
