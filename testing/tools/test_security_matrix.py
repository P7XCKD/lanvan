"""
Comprehensive Security Matrix Runtime Test Script for Lanvan
Validates dangerous file blocking and safe file passage across all runtime, protocol, and configuration modes.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.validation import FileValidator

def run_security_matrix_tests():
    print("=" * 60)
    print("  LANVAN SECURITY MATRIX RUNTIME VERIFICATION")
    print("=" * 60)

    safe_filename = "vacation_photo.jpg"
    dangerous_filenames = ["malware.exe", "installer.bat", "library.dll"]

    matrix_cases = [
        # (Mode Name, env_block_dangerous, is_https, expected_safe, expected_dangerous)
        ("1. Docker/Local HTTP Default", "false", False, True, True),
        ("2. Docker/Local HTTP + --block-dangerous", "true", False, True, False),
        ("3. Docker/Local HTTPS Default", "", True, True, False),
        ("4. Docker/Local HTTPS + --block-dangerous", "true", True, True, False),
        ("5. APK HTTP Default (Security Toggle OFF)", "false", False, True, True),
        ("6. APK HTTP Security Enabled (Security Toggle ON)", "true", False, True, False),
        ("7. APK HTTPS Default", "", True, True, False),
    ]

    all_passed = True

    for title, env_val, is_https, expect_safe, expect_dangerous in matrix_cases:
        if env_val == "":
            if "BLOCK_DANGEROUS" in os.environ:
                del os.environ["BLOCK_DANGEROUS"]
        else:
            os.environ["BLOCK_DANGEROUS"] = env_val

        # Test Safe File
        safe_res = FileValidator.validate_filename(safe_filename, is_https=is_https)
        safe_ok = (safe_res["valid"] == expect_safe)

        # Test Dangerous Files
        dangerous_results = [
            FileValidator.validate_filename(df, is_https=is_https) for df in dangerous_filenames
        ]
        dangerous_ok = all(r["valid"] == expect_dangerous for r in dangerous_results)

        case_passed = safe_ok and dangerous_ok
        if not case_passed:
            all_passed = False

        status_str = "[PASS]" if case_passed else "[FAIL]"
        print(f"\n{status_str} {title}")
        print(f"      ENV BLOCK_DANGEROUS: {os.getenv('BLOCK_DANGEROUS', '<unset>')}")
        print(f"      is_https: {is_https}")
        print(f"      Safe file ('{safe_filename}'): valid={safe_res['valid']} (Expected {expect_safe})")
        for df, res in zip(dangerous_filenames, dangerous_results):
            print(f"      Dangerous file ('{df}'): valid={res['valid']} (Expected {expect_dangerous})")

    print("\n" + "=" * 60)
    if all_passed:
        print("  RESULT: ALL 7 SECURITY MATRIX CASES PASSED VERIFICATION! 100%")
    else:
        print("  RESULT: SECURITY MATRIX FAILURE ENCOUNTERED.")
    print("=" * 60)

    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    run_security_matrix_tests()
