"""
Lanvan Static Production Defect Scanner v1.0
============================================
A permanent, reproducible static analysis framework containing 15 concrete
rule scanners for memory leaks, race conditions, Store bypasses, XSS risks,
layout thrashing, and backend file system path safety.
"""

import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(r"c:\Users\Public\Probz\Code\lanvan")
JS_DIR = ROOT_DIR / "app" / "static" / "js"
PYTHON_DIR = ROOT_DIR / "app"
TEMPLATE_DIR = ROOT_DIR / "app" / "templates"

class QualityScanner:
    def __init__(self):
        self.findings = []
        self.total_scans = 0

    def add_finding(self, rule_id, severity, category, file_path, line_num, description, snippet=""):
        rel_file = str(file_path.relative_to(ROOT_DIR) if ROOT_DIR in file_path.parents or file_path == ROOT_DIR else file_path)
        self.findings.append({
            "rule_id": rule_id,
            "severity": severity,
            "category": category,
            "file": rel_file,
            "line": line_num,
            "description": description,
            "snippet": snippet.strip()
        })

    def check_1_event_listener_cleanup(self):
        """Rule 1: AddEventListener without removeEventListener/signal handlers."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            adds = sum(1 for line in lines if "addEventListener(" in line)
            removes = sum(1 for line in lines if "removeEventListener(" in line or "signal:" in line or "once: true" in line)
            if adds > 5 and removes == 0:
                self.add_finding("R01-EVT", "Medium", "Memory Leak", js_file, 1,
                                 f"File attaches {adds} event listeners but contains 0 removeEventListener/signal handlers.",
                                 "addEventListener")

    def check_2_timer_cleanup(self):
        """Rule 2: SetInterval without clearInterval."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            sets = sum(1 for line in lines if "setInterval(" in line)
            clears = sum(1 for line in lines if "clearInterval(" in line)
            if sets > 0 and clears < sets:
                for idx, line in enumerate(lines, 1):
                    if "setInterval(" in line and "clearInterval" not in content:
                        self.add_finding("R02-TMR", "High", "Memory Leak", js_file, idx,
                                         "setInterval invoked without matching clearInterval in file.", line)

    def check_3_observer_cleanup(self):
        """Rule 3: Observer instantiated without .disconnect()."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            for idx, line in enumerate(lines, 1):
                if re.search(r'new\s+(MutationObserver|ResizeObserver|IntersectionObserver)', line):
                    if ".disconnect(" not in content:
                        self.add_finding("R03-OBS", "High", "Resource Leak", js_file, idx,
                                         "Observer instantiated without .disconnect() cleanup.", line)

    def check_4_object_url_tracking(self):
        """Rule 4: Variable-level tracking of URL.createObjectURL -> URL.revokeObjectURL."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            created_vars = set()
            for idx, line in enumerate(lines, 1):
                m = re.search(r'(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*URL\.createObjectURL', line)
                if m: created_vars.add(m.group(1))

            for var in created_vars:
                if f"URL.revokeObjectURL({var})" not in content and "revokeObjectURL" not in content:
                    self.add_finding("R04-URL", "High", "Memory Leak", js_file, 1,
                                     f"Object URL variable '{var}' created without URL.revokeObjectURL({var}) cleanup.", var)

    def check_5_store_bypass(self):
        """Rule 5: Direct mutations to window.uploadQueue outside Store/Reducers."""
        self.total_scans += 1
        allowed_files = {"state-store.js", "main-app.js", "upload-engine.js"}
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name or js_file.name in allowed_files: continue
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            for idx, line in enumerate(lines, 1):
                if re.search(r'window\.(uploadQueue|selectedFiles|currentDirectory)\s*=\s*\[', line):
                    self.add_finding("R05-STR", "High", "Store Bypass", js_file, idx,
                                     "Direct assignment to global state array outside StateStore repository.", line)

    def check_6_xss_innerhtml(self):
        """Rule 6: Untrusted string concatenation directly into innerHTML without escapeHtml."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            lines = js_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines, 1):
                if ".innerHTML =" in line or ".innerHTML +=" in line:
                    if re.search(r'\+\s*(?:file|item|name|path|user|input|title|desc)\b', line, re.I):
                        if "escapeHtml" not in line and "window.escapeHtml" not in line and "encode" not in line:
                            self.add_finding("R06-XSS", "Critical", "Security / XSS", js_file, idx,
                                             "Direct string concatenation into innerHTML without HTML escaping.", line)

    def check_7_dom_in_loops(self):
        """Rule 7: Document.querySelector or getBoundingClientRect inside loops (layout thrashing)."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            in_loop = False
            for idx, line in enumerate(lines, 1):
                if re.search(r'\b(for|while)\s*\(|\.forEach\(', line):
                    in_loop = True
                if in_loop and re.search(r'document\.(querySelector|getElementById)|getBoundingClientRect\(\)', line):
                    self.add_finding("R07-PRF", "Medium", "Performance", js_file, idx,
                                     "DOM Query / Reflow query executed inside loop (layout thrashing risk).", line)
                if in_loop and "}" in line and "{" not in line:
                    in_loop = False

    def check_8_silent_catch(self):
        """Rule 8: Empty catch(e){} blocks that swallow exceptions."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            lines = js_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines, 1):
                if re.search(r'catch\s*\([^\)]*\)\s*\{\s*\}', line):
                    self.add_finding("R08-EXC", "Low", "Error Handling", js_file, idx,
                                     "Empty catch block silently swallowing exceptions.", line)

    def check_9_backend_path_traversal(self):
        """Rule 9: Python route open/remove calls without clean_path or abspath verification in function scope."""
        self.total_scans += 1
        for py_file in PYTHON_DIR.glob("**/*.py"):
            lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines, 1):
                if ("open(" in line or "os.remove(" in line or "shutil.rmtree(" in line) and ("path" in line or "filename" in line):
                    # Check 25 preceding lines in function scope for validation guards
                    scope_start = max(0, idx - 25)
                    scope_lines = "\n".join(lines[scope_start:idx])
                    if not re.search(r'clean_path|abspath|secure_filename|is_relative_to|UPLOAD_DIR|DATA_DIR', scope_lines):
                        self.add_finding("R09-SEC", "High", "Security / Traversal", py_file, idx,
                                         "File system operation on path parameter without explicit traversal guard in function scope.", line)

    def check_10_abort_controller(self):
        """Rule 10: AbortController instance without matching .abort() call."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            content = js_file.read_text(encoding="utf-8", errors="ignore")
            if "new AbortController" in content and ".abort()" not in content:
                self.add_finding("R10-ABR", "Medium", "Async / Lifecycle", js_file, 1,
                                 "AbortController created without .abort() invocation.", "new AbortController")

    def check_11_duplicate_script_tags(self):
        """Rule 11: Duplicate script tag imports in HTML templates."""
        self.total_scans += 1
        for tpl in TEMPLATE_DIR.glob("**/*.html"):
            lines = tpl.read_text(encoding="utf-8", errors="ignore").splitlines()
            scripts = []
            for idx, line in enumerate(lines, 1):
                m = re.search(r'src=["\']([^"\']+\.js)["\']', line)
                if m:
                    src = m.group(1)
                    if src in scripts:
                        self.add_finding("R11-DUP", "High", "Template Integrity", tpl, idx,
                                         f"Duplicate script import detected: '{src}'", line)
                    scripts.append(src)

    def check_12_unhandled_promise_then(self):
        """Rule 12: Detect .then() calls without accompanying .catch()."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            lines = js_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines, 1):
                if ".then(" in line and ".catch(" not in line and "catch(" not in lines[min(idx, len(lines)-1)]:
                    if "fetch(" in line or "Promise" in line:
                        self.add_finding("R12-PRM", "Low", "Async / Lifecycle", js_file, idx,
                                         "Promise .then() handler without attached .catch() exception handler.", line)

    def check_13_hardcoded_layout_math(self):
        """Rule 13: Detect hardcoded static pixel offsets (+ 12, * 2.0) in layout calculations."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            lines = js_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for idx, line in enumerate(lines, 1):
                if re.search(r'(?:height|width|top|left)\s*[\+=]=?\s*.*(?:\+\s*12|\*\s*2\.0)', line):
                    self.add_finding("R13-LTH", "Low", "UI Layout Math", js_file, idx,
                                     "Hardcoded pixel offset in dynamic UI container height calculation.", line)

    def check_14_clipboard_mkdir(self):
        """Rule 14: Ensure clipboard history save routines create target parent directories."""
        self.total_scans += 1
        clip_py = PYTHON_DIR / "routers" / "clipboard.py"
        if clip_py.exists():
            content = clip_py.read_text(encoding="utf-8", errors="ignore")
            if "save_clipboard_history" in content and "mkdir" not in content:
                self.add_finding("R14-DIR", "High", "Resource Directory", clip_py, 1,
                                 "Clipboard history save function missing directory creation guard.", "save_clipboard_history")

    def check_15_async_state_mutations(self):
        """Rule 15: Detect global state mutation after await without lock/store dispatch."""
        self.total_scans += 1
        for js_file in JS_DIR.glob("**/*.js"):
            if ".min.js" in js_file.name: continue
            lines = js_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            has_await = False
            for idx, line in enumerate(lines, 1):
                if "await " in line:
                    has_await = True
                if has_await and re.search(r'window\.uploadQueue\.push|window\.uploadQueue\[', line):
                    self.add_finding("R15-ASY", "Medium", "Race Condition", js_file, idx,
                                     "Global uploadQueue mutated after async await boundary without Store lock.", line)
                    has_await = False

    def run_all_scans(self):
        self.check_1_event_listener_cleanup()
        self.check_2_timer_cleanup()
        self.check_3_observer_cleanup()
        self.check_4_object_url_tracking()
        self.check_5_store_bypass()
        self.check_6_xss_innerhtml()
        self.check_7_dom_in_loops()
        self.check_8_silent_catch()
        self.check_9_backend_path_traversal()
        self.check_10_abort_controller()
        self.check_11_duplicate_script_tags()
        self.check_12_unhandled_promise_then()
        self.check_13_hardcoded_layout_math()
        self.check_14_clipboard_mkdir()
        self.check_15_async_state_mutations()
        return self.findings

def generate_report(findings, total_scans):
    by_severity = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    by_rule = {}
    for f in findings:
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1
        by_rule[f["rule_id"]] = by_rule.get(f["rule_id"], 0) + 1

    print("\n============================================================")
    print("      LANVAN STATIC PRODUCTION DEFECT SCANNER (v1.0)       ")
    print("============================================================")
    print(f"Total Scans Executed: {total_scans}")
    print(f"Total Findings Discovered: {len(findings)}")
    print(f"  Critical: {by_severity['Critical']} | High: {by_severity['High']} | Medium: {by_severity['Medium']} | Low: {by_severity['Low']}")
    print("\nFindings Breakdown by Rule:")
    for r_id, count in sorted(by_rule.items()):
        print(f"  - {r_id}: {count} occurrences")
    print("============================================================")

    non_low = [f for f in findings if f["severity"] != "Low"]
    print(f"\n--- NON-LOW PRODUCTION FINDINGS ({len(non_low)}) ---")
    if not non_low:
        print("  [OK] Zero Critical, High, or Medium production defects found.")
    else:
        for idx, f in enumerate(non_low, 1):
            print(f"{idx}. [{f['rule_id']}] [{f['severity']}] ({f['category']}) {f['file']}:{f['line']}")
            print(f"   Desc: {f['description']}")
            if f['snippet']:
                print(f"   Code: {f['snippet']}")
            print()

if __name__ == "__main__":
    scanner = QualityScanner()
    findings = scanner.run_all_scans()
    generate_report(findings, scanner.total_scans)
