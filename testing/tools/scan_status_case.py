"""
Scanner & Auto-Fixer: Finds all upload status string comparisons in JS files
to identify case mismatches with the normalization direction used by the
uploadQueue setter at main-app.js:352.

If the setter normalizes to .toLowerCase(), all comparisons should be lowercase.
If the setter normalizes to .toUpperCase(), all comparisons should be UPPERCASE.

Usage:
  python scan_status_case.py           # Scan only (report mismatches)
  python scan_status_case.py --fix     # Scan + auto-fix mismatches
"""

import os
import re
import sys
import shutil

JS_DIR = "app/static/js"
SETTER_FILE = os.path.join(JS_DIR, "main-app.js")

# Patterns to find status comparisons
PATTERNS = [
    (r'\.status\s*===?\s*["\'](uploading|queued|processing|paused|completed|cancelled|deleted|error|failed)["\']',
     "direct_status_check"),
    (r"status\s*:?\s*['\"](uploading|queued|processing|paused|completed|cancelled|deleted|error|failed)['\"]",
     "status_assignment"),
    (r"\.includes\(\s*['\"](uploading|queued|processing|paused|completed|cancelled|deleted|error|failed)['\"]",
     "array_includes"),
]

# Known safe patterns that should NOT be auto-fixed
SAFE_PATTERNS = [
    r'status\s*:\s*['"'](?:uploading|queued|processing|paused|completed|cancelled|deleted|error|failed)['"']\s*[}\],]',
    r"['"'](?:uploading|queued|processing|paused|completed|cancelled|deleted|error|failed)['"']\s*:\s*",
]


def detect_normalization_direction():
    """Detect whether the setter normalizes to lowercase or uppercase."""
    if not os.path.exists(SETTER_FILE):
        return "lowercase"  # default safe assumption

    with open(SETTER_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for .toLowerCase() in the setter
    if ".toUpperCase()" in content:
        return "uppercase"
    elif ".toLowerCase()" in content:
        return "lowercase"
    else:
        # Default check
        if re.search(r'\.status\s*=\s*[^;]+\.toUpperCase\(\)', content):
            return "uppercase"
        if re.search(r'\.status\s*=\s*[^;]+\.toLowerCase\(\)', content):
            return "lowercase"
    return "lowercase"


def get_expected_case(normalization):
    """Get the expected case for status strings."""
    return "lowercase" if normalization == "lowercase" else "UPPERCASE"


def scan_file(filepath, normalization):
    """Scan a file for status case mismatches."""
    expected_lower = normalization == "lowercase"
    lines_found = []

    with open(filepath, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            for pattern, pat_type in PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for m in matches:
                    status_value = m.group(1)
                    # Check if the case matches the expected direction
                    is_lower = status_value.islower()
                    mismatch = (expected_lower and not is_lower) or (not expected_lower and is_lower)
                    if mismatch:
                        lines_found.append((lineno, line.rstrip(), status_value, pat_type, m.start(), m.end()))
    return lines_found


def fix_file(filepath, mismatches, normalization):
    """Auto-fix mismatches in a file."""
    expected_lower = normalization == "lowercase"

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed_count = 0
    for lineno, line, status_value, pat_type, start, end in mismatches:
        # Convert status to expected case
        new_status = status_value.lower() if expected_lower else status_value.upper()
        if new_status == status_value:
            continue

        # Replace in the line
        old_line = lines[lineno - 1]
        new_line = old_line.replace(f"'{status_value}'", f"'{new_status}'")
        new_line = new_line.replace(f'"{status_value}"', f'"{new_status}"')

        if new_line != old_line:
            lines[lineno - 1] = new_line
            fixed_count += 1

    if fixed_count > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return fixed_count


def main():
    do_fix = "--fix" in sys.argv

    normalization = detect_normalization_direction()
    expected = "lowercase" if normalization == "lowercase" else "UPPERCASE"

    print("=" * 80)
    print("STATUS CASE MISMATCH SCANNER & AUTO-FIXER")
    print("=" * 80)
    print()
    print(f"UploadQueue setter normalizes to: {normalization}")
    print(f"Expected status comparison case: {expected}")
    print(f"Mode: {'SCAN + AUTO-FIX' if do_fix else 'SCAN ONLY'}")
    print()

    total_mismatches = 0
    total_fixed = 0
    files_fixed = []

    for root, dirs, files in os.walk(JS_DIR):
        for filename in files:
            if not filename.endswith('.js'):
                continue
            if 'docx-preview' in filename or 'lucide' in filename:
                continue
            filepath = os.path.join(root, filename)
            mismatches = scan_file(filepath, normalization)

            if mismatches:
                print(f"\n{'=' * 80}")
                print(f"FILE: {filepath}")
                print(f"{'=' * 80}")
                for lineno, line, status, pat_type, _, _ in mismatches:
                    print(f"  Line {lineno:4d}: [{status}] {line.strip()[:120]}")
                    total_mismatches += 1

                if do_fix:
                    fixed = fix_file(filepath, mismatches, normalization)
                    if fixed > 0:
                        total_fixed += fixed
                        files_fixed.append(filepath)
                        print(f"  ✅ FIXED: {fixed} mismatches corrected")

    print(f"\n{'=' * 80}")
    if total_mismatches == 0:
        print("✅ NO MISMATCHES FOUND — all status comparisons are consistent")
        print(f"   (Setter normalizes to {normalization}, all comparisons use {expected})")
    else:
        print(f"TOTAL MISMATCHES: {total_mismatches}")
        if do_fix:
            print(f"TOTAL FIXED: {total_fixed} in {len(files_fixed)} file(s)")
        else:
            print("Run with --fix to auto-correct all mismatches")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()