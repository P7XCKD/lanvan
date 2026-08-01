# -*- coding: utf-8 -*-
"""
enforce_naming.py
-----------------
Repository-wide production naming enforcement for Lanvan.

Renames all historical development terminology (prototype, gdrive, Google Drive,
drive-like, etc.) across all project-owned source files.

Protections:
  - ANY  Foo.prototype.bar  chain is sentinel-protected (JS prototype-based OOP)
  - Known browser runtime objects (Object, Array, XMLHttpRequest, etc.) are kept
  - External product references (Google Play, Google Fonts, etc.) are preserved

Usage:
    python enforce_naming.py [--dry-run]
"""

import io
import os
import re
import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent

# Directories to skip entirely (binary, vendored, generated, VCS)
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "vendor",
    ".vscode",
    "certs",
    "data",
    "scratch",
    "temp_files",
    "test downlaods",
    "copilot",
}

# Specific filenames to never touch (this script, vendored libs)
SKIP_FILES = {
    "enforce_naming.py",
    "lucide.min.js",
    "docx-preview.min.js",
}

# Generated/stale files to delete outright (will be regenerated on next run)
DELETE_STALE_FILES = {
    "runtime_css_report.json",
}

# Extensions to process
PROCESS_EXTENSIONS = {
    ".js", ".css", ".html", ".py", ".md", ".txt", ".json", ".bat", ".sh",
}


# ---------------------------------------------------------------------------
# Sentinel system
# Protects ALL  SomeClass.prototype.someMethod  chains — both JS builtins AND
# project-defined prototype-based classes (ProjectionLayer, RenderScheduler,
# FileRepository, LanvanStore, etc.) — before the rename passes run.
# ---------------------------------------------------------------------------

SENTINEL_PREFIX = "___LV_PROTO_SENTINEL_"

# Matches ANY  \w+.prototype  or  \w+.prototype.\w+  pattern
# (covers ProjectionLayer.prototype.build, Array.prototype.slice, etc.)
RUNTIME_PROTO_RE = re.compile(r'\b\w+\.prototype\b')


def protect_runtime_patterns(text):
    """Replace all .prototype chains with unique sentinels."""
    sentinels = {}
    counter = [0]

    def replacer(m):
        key = f"{SENTINEL_PREFIX}{counter[0]}___"
        sentinels[key] = m.group(0)
        counter[0] += 1
        return key

    protected = RUNTIME_PROTO_RE.sub(replacer, text)
    return protected, sentinels


def restore_sentinels(text, sentinels):
    """Restore sentinels to their original .prototype strings."""
    for key, original in sentinels.items():
        text = text.replace(key, original)
    return text


# ---------------------------------------------------------------------------
# Token-level renames — applied globally (identifiers, CSS classes, etc.)
# Most-specific compound names listed first.
# ---------------------------------------------------------------------------

TOKEN_RENAMES = [
    # ── Compound camelCase/PascalCase project identifiers ──────────────────

    # Dunder sentinel
    (r'\b__prototypeWrapped__\b',           '__renderWrapped__'),

    # Named compound identifiers (from the specification)
    (r'\bprototypeRendererSignature\b',     'rendererSignature'),
    (r'\bprototypeRenderer\b',              'fileRenderer'),
    (r'\bprototypeWrapper\b',               'renderWrapper'),
    (r'\bprototypeDisplay\b',               'displayView'),
    (r'\bprototypeSelectedItems\b',         'selectedItems'),
    (r'\bprototypeContainer\b',             'containerElement'),
    (r'\bprototypeMeta\b',                  'viewMetadata'),
    (r'\bprototypeClipboard\b',             'clipboardView'),
    (r'\bprototypePanel\b',                 'panelMetadata'),
    (r'\bprototypeHistory\b',               'renderHistory'),
    (r'\bprototypeRender\b',                'fileRender'),
    (r'\bprototypeDropzone\b',              'dropzoneIntegration'),
    (r'\bprototypeList\b',                  'renderList'),
    (r'\bprototypeSlice\b',                 'renderSlice'),
    (r'\bprototypeReason\b',                'renderReason'),
    (r'\bprototypeWrapped\b',               'renderWrapped'),

    # ── Function-name patterns ─────────────────────────────────────────────
    (r'\brenderPrototypeFileList\b',        'renderFileList'),
    (r'\bsyncPrototypeClipboard\b',         'syncClipboardView'),
    (r'\brenderPrototype\b',                'renderView'),
    (r'\bprototypeDraw\b',                  'drawView'),
    (r'\bprototypeUpdate\b',                'updateView'),
    (r'\bprototypeInit\b',                  'initView'),

    # ── Reason/event string tokens (underscore-delimited variants) ────────
    # These appear as string event/reason identifiers like "prototype_render".
    # Note: \bprototype\b does NOT match these because _ is \w (no word boundary).
    (r'\bprototype_render\b',               'file_render'),
    (r'\bprototype_list\b',                 'file_list'),
    (r'\brender_prototype\b',               'render_view'),

    # ── CSS / HTML hyphenated class names ──────────────────────────────────
    (r'\bgdrive-preview-overlay\b',         'lv-preview-overlay'),
    (r'\bgdrive-toolbar\b',                 'lv-toolbar'),
    (r'\bgdrive-sidebar\b',                 'lv-sidebar'),
    (r'\bgdrive-file-card\b',               'lv-file-card'),
    (r'\bgdrive-file-list\b',               'lv-file-list'),
    (r'\bgdrive-modal\b',                   'lv-modal'),
    (r'\bgdrive-nav\b',                     'lv-nav'),
    (r'\bgdrive-badge\b',                   'lv-badge'),
    (r'\bgdrive-icon\b',                    'lv-icon'),
    (r'\bgdrive-btn\b',                     'lv-btn'),
    (r'\bgdrive-style\b',                   'lv-style'),
    (r'\bgdrive-panel\b',                   'lv-panel'),
    (r'\bgdrive-search\b',                  'lv-search'),
    (r'\bgdrive-upload\b',                  'lv-upload'),
    (r'\bgdrive-progress\b',                'lv-progress'),
    (r'\bgdrive-header\b',                  'lv-header'),
    (r'\bgdrive-footer\b',                  'lv-footer'),
    (r'\bgdrive-grid\b',                    'lv-grid'),
    (r'\bgdrive-list\b',                    'lv-list'),

    # ── Bare identifier forms ──────────────────────────────────────────────
    (r'\bGDRIVE\b',                         'LANVAN'),
    (r'\bGDrive\b',                         'Lanvan'),
    (r'\bgdrive\b',                         'lanvan'),
    (r'\bGoogle\s+Drive\b',                 'Lanvan'),
    (r'\bgoogle\s+drive\b',                 'lanvan'),
    (r'\bdrive-like\b',                     'Lanvan-style'),
    (r'\bdrive\s*-\s*style\b',              'Lanvan-style'),
    (r'\bDrive\s+style\b',                  'Lanvan style'),
    (r'\bdrive\s+style\b',                  'Lanvan style'),

    # ── PascalCase project-concept variants ────────────────────────────────
    (r'\bPrototypeUI\b',                    'LanvanUI'),
    (r'\bPrototypeApp\b',                   'LanvanApp'),
    (r'\bPrototypeView\b',                  'LanvanView'),
    (r'\bPrototypePage\b',                  'LanvanPage'),
]

COMPILED_TOKEN_RENAMES = [
    (re.compile(pattern), replacement)
    for pattern, replacement in TOKEN_RENAMES
]


# ---------------------------------------------------------------------------
# Phrase-level renames — applied to comment lines AND string literals
# ---------------------------------------------------------------------------

PHRASE_RENAMES = [
    # Multi-word phrases (most specific first)
    (re.compile(r'\bprototype renderer\b',               re.IGNORECASE), 'file renderer'),
    (re.compile(r'\bprototype wrappers?\b',               re.IGNORECASE), 'rendering wrapper'),
    (re.compile(r'\bprototype UI\b',                      re.IGNORECASE), 'Lanvan UI'),
    (re.compile(r'\bprototype adapter\b',                 re.IGNORECASE), 'UI integration layer'),
    (re.compile(r'\bprototype display\b',                 re.IGNORECASE), 'display renderer'),
    (re.compile(r'\bprototype containers?\b',             re.IGNORECASE), 'UI container'),
    (re.compile(r'\bprototype helpers?\b',                re.IGNORECASE), 'render helper'),
    (re.compile(r'\bprototype component\b',               re.IGNORECASE), 'UI component'),
    (re.compile(r'\bprototype layer\b',                   re.IGNORECASE), 'render layer'),
    (re.compile(r'\bprototype file\b',                    re.IGNORECASE), 'Lanvan file'),
    (re.compile(r'\bprototype dom\b',                     re.IGNORECASE), 'Lanvan DOM'),
    (re.compile(r'\bprototype dropzone\b',                re.IGNORECASE), 'dropzone integration'),
    (re.compile(r'\boutput prototype dom\b',              re.IGNORECASE), 'output Lanvan DOM'),
    (re.compile(r'\bchecking for prototype dropzone\b',   re.IGNORECASE), 'checking for fallback dropzone'),
    (re.compile(r'\btrying prototype input\b',            re.IGNORECASE), 'trying fallback input'),
    (re.compile(r'\bprototype hidden file input\b',       re.IGNORECASE), 'fallback file input'),
    (re.compile(r'\bprototype input\b',                   re.IGNORECASE), 'fallback input'),
    (re.compile(r'\bprototype dropzone\b',                re.IGNORECASE), 'fallback dropzone'),

    # Audit / testing terminology
    (re.compile(r'prototype-only,\s*skip',                re.IGNORECASE), 'reference-only, skip'),
    (re.compile(r'must match prototype',                  re.IGNORECASE), 'must match reference build'),
    (re.compile(r'matches prototype',                     re.IGNORECASE), 'matches reference build'),
    (re.compile(r'match prototype\b',                     re.IGNORECASE), 'match reference build'),
    (re.compile(r'Prototype Limitation',                  re.IGNORECASE), 'Reference Limitation'),
    (re.compile(r'Lanvan improved over prototype',        re.IGNORECASE), 'Lanvan improved over reference build'),
    (re.compile(r'Intentional Improvement.*?prototype',   re.IGNORECASE), 'Intentional Improvement over reference'),
    (re.compile(r'prototype-only',                        re.IGNORECASE), 'reference-only'),
    (re.compile(r'DIFF:\s*Prototype vs Lanvan',           re.IGNORECASE), 'DIFF: Reference vs Lanvan'),
    (re.compile(r'Compare prototype vs Lanvan',           re.IGNORECASE), 'Compare reference vs Lanvan'),
    (re.compile(r'Prototype:\s',                          re.IGNORECASE), 'Reference: '),
    (re.compile(r'"Prototype"',                           re.IGNORECASE), '"Reference"'),
    (re.compile(r'"PROTOTYPE"',                           re.IGNORECASE), '"REFERENCE"'),
    (re.compile(r'Inspect Prototype\b',                   re.IGNORECASE), 'Inspect Reference Build'),
    (re.compile(r'Adapted from prototype for production', re.IGNORECASE), 'Adapted for production'),
    (re.compile(r'Added missing prototype selector',      re.IGNORECASE), 'Added missing selector'),
    (re.compile(r'Merge remaining prototype classes',     re.IGNORECASE), 'Merge remaining classes'),
    (re.compile(r'missing prototype selector',            re.IGNORECASE), 'missing selector'),

    # Google Drive / GDrive
    (re.compile(r'\bGoogle Drive\b'),                      'Lanvan'),
    (re.compile(r'\bgoogle drive\b',         re.IGNORECASE), 'Lanvan'),
    (re.compile(r'\bGDrive\b'),                            'Lanvan'),
    (re.compile(r'\bgdrive\b',               re.IGNORECASE), 'lanvan'),
    (re.compile(r'\bdrive-like\b',           re.IGNORECASE), 'Lanvan-style'),
    (re.compile(r'\bdrive style\b',          re.IGNORECASE), 'Lanvan style'),

    # Catch-all for bare "prototype" word
    (re.compile(r'\bprototype\b',                         re.IGNORECASE), 'production'),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_comment_context(line):
    """Heuristic: is this line primarily a comment or docstring?"""
    stripped = line.strip()
    return (
        stripped.startswith('//')
        or stripped.startswith('/*')
        or stripped.startswith('*')
        or stripped.startswith('#')
        or stripped.startswith('<!--')
        or stripped.startswith('"""')
        or stripped.startswith("'''")
    )


def apply_token_renames(text):
    """Apply all identifier-level renames to the entire text."""
    for pattern, replacement in COMPILED_TOKEN_RENAMES:
        text = pattern.sub(replacement, text)
    return text


def apply_phrase_renames_to_comments(text):
    """Apply phrase-level rewrites to comment and docstring lines."""
    lines = text.splitlines(keepends=True)
    result = []
    in_block_comment = False

    for line in lines:
        if '/*' in line:
            in_block_comment = True
        if in_block_comment or is_comment_context(line):
            for pattern, replacement in PHRASE_RENAMES:
                line = pattern.sub(replacement, line)
        if '*/' in line:
            in_block_comment = False
        result.append(line)

    return ''.join(result)


# String literal regex — matches single/double-quoted strings, f-strings, template literals
_STRING_LIT_RE = re.compile(
    r'""".*?"""|'           # Python triple-double
    r"'''.*?'''|"           # Python triple-single
    r'f?"(?:[^"\\]|\\.)*"|'  # Double-quoted / f-string
    r"f?'(?:[^'\\]|\\.)*'|"  # Single-quoted / f-string
    r'`(?:[^`\\]|\\.)*`',   # JS template literal
    re.DOTALL,
)


def _rename_in_string_literal(m):
    """Apply phrase renames inside a single captured string literal."""
    result = m.group(0)
    for pattern, replacement in PHRASE_RENAMES:
        result = pattern.sub(replacement, result)
    return result


def apply_phrase_renames_to_strings(text):
    """Apply phrase-level rewrites inside quoted string literals in code."""
    return _STRING_LIT_RE.sub(_rename_in_string_literal, text)


# HTML text-content regex — matches text between HTML tags
_HTML_TEXT_RE = re.compile(r'>([^<\n]+)<')


def _rename_in_html_text(m):
    """Apply phrase renames to text between HTML tags."""
    original = m.group(1)
    result = original
    for pattern, replacement in PHRASE_RENAMES:
        result = pattern.sub(replacement, result)
    if result != original:
        return f'>{result}<'
    return m.group(0)


def apply_phrase_renames_to_html_text(text):
    """Apply phrase-level rewrites to bare text between HTML tags."""
    return _HTML_TEXT_RE.sub(_rename_in_html_text, text)


def transform_content(content):
    """
    Full transformation pipeline:
      1. Protect all .prototype chains with sentinels
      2. Token-level identifier renames (global, including inside strings)
      3. Phrase renames in comment/docstring lines
      4. Phrase renames inside string literals in code
      5. Phrase renames inside HTML tag text content
      6. Restore sentinels
    """
    protected, sentinels = protect_runtime_patterns(content)
    out = apply_token_renames(protected)
    out = apply_phrase_renames_to_comments(out)
    out = apply_phrase_renames_to_strings(out)
    out = apply_phrase_renames_to_html_text(out)
    out = restore_sentinels(out, sentinels)
    return out


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def should_process(path: Path) -> bool:
    """Return True if this file should be processed."""
    for part in path.parts:
        if part in SKIP_DIRS:
            return False
    if path.name in SKIP_FILES:
        return False
    if path.name in DELETE_STALE_FILES:
        return False
    if path.suffix.lower() not in PROCESS_EXTENSIONS:
        return False
    return True


def should_delete(path: Path) -> bool:
    """Return True if this file is a stale generated artifact to delete."""
    for part in path.parts:
        if part in SKIP_DIRS:
            return False
    return path.name in DELETE_STALE_FILES


def iter_repo_files(root: Path):
    """Yield all processable files in the repository."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if should_process(fpath):
                yield fpath
            elif should_delete(fpath):
                yield fpath  # included so we can delete it


# ---------------------------------------------------------------------------
# Banned-terms counter (for before/after reporting)
# Includes both standalone words AND compound camelCase identifiers.
# ---------------------------------------------------------------------------

BANNED_RE = re.compile(
    r'(?<![.\w])('
    # Standalone words
    r'prototype|Prototype|PROTOTYPE'
    r'|gdrive|GDrive|GDRIVE'
    r'|Google\s+Drive|google\s+drive'
    r'|drive-like|drive\s+style|Drive\s+style'
    # Compound camelCase identifiers
    r'|prototypeSelectedItems|prototypeRenderer|prototypeWrapper'
    r'|prototypeDisplay|prototypeContainer|prototypeMeta'
    r'|prototypeClipboard|prototypePanel|prototypeHistory'
    r'|prototypeRender|prototypeDropzone|prototypeList'
    r'|prototypeSlice|prototypeReason|prototypeWrapped'
    r'|__prototypeWrapped__'
    r'|renderPrototypeFileList|syncPrototypeClipboard'
    r'|renderPrototype|prototypeDraw|prototypeUpdate|prototypeInit'
    r')(?!\w)',
)


def count_banned(text):
    """Count non-.prototype-chain banned occurrences in text."""
    protected, _ = protect_runtime_patterns(text)
    return len(BANNED_RE.findall(protected))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Lanvan production naming enforcement"
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Report what would change without modifying files"
    )
    args = parser.parse_args()

    # Force UTF-8 output (avoids cp1252 errors on Windows terminals)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\n{'='*70}")
    print(f"  Lanvan Production Naming Enforcement  [{mode}]")
    print(f"{'='*70}\n")

    total_before  = 0
    total_after   = 0
    files_scanned = 0
    files_changed = 0
    files_deleted = 0
    remaining_hits = []

    for fpath in sorted(iter_repo_files(REPO_ROOT)):
        rel = fpath.relative_to(REPO_ROOT)

        # Handle stale generated files — delete them
        if fpath.name in DELETE_STALE_FILES:
            if fpath.exists():
                print(f"  [DELETE] {rel}  (stale generated artifact)")
                if not args.dry_run:
                    try:
                        fpath.unlink()
                        files_deleted += 1
                    except Exception as exc:
                        print(f"    ERROR deleting {rel}: {exc}")
            continue

        files_scanned += 1

        try:
            content = fpath.read_text(encoding='utf-8', errors='replace')
        except Exception as exc:
            print(f"  [SKIP] {rel} — read error: {exc}")
            continue

        before = count_banned(content)
        total_before += before

        # Always transform (don't skip on zero count — camelCase compounds
        # are not counted by BANNED_RE but ARE renamed by token pass)
        new_content = transform_content(content)
        after = count_banned(new_content)
        total_after += after

        changed = new_content != content

        if changed:
            files_changed += 1
            print(f"  [MODIFY] {rel}  ({before} -> {after})")
            if not args.dry_run:
                try:
                    fpath.write_text(new_content, encoding='utf-8')
                except Exception as exc:
                    print(f"    ERROR writing {rel}: {exc}")

        # Collect remaining occurrences
        if after > 0:
            protected, _ = protect_runtime_patterns(new_content)
            for lineno, line in enumerate(protected.splitlines(), 1):
                if BANNED_RE.search(line):
                    remaining_hits.append((str(rel), lineno, line.strip()))

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"  Files scanned       : {files_scanned}")
    print(f"  Files modified      : {files_changed}")
    print(f"  Stale files deleted : {files_deleted}")
    print(f"  Occurrences BEFORE  : {total_before}")
    print(f"  Occurrences AFTER   : {total_after}")
    print()

    if remaining_hits:
        print(f"  REMAINING ({len(remaining_hits)} occurrences):")
        print(f"  {'--'*30}")
        for filepath, lineno, snippet in remaining_hits:
            print(f"  {filepath}:{lineno}")
            print(f"    {snippet}")
        print()
    else:
        print("  All production naming rules satisfied. Zero banned terms remain.")
        print()

    return 0 if not remaining_hits else 1


if __name__ == '__main__':
    sys.exit(main())
