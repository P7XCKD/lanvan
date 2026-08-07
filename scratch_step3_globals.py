import sys, re
from pathlib import Path

js_dir = Path('app/static/js')
all_js = sorted([f for f in js_dir.rglob('*.js') if not f.name.endswith('.min.js')])

print("="*60)
print("PHASE 3 — STEP 3: GLOBAL SCOPE AUDIT REPORT")
print("="*60)

window_exports = {}

for filepath in all_js:
    code = filepath.read_text(encoding='utf-8', errors='ignore')
    rel_path = str(filepath.relative_to(js_dir))
    
    # Search for window.XYZ = ...
    matches = re.finditer(r'^\s*window\.([a-zA-Z0-9_$]+)\s*=\s*(.*?);?$', code, re.MULTILINE)
    for m in matches:
        name = m.group(1)
        expr = m.group(2).strip()
        line = code[:m.start()].count('\n') + 1
        
        is_wrapper = 'apply(this' in expr or 'window.' in expr or 'function()' in expr or 'function (' in expr
        
        if name not in window_exports:
            window_exports[name] = []
        window_exports[name].append({
            'module': rel_path,
            'line': line,
            'expr': expr[:60],
            'is_wrapper': is_wrapper
        })

print(f"Total Unique window.* Exports Discovered: {len(window_exports)}\n")

multi_exports = {k: v for k, v in window_exports.items() if len(v) > 1}
print(f"Exports defined in multiple places: {len(multi_exports)}")
for name, locs in sorted(multi_exports.items()):
    print(f"\n• window.{name}:")
    for l in locs:
        w_tag = "[WRAPPER ALIAS]" if l['is_wrapper'] else "[PRIMARY IMPLEMENTATION]"
        print(f"    - {l['module']}:L{l['line']} {w_tag} -> {l['expr']}")
