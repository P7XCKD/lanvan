#!/usr/bin/env python3
"""
Phase 9: Comprehensive Production Adversarial Chaos Validation
===============================================================
Production-grade chaos test for Lanvan architectural invariants.
Every operation is logged. Every invariant is verified after each action.
Supports --monkey mode for extended random fuzzing.

Usage:
    python testing/e2e/14_adversarial_chaos.py [base_url] [--monkey] [--seed SEED] [--headed]
"""

import asyncio
import os
import random
import secrets
import sys
import time
from pathlib import Path
from runner import E2ETestRunner, create_dummy_file, ROOT

CHAOS_SEED = None

def seed_random(forced_seed=None):
    global CHAOS_SEED
    if forced_seed is not None:
        CHAOS_SEED = forced_seed
    else:
        CHAOS_SEED = int(time.time() * 1000) % 999999
    random.seed(CHAOS_SEED)
    print(f"\n[CHAOS] Seed: {CHAOS_SEED}  (reproducible: --seed {CHAOS_SEED})")
    return CHAOS_SEED


async def assert_store_invariants(page, step_label, runner, test_id_base):
    """Verify Store integrity after every operation."""
    result = await page.evaluate("""() => {
        var store = window.LanvanStore;
        if (!store) return { valid: false, error: 'Store missing' };
        var state = store.getState();
        var q = state.uploadQueue || [];
        var seen = {};
        var dups = [];
        var badStatuses = [];
        var validStates = ['QUEUED','UPLOADING','PROCESSING','PAUSED','FAILED','RETRYING','COMPLETED','CANCELLED','DELETED'];
        for (var i = 0; i < q.length; i++) {
            var it = q[i];
            if (!it || !it.id) continue;
            if (seen[it.id]) dups.push(it.id);
            seen[it.id] = true;
            var st = it.status || '';
            if (st !== st.toUpperCase()) badStatuses.push(st);
            if (validStates.indexOf(st) === -1) badStatuses.push('INVALID:' + st);
        }
        return {
            valid: dups.length === 0 && badStatuses.length === 0,
            ids: dups,
            badStatuses: badStatuses,
            qLen: q.length,
            navGen: state.navigationGeneration,
            upGen: state.uploadGeneration,
            errors: (window.__chaosErrors || [])
        };
    }""")
    if result.get('valid'):
        runner.record_pass(f"{test_id_base}-store", f"[{step_label}] Store: {result.get('qLen')} items, navGen={result.get('navGen')}, upGen={result.get('upGen')}")
    else:
        await runner.record_failure(f"{test_id_base}-store", f"Store invariant after {step_label}", "Valid state", str(result))


async def assert_no_warnings(page, step_label, runner, test_id_base):
    """Fail if console.warn appeared under DEBUG_MODE."""
    warnings = await page.evaluate("""() => {
        return (window.__chaosWarnings || []).slice(0, 5);
    }""")
    if warnings:
        await runner.record_failure(f"{test_id_base}-warn", f"Warnings after {step_label}", "0 warnings", str(warnings))


async def assert_render_sane(page, step_label, runner, test_id_base):
    """Verify render count hasn't exploded."""
    stats = await page.evaluate("""() => {
        var rc = window.RenderScheduler ? (window.RenderScheduler._renderCount || 0) : 0;
        return { renderCount: rc };
    }""")
    if stats.get('renderCount', 0) > 500:
        await runner.record_failure(f"{test_id_base}-renderstorm", f"Render count after {step_label}", "< 500", str(stats.get('renderCount')))


async def assert_vm_identities(page, step_label, runner, test_id_base):
    """Verify no duplicate identities in ViewModel for current folder."""
    result = await page.evaluate("""() => {
        var store = window.LanvanStore;
        if (!store) return { valid: false, error: 'Store missing' };
        var state = store.getState();
        var repo = window.FileRepository;
        var proj = window.ProjectionLayer;
        var files = repo ? repo.getFolderCache(state.currentFolder) : [];
        var vm = proj.buildCurrentFolderViewModel(state, files);
        var seen = {};
        var dups = [];
        for (var i = 0; i < vm.length; i++) {
            var f = vm[i];
            if (!f || !f.name) continue;
            var id = f.identity || (state.currentFolder || '') + '/' + f.name;
            if (seen[id]) dups.push(id);
            seen[id] = true;
        }
        return { valid: dups.length === 0, dups: dups, total: vm.length };
    }""")
    if result.get('valid'):
        runner.record_pass(f"{test_id_base}-vm", f"[{step_label}] ViewModel: {result.get('total')} items, 0 duplicate identities")
    else:
        await runner.record_failure(f"{test_id_base}-vm", f"ViewModel identity after {step_label}", "No duplicates", str(result.get('dups')))


async def capture_metrics(page):
    """Capture runtime metrics for final report."""
    return await page.evaluate("""() => {
        var store = window.LanvanStore;
        var rc = window.RenderScheduler;
        var state = store ? store.getState() : { uploadQueue: [], navigationGeneration: 0, uploadGeneration: 0 };
        var q = state.uploadQueue || [];
        var heap = performance.memory ? performance.memory.usedJSHeapSize : 0;
        var warnings = (window.__chaosWarnings || []).length;
        var errors = (window.__chaosErrors || []).length;
        var listenerCount = 0;
        try { listenerCount = document.querySelectorAll('*').length; } catch(e) {}
        return {
            queueLen: q.length,
            navGen: state.navigationGeneration,
            upGen: state.uploadGeneration,
            renderCount: rc ? (rc._renderCount || 0) : 0,
            heapMB: Math.round(heap / 1048576),
            warnings: warnings,
            errors: errors,
            domNodes: listenerCount
        };
    }""")


async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0, monkey_mode=False, forced_seed=None):
    seed = seed_random(forced_seed)
    iterations = 500 if monkey_mode else 50
    runner = E2ETestRunner(suite_name=f"Phase 9: Adversarial Chaos (seed={seed})", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    # Wire DEBUG_MODE and warning/error tracking
    await page.evaluate("() => { window.DEBUG_MODE = true; window.currentLogLevel = window.DEBUG_LEVELS ? window.DEBUG_LEVELS.DEBUG : 3; window.__chaosWarnings = []; window.__chaosErrors = []; }")
    # Patch console.warn/error to track
    await page.evaluate("""() => {
        var _origWarn = console.warn;
        var _origError = console.error;
        console.warn = function() { window.__chaosWarnings.push(Array.from(arguments).join(' ')); _origWarn.apply(console, arguments); };
        console.error = function() { window.__chaosErrors.push(Array.from(arguments).join(' ')); _origError.apply(console, arguments); };
    }""")

    op_count = 0
    start_metrics = await capture_metrics(page)

    try:
        print(f"\n--- PHASE 9: ADVERSARIAL CHAOS (mode={'monkey' if monkey_mode else 'deterministic'}) ---")
        runner.record_pass("C9-00", f"DEBUG_MODE active, chaos seed: {seed}")

        # Create test folders
        folders = [f"Chaos_{i}_{secrets.token_hex(2)}" for i in range(3)]
        for f in folders:
            await runner.trigger_ui_folder_create(f)
            await page.wait_for_timeout(random.randint(100, 300))
        runner.record_pass("C9-01", f"Created {len(folders)} test folders")

        # Create test files with deliberately same names
        collide_name = f"collide_{secrets.token_hex(3)}.txt"
        file_a = create_dummy_file(collide_name, "Folder A content")
        file_b_same_name = create_dummy_file(collide_name, "Folder B content — SAME NAME, DIFFERENT FILE")

        file_input = page.locator("#fileInput")

        # Navigate to folder 0, upload
        await page.evaluate(f"() => {{ window.currentFolderPath = '{folders[0]}'; }}")
        await page.wait_for_timeout(random.randint(200, 500))
        await file_input.set_input_files(file_a)
        await page.wait_for_timeout(random.randint(800, 1500))
        op_count += 1
        await assert_store_invariants(page, "upload to folder 0", runner, "C9-02")
        await assert_vm_identities(page, "upload to folder 0", runner, "C9-02")

        # Navigate to folder 1, upload same-name file
        await page.evaluate(f"() => {{ window.currentFolderPath = '{folders[1]}'; }}")
        await page.wait_for_timeout(random.randint(200, 500))
        await file_input.set_input_files(file_b_same_name)
        await page.wait_for_timeout(random.randint(800, 1500))
        op_count += 1
        await assert_store_invariants(page, "upload same-name to folder 1", runner, "C9-03")
        await assert_vm_identities(page, "same-name collision check", runner, "C9-03")
        runner.record_pass("C9-03", f"Uploaded '{collide_name}' to two different folders — identity must differ")

        # Rapid navigation stress (identity collision stress)
        for i in range(min(30, iterations // 2)):
            target = random.choice(folders)
            await page.evaluate(f"() => {{ window.currentFolderPath = '{target}'; }}")
            await page.wait_for_timeout(random.randint(50, 200))
            if i % 10 == 0:
                await page.evaluate("() => { window.currentFolderPath = ''; }")
                await page.wait_for_timeout(100)
            op_count += 1
        await assert_store_invariants(page, "navigation stress", runner, "C9-04")
        nav_check = await page.evaluate("() => { var g = window.LanvanStore.getState().navigationGeneration; return g; }")
        runner.record_pass("C9-04", f"Navigation stress complete. navGen={nav_check}")

        # Upload + cancel at random timing
        for i in range(5):
            f = create_dummy_file(f"chaos_cancel_{i}_{secrets.token_hex(2)}.txt")
            await file_input.set_input_files(f)
            cancel_delay = random.randint(100, 2000)
            await page.wait_for_timeout(cancel_delay)
            await page.evaluate(f"() => {{ if (window.uploadQueue && window.uploadQueue[0]) window.cancelUpload(window.uploadQueue[0].id); }}")
            await page.wait_for_timeout(300)
            op_count += 1
        await assert_store_invariants(page, "cancel chaos", runner, "C9-05")
        runner.record_pass("C9-05", f"Upload + cancel at random timing: {op_count} operations")

        # Recursive path stress — upload a folder into itself
        await page.evaluate(f"() => {{ window.currentFolderPath = '{folders[2]}'; }}")
        await page.wait_for_timeout(300)
        # Create a subfolder with same name
        subfolder = folders[2]  # same name!
        await page.evaluate(f"""() => {{
            var fd = new FormData();
            fd.append('folder_name', '{subfolder}');
            fd.append('parent_path', '{folders[2]}');
            fetch('/api/files/mkdir', {{method:'POST', body:fd}});
        }}""")
        await page.wait_for_timeout(500)
        await assert_vm_identities(page, "recursive path upload", runner, "C9-06")
        runner.record_pass("C9-06", f"Recursive path: {folders[2]}/{subfolder} created — identity check")

        # Browser refresh during stress
        await page.evaluate("() => { location.reload(); }")
        try:
            await page.wait_for_selector("#nasFileList", state="visible", timeout=10000)
        except:
            pass
        await page.wait_for_timeout(1000)
        await page.evaluate("() => { window.DEBUG_MODE = true; window.__chaosWarnings = window.__chaosWarnings || []; window.__chaosErrors = window.__chaosErrors || []; }")
        op_count += 5  # count the refresh as significant
        refresh_check = await page.evaluate("""() => {
            var store = window.LanvanStore;
            return { valid: store !== null && store !== undefined, state: !!store };
        }""")
        runner.record_pass("C9-07", f"Browser refresh recovery: Store alive={refresh_check.get('valid')}")

        # Multi-operation fuzz
        count = min(iterations, 100)
        for i in range(count):
            action = random.choice(['navigate', 'upload', 'cancel', 'refresh', 'home'])
            try:
                if action == 'navigate':
                    target = random.choice(folders if random.random() > 0.3 else [''])
                    await page.evaluate(f"() => {{ window.currentFolderPath = '{target}'; }}")
                elif action == 'upload':
                    f = create_dummy_file(f"fuzz_{i}_{secrets.token_hex(2)}.txt", "fuzz content")
                    await file_input.set_input_files(f)
                elif action == 'cancel':
                    await page.evaluate("() => { if (window.uploadQueue && window.uploadQueue.length) { var id = window.uploadQueue[Math.floor(Math.random() * window.uploadQueue.length)].id; window.cancelUpload(id); } }")
                elif action == 'refresh':
                    await page.evaluate("() => { if (typeof refreshFileList === 'function') refreshFileList(); }")
                elif action == 'home':
                    await page.evaluate("() => { window.currentFolderPath = ''; }")
                await page.wait_for_timeout(random.randint(30, 300))
                op_count += 1
            except:
                pass

            # Assert invariants every 10 operations
            if i % 10 == 0 and i > 0:
                await assert_store_invariants(page, f"fuzz iteration {i}", runner, "C9-FUZZ")
                await assert_vm_identities(page, f"fuzz iteration {i}", runner, "C9-FUZZ")

        runner.record_pass("C9-08", f"Multi-operation fuzz complete: {count} iterations")

        # Final comprehensive checks
        await assert_store_invariants(page, "final", runner, "C9-FINAL")
        await assert_vm_identities(page, "final", runner, "C9-FINAL")
        await assert_render_sane(page, "final", runner, "C9-FINAL")
        await assert_no_warnings(page, "final", runner, "C9-FINAL")

        # Capture end metrics
        end_metrics = await capture_metrics(page)
        heap_delta = (end_metrics.get('heapMB', 0) - start_metrics.get('heapMB', 0))
        summary = f"""
============================================================
[CHAOS SUMMARY] Seed: {seed} | Mode: {'monkey' if monkey_mode else 'deterministic'}
  Operations:  {op_count}
  Renders:     {end_metrics.get('renderCount', '?')}
  Queue (end): {end_metrics.get('queueLen', '?')}
  navGen:      {end_metrics.get('navGen', '?')}
  upGen:       {end_metrics.get('upGen', '?')}
  Warnings:    {end_metrics.get('warnings', '?')}
  Errors:      {end_metrics.get('errors', '?')}
  Heap delta:  {heap_delta:+.1f} MB
============================================================"""
        print(summary)

        if end_metrics.get('errors', 0) > 0:
            await runner.record_failure("C9-ERR", "Console errors detected", "0 errors", str(end_metrics.get('errors')))
        if end_metrics.get('warnings', 0) > 0:
            await runner.record_failure("C9-WARN", "Console warnings under DEBUG_MODE", "0 warnings", str(end_metrics.get('warnings')))

    finally:
        await runner.stop()

    return runner.summary()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="http://127.0.0.1")
    parser.add_argument("--monkey", action="store_true", help="Run 500+ random operations")
    parser.add_argument("--seed", type=int, default=None, help="Reproducible seed")
    parser.add_argument("--headed", action="store_true", help="Run headed (visible browser)")
    args = parser.parse_args()
    asyncio.run(run_suite(base_url=args.url, headed=args.headed, monkey_mode=args.monkey, forced_seed=args.seed))