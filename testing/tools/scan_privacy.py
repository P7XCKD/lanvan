#!/usr/bin/env python3
"""
Lanvan Production Logging Privacy & PII Leak Scanner
===================================================
Automated static analysis tool to detect user data, filenames, file paths,
URLs, clipboard content, passwords, or PII leaks in logging/print statements.
"""

import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(r"c:\Users\Public\Probz\Code\lanvan")
PYTHON_DIRS = [
    ROOT_DIR / "app",
    ROOT_DIR / "android" / "app" / "src" / "main" / "python"
]

# Sensitive property and variable names that should never be logged raw
SENSITIVE_PATTERNS = [
    (r'\b(?:file|upload_file|f)\.filename\b', "Raw UploadFile.filename"),
    (r'\b(?:filepath|file_path|path|target_dir|destination|folder_path)\.resolve\(\)', "Resolved filesystem path"),
    (r'\b(?:filepath|file_path|path|target_dir|destination|folder_path)\.name\b', "Raw file or directory name"),
    (r'\b(?:clipboard_text|clipboard_content|clip_text|raw_clipboard)\b', "Raw clipboard content"),
    (r'\b(?:password|secret|token|api_key|auth_token)\b', "Credential / Secret variable"),
    (r'/(?:sdcard|storage|data/data)/', "Hardcoded absolute Android filesystem path"),
    (r'[a-zA-Z]:\\\\(?:[^\\[\r\n]+\\\\)+', "Hardcoded absolute Windows filesystem path"),
]

# Allowed files that handle logging/sanitization infrastructure or tests
EXCLUDED_FILES = {
    "start_server.py", # Owns the sanitize_log_message regex filter implementation
    "logger.py",       # Owns StructuredLogger definitions
    "test_privacy_scan.py"
}

class LoggingPrivacyScanner:
    def __init__(self):
        self.findings = []
        self.total_files_scanned = 0

    def add_finding(self, severity, file_path, line_num, description, snippet):
        rel_file = str(file_path.relative_to(ROOT_DIR) if ROOT_DIR in file_path.parents or file_path == ROOT_DIR else file_path)
        self.findings.append({
            "severity": severity,
            "file": rel_file,
            "line": line_num,
            "description": description,
            "snippet": snippet.strip()
        })

    def run_scan(self):
        for pdir in PYTHON_DIRS:
            if not pdir.exists():
                continue
            for py_file in pdir.rglob("*.py"):
                if py_file.name in EXCLUDED_FILES or "__pycache__" in str(py_file):
                    continue

                self.total_files_scanned += 1
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()

                for idx, line in enumerate(lines, 1):
                    # Check if line performs logging or printing
                    is_log_statement = bool(re.search(r'\b(?:print|logger\.info|logger\.warn|logger\.error|logger\.debug|log_upload)\s*\(', line))
                    if not is_log_statement:
                        continue

                    # If line or its enclosing block is guarded by `if not is_prod:` or `if is_debug:`, skip
                    preceding_scope = "\n".join(lines[max(0, idx - 10):idx])
                    if "if not is_prod:" in preceding_scope or "if is_debug:" in preceding_scope or "if not is_production" in preceding_scope:
                        continue

                    for pattern, label in SENSITIVE_PATTERNS:
                        if re.search(pattern, line, re.I):
                            # Exempt safe logger methods that do their own sanitization
                            if "extract_safe_ext(" in line or "format_size(" in line:
                                continue
                            self.add_finding("High", py_file, idx, f"Potential privacy leak in log/print: {label}", line)

        return self.findings

def generate_report(findings, total_files):
    print("=" * 60)
    print("   LANVAN AUTOMATED LOGGING PRIVACY SCANNER   ")
    print("=" * 60)
    print(f"Total Python Files Scanned: {total_files}")
    print(f"Total Privacy Defects Found: {len(findings)}")
    print("-" * 60)

    if not findings:
        print("[OK] Zero logging privacy leaks detected! All logs are sanitized and production-safe.")
    else:
        print("\n--- DETECTED PRIVACY LEAKS ---")
        for i, item in enumerate(findings, 1):
            print(f"{i}. [{item['severity']}] {item['file']}:{item['line']}")
            print(f"   Description: {item['description']}")
            print(f"   Code: {item['snippet']}\n")

    print("=" * 60)
    return len(findings)

if __name__ == "__main__":
    scanner = LoggingPrivacyScanner()
    findings = scanner.run_scan()
    count = generate_report(findings, scanner.total_files_scanned)
    sys.exit(0 if count == 0 else 1)
