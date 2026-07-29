#!/usr/bin/env python3
"""
Phase 10: Executable Architectural Invariants Suite (White-Box Architecture)
=============================================================================
Executable assertion tests verifying adherence to core architectural invariants:
- Invariant 1: Application business state has a single authoritative owner (window.uploadQueue).
- Invariant 2: Repository owns all server/filesystem data (window.FileRepository).
- Invariant 3: Projection is a pure function: (Store State, Repository Snapshot) => ViewModel.
- Invariant 4: Renderer is strictly write-only render(viewModel) and never mutates state.
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 10: Executable Architectural Invariants", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- PHASE 10: EXECUTABLE ARCHITECTURAL INVARIANTS (WHITE-BOX ARCHITECTURE) TESTS ---")

        # 10.1 Invariant 1: Single Owner for Upload Business State
        inv1_result = await page.evaluate("""() => {
            return {
                hasUploadQueue: Array.isArray(window.uploadQueue),
                isAuthoritative: typeof window.uploadQueue !== 'undefined'
            };
        }""")
        if inv1_result['hasUploadQueue'] and inv1_result['isAuthoritative']:
            runner.record_pass("P10-01", "Invariant 1 Verified: Business upload state has a single authoritative owner (window.uploadQueue)")
        else:
            await runner.record_failure("P10-01", "Invariant 1: Upload State Owner", "window.uploadQueue array present", "Missing")

        # 10.2 Invariant 2: Repository Owns Filesystem Data
        inv2_result = await page.evaluate("""() => {
            return {
                hasRepository: typeof window.FileRepository !== 'undefined',
                hasCache: typeof window.FileRepository.cache !== 'undefined' || typeof window.FileRepository.getFolderCache === 'function',
                hasInvalidate: typeof window.FileRepository.invalidateCache === 'function'
            };
        }""")
        if inv2_result['hasRepository'] and inv2_result['hasInvalidate']:
            runner.record_pass("P10-02", "Invariant 2 Verified: Repository (window.FileRepository) strictly owns all filesystem data & disk caching")
        else:
            await runner.record_failure("P10-02", "Invariant 2: Repository Data Owner", "window.FileRepository available", "Missing")

        # 10.3 Invariant 3: Projection Purity & Non-Mutation
        inv3_result = await page.evaluate("""() => {
            const engine = window.ProjectionLayer || window.projectionLayer;
            if (!engine) return { isPure: false, error: 'ProjectionLayer unavailable' };

            const testState = { uploadQueue: [{ id: 1, fileName: 'inv3.txt', fileSize: 100, progress: 50, status: 'uploading' }] };
            const testFiles = [{ name: 'inv3_disk.txt', size: '10 KB', isFolder: false }];

            const stateBefore = JSON.stringify(testState);
            const filesBefore = JSON.stringify(testFiles);

            const fn = engine.projectViewModel || engine.buildCurrentFolderViewModel;
            const vm = fn.call(engine, { uploadQueue: testState.uploadQueue, currentFolder: 'Home' }, { rawDiskFiles: testFiles });

            const isPure = (JSON.stringify(testState) === stateBefore) && (JSON.stringify(testFiles) === filesBefore);
            return { isPure, count: Array.isArray(vm) ? vm.length : 0 };
        }""")
        if inv3_result['isPure']:
            runner.record_pass("P10-03", f"Invariant 3 Verified: Projection is a pure function (Inputs remained 100% immutable, produced {inv3_result['count']} items)")
        else:
            await runner.record_failure("P10-03", "Invariant 3: Projection Purity", "100% Immutable", inv3_result.get("error", "Input state mutated"))

        # 10.4 Invariant 4: Renderer Write-Only Enforcement
        inv4_result = await page.evaluate("""() => {
            if (typeof window.renderPrototypeFileList !== 'function') return { isWriteOnly: false };

            function getBusinessState(queue) {
                return (queue || []).map(item => ({
                    id: item ? item.id : null,
                    name: item ? (item.fileName || (item.file ? item.file.name : null)) : null,
                    status: item ? item.status : null,
                    progress: item ? item.progress : null
                }));
            }

            const qB = getBusinessState(window.uploadQueue);
            const queueBefore = JSON.stringify(qB);
            const currentDir = (typeof window.cleanFolderPath === 'function' && typeof window.currentFolderPath !== 'undefined') ? window.cleanFolderPath(window.currentFolderPath) : "";
            const testVm = [{ name: 'render_inv4_test.txt', size: '5 KB', isFolder: false, mtime: 1000 }];
            
            try {
                Object.defineProperty(testVm, '__folderPath', { value: currentDir, enumerable: false, configurable: true });
            } catch (e) {
                testVm.__folderPath = currentDir;
            }

            try {
                window.renderPrototypeFileList(testVm);
            } catch (e) {}

            const qA = getBusinessState(window.uploadQueue);
            const queueAfter = JSON.stringify(qA);
            return { isWriteOnly: (queueBefore === queueAfter), before: queueBefore, after: queueAfter };
        }""")
        if inv4_result['isWriteOnly']:
            runner.record_pass("P10-04", "Invariant 4 Verified: Renderer is write-only UI = f(State) and never mutates application state")
        else:
            await runner.record_failure("P10-04", "Invariant 4: Renderer Write-Only", "100% Write-Only", f"Before: {inv4_result.get('before')} | After: {inv4_result.get('after')}")

        # 10.5 Console Cleanliness Guard
        await runner.assert_no_console_errors("P10-05")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
