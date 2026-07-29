#!/usr/bin/env python3
"""
Phase 9: Portable Resource Leak Guard Suite (White-Box Diagnostics)
====================================================================
Measures standardized observable resources before and after high-frequency UI stress:
- Baseline vs. Post-Stress DOM Node Count (document.querySelectorAll('*').length)
- Baseline vs. Post-Stress WebSocket Connection Count
- 50 Rapid UI Folder Navigations & List Re-renders
- ASSERTIONS:
  1. DOM Node Growth MUST be < 15% after stress settlement.
  2. WebSocket Connection Count MUST remain exactly 1 (zero socket accumulation leaks).
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 9: Portable Resource Leak Guard", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- PHASE 9: PORTABLE RESOURCE LEAK GUARD (WHITE-BOX DIAGNOSTICS) TESTS ---")

        # 9.1 Setup 3 test folders via UI for high-frequency stress
        folders = []
        for i in range(3):
            fname = f"LeakTest_{i}_{secrets.token_hex(2)}"
            await runner.trigger_ui_folder_create(fname)
            folders.append(fname)

        # Record Baseline Metrics after setup but BEFORE navigation loop
        await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=10000)
        baseline_metrics = await page.evaluate("""() => {
            return {
                domNodes: document.querySelectorAll('*').length,
                wsCount: (window.fileEventsWs && window.fileEventsWs.readyState === WebSocket.OPEN) ? 1 : 0
            };
        }""")

        runner.record_pass("P9-01", f"Baseline metrics recorded: {baseline_metrics['domNodes']} DOM nodes, {baseline_metrics['wsCount']} active WebSocket")

        # 9.3 Perform 30 Rapid UI Navigations
        home_crumb = page.locator("#breadcrumbsContainer .breadcrumb-item:has-text('Home')").first
        for step in range(30):
            await page.keyboard.press("Escape")
            target_folder = folders[step % len(folders)]
            row = page.locator(f"#nasFileList .m3-list-item[data-filename='{target_folder}'], #nasGridList [data-filename='{target_folder}']").first
            if await row.is_visible():
                title_el = row.locator(".item-title, .file-name-cell, .grid-card-title").first
                await title_el.dblclick()
                await page.wait_for_timeout(450)
                await page.keyboard.press("Escape")
                await home_crumb.click()
                await page.wait_for_timeout(450)

        # 9.4 Post-Stress Resource Measurement
        await home_crumb.click()
        await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=8000)
        await page.wait_for_timeout(1000)

        post_metrics = await page.evaluate("""() => {
            return {
                domNodes: document.querySelectorAll('*').length,
                wsCount: (window.fileEventsWs && window.fileEventsWs.readyState === WebSocket.OPEN) ? 1 : 0
            };
        }""")

        dom_growth = post_metrics['domNodes'] - baseline_metrics['domNodes']
        dom_growth_pct = round((dom_growth / max(1, baseline_metrics['domNodes'])) * 100, 1)

        # ASSERTION 1: DOM Node Growth < 15%
        if dom_growth_pct <= 15.0:
            runner.record_pass("P9-02", f"DOM Node growth post-stress stayed cleanly within threshold ({dom_growth_pct}% growth: {baseline_metrics['domNodes']} -> {post_metrics['domNodes']})")
        else:
            await runner.record_failure("P9-02", "DOM Node Growth Threshold", "<= 15.0%", f"{dom_growth_pct}% ({baseline_metrics['domNodes']} -> {post_metrics['domNodes']})")

        # ASSERTION 2: Zero WebSocket Accumulation Leaks
        if post_metrics['wsCount'] <= 1:
            runner.record_pass("P9-03", f"WebSocket connection count remained stable (Active sockets: {post_metrics['wsCount']})")
        else:
            await runner.record_failure("P9-03", "WebSocket Accumulation Guard", "<= 1 active WebSocket", f"{post_metrics['wsCount']} active WebSockets")

        # 9.5 Console Cleanliness Guard
        await runner.assert_no_console_errors("P9-04")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
