#!/usr/bin/env python3
"""
Master E2E Level Runner
=======================
Executes all modular Playwright level test suites in sequence:
- Level 1: Smoke & Normal User
- Level 4: Navigation Chaos
- Level 3: Concurrency & Upload TargetDir
- Level 10: Chaos Monkey & Edge Cases

Usage:
    python run_all_levels.py [--url URL] [--headed] [--slow 200]
"""

import asyncio
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import importlib

async def main():
    parser = argparse.ArgumentParser(description="Lanvan Playwright Master E2E Runner")
    parser.add_argument("--url", default="http://127.0.0.1", help="Lanvan active server URL")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    parser.add_argument("--slow", type=int, default=0, help="Slow-motion delay in ms")
    args = parser.parse_args()

    suites = [
        ("01_smoke", "Level 1: Real User UI Smoke Tests"),
        ("02_navigation_chaos", "Level 4: Real UI Navigation Chaos Tests"),
        ("03_upload_chaos", "Level 3: Upload Chaos & Queue State Tests"),
        ("05_network_browser_chaos", "Level 5: Network & Browser Chaos Tests"),
        ("07_multitab", "Level 7: Multi-Tab Real-Time Sync Tests"),
        ("10_chaos_monkey", "Level 10: Unscripted Real UI Chaos Monkey")
    ]

    all_passed = True
    print("=" * 60)
    print(" [LANVAN PLAYWRIGHT MODULAR E2E MASTER TEST RUNNER]")
    print("=" * 60)

    for mod_name, suite_label in suites:
        print(f"\n[RUN] Running {suite_label}...")
        try:
            mod = importlib.import_module(mod_name)
            success = await mod.run_suite(base_url=args.url, headed=args.headed, slow_mo=args.slow)
            if not success:
                all_passed = False
        except Exception as e:
            print(f"[FAIL] Error executing {suite_label}: {e}")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print(" [OK] ALL MODULAR E2E PLAYWRIGHT SUITES PASSED (100% SUCCESS)!")
    else:
        print(" [FAIL] SOME E2E PLAYWRIGHT SUITES FAILED. SEE ARTIFACTS FOR TRACES & SCREENSHOTS.")
    print("=" * 60 + "\n")

    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    asyncio.run(main())
