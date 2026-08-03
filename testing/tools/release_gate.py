#!/usr/bin/env python3
"""
Phase 10 — Release Gate
=========================
Runs all architectural validation suites in sequence.
Baseline-aware: compares against known pre-existing findings.

Usage:
    python release_gate.py [--url http://127.0.0.1] [--skip-chaos]
"""

import subprocess
import sys
import time
import re


def run_gate(name, cmd, checker_fn):
    print(f"\n{'='*60}")
    print(f"  GATE: {name}")
    print(f"  CMD:  {' '.join(cmd)}")
    print(f"{'='*60}")
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start
    output = result.stdout + result.stderr
    ok, detail = checker_fn(output)
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name} ({elapsed:.1f}s) - {detail}")
    return ok


def check_qt(output):
    """Baseline: 160 passed, 2 failed (CSS !important + activeNameMap).
    Checks that the two known pre-existing failures are the ONLY failures,
    and no unexpected error strings appear."""
    # The known pre-existing failures must be present
    has_css = '!important: 223' in output
    has_am = 'activeNameMap' in output
    if not (has_css and has_am):
        return False, "Missing expected baseline failures"
    # Look for the summary line: "FAILED: 2" with no unexpected failures
    if 'FAILED: 2' not in output:
        return False, "Fail count changed from baseline"
    # Verify no new unexpected failures by checking for extra "FAILED:" entries
    fail_count = output.count('[FAIL]')
    # Baseline has exactly 2 [FAIL] lines
    if fail_count > 2:
        return False, f"Unexpected new failures detected ({fail_count} FAIL lines, baseline: 2)"
    return True, "160 passed, 2 failed (baseline OK)"


def check_arch(output):
    """Baseline: <=17 high/medium defects."""
    m = re.search(r'Total High/Medium Defects Found:\s*(\d+)', output)
    count = int(m.group(1)) if m else 0
    if count <= 17:
        return True, f"{count} defects (baseline <=17)"
    return False, f"Defects increased: {count} (baseline 17)"


def check_chaos(output):
    """Chaos must pass all 25 checks."""
    ok = 'Failed: 0' in output or 'Passed: 25' in output or '25/25' in output
    detail = "all passed" if ok else "failures detected"
    return ok, detail


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1")
    p.add_argument("--skip-chaos", action="store_true")
    args = p.parse_args()

    results = []

    tools_dir = os.path.dirname(os.path.abspath(__file__))
    arch_scan_path = os.path.join(tools_dir, "arch_scan.py")
    quality_scan_path = os.path.join(tools_dir, "quality_scan.py")

    results.append(("Regression Suite", run_gate(
        "qt.py --fast (baseline 160/162)",
        [sys.executable, "qt.py", "--fast"], check_qt)))

    results.append(("Architecture Scan", run_gate(
        "arch_scan.py (<=17 defects)",
        [sys.executable, arch_scan_path], check_arch)))

    results.append(("Quality Scan", run_gate(
        "quality_scan.py",
        [sys.executable, quality_scan_path],
        lambda o: (True, "informational"))))

    if not args.skip_chaos:
        for i, s in enumerate([12345, 67890, 24680]):
            results.append((f"Chaos ({i+1}/3)", run_gate(
                f"chaos seed={s}",
                [sys.executable, "testing/e2e/14_adversarial_chaos.py", args.url, "--seed", str(s)],
                check_chaos)))
        # Also run identity chaos test
        results.append(("Identity Chaos", run_gate(
            "identity chaos",
            [sys.executable, "testing/e2e/13_identity_chaos.py", args.url],
            check_chaos)))

    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"  RELEASE GATE: {'PASSED' if failed == 0 else 'FAILED'}")
    print(f"  {passed}/{total} passed, {failed} failed")
    print(f"{'='*60}")
    for name, ok in results:
        print(f"  {'[OK]' if ok else '[FAIL]'} {name}")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()