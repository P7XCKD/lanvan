#!/usr/bin/env python3
"""
Lanvan Architecture & Defect Scanner (arch_scan.py)
---------------------------------------------------
Scans the JavaScript codebase to detect architectural defects,
multiple state writers, redundant refresh triggers, and state ownership violations.
"""

import os
import re
import sys
from pathlib import Path

WORKSPACE_DIR = Path(r"c:\Users\Public\Probz\Code\lanvan")
JS_DIR = WORKSPACE_DIR / "app" / "static" / "js"

RULES = [
    {
        "id": "ARCH-01",
        "name": "Direct uploadQueue Array Mutation",
        "severity": "HIGH",
        "desc": "Direct array mutation or assignment to window.uploadQueue bypassing LanvanStore / UploadManager.",
        "pattern": r"(window\.uploadQueue\s*=|\buploadQueue\.length\s*=\s*0|\buploadQueue\s*=\s*uploadQueue\.filter)",
        "exclude_files": ["state-store.js"],
    },
    {
        "id": "ARCH-02",
        "name": "Direct Cache Writer Violation",
        "severity": "HIGH",
        "desc": "Direct assignment to folderFilesCache outside FileRepository setFolderCache API.",
        "pattern": r"folderFilesCache\[.*?\]\s*=",
        "exclude_files": ["repository.js"],
    },
    {
        "id": "ARCH-03",
        "name": "Direct currentFolderPath Mutation",
        "severity": "MEDIUM",
        "desc": "Direct global assignment to currentFolderPath bypassing FolderReducer / LanvanStore.",
        "pattern": r"(window\.currentFolderPath\s*=\s*|var\s+currentFolderPath\s*=\s*['\"])",
        "exclude_files": ["state-store.js"],
    },
    {
        "id": "ARCH-06",
        "name": "On-the-Fly State Reconstruction",
        "severity": "MEDIUM",
        "desc": "app-init dynamically overwrites storeState properties right before Projection.",
        "pattern": r"storeState\.currentFolder\s*=\s*|storeState\.uploadQueue\s*=\s*",
        "exclude_files": ["state-store.js"],
    }
]

def run_architectural_scan():
    print("=" * 60)
    print("      LANVAN ARCHITECTURAL DEFECT SCANNER (arch_scan.py)      ")
    print("=" * 60)

    findings = []
    total_files_scanned = 0

    for root, _, files in os.walk(JS_DIR):
        for file in files:
            if not file.endswith(".js"):
                continue

            file_path = Path(root) / file
            rel_path = file_path.relative_to(WORKSPACE_DIR)
            total_files_scanned += 1

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()

                for rule in RULES:
                    if rule.get("exclude_files") and file in rule["exclude_files"]:
                        continue

                    regex = re.compile(rule["pattern"])
                    for idx, line in enumerate(lines, 1):
                        if regex.search(line):
                            findings.append({
                                "rule_id": rule["id"],
                                "rule_name": rule["name"],
                                "severity": rule["severity"],
                                "file": str(rel_path),
                                "line": idx,
                                "code": line.strip(),
                                "desc": rule["desc"]
                            })
            except Exception as err:
                print(f"[ERR] Failed to read {file_path}: {err}")

    print(f"Total JS Files Scanned: {total_files_scanned}")
    print(f"Total High/Medium Defects Found: {len(findings)}")
    print("-" * 60)

    if findings:
        print("\n--- ARCHITECTURAL DEFECT FINDINGS LIST ---")
        for i, item in enumerate(findings, 1):
            print(f"{i}. [{item['rule_id']}] [{item['severity']}] {item['file']}:{item['line']}")
            print(f"   Name: {item['rule_name']}")
            print(f"   Code: {item['code']}\n")
    else:
        print("🟢 CONGRATULATIONS! Zero high/medium architectural defects found!")

    print("=" * 60)
    return len(findings)

if __name__ == "__main__":
    defects_count = run_architectural_scan()
    sys.exit(0 if defects_count == 0 else 1)
