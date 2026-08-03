"""
Lanvan Industry-Standard Production Build System
Generates an isolated, disposable production build in dist/ with SHA-256 build manifest tracking.

Usage:
    python build.py
"""

import os
import shutil
import sys
import time
import json
import hashlib

WATCHED_FRONTEND_DIRS = [
    os.path.join("app", "static", "js"),
    os.path.join("app", "static", "css"),
    os.path.join("app", "templates"),
    "build.py"
]

def compute_frontend_hash(watched_dirs=None) -> str:
    """
    Computes a deterministic SHA-256 hash across all watched frontend asset files
    (JavaScript, CSS, and Jinja templates).
    """
    if watched_dirs is None:
        watched_dirs = WATCHED_FRONTEND_DIRS
        
    hasher = hashlib.sha256()
    for wdir in sorted(watched_dirs):
        if not os.path.exists(wdir):
            continue
        if os.path.isfile(wdir):
            try:
                with open(wdir, "rb") as f:
                    hasher.update(wdir.encode("utf-8"))
                    hasher.update(f.read())
            except OSError:
                pass
        else:
            for root, _, files in sorted(os.walk(wdir)):
                for file in sorted(files):
                    if file.endswith(".min.js") and file not in ("docx-preview.min.js", "lucide.min.js"):
                        continue
                    fpath = os.path.join(root, file)
                    try:
                        with open(fpath, "rb") as f:
                            hasher.update(fpath.encode("utf-8"))
                            hasher.update(f.read())
                    except OSError:
                        pass
    return hasher.hexdigest()

def minify_js_code(js_code: str) -> str:
    """
    Fast, 100% reliable state-machine JS minifier:
    - Preserves single quotes ('...'), double quotes ("..."), and template literals (`...`)
    - Preserves URLs (http://, https://, ws://, wss://, file://) inside or outside strings
    - Strips single-line (//...) and multi-line (/*...*/) comments safely
    - Collapses empty lines and trailing whitespace
    """
    out = []
    i = 0
    n = len(js_code)

    while i < n:
        char = js_code[i]

        # 1. String or template literals: '...', "...", `...`
        if char in ("'", '"', '`'):
            quote = char
            out.append(char)
            i += 1
            while i < n:
                c = js_code[i]
                out.append(c)
                if c == '\\':
                    i += 1
                    if i < n:
                        out.append(js_code[i])
                elif c == quote:
                    i += 1
                    break
                i += 1
            continue

        # 2. Multi-line comment /* ... */
        if char == '/' and i + 1 < n and js_code[i + 1] == '*':
            i += 2
            while i < n and not (js_code[i] == '*' and i + 1 < n and js_code[i + 1] == '/'):
                i += 1
            i += 2
            continue

        # 3. Single-line comment // ...
        if char == '/' and i + 1 < n and js_code[i + 1] == '/':
            prev_chunk = "".join(out[-6:]).lower()
            if (prev_chunk.endswith("http:") or 
                prev_chunk.endswith("https:") or 
                prev_chunk.endswith("ws:") or 
                prev_chunk.endswith("wss:") or 
                prev_chunk.endswith("file:")):
                out.append('/')
                out.append('/')
                i += 2
                continue
            else:
                i += 2
                while i < n and js_code[i] not in ('\r', '\n'):
                    i += 1
                continue

        # 4. Normal character
        out.append(char)
        i += 1

    raw = "".join(out)
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return "\n".join(lines)


def build_production_bundle(src_app_dir: str = "app", dist_dir: str = "dist"):
    """
    Performs a clean, isolated production build into dist/:
    1. Removes any existing dist/ directory.
    2. Copies static CSS, images, icons, fonts, and templates into dist/.
    3. Minifies all application JS files into dist/static/js/*.min.js.
    4. Writes dist/build-manifest.json with SHA-256 hash of frontend assets.
    5. Leaves source directory app/ 100% untouched.
    """
    start_time = time.time()
    
    print("============================================================")
    print("  Lanvan Industry-Standard Production Build System")
    print("============================================================")

    # 1. Clean previous build output
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir, ignore_errors=True)
        print(f"  [OK] Cleaned previous build directory: {dist_dir}/")

    os.makedirs(dist_dir, exist_ok=True)
    
    src_static = os.path.join(src_app_dir, "static")
    dist_static = os.path.join(dist_dir, "static")

    # 2. Copy static subdirectories (css, images, icons, fonts, etc.)
    if os.path.exists(src_static):
        for item in os.listdir(src_static):
            s_item = os.path.join(src_static, item)
            d_item = os.path.join(dist_static, item)
            if os.path.isdir(s_item) and item != "js":
                shutil.copytree(s_item, d_item)
                print(f"  [OK] Copied asset folder: static/{item}/")

    # 3. Copy templates folder
    src_templates = os.path.join(src_app_dir, "templates")
    dist_templates = os.path.join(dist_dir, "templates")
    if os.path.exists(src_templates):
        shutil.copytree(src_templates, dist_templates)
        print("  [OK] Copied template templates/")

    # 4. Process JavaScript assets into dist/static/js/
    src_js = os.path.join(src_static, "js")
    dist_js = os.path.join(dist_static, "js")
    os.makedirs(dist_js, exist_ok=True)

    count = 0
    total_orig_bytes = 0
    total_min_bytes = 0

    for root, _, files in os.walk(src_js):
        rel_root = os.path.relpath(root, src_js)
        target_dir = os.path.join(dist_js, rel_root) if rel_root != "." else dist_js
        os.makedirs(target_dir, exist_ok=True)

        for file in files:
            src_file_path = os.path.join(root, file)
            
            if file.endswith(".js") and not file.endswith(".min.js"):
                min_filename = file[:-3] + ".min.js"
                dist_min_path = os.path.join(target_dir, min_filename)
                dist_orig_path = os.path.join(target_dir, file)

                with open(src_file_path, "r", encoding="utf-8") as f:
                    orig_code = f.read()

                min_code = minify_js_code(orig_code)

                # Write minified version to dist/
                with open(dist_min_path, "w", encoding="utf-8") as f:
                    f.write(min_code)

                # Keep unminified copy in dist for optional fallback
                with open(dist_orig_path, "w", encoding="utf-8") as f:
                    f.write(orig_code)

                orig_size = len(orig_code.encode("utf-8"))
                min_size = len(min_code.encode("utf-8"))
                total_orig_bytes += orig_size
                total_min_bytes += min_size
                count += 1

                rel_src = os.path.relpath(src_file_path, src_static)
                rel_min = os.path.relpath(dist_min_path, dist_static)
                savings = (1 - (min_size / orig_size)) * 100 if orig_size > 0 else 0
                print(f"  [OK] {rel_src} -> {rel_min} ({orig_size:,} bytes -> {min_size:,} bytes | -{savings:.1f}%)")
            else:
                shutil.copy2(src_file_path, os.path.join(target_dir, file))

    # 5. Write build manifest
    frontend_hash = compute_frontend_hash()
    manifest_data = {
        "build_timestamp": int(time.time()),
        "frontend_hash": frontend_hash,
        "js_files_count": count
    }
    manifest_path = os.path.join(dist_dir, "build-manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    elapsed = time.time() - start_time
    saved_bytes = total_orig_bytes - total_min_bytes
    overall_savings = (saved_bytes / total_orig_bytes * 100) if total_orig_bytes > 0 else 0

    print("============================================================")
    print(f"  Build Complete: Produced isolated dist/ in {elapsed:.2f}s")
    print(f"  Manifest SHA-256: {frontend_hash[:16]}...")
    print(f"  Minified Modules: {count} JS files")
    print(f"  Total JS Size: {total_orig_bytes:,} bytes -> {total_min_bytes:,} bytes (-{overall_savings:.1f}%)")
    print("  Source Tree (app/): 100% UNTOUCHED")
    print("  Source Maps: DISABLED (0 .map files generated)")
    print("============================================================")

if __name__ == "__main__":
    build_production_bundle()
