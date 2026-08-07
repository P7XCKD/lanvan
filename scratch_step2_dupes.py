import sys, re
from pathlib import Path

js_dir = Path('app/static/js')
all_js = sorted([f for f in js_dir.rglob('*.js') if not f.name.endswith('.min.js')])

print("="*60)
print("PHASE 3 — STEP 2: DUPLICATE IMPLEMENTATION AUDIT")
print("="*60)

# Map function_name -> list of (file, line_no, full_declaration_type)
func_defs = {}

for filepath in all_js:
    code = filepath.read_text(encoding='utf-8', errors='ignore')
    rel_path = str(filepath.relative_to(js_dir))
    
    # 1. Named functions: function funcName(...)
    for match in re.finditer(r'^\s*function\s+([a-zA-Z0-9_$]+)\s*\(', code, re.MULTILINE):
        fname = match.group(1)
        line_no = code[:match.start()].count('\n') + 1
        if fname not in func_defs: func_defs[fname] = []
        func_defs[fname].append({'file': rel_path, 'line': line_no, 'type': 'function declaration'})
        
    # 2. window exports / assignments: window.funcName = function / (args) =>
    for match in re.finditer(r'^\s*window\.([a-zA-Z0-9_$]+)\s*=\s*(function|\([^)]*\)\s*=>|\w+\s*=>)', code, re.MULTILINE):
        fname = match.group(1)
        line_no = code[:match.start()].count('\n') + 1
        if fname not in func_defs: func_defs[fname] = []
        func_defs[fname].append({'file': rel_path, 'line': line_no, 'type': 'window assignment'})

dupes = {k: v for k, v in func_defs.items() if len(v) > 1}

print(f"Total Unique Function Symbols Analyzed: {len(func_defs)}")
print(f"Duplicate Function Symbol Occurrences: {len(dupes)}\n")

for fname, locations in sorted(dupes.items()):
    print(f"• Symbol: {fname} ({len(locations)} occurrences)")
    for loc in locations:
        print(f"    - {loc['file']}:L{loc['line']} ({loc['type']})")
