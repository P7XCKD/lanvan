import sys, re
from pathlib import Path

js_dir = Path('app/static/js')
all_js = sorted([f for f in js_dir.rglob('*.js') if not f.name.endswith('.min.js')])

print("="*60)
print("PHASE 3 — STEP 5: INITIALIZATION & AUDIT")
print("="*60)

# Check DOMContentLoaded, setInterval, setTimeout, rAF, observers
for filepath in all_js:
    rel = str(filepath.relative_to(js_dir))
    code = filepath.read_text(encoding='utf-8', errors='ignore')
    
    dom_loaded = len(re.findall(r'DOMContentLoaded', code))
    intervals = len(re.findall(r'setInterval', code))
    timeouts = len(re.findall(r'setTimeout', code))
    rafs = len(re.findall(r'requestAnimationFrame', code))
    mut_obs = len(re.findall(r'MutationObserver', code))
    res_obs = len(re.findall(r'ResizeObserver', code))
    ws_conns = len(re.findall(r'new\s+WebSocket', code))
    
    print(f"• {rel}:")
    print(f"    - DOMContentLoaded: {dom_loaded}")
    print(f"    - setInterval / setTimeout: {intervals} / {timeouts}")
    print(f"    - requestAnimationFrame: {rafs}")
    print(f"    - Observers (Mutation/Resize): {mut_obs} / {res_obs}")
    print(f"    - WebSockets: {ws_conns}")
