#!/usr/bin/env python3
"""Lanvan Visual Audit — Module 5 (CSS Property Comparison)"""
import re, sys
from pathlib import Path
from collections import defaultdict

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"
BASE = Path(__file__).parent.parent.parent
PROTO_CSS = BASE / "Reference" / "production.css"
LANVAN_CSS = BASE / "app" / "static" / "css" / "lanvan.css"
passed = 0; failed = 0; critical = 0

def check(component, condition, detail="", is_critical=True):
    global passed, failed, critical
    if condition:
        passed += 1; print(f"  {GREEN}PASS{RESET} {component}" + (f" — {detail}" if detail else ""))
    else:
        if is_critical:
            failed += 1; critical += 1
            print(f"  {RED}FAIL{RESET} {component}" + (f" — {detail}" if detail else "") + " [CRITICAL]")
        else:
            print(f"  {YELLOW}WARN{RESET} {component}" + (f" — {detail}" if detail else ""))

def parse_rules(css):
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    rules = {}
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
        sel = m.group(1).strip()
        body = m.group(2).strip()
        props = {}
        for pm in re.finditer(r'([a-zA-Z-]+)\s*:\s*([^;]+);', body):
            props[pm.group(1).strip()] = pm.group(2).strip()
        rules[sel] = props
    return rules

def norm(val):
    v = val.lower().replace(' ','')
    if v.startswith('#'):
        return v
    if 'px' in v or 'rem' in v or 'em' in v:
        return v
    return v

print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  Module 5: Visual Audit — CSS Property Comparison{RESET}")
print(f"{BOLD}{'='*60}")

proto_rules = parse_rules(Path(PROTO_CSS).read_text(encoding="utf-8")) if PROTO_CSS.exists() else {}
lanvan_rules = parse_rules(Path(LANVAN_CSS).read_text(encoding="utf-8")) if LANVAN_CSS.exists() else {}

# Critical selectors that must match reference build
critical_selectors = [
    ".app-sidebar", ".app-bar", ".search-shell", ".search-shell input",
    ".m3-card", ".m3-list-item", ".m3-list-item:hover", ".m3-list-item.selected",
    ".quick-card", ".quick-card:hover", ".bottom-nav", ".nav-item",
    ".btn-icon", ".btn-icon:hover", ".file-toolbar", ".filter-chip",
    ".upload-toast-stack", ".upload-toast", ".upload-toast-progress-fill",
    ".desktop-panel-header", ".panel-title", ".m3-primary-btn",
    ".clipboard-input-wrapper", ".clipboard-input",
    ".m3-dialog", ".custom-context-menu", ".context-item",
    ".sidebar-item", ".sidebar-item.active"
]

print(f"\n{BOLD}Critical CSS Selectors (must match reference build){RESET}")
print(f"{'─'*50}")

for sel in critical_selectors:
    proto_props = proto_rules.get(sel, {})
    lanvan_props = lanvan_rules.get(sel, {})
    
    if not proto_props:
        check(f"  {sel}", True, "reference-only, skip")
        continue
    
    if not lanvan_props:
        check(f"  {sel}", False, "MISSING from lanvan.css")
        continue
    
    # Compare key properties: display, position, padding, margin, border-radius, background, color
    key_props = ['display','position','padding','margin','border-radius','background','background-color',
                 'color','width','height','font-size','font-weight','gap','overflow','z-index']
    
    mismatches = []
    for kp in key_props:
        pv = proto_props.get(kp)
        lv = lanvan_props.get(kp)
        if pv and lv and norm(pv) != norm(lv):
            mismatches.append(f"{kp}: {pv} → {lv}")
    
    if not mismatches:
        check(f"  {sel}", True, "matches reference build")
    else:
        check(f"  {sel}", False, f"MISMATCHES: {', '.join(mismatches[:3])}")

print(f"\n{BOLD}Dark Mode Overrides{RESET}")
print(f"{'─'*50}")

dark_selectors = [s for s in proto_rules if 'dark' in s.lower()]
for ds in dark_selectors[:10]:
    check(f"  {ds}", ds in str(lanvan_rules.keys()), "present" if ds in str(lanvan_rules.keys()) else "MISSING")

total = passed + failed
score = round((passed / max(total, 1)) * 100, 1)
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"\n{BOLD}Module 5: Visual Audit Score{RESET}")
print(f"  {GREEN}Passed: {passed}{RESET}  {RED}Failed: {failed} (Critical: {critical}){RESET}  {BOLD}Score: {score}%{RESET}")
print(f"\n{'✅ Visual audit complete!' if critical == 0 else f'❌ {critical} CSS issues'}{RESET}\n")
sys.exit(0 if critical == 0 else 1)