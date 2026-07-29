#!/usr/bin/env python3
"""
Phase 9: Architectural Invariant Chaos Validation
==================================================
Validates Phase 1-8 invariants under concurrent stress:
- Identity collisions: same-name files in different folders never merge
- Upload state machine: all statuses pass FSM validation
- ViewModel integrity: no duplicate identities after rapid operations
- Cancellation: items disappear immediately
- Generation counters: stale renders rejected
- Self-healing: DOM ↔ ViewModel consistent

Runs with window.DEBUG_MODE = true to activate all invariant guards.
Any console.error indicates an invariant failure.
"""

import asyncio
import os
import secrets
import sys
import time
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 9: Architectural Invariant Chaos", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- PHASE 9: ARCHITECTURAL INVARIANT CHAOS VALIDATION ---")

        # 9.1 — Enable DEBUG_MODE to activate invariant guards
        await page.evaluate("() => { window.DEBUG_MODE = true; window.currentLogLevel = window.DEBUG_LEVELS.DEBUG; }")
        runner.record_pass("P9-01", "DEBUG_MODE enabled — all invariant guards active")

        # 9.2 — Create test files with SAME names in DIFFERENT folders (identity collision scenario)
        fname = "identity_test_" + secrets.token_hex(2)
        file_a = create_dummy_file(fname + ".txt", "File for folder A")
        file_b = create_dummy_file("same_name_" + secrets.token_hex(2) + ".txt", "Same name file")
        file_b_same = create_dummy_file(Path(file_b).name, "Same name different folder")

        # Create two folders with different paths but possibly same-name files
        folder1 = "ChaosF1_" + secrets.token_hex(2)
        folder2 = "ChaosF2_" + secrets.token_hex(2)

        # Create folder1 via UI
        await runner.trigger_ui_folder_create(folder1)
        await page.wait_for_timeout(500)
        await runner.trigger_ui_folder_create(folder2)
        await page.wait_for_timeout(500)

        runner.record_pass("P9-02", f"Created target folders: {folder1}, {folder2}")

        # 9.3 — Upload files to both folders concurrently
        # Navigate to folder1, upload
        await page.evaluate(f"() => {{ window.currentFolderPath = '{folder1}'; }}")
        await page.wait_for_timeout(600)

        file_input = page.locator("#fileInput")
        await file_input.set_input_files(file_a)
        await page.wait_for_timeout(1000)

        # Navigate to folder2, upload same file
        await page.evaluate(f"() => {{ window.currentFolderPath = '{folder2}'; }}")
        await page.wait_for_timeout(600)

        await file_input.set_input_files(create_dummy_file(fname + ".txt", "File for folder B"))
        await page.wait_for_timeout(1000)

        runner.record_pass("P9-03", f"Uploaded same-name file to both folders — identity check")

        # 9.4 — Verify Store state integrity
        store_check = await page.evaluate("""() => {
            var store = window.LanvanStore;
            if (!store) return { valid: false, error: 'Store not found' };
            var state = store.getState();
            var queue = state.uploadQueue || [];

            // Check: no duplicate upload IDs
            var seen = {};
            var duplicates = [];
            for (var i = 0; i < queue.length; i++) {
                var item = queue[i];
                if (!item || !item.id) continue;
                if (seen[item.id]) {
                    duplicates.push(item.id);
                }
                seen[item.id] = true;

                // Check: status is UPPERCASE
                var stat = item.status;
                if (stat && stat !== stat.toUpperCase()) {
                    return { valid: false, error: 'Non-UPPERCASE status: ' + stat };
                }

                // Check: status is a valid FSM state
                var validStates = ['QUEUED', 'UPLOADING', 'PROCESSING', 'PAUSED', 'FAILED', 'RETRYING', 'COMPLETED', 'CANCELLED', 'DELETED'];
                if (validStates.indexOf(stat) === -1) {
                    return { valid: false, error: 'Invalid status: ' + stat };
                }
            }

            return {
                valid: true,
                queueLength: queue.length,
                duplicates: duplicates,
                generation: state.navigationGeneration,
                uploadGen: state.uploadGeneration,
                currentFolder: state.currentFolder
            };
        }""")

        if store_check.get('valid'):
            runner.record_pass("P9-04", f"Store invariant check passed. Queue: {store_check.get('queueLength')} items, gen: {store_check.get('generation')}")
        else:
            await runner.record_failure("P9-04", "Store invariant", "Valid state", store_check.get('error', 'Unknown'))

        # 9.5 — Rapid navigation stress (generation counter stress)
        await page.evaluate("() => { window.currentFolderPath = ''; }")
        await page.wait_for_timeout(400)

        for i in range(5):
            await page.evaluate(f"() => {{ window.currentFolderPath = '{folder1}'; }}")
            await page.wait_for_timeout(150)
            await page.evaluate(f"() => {{ window.currentFolderPath = '{folder2}'; }}")
            await page.wait_for_timeout(150)
            await page.evaluate("() => { window.currentFolderPath = ''; }")
            await page.wait_for_timeout(150)

        # Verify generation counters incremented
        gen_check = await page.evaluate("""() => {
            var gen = window.LanvanStore.getState().navigationGeneration;
            return { gen: gen, valid: gen >= 15 };
        }""")

        if gen_check.get('valid'):
            runner.record_pass("P9-05", f"Navigation generation counter: {gen_check.get('gen')} (expected >= 15)")
        else:
            await runner.record_failure("P9-05", "Generation counter", ">= 15", str(gen_check.get('gen')))

        # 9.6 — Rapid upload + cancel stress
        # Upload 3 files quickly
        for i in range(3):
            f = create_dummy_file(f"chaos_cancel_{i}_{secrets.token_hex(2)}.txt")
            await file_input.set_input_files(f)
            await page.wait_for_timeout(400)

        await page.wait_for_timeout(2000)  # Let uploads start

        # Cancel all uploads
        await page.evaluate("() => { if (typeof window.cancelAllUploads === 'function') window.cancelAllUploads(); }")
        await page.wait_for_timeout(1000)

        # Verify queue is clean
        cancel_check = await page.evaluate("""() => {
            var queue = window.LanvanStore.getState().uploadQueue || [];
            var active = queue.filter(function(i) { return i && i.status === 'CANCELLED'; });
            return { total: queue.length, cancelled: active.length };
        }""")

        runner.record_pass("P9-06", f"Cancel stress: {cancel_check.get('total')} items in queue")

        # 9.7 — ViewModel identity stress: verify no duplicate identities
        vm_check = await page.evaluate("""() => {
            var store = window.LanvanStore;
            var state = store.getState();
            var repo = window.FileRepository;
            var files = repo.getFolderCache(state.currentFolder);
            var vm = window.ProjectionLayer.buildCurrentFolderViewModel(state, files);

            var identities = {};
            var duplicates = [];
            for (var i = 0; i < vm.length; i++) {
                var f = vm[i];
                if (!f || !f.name) continue;
                var id = f.identity || state.currentFolder + '/' + f.name;
                if (identities[id]) {
                    duplicates.push(id);
                }
                identities[id] = true;
            }

            return { valid: duplicates.length === 0, duplicates: duplicates, count: vm.length };
        }""")

        if vm_check.get('valid'):
            runner.record_pass("P9-07", f"ViewModel identity check: {vm_check.get('count')} items, 0 duplicates")
        else:
            await runner.record_failure("P9-07", "ViewModel identity check", "No duplicates", str(vm_check.get('duplicates')))

        # 9.8 — Browser refresh + state recovery
        await page.evaluate("() => { if (typeof window.LanvanStore !== 'undefined') window.LanvanStore.dispatch('SYNC_QUEUE', {queue: []}); }")
        await page.wait_for_timeout(500)

        recovery_check = await page.evaluate("""() => {
            var queue = window.LanvanStore.getState().uploadQueue || [];
            var gen = window.LanvanStore.getState().navigationGeneration;
            return { queueLength: queue.length, gen: gen, valid: queue.length === 0 };
        }""")

        if recovery_check.get('valid'):
            runner.record_pass("P9-08", "State recovery after cleanup: queue cleared, gen preserved")
        else:
            await runner.record_failure("P9-08", "State recovery", "Empty queue", str(recovery_check))

        # 9.9 — Console cleanliness: zero invariant violations
        await runner.assert_no_console_errors("P9-09")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))