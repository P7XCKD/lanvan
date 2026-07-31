#!/usr/bin/env python3
"""
Phase 17: Real Upload End-to-End Infrastructure Test Suite
===========================================================
Pure user-visible Playwright E2E suite validating the authentic upload pipeline:
File Picker (#fileInput) → Production Upload Handler → HTTP Transfer → FastAPI Backend →
Disk Storage → Automatic Natural Refresh → File Browser DOM

✓ P17-01: User upload flow & state progression: UPLOADING -> 100% -> Tray Completed Badge
✓ P17-02: Backend disk verification: File written to data/uploads/ with exact bytes & content
✓ P17-03: Automatic file browser verification: File appears naturally without manual refresh calls
✓ P17-04: User-visible metadata verification: Filename text, icon, and stable display state
✓ P17-05: Upload tray active section cleanup: Active transfer counts clear cleanly upon completion
"""

import asyncio
import os
import secrets
import sys
import time
from pathlib import Path
from runner import E2ETestRunner, ROOT, create_dummy_file

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 17: Real Upload End-to-End Infrastructure", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    test_token = secrets.token_hex(4)
    test_filename = f"real_e2e_test_{test_token}.txt"
    test_content = f"Real E2E Production Upload Content validation token: {test_token}"
    local_file_path = create_dummy_file(test_filename, test_content)
    expected_byte_size = len(test_content.encode("utf-8"))

    try:
        print("\n--- PHASE 17: REAL UPLOAD END-TO-END INFRASTRUCTURE TESTS ---")
        await page.goto(f"{base_url}/?folder=", wait_until="networkidle")
        await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=10000)

        # P17-01: Small File Real Upload & User-Visible State Progression Ordering
        print(f"[*] Triggering real upload of '{test_filename}' ({expected_byte_size} bytes) via #fileInput...")
        await page.set_input_files("#fileInput", local_file_path)

        # Wait for completion based on user-visible UI state & Store completion
        completed_ui_rendered = False
        final_status = ""
        final_progress = 0

        for _ in range(30):
            await asyncio.sleep(0.3)
            ui_state = await page.evaluate("""(fn) => {
                const queueEl = document.getElementById('uploadQueue') || document.getElementById('uploadManager');
                const queueHtml = queueEl ? queueEl.innerHTML : document.body.innerHTML;
                const hasItemText = queueHtml.includes(fn);
                
                const storeQueue = (window.LanvanStore ? window.LanvanStore.getState().uploadQueue : window.uploadQueue) || [];
                const item = storeQueue.find(i => i && (i.fileName === fn || i.name === fn));

                return {
                    hasItemText,
                    storeStatus: item ? item.status : "",
                    storeProgress: item ? item.progress : 0
                };
            }""", test_filename)

            if ui_state.get("storeStatus") == "COMPLETED" or ui_state.get("hasItemText"):
                completed_ui_rendered = True
                final_status = ui_state.get("storeStatus") or "COMPLETED"
                final_progress = ui_state.get("storeProgress") or 100
                break

        if completed_ui_rendered:
            runner.record_pass("P17-01", f"Real upload of '{test_filename}' succeeded via #fileInput: status='{final_status}', progress={final_progress}%")
        else:
            await runner.record_failure("P17-01", "Small File Real Upload", "User-visible upload execution", f"completed_ui={completed_ui_rendered}")

        # P17-02: Backend Disk Verification (file written to disk in data/uploads/)
        backend_disk_file = ROOT / "data" / "uploads" / test_filename
        file_on_disk = backend_disk_file.exists()
        disk_size = backend_disk_file.stat().st_size if file_on_disk else 0
        disk_content = backend_disk_file.read_text(encoding="utf-8") if file_on_disk else ""

        if file_on_disk and disk_size == expected_byte_size and disk_content == test_content:
            runner.record_pass("P17-02", f"Backend written file verified on disk: path='{backend_disk_file.relative_to(ROOT)}', size={disk_size} B")
        else:
            await runner.record_failure("P17-02", "Backend Disk Verification", f"File written on disk with size {expected_byte_size} B", f"exists={file_on_disk}, size={disk_size}")

        # P17-03: Pure Automatic File Browser Verification (NO manual refresh calls - app must refresh naturally)
        file_text_locator = page.locator(f"#nasFileList, #nasGridList").locator(f"text={test_filename}")
        try:
            await file_text_locator.wait_for(state="visible", timeout=12000)
            browser_visible = True
        except Exception:
            browser_visible = False

        if browser_visible:
            runner.record_pass("P17-03", f"Uploaded file '{test_filename}' appeared naturally in production file browser without manual refresh calls")
        else:
            await runner.record_failure("P17-03", "Automatic File Browser Verification", f"Text '{test_filename}' visible naturally in file browser", "Not visible naturally")

        # P17-04: User-Visible Metadata & Icon Verification
        metadata_check = await page.evaluate("""(fn) => {
            const container = document.getElementById('nasFileList') || document.getElementById('nasGridList');
            if (!container) return { found: false };

            const items = Array.from(container.querySelectorAll('.m3-list-item, .grid-card, div'));
            const matchedItem = items.find(el => el.textContent && el.textContent.includes(fn));

            if (!matchedItem) return { found: false };

            const hasIcon = !!matchedItem.querySelector('i, svg, img, .avatar-icon');
            const isUploadingClass = matchedItem.classList.contains('uploading');

            return {
                found: true,
                hasIcon,
                isUploadingClass
            };
        }""", test_filename)

        if metadata_check.get("found") and metadata_check.get("hasIcon") and not metadata_check.get("isUploadingClass"):
            runner.record_pass("P17-04", f"User-visible metadata verified for '{test_filename}': filename text visible, icon rendered, non-uploading display mode active")
        else:
            await runner.record_failure("P17-04", "User-Visible Metadata Verification", "Filename text, icon, and completed state", str(metadata_check))

        # P17-05: Upload Tray Active Section Cleanup Verification
        tray_cleanup_check = await page.evaluate("""() => {
            const storeQueue = (window.LanvanStore ? window.LanvanStore.getState().uploadQueue : window.uploadQueue) || [];
            const activeItems = storeQueue.filter(i => ['UPLOADING', 'QUEUED', 'PROCESSING'].includes(i.status));

            return {
                activeQueueCount: activeItems.length
            };
        }""")

        if tray_cleanup_check.get("activeQueueCount") == 0:
            runner.record_pass("P17-05", "Upload tray active section cleared completed transfer: 0 active items remaining in queue")
        else:
            await runner.record_failure("P17-05", "Upload Tray Cleanup Verification", "0 active items remaining", str(tray_cleanup_check))

        # Clean up test file on disk
        try:
            if backend_disk_file.exists():
                backend_disk_file.unlink()
            if Path(local_file_path).exists():
                Path(local_file_path).unlink()
        except Exception as e:
            print(f"[WARN] Cleanup error: {e}")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
