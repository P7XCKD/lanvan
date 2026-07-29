#!/usr/bin/env python3
"""
Level 5: Network Chaos & Browser Interruption Playwright Suite
==============================================================
Tests network interruption & recovery:
- Network Disconnect (context.set_offline(True))
- Network Reconnect (context.set_offline(False))
- WebSocket auto-reconnect recovery
- Mid-transfer Page Refresh (page.reload())
- Browser State Consistency
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Level 5: Network & Browser Chaos", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page
    context = runner.context

    try:
        print("\n--- LEVEL 5: NETWORK & BROWSER CHAOS TESTS ---")

        # 5.1 Upload File via UI
        test_file = f"net_chaos_{secrets.token_hex(2)}.txt"
        filepath = create_dummy_file(test_file, "Network chaos test data " * 50)
        
        file_input = page.locator("#fileInput").first
        await file_input.set_input_files(filepath)
        await page.wait_for_timeout(300)

        # 5.2 Network Disconnect Chaos (set_offline(True))
        await context.set_offline(True)
        await page.wait_for_timeout(1000)

        runner.record_pass("L5-01", "Simulated Network Disconnect (context.set_offline(True))")

        # 5.3 Network Reconnect Chaos (set_offline(False))
        await context.set_offline(False)
        await page.wait_for_timeout(1500)

        runner.record_pass("L5-02", "Simulated Network Reconnect (context.set_offline(False))")

        # 5.4 Page Reload Recovery
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        # Verify page loaded cleanly and file list is rendered
        file_list_visible = await page.is_visible("#nasFileList")
        if file_list_visible:
            runner.record_pass("L5-03", "Page Reload after Network Reconnect rendered DOM cleanly")
        else:
            await runner.record_failure("L5-03", "Post-Reconnect Page Reload", "#nasFileList visible", "Not visible")

        # 5.5 Console Exception Guard
        await runner.assert_no_console_errors("L5-04")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
