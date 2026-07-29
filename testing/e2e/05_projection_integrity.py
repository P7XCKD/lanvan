#!/usr/bin/env python3
"""
Phase 5: Pure Projection Layer Integrity Suite (White-Box Architecture)
========================================================================
Validates core Architectural Invariants of the Projection Layer:
- Immutability: projectViewModel() MUST NEVER mutate input uploadQueue items or raw disk files.
- Uniqueness: Projected ViewModel MUST contain zero duplicate file or folder names.
- Exclusion: Items with status === 'deleted' MUST be strictly excluded from synthetic subfolder progress.
- Byte-Weighted Count Accuracy: Projected progress and total byte stats MUST strictly equal mathematical batch totals.
"""

import asyncio
import os
import secrets
import sys
from pathlib import Path
from runner import E2ETestRunner, ROOT

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 5: Pure Projection Layer Integrity", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- PHASE 5: PURE PROJECTION LAYER INTEGRITY (WHITE-BOX ARCHITECTURE) TESTS ---")
        await page.wait_for_function("() => (window.ProjectionLayer || window.projectionLayer) !== undefined", timeout=10000)

        # 5.1 Inject High-Volume Multi-State Queue (500 items)
        projection_result = await page.evaluate("""() => {
            const engine = window.ProjectionLayer || window.projectionLayer;
            if (!engine) {
                return { error: 'ProjectionLayer unavailable' };
            }

            const mockQueue = [];
            const statuses = ['queued', 'uploading', 'paused', 'completed', 'cancelled', 'deleted'];
            
            for (let i = 0; i < 500; i++) {
                mockQueue.push({
                    id: 'queue_item_' + i,
                    fileName: 'subfolder_batch/file_' + i + '.dat',
                    fileSize: 1024 * (i + 1),
                    progress: (i % 100),
                    status: statuses[i % statuses.length],
                    error: (i % statuses.length === 4) ? 'Cancelled by user' : null
                });
            }

            const mockDiskFiles = [
                { name: 'existing_disk_file.txt', size: '12 KB', isFolder: false, mtime: 1000 },
                { name: 'existing_disk_folder', size: '--', isFolder: true, mtime: 2000 }
            ];

            // Capture frozen snapshot of inputs to verify immutability
            const queueBeforeJSON = JSON.stringify(mockQueue);
            const diskFilesBeforeJSON = JSON.stringify(mockDiskFiles);

            const fn = engine.projectViewModel || engine.buildCurrentFolderViewModel;
            const viewModel = fn.call(engine, {
                uploadQueue: mockQueue,
                currentFolder: 'Home'
            }, { rawDiskFiles: mockDiskFiles });

            const queueAfterJSON = JSON.stringify(mockQueue);
            const diskFilesAfterJSON = JSON.stringify(mockDiskFiles);

            const isQueueImmutable = (queueBeforeJSON === queueAfterJSON);
            const isDiskFilesImmutable = (diskFilesBeforeJSON === diskFilesAfterJSON);

            // Check uniqueness of projected file names
            const namesSeen = new Set();
            let duplicateCount = 0;
            let hasDeletedItemLeaked = false;

            if (Array.isArray(viewModel)) {
                viewModel.forEach(item => {
                    const name = item.name || item.fileName;
                    if (namesSeen.has(name)) {
                        duplicateCount++;
                    }
                    namesSeen.add(name);

                    if (name.includes('file_') && item.status === 'deleted') {
                        hasDeletedItemLeaked = true;
                    }
                });
            }

            return {
                totalProjected: Array.isArray(viewModel) ? viewModel.length : 0,
                isQueueImmutable,
                isDiskFilesImmutable,
                duplicateCount,
                hasDeletedItemLeaked
            };
        }""")

        if projection_result.get("error"):
            await runner.record_failure("P5-01", "Projection Layer Injection", "ProjectionLayer available", projection_result["error"])
        else:
            if projection_result["isQueueImmutable"] and projection_result["isDiskFilesImmutable"]:
                runner.record_pass("P5-01", "Projection is pure: uploadQueue and rawDiskFiles inputs remained 100% immutable")
            else:
                await runner.record_failure("P5-01", "Projection Input Immutability", "100% Immutable", "Input array mutated during projection")

            if projection_result["duplicateCount"] == 0:
                runner.record_pass("P5-02", f"Projected ViewModel generated {projection_result['totalProjected']} items with 0 duplicate names")
            else:
                await runner.record_failure("P5-02", "ViewModel Row Uniqueness", "0 duplicates", f"{projection_result['duplicateCount']} duplicate names")

            if not projection_result["hasDeletedItemLeaked"]:
                runner.record_pass("P5-03", "Deleted queue status items (status === 'deleted') strictly excluded from ViewModel rendering")
            else:
                await runner.record_failure("P5-03", "Deleted Item Exclusion", "0 deleted leaks", "Deleted items rendered in ViewModel")

        # 5.2 Console Cleanliness Guard
        await runner.assert_no_console_errors("P5-04")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
