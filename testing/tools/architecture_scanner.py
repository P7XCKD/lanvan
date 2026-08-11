import os
import re
import json
import glob
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATIC_JS_DIR = os.path.join(ROOT_DIR, "app", "static", "js")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "app", "templates")
ARTIFACTS_DIR = os.path.join(ROOT_DIR, "testing", "artifacts")

os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def run_architecture_scan():
    """
    Scan JavaScript and template files for architecture-related symbols, dependencies, and usage patterns, then write JSON and text reports to the artifacts directory.
    """
    js_files = glob.glob(os.path.join(STATIC_JS_DIR, "**", "*.js"), recursive=True)
    template_files = glob.glob(os.path.join(TEMPLATES_DIR, "**", "*.html"), recursive=True)

    scan_data = {
        "generated_at": datetime.now().isoformat(),
        "root": STATIC_JS_DIR,
        "total_js_files": len(js_files),
        "files": [],
        "symbols": [],
        "references": [],
        "network_calls": [],
        "dom_dependencies": [],
        "identity_patterns": [],
        "state_access": [],
        "duplicates": []
    }

    symbol_map = {}

    for file_path in sorted(js_files):
        rel_path = os.path.relpath(file_path, ROOT_DIR).replace("\\", "/")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        loc = len(lines)
        file_size = os.path.getsize(file_path)

        file_info = {
            "path": rel_path,
            "filename": os.path.basename(file_path),
            "directory": os.path.dirname(rel_path),
            "physical_loc": loc,
            "file_size_bytes": file_size,
            "functions": [],
            "window_assigns": [],
            "fetch_count": 0,
            "xhr_count": 0,
            "ws_count": 0,
            "dom_count": 0,
            "repository_refs": 0,
            "projection_refs": 0,
            "upload_queue_refs": 0,
            "selected_items_refs": 0
        }

        # Analyze lines for symbols & patterns
        for idx, line in enumerate(lines, 1):
            # Function declarations
            fn_match = re.search(r'(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(', line)
            if fn_match:
                fn_name = fn_match.group(1)
                file_info["functions"].append({"name": fn_name, "line": idx})
                scan_data["symbols"].append({
                    "file": rel_path,
                    "line": idx,
                    "symbol": fn_name,
                    "symbol_type": "function"
                })
                symbol_map.setdefault(fn_name, []).append({"file": rel_path, "line": idx})

            # Window assignments
            win_match = re.search(r'window\.([a-zA-Z0-9_$]+)\s*=', line)
            if win_match:
                win_name = win_match.group(1)
                file_info["window_assigns"].append({"name": win_name, "line": idx})
                scan_data["symbols"].append({
                    "file": rel_path,
                    "line": idx,
                    "symbol": win_name,
                    "symbol_type": "window_assignment"
                })

            # Network Calls
            if "fetch(" in line:
                file_info["fetch_count"] += 1
                endpoint_match = re.search(r"fetch\(\s*['\"]([^'\"]+)['\"]", line)
                endpoint = endpoint_match.group(1) if endpoint_match else "DYNAMIC"
                scan_data["network_calls"].append({
                    "file": rel_path,
                    "line": idx,
                    "type": "fetch",
                    "endpoint": endpoint
                })

            if "XMLHttpRequest" in line or "new XMLHttpRequest()" in line:
                file_info["xhr_count"] += 1

            if "WebSocket(" in line or "new WebSocket(" in line or "window.ws" in line:
                file_info["ws_count"] += 1

            # DOM Access
            if re.search(r'document\.(getElementById|querySelector|querySelectorAll|createElement)\s*\(', line):
                file_info["dom_count"] += 1
                dom_match = re.search(r"(?:getElementById|querySelector|querySelectorAll)\s*\(\s*['\"]([^'\"]+)['\"]", line)
                if dom_match:
                    scan_data["dom_dependencies"].append({
                        "file": rel_path,
                        "line": idx,
                        "selector": dom_match.group(1)
                    })

            # Identity / Path Patterns
            if re.search(r'(getCanonicalIdentity|currentFolderPath|parentPath|targetDir|\.name|relative_path|basename)', line):
                scan_data["identity_patterns"].append({
                    "file": rel_path,
                    "line": idx,
                    "snippet": line.strip()[:100]
                })

            # State Access
            if "uploadQueue" in line:
                file_info["upload_queue_refs"] += 1
                scan_data["state_access"].append({
                    "file": rel_path,
                    "line": idx,
                    "state": "uploadQueue",
                    "op": "WRITE" if "uploadQueue." in line or "uploadQueue =" in line else "READ"
                })

            if "selectedItems" in line:
                file_info["selected_items_refs"] += 1

            if "FileRepository" in line or "repository" in line.lower() and "cache" in line.lower():
                file_info["repository_refs"] += 1

            if "Projection" in line or "projection" in line.lower():
                file_info["projection_refs"] += 1

        scan_data["files"].append(file_info)

    # Detect duplicates across files
    for fn_name, occurrences in symbol_map.items():
        if len(occurrences) > 1:
            scan_data["duplicates"].append({
                "symbol": fn_name,
                "occurrences": occurrences
            })

    # Save JSON artifact
    json_path = os.path.join(ARTIFACTS_DIR, "architecture_scan.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(scan_data, f, indent=2)

    # Save TXT summary artifact
    txt_path = os.path.join(ARTIFACTS_DIR, "architecture_scan.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("============================================================\n")
        f.write("LANVAN STATIC ARCHITECTURE SCANNER SUMMARY\n")
        f.write(f"Generated At: {scan_data['generated_at']}\n")
        f.write(f"Total Discovered JS Files: {scan_data['total_js_files']}\n")
        f.write("============================================================\n\n")

        for fi in scan_data["files"]:
            f.write(f"File: {fi['path']} | LOC: {fi['physical_loc']} | Functions: {len(fi['functions'])} | Fetch: {fi['fetch_count']} | DOM: {fi['dom_count']}\n")

    print(f"Scan complete. Found {len(js_files)} JS files.")
    print(f"JSON Report: {json_path}")
    print(f"TXT Report:  {txt_path}")

if __name__ == "__main__":
    run_architecture_scan()
