#!/usr/bin/env python3
"""
View Isolation Investigation
=============================
Investigates whether parent folder ViewModels are contaminated
by upload operations inside child folders.

Usage:
    python testing/e2e/investigate_view_isolation.py [base_url] [--headed]
"""

import asyncio
import secrets
import sys
from runner import E2ETestRunner, create_dummy_file, ROOT


async def run_suite(base_url="http://127.0.0.1", headed=False):
    runner = E2ETestRunner(suite_name="View Isolation Investigation", headed=headed, slow_mo=0, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        await page.evaluate("() => { window.DEBUG_MODE = true; window.currentLogLevel = window.DEBUG_LEVELS ? window.DEBUG_LEVELS.DEBUG : 3; window.__chaosWarnings = []; window.__chaosErrors = []; }")
        await page.evaluate("""() => {
            var _origWarn = console.warn;
            var _origError = console.error;
            console.warn = function() { window.__chaosWarnings.push(Array.from(arguments).join(' ')); _origWarn.apply(console, arguments); };
            console.error = function() { window.__chaosErrors.push(Array.from(arguments).join(' ')); _origError.apply(console, arguments); };
        }""")
        print("\n--- VIEW ISOLATION INVESTIGATION ---")

        # Step 1: Create a test folder and upload files to it
        parent_folder = f"VizParent_{secrets.token_hex(3)}"
        await runner.trigger_ui_folder_create(parent_folder)
        await page.wait_for_timeout(300)

        # Navigate into the parent folder and upload files
        await page.evaluate(f"() => {{ window.currentFolderPath = '{parent_folder}'; }}")
        await page.wait_for_timeout(500)

        file_input = page.locator("#fileInput")
        for i in range(3):
            f = create_dummy_file(f"viz_file_{i}_{secrets.token_hex(2)}.txt", f"viz content {i}")
            await file_input.set_input_files(f)
            await page.wait_for_timeout(500)

        # Wait for uploads to complete, then navigate back to home
        await page.wait_for_timeout(2000)
        await page.evaluate("() => { window.currentFolderPath = ''; }")
        await page.wait_for_timeout(500)

        runner.record_pass("V01", f"Created parent folder '{parent_folder}' with 3 files")

        # Step 2: Capture parent folder state BEFORE child operation
        parent_state_before = await page.evaluate(f"""() => {{
            var vm = window.ProjectionLayer.buildCurrentFolderViewModel(
                window.LanvanStore.getState(),
                window.FileRepository.getFolderCache('{parent_folder}')
            );
            return {{
                count: vm.length,
                identities: vm.map(function(f) {{ return f.identity || (f.name || ''); }}),
                names: vm.map(function(f) {{ return f.name || ''; }}),
                uploadStatuses: vm.filter(function(f) {{ return f.uploading; }}).map(function(f) {{ return f.uploadStatus; }}),
                renderCount: window.RenderScheduler ? (window.RenderScheduler._renderCount || 0) : 0,
                navGen: window.LanvanStore.getState().navigationGeneration,
                upGen: window.LanvanStore.getState().uploadGeneration
            }};
        }}""")
        
        runner.record_pass("V02", f"Parent folder BEFORE: {parent_state_before['count']} items, identities: {parent_state_before['identities']}")

        # Step 3: Navigate into parent folder, then upload the SAME folder as a child
        await page.evaluate(f"() => {{ window.currentFolderPath = '{parent_folder}'; }}")
        await page.wait_for_timeout(500)

        # Upload a folder containing files — this creates parent_folder/parent_folder/files
        child_entry = f"viz_child_{secrets.token_hex(2)}.txt"
        child_file = create_dummy_file(child_entry, "child file content")
        await file_input.set_input_files(child_file)
        await page.wait_for_timeout(1000)

        # Create a subfolder manually to simulate "upload same folder"
        await page.evaluate(f"""() => {{
            var fd = new FormData();
            fd.append('folder_name', '{parent_folder}');
            fd.append('parent_path', '{parent_folder}');
            fetch('/api/files/mkdir', {{method:'POST', body:fd}});
        }}""")
        await page.wait_for_timeout(500)

        # Upload another file into the nested folder
        nested_file = create_dummy_file(f"nested_{secrets.token_hex(2)}.txt", "nested")
        await file_input.set_input_files(nested_file)
        await page.wait_for_timeout(1000)

        # Navigate into the nested child folder
        await page.evaluate(f"() => {{ window.currentFolderPath = '{parent_folder}/{parent_folder}'; }}")
        await page.wait_for_timeout(500)

        runner.record_pass("V03", f"Navigated into child: {parent_folder}/{parent_folder}")

        # Step 4: Upload more files in the CHILD folder while capturing parent state
        for i in range(2):
            f = create_dummy_file(f"child_upload_{i}_{secrets.token_hex(2)}.txt", "child")
            await file_input.set_input_files(f)
            await page.wait_for_timeout(500)

        await page.wait_for_timeout(1500)

        # Step 5: Navigate back to parent and capture state AFTER child operation
        await page.evaluate(f"() => {{ window.currentFolderPath = '{parent_folder}'; }}")
        await page.wait_for_timeout(500)

        parent_state_after = await page.evaluate(f"""() => {{
            var vm = window.ProjectionLayer.buildCurrentFolderViewModel(
                window.LanvanStore.getState(),
                window.FileRepository.getFolderCache('{parent_folder}')
            );
            return {{
                count: vm.length,
                identities: vm.map(function(f) {{ return f.identity || (f.name || ''); }}),
                names: vm.map(function(f) {{ return f.name || ''; }}),
                uploadStatuses: vm.filter(function(f) {{ return f.uploading; }}).map(function(f) {{ return f.uploadStatus; }}),
                renderCount: window.RenderScheduler ? (window.RenderScheduler._renderCount || 0) : 0,
                navGen: window.LanvanStore.getState().navigationGeneration,
                upGen: window.LanvanStore.getState().uploadGeneration
            }};
        }}""")

        runner.record_pass("V04", f"Parent folder AFTER: {parent_state_after['count']} items, identities: {parent_state_after['identities']}")

        # Step 6: Verify invariants
        # Check 1: Parent folder should have 1 extra item (the child folder itself)
        # Before had 3 files, after should have 3 files + 1 child folder = 4 items
        expected_count = parent_state_before['count'] + 1  # +1 for the nested folder
        if parent_state_after['count'] == expected_count:
            runner.record_pass("V05-A", f"Parent count correct: {parent_state_before['count']} → {parent_state_after['count']} (expected {expected_count})")
        else:
            await runner.record_failure("V05-A", "Parent count", str(expected_count), str(parent_state_after['count']))

        # Check 2: All original items should still have same identities
        orig_ids = set(parent_state_before['identities'])
        after_ids = set(parent_state_after['identities'])
        missing = orig_ids - after_ids
        if not missing:
            runner.record_pass("V05-B", "All original parent identities preserved")
        else:
            await runner.record_failure("V05-B", "Original identities preserved", "All present", f"Missing: {missing}")

        # Check 3: No upload overlays should appear on files already in parent
        upload_count = len(parent_state_after['uploadStatuses'])
        if upload_count == 0:
            runner.record_pass("V05-C", "No upload overlays contaminating parent files")
        else:
            # Accept if the only overlay is on the newly added child folder
            await runner.record_failure("V05-C", "No upload overlays", "0", str(upload_count))

        # Check 4: Render count should not have spiked dramatically
        render_delta = parent_state_after['renderCount'] - parent_state_before['renderCount']
        if render_delta < 10:
            runner.record_pass("V05-D", f"Render delta: {render_delta} (acceptable)")
        else:
            await runner.record_failure("V05-D", "Render delta < 10", str(render_delta), f"Render count spike: {render_delta}")

        # Check 5: Repository data should be consistent
        repo_check = await page.evaluate(f"""() => {{
            var cache = window.FileRepository.getFolderCache('{parent_folder}');
            return {{
                cacheCount: cache.length,
                hasChildFolder: cache.some(function(f) {{ return (f.isFolder || f.is_dir || f.is_folder) && (f.name || '').trim().toLowerCase() === '{parent_folder.lower()}'; }})
            }};
        }}""")
        
        if repo_check.get('hasChildFolder'):
            runner.record_pass("V05-E", "Repository cache shows nested folder present")
        else:
            await runner.record_failure("V05-E", "Nested folder in cache", "Present", "Missing")

        # Check 6: Console errors under DEBUG_MODE
        errors = await page.evaluate("() => window.__chaosErrors || []")
        invariant_fails = [e for e in errors if 'INVARIANT FAILED' in str(e)]
        if invariant_fails:
            await runner.record_failure("V05-F", "Zero invariant violations", "0", str(invariant_fails[:5]))
        else:
            runner.record_pass("V05-F", "Zero invariant violations")

        # Summary
        warnings = await page.evaluate("() => (window.__chaosWarnings || []).length")
        print(f"\n--- VIEW ISOLATION RESULTS ---")
        print(f"  Before: {parent_state_before['count']} items → After: {parent_state_after['count']} items")
        print(f"  Render delta: {render_delta}")
        print(f"  Warnings: {warnings}")
        print(f"  Errors: {len(errors)}")

    finally:
        await runner.stop()

    return runner.summary()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    headed = "--headed" in sys.argv
    asyncio.run(run_suite(base_url=url, headed=headed))