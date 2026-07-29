#!/usr/bin/env python3
"""
Lanvan Playwright E2E Master Harness & Base Runner
==================================================
Manages Playwright browser instance, console log capturing, JS exception tracking,
screenshots on failure, trace ZIP exports, and structured failure reporting.
"""

import asyncio
import os
import sys
import time
import secrets
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

TEST_FILES_DIR = ROOT / "testing" / "e2e" / "test_data"
TEST_FILES_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACTS_DIR = ROOT / "testing" / "e2e" / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def create_dummy_file(filename, content="Dummy test content for Playwright E2E testing"):
    filePath = TEST_FILES_DIR / filename
    filePath.write_text(content, encoding="utf-8")
    return str(filePath)

class E2ETestRunner:
    def __init__(self, suite_name="E2E Suite", headed=False, slow_mo=0, base_url="http://127.0.0.1"):
        self.suite_name = suite_name
        self.headed = headed
        self.slow_mo = slow_mo
        self.base_url = base_url.rstrip('/')
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.console_logs = []
        self.js_errors = []
        self.network_errors = []
        self.failures = []
        self.passes = 0

    async def start(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(
            headless=not self.headed,
            slow_mo=self.slow_mo,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            accept_downloads=True
        )
        # Enable trace recording
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)

        self.page = await self.context.new_page()

        # Wire up console & exception listeners
        self.page.on("console", lambda msg: self.console_logs.append(f"[{msg.type.upper()}] {msg.text}"))
        self.page.on("pageerror", lambda err: self.js_errors.append(str(err)))
        self.page.on("requestfailed", lambda req: self.network_errors.append(f"{req.method} {req.url} -> {req.failure}"))

        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(1000)

    async def stop(self):
        if self.context:
            trace_path = ARTIFACTS_DIR / f"trace_{self.suite_name.lower().replace(' ', '_')}.zip"
            await self.context.tracing.stop(path=str(trace_path))
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()

    async def assert_no_console_errors(self, test_id):
        critical_errors = [
            log for log in self.console_logs
            if "[ERROR]" in log and "lucide" not in log and "ERR_INTERNET_DISCONNECTED" not in log and "Failed to fetch" not in log and "Server shutdown" not in log and "Server connection failed" not in log
        ]
        if critical_errors or self.js_errors:
            err_msg = f"Console/JS Exceptions found: {self.js_errors} | Console: {critical_errors[:3]}"
            await self.record_failure(test_id, "Console Cleanliness", "Uncaught JavaScript Exception or Console Error", err_msg)
            return False
        return True

    async def record_failure(self, test_id, feature, expected, actual, severity="High", priority="P1"):
        screenshot_file = ARTIFACTS_DIR / f"fail_{test_id}_{secrets.token_hex(2)}.png"
        try:
            await self.page.screenshot(path=str(screenshot_file), full_page=True)
        except Exception:
            pass

        failure_report = {
            "test_id": test_id,
            "severity": severity,
            "priority": priority,
            "feature": feature,
            "expected": expected,
            "actual": actual,
            "console_errors": self.console_logs[-5:],
            "js_errors": self.js_errors[-3:],
            "screenshot": str(screenshot_file)
        }
        self.failures.append(failure_report)
        print(f"\n[FAIL] [{test_id}] {feature}")
        print(f"   Expected: {expected}")
        print(f"   Actual:   {actual}")
        print(f"   Screenshot saved: {screenshot_file}")

    def record_pass(self, test_id, feature):
        self.passes += 1
        print(f"  [OK] [{test_id}] {feature}")

    def summary(self):
        total = self.passes + len(self.failures)
        print(f"\n{'='*60}")
        print(f"   {self.suite_name.upper()} EXECUTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Checks: {total} | Passed: {self.passes} | Failed: {len(self.failures)}")
        if self.failures:
            print(f"\n--- FAILURE BREAKDOWN ---")
            for f in self.failures:
                print(f"• [{f['test_id']}] {f['feature']}: {f['actual']} (Screenshot: {f['screenshot']})")
        print(f"{'='*60}\n")
        return len(self.failures) == 0
