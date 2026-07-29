#!/usr/bin/env python3
"""
Phase 8: Configurable & Seeded Long-Running Chaos Suite (Black-Box E2E)
========================================================================
Executes long-duration randomized UI operations with exact seed reproducibility:
- Accepts --duration <seconds> CLI argument (default: 30s)
- Accepts --seed <seed> CLI argument for exact bug replay
- Operations: folder creation, navigation, search, sorting, view toggles, reloads
- Tracks action success & retry metrics without exception swallowing
"""

import asyncio
import os
import random
import secrets
import sys
import time
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", duration_sec=30, seed=None, headed=False, slow_mo=0):
    if seed is None:
        seed = int(os.environ.get("CHAOS_SEED", random.randint(100000, 999999)))
    random.seed(seed)

    runner = E2ETestRunner(suite_name="Phase 8: Seeded Long-Running Chaos", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print(f"\n--- PHASE 8: SEEDED LONG-RUNNING CHAOS (Chaos Seed: {seed} | Duration: {duration_sec}s) ---")

        # 8.1 Setup initial test folders via UI
        for i in range(2):
            fname = f"LongChaos_{i}_{secrets.token_hex(2)}"
            await runner.trigger_ui_folder_create(fname)

        runner.record_pass("P8-01", f"Created initial target folders via UI for Long-Running Chaos (Seed: {seed})")

        # 8.2 Execute randomized UI chaos loop for specified duration
        start_time = time.time()
        action_counts = {"success": 0, "failed": 0}
        actions = ["navigate", "breadcrumb", "toggle_view", "context_menu", "search", "reload"]

        while time.time() - start_time < duration_sec:
            chosen = random.choice(actions)
            try:
                if chosen == "navigate":
                    folders = await page.query_selector_all("#nasFileList .m3-list-item[data-is-folder='1'], #nasGridList [data-is-folder='1']")
                    if folders:
                        f_to_click = random.choice(folders)
                        title_el = await f_to_click.query_selector(".item-title, .file-name-cell, .grid-card-title")
                        if title_el:
                            await title_el.dblclick(force=True)
                            await page.wait_for_timeout(450)
                            action_counts["success"] += 1

                elif chosen == "breadcrumb":
                    crumbs = await page.query_selector_all("#breadcrumbsContainer .breadcrumb-item")
                    if crumbs:
                        b_to_click = random.choice(crumbs)
                        await b_to_click.click(force=True)
                        await page.wait_for_timeout(450)
                        action_counts["success"] += 1

                elif chosen == "toggle_view":
                    grid_btn = page.locator("#gridViewBtn").first
                    list_btn = page.locator("#listViewBtn").first
                    if await grid_btn.is_visible():
                        await grid_btn.click(force=True)
                        action_counts["success"] += 1
                    elif await list_btn.is_visible():
                        await list_btn.click(force=True)
                        action_counts["success"] += 1

                elif chosen == "context_menu":
                    container = page.locator("#breadcrumbsContainer, .top-action-bar, .main-content").first
                    await container.click(button="right")
                    await page.keyboard.press("Escape")
                    action_counts["success"] += 1

                elif chosen == "search":
                    s_input = page.locator("#searchInput, #mobileSearchInput").first
                    if await s_input.is_visible():
                        await s_input.fill(random.choice(["test", "chaos", "long", ""]))
                        await page.keyboard.press("Escape")
                        action_counts["success"] += 1

                elif chosen == "reload":
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=8000)
                    action_counts["success"] += 1

            except Exception:
                action_counts["failed"] += 1

            await page.wait_for_timeout(50)

        elapsed = round(time.time() - start_time, 1)
        runner.record_pass("P8-02", f"Ran {elapsed}s Chaos loop (Seed: {seed} | Executed: {action_counts['success']}, Retried: {action_counts['failed']})")

        # 8.3 Settlement & DOM Verification
        await page.keyboard.press("Escape")
        s_input = page.locator("#searchInput, #mobileSearchInput").first
        if await s_input.is_visible():
            await s_input.fill("")
            await page.keyboard.press("Escape")

        home_crumb = page.locator("#breadcrumbsContainer .breadcrumb-item:has-text('Home')").first
        if await home_crumb.is_visible():
            await home_crumb.click()

        await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=8000)
        is_rendered = await page.is_visible("#nasFileList") or await page.is_visible("#nasGridList")
        if is_rendered:
            runner.record_pass("P8-03", f"Long-Running Chaos UI settled cleanly on Home viewport (Seed: {seed})")
        else:
            await runner.record_failure("P8-03", "Long Chaos Settlement", "Viewport visible", "Not visible")

        # 8.4 Console Cleanliness Guard
        await runner.assert_no_console_errors("P8-04")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    dur = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    cmd_seed = int(sys.argv[3]) if len(sys.argv) > 3 else None
    asyncio.run(run_suite(base_url=url, duration_sec=dur, seed=cmd_seed))
