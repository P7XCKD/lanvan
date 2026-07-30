#!/usr/bin/env python3
"""
Phase 13: Dedicated Resume Operator Precedence Regression Test
================================================================
Verifies that resuming a paused upload in a subfolder:
- Resumes all paused uploads within the target folder (Folder A).
- Does NOT resume paused uploads in Folder B.
- Does NOT resume paused uploads in Root ("").
- Handles nested folder uploads correctly.
- Prevents cross-folder leakage.
"""

import asyncio
import sys
from runner import E2ETestRunner

async def run_suite(base_url="http://127.0.0.1", headed=False, slow_mo=0):
    runner = E2ETestRunner(suite_name="Phase 13: Resume Operator Precedence Regression", headed=headed, slow_mo=slow_mo, base_url=base_url)
    await runner.start()
    page = runner.page

    try:
        print("\n--- PHASE 13: RESUME OPERATOR PRECEDENCE REGRESSION TESTS ---")
        await page.goto(f"{base_url}/?folder=", wait_until="networkidle")
        await page.wait_for_selector("#nasFileList, #nasGridList", state="visible", timeout=10000)

        # Populate window.uploadQueue via Store dispatches with items across multiple folders
        setup_res = await page.evaluate("""() => {
            if (!window.LanvanStore) return { success: false, reason: "Store missing" };

            // Stub network transfer trigger for unit test stability
            window.uploadLargeFileChunked = function() {};

            // Reset queue
            window.LanvanStore.dispatch("SYNC_QUEUE", { queue: [] });

            // Folder A items
            window.LanvanStore.dispatch("ADD_UPLOAD_ITEM", {
                item: { id: "item_a1", fileName: "a1.txt", fileSize: 1000, targetDir: "Folder_A", status: "PAUSED", progress: 20 }
            });
            window.LanvanStore.dispatch("ADD_UPLOAD_ITEM", {
                item: { id: "item_a2", fileName: "a2.txt", fileSize: 1000, targetDir: "Folder_A", status: "PAUSED", progress: 30 }
            });

            // Folder B items
            window.LanvanStore.dispatch("ADD_UPLOAD_ITEM", {
                item: { id: "item_b1", fileName: "b1.txt", fileSize: 1000, targetDir: "Folder_B", status: "PAUSED", progress: 10 }
            });
            window.LanvanStore.dispatch("ADD_UPLOAD_ITEM", {
                item: { id: "item_b2", fileName: "b2.txt", fileSize: 1000, targetDir: "Folder_B", status: "PAUSED", progress: 15 }
            });

            // Root item
            window.LanvanStore.dispatch("ADD_UPLOAD_ITEM", {
                item: { id: "item_root", fileName: "root.txt", fileSize: 1000, targetDir: "", status: "PAUSED", progress: 40 }
            });

            // Nested Folder A/Sub items
            window.LanvanStore.dispatch("ADD_UPLOAD_ITEM", {
                item: { id: "item_sub1", fileName: "sub1.txt", fileSize: 1000, targetDir: "Folder_A/Sub", status: "PAUSED", progress: 50 }
            });
            window.LanvanStore.dispatch("ADD_UPLOAD_ITEM", {
                item: { id: "item_sub2", fileName: "sub2.txt", fileSize: 1000, targetDir: "Folder_A/Sub", status: "PAUSED", progress: 60 }
            });

            return { success: true, count: window.uploadQueue.length };
        }""")

        if not setup_res.get("success"):
            await runner.record_failure("P13-01", "Setup Upload Queue", "Queue populated", setup_res.get("reason"))
            return runner.summary()

        runner.record_pass("P13-01", f"Test queue populated with {setup_res['count']} items across Folder_A, Folder_B, Root, and Folder_A/Sub")

        # TEST 1: Resume item_a1 in Folder_A
        # Expectation: item_a1 AND item_a2 resume to UPLOADING. Folder_B, Root, and Folder_A/Sub remain PAUSED.
        res_test1 = await page.evaluate("""() => {
            if (!window.LanvanUploadEngine || typeof window.LanvanUploadEngine.resumeUploadItem !== 'function') {
                return { error: "LanvanUploadEngine.resumeUploadItem missing" };
            }

            window.LanvanUploadEngine.resumeUploadItem("item_a1");

            const q = window.uploadQueue || [];
            const getStatus = (id) => {
                const found = q.find(i => i && i.id === id);
                return found ? found.status : null;
            };

            return {
                a1: getStatus("item_a1"),
                a2: getStatus("item_a2"),
                b1: getStatus("item_b1"),
                b2: getStatus("item_b2"),
                root: getStatus("item_root"),
                sub1: getStatus("item_sub1"),
                sub2: getStatus("item_sub2")
            };
        }""")

        if res_test1.get("error"):
            await runner.record_failure("P13-02", "Resume Folder_A Item", "No error", res_test1["error"])
        else:
            is_a1_up = res_test1["a1"] == "UPLOADING"
            is_a2_up = res_test1["a2"] == "UPLOADING"
            is_b1_paused = res_test1["b1"] == "PAUSED"
            is_b2_paused = res_test1["b2"] == "PAUSED"
            is_root_paused = res_test1["root"] == "PAUSED"
            is_sub1_paused = res_test1["sub1"] == "PAUSED"
            is_sub2_paused = res_test1["sub2"] == "PAUSED"

            if is_a1_up and is_a2_up and is_b1_paused and is_b2_paused and is_root_paused and is_sub1_paused and is_sub2_paused:
                runner.record_pass("P13-02", "Resuming Folder_A resumed item_a1 & item_a2 together while Folder_B, Root, and Folder_A/Sub remained PAUSED")
            else:
                await runner.record_failure("P13-02", "Folder_A Resume Isolation", "Folder_A UPLOADING, rest PAUSED", str(res_test1))

        # TEST 2: Resume item_sub1 in nested folder Folder_A/Sub
        # Expectation: item_sub1 & item_sub2 resume to UPLOADING. Folder_B & Root remain PAUSED.
        res_test2 = await page.evaluate("""() => {
            window.LanvanUploadEngine.resumeUploadItem("item_sub1");

            const q = window.uploadQueue || [];
            const getStatus = (id) => {
                const found = q.find(i => i && i.id === id);
                return found ? found.status : null;
            };

            return {
                b1: getStatus("item_b1"),
                b2: getStatus("item_b2"),
                root: getStatus("item_root"),
                sub1: getStatus("item_sub1"),
                sub2: getStatus("item_sub2")
            };
        }""")

        if res_test2.get("sub1") == "UPLOADING" and res_test2.get("sub2") == "UPLOADING" and res_test2.get("b1") == "PAUSED" and res_test2.get("b2") == "PAUSED" and res_test2.get("root") == "PAUSED":
            runner.record_pass("P13-03", "Nested folder Folder_A/Sub resumed cleanly without affecting Folder_B or Root")
        else:
            await runner.record_failure("P13-03", "Nested Folder Resume Isolation", "Nested UPLOADING, Folder_B & Root PAUSED", str(res_test2))

        # TEST 3: Resume item_root in Root ("")
        # Expectation: item_root resumes. Folder_B items remain PAUSED.
        res_test3 = await page.evaluate("""() => {
            window.LanvanUploadEngine.resumeUploadItem("item_root");

            const q = window.uploadQueue || [];
            const getStatus = (id) => {
                const found = q.find(i => i && i.id === id);
                return found ? found.status : null;
            };

            return {
                b1: getStatus("item_b1"),
                b2: getStatus("item_b2"),
                root: getStatus("item_root")
            };
        }""")

        if res_test3.get("root") == "UPLOADING" and res_test3.get("b1") == "PAUSED" and res_test3.get("b2") == "PAUSED":
            runner.record_pass("P13-04", "Root upload resumed while Folder_B items remained PAUSED")
        else:
            await runner.record_failure("P13-04", "Root Resume Isolation", "Root UPLOADING, Folder_B PAUSED", str(res_test3))

        # Clean up queue
        await page.evaluate("""() => {
            if (window.LanvanStore) window.LanvanStore.dispatch("SYNC_QUEUE", { queue: [] });
        }""")

    finally:
        await runner.stop()

    return runner.summary()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1"
    asyncio.run(run_suite(base_url=url))
