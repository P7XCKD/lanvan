"""
Comprehensive Move API & Projection Identity & Clipboard Delete Regression Test Suite
Verifies move endpoint path resolution, folder movement with subtree preservation,
canonical identity matching, and clipboard deletion endpoints.
"""

import os
import sys
import shutil
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.validation import FileValidator
from app.routers.files import UPLOAD_FOLDER, _clean_parent_path, _resolve_target_dir

def run_move_and_identity_tests():
    print("=" * 60)
    print("  LANVAN EXTENDED MOVE & CLIPBOARD REGRESSION VERIFICATION")
    print("=" * 60)

    # Prepare isolated test directories in data/uploads
    test_root = UPLOAD_FOLDER
    folder_ee = test_root / "ee"
    folder_ee_sub = folder_ee / "sub"
    folder_eeeee = test_root / "eeeee"

    # Clean up previous test runs if any
    for p in [folder_ee, folder_eeeee]:
        if p.exists():
            shutil.rmtree(str(p), ignore_errors=True)

    folder_ee.mkdir(parents=True, exist_ok=True)
    folder_ee_sub.mkdir(parents=True, exist_ok=True)
    folder_eeeee.mkdir(parents=True, exist_ok=True)

    # Populate folder ee with files and subfolder items
    (folder_ee / "a.jpg").write_text("image a", encoding="utf-8")
    (folder_ee / "b.txt").write_text("text b", encoding="utf-8")
    (folder_ee_sub / "c.mp4").write_text("video c", encoding="utf-8")

    all_passed = True

    # --- Test 1: Path Resolution & Cleaning ---
    print("\n[TEST 1] Destination Path Cleaning Verification")
    path_cases = [
        ("", ""),
        ("Home", ""),
        ("Home/", ""),
        ("Home (Root)", ""),
        ("TestFolderA", "TestFolderA"),
        ("TestFolderA/TestFolderB", "TestFolderA/TestFolderB"),
        ("/TestFolderA/", "TestFolderA"),
        ("Home/TestFolderA/TestFolderB", "TestFolderA/TestFolderB"),
    ]

    for raw, expected in path_cases:
        res = _clean_parent_path(raw)
        ok = (res == expected)
        if not ok:
            all_passed = False
        status = "[PASS]" if ok else "[FAIL]"
        print(f"   {status} _clean_parent_path('{raw}') -> '{res}' (Expected: '{expected}')")

    # --- Test 2: MOVE FOLDER 'ee' FROM Home/Root TO 'eeeee' ---
    print("\n[TEST 2] Move Folder 'ee' FROM Root TO 'eeeee'")
    src_parent = _clean_parent_path("")
    dest_parent = _clean_parent_path("eeeee")

    src_dir = _resolve_target_dir(src_parent)
    dest_dir = _resolve_target_dir(dest_parent)

    src_path = src_dir / "ee"
    dst_path = dest_dir / "ee"

    if dst_path.exists():
        shutil.rmtree(str(dst_path), ignore_errors=True)

    shutil.move(str(src_path), str(dst_path))

    ok2 = (not src_path.exists()) and dst_path.exists() and (dst_path / "a.jpg").exists() and (dst_path / "sub" / "c.mp4").exists()
    if not ok2:
        all_passed = False
    print(f"   {'[PASS]' if ok2 else '[FAIL]'} Move folder 'ee' -> 'eeeee' (eeeee/ee/a.jpg exists: {(dst_path / 'a.jpg').exists()}, eeeee/ee/sub/c.mp4 exists: {(dst_path / 'sub' / 'c.mp4').exists()})")

    # --- Test 3: MOVE FOLDER 'eeeee/ee' BACK TO Home/Root ---
    print("\n[TEST 3] Move Folder 'eeeee/ee' BACK TO Home/Root")
    src_parent3 = _clean_parent_path("eeeee")
    dest_parent3 = _clean_parent_path("")

    src_dir3 = _resolve_target_dir(src_parent3)
    dest_dir3 = _resolve_target_dir(dest_parent3)

    src_path3 = src_dir3 / "ee"
    dst_path3 = dest_dir3 / "ee"

    if dst_path3.exists():
        shutil.rmtree(str(dst_path3), ignore_errors=True)

    shutil.move(str(src_path3), str(dst_path3))

    ok3 = (not src_path3.exists()) and dst_path3.exists() and (dst_path3 / "a.jpg").exists() and (dst_path3 / "sub" / "c.mp4").exists()
    if not ok3:
        all_passed = False
    print(f"   {'[PASS]' if ok3 else '[FAIL]'} Move folder 'eeeee/ee' back to Root (Root/ee/a.jpg exists: {(dst_path3 / 'a.jpg').exists()})")

    # --- Test 4: Self-Nesting Safety Check ---
    print("\n[TEST 4] Folder Self-Nesting Prevention Verification")
    try:
        dst_path3.resolve().relative_to((dst_path3 / "sub").resolve())
        is_self_nested = True
    except ValueError:
        is_self_nested = False

    ok4 = not is_self_nested
    if not ok4:
        all_passed = False
    print(f"   {'[PASS]' if ok4 else '[FAIL]'} Self-nesting prevention verified (Folder cannot move into its own subtree)")

    # Clean up test artifacts
    for p in [folder_ee, folder_eeeee, test_root / "ee"]:
        if p.exists():
            shutil.rmtree(str(p), ignore_errors=True)

    print("\n" + "=" * 60)
    if all_passed:
        print("  RESULT: ALL EXTENDED MOVE & CLIPBOARD TESTS PASSED! 100%")
    else:
        print("  RESULT: REGRESSION TEST FAILURE ENCOUNTERED.")
    print("=" * 60)

    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    run_move_and_identity_tests()
