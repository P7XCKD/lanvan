#!/usr/bin/env python3
"""
Playwright Runtime Diagnostics Tool
Answers: Which CSS loaded? What styles won? Why does it look different?
"""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"
BASE = Path(__file__).parent.parent.parent
LANVAN_URL = "http://localhost"
PROTO_URL = f"file:///{BASE}/prototype/prototype.html"

CRITICAL_ELEMENTS = [
    ("body", "body"),
    ("root", ":root"),
    (".app-sidebar", ".app-sidebar"),
    (".search-shell", ".search-shell"),
    (".app-bar", ".app-bar"),
    (".m3-card", ".m3-card"),
    (".m3-list-item", ".m3-list-item"),
    (".quick-card", ".quick-card"),
    (".btn-icon", ".btn-icon"),
    (".file-toolbar", ".file-toolbar"),
    (".bottom-nav", ".bottom-nav"),
    (".m3-primary-btn", ".m3-primary-btn"),
    (".sidebar-item", ".sidebar-item"),
]

CRITICAL_PROPS = ["font-family", "color", "background-color", "padding", "margin",
                  "border-radius", "font-size", "font-weight", "width", "height",
                  "display", "gap", "overflow"]

def inspect_page(page, url, label):
    """Inspect a page and return diagnostics."""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  Inspecting: {label}{RESET}")
    print(f"{BOLD}  URL: {url}{RESET}")
    print(f"{BOLD}{'='*60}")

    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1000)

    report = {"label": label, "url": url, "stylesheets": [], "computed": {}, "css_vars": {},
              "console": [], "layout": {}, "fonts": []}

    # ── 1. Network: Loaded Stylesheets ──
    print(f"\n{BOLD}1. Loaded Stylesheets{RESET}")
    stylesheets = page.evaluate("""() => {
        return Array.from(document.styleSheets).map(s => {
            let rulesCount = 0;
            try { rulesCount = s.cssRules ? s.cssRules.length : 0; } catch(e) {}
            return {
                href: s.href || '(inline)',
                disabled: s.disabled,
                rulesCount: rulesCount
            };
        });
    }""")
    for ss in stylesheets:
        status = f"{GREEN}ACTIVE{RESET}" if not ss["disabled"] else f"{RED}DISABLED{RESET}"
        print(f"  {status} {ss['href']} ({ss['rulesCount']} rules)")
        report["stylesheets"].append(ss)

    # ── 2. Console Errors ──
    print(f"\n{BOLD}2. Console Errors{RESET}")
    console_msgs = []
    page.on("console", lambda msg: console_msgs.append({"type": msg.type, "text": msg.text}))
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1000)
    errors = [m for m in console_msgs if m["type"] == "error"]
    if errors:
        for e in errors:
            print(f"  {RED}ERROR{RESET} {e['text'][:100]}")
    else:
        print(f"  {GREEN}No console errors{RESET}")
    report["console"] = errors

    # ── 3. CSS Custom Properties (:root) ──
    print(f"\n{BOLD}3. CSS Custom Properties (:root){RESET}")
    css_vars = page.evaluate("""() => {
        const styles = getComputedStyle(document.documentElement);
        const vars = {};
        for (let i = 0; i < styles.length; i++) {
            const prop = styles[i];
            if (prop.startsWith('--')) {
                vars[prop] = styles.getPropertyValue(prop).trim();
            }
        }
        return vars;
    }""")
    for var_name in sorted(css_vars.keys())[:15]:
        print(f"  {var_name}: {css_vars[var_name]}")
    report["css_vars"] = css_vars

    # ── 4. Computed Styles for Critical Elements ──
    print(f"\n{BOLD}4. Computed Styles (Critical Elements){RESET}")
    for name, selector in CRITICAL_ELEMENTS:
        try:
            computed = page.evaluate(f"""(selector) => {{
                const el = document.querySelector(selector);
                if (!el) return null;
                const styles = getComputedStyle(el);
                const result = {{}};
                const props = {json.dumps(CRITICAL_PROPS)};
                for (const p of props) {{
                    result[p] = styles.getPropertyValue(p).trim();
                }}
                return result;
            }}""", selector)
            if computed:
                print(f"  {GREEN}{name}{RESET}: font={computed.get('font-family','?')[:30]}, color={computed.get('color','?')}, bg={computed.get('background-color','?')}")
                report["computed"][name] = computed
            else:
                print(f"  {RED}{name}{RESET}: NOT FOUND in DOM")
        except Exception as e:
            print(f"  {RED}{name}{RESET}: Error - {e}")

    # ── 5. Layout Metrics ──
    print(f"\n{BOLD}5. Layout Metrics (Key Elements){RESET}")
    layout_elements = [".app-sidebar", ".search-shell", ".app-bar", ".app-content", ".bottom-nav"]
    for sel in layout_elements:
        try:
            rect = page.evaluate(f"""(sel) => {{
                const el = document.querySelector(sel);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {{ width: Math.round(r.width), height: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left) }};
            }}""", sel)
            if rect:
                print(f"  {sel}: {rect['width']}×{rect['height']}px (top={rect['top']}, left={rect['left']})")
                report["layout"][sel] = rect
            else:
                print(f"  {RED}{sel}: NOT FOUND{RESET}")
        except Exception as e:
            print(f"  {RED}{sel}: Error{RESET}")

    # ── 6. Fonts ──
    print(f"\n{BOLD}6. Loaded Fonts{RESET}")
    fonts = page.evaluate("""() => {
        return Array.from(document.fonts).map(f => ({
            family: f.family,
            status: f.status,
            weight: f.weight,
            style: f.style
        }));
    }""")
    for f in fonts[:8]:
        status = f"{GREEN}loaded{RESET}" if f["status"] == "loaded" else f"{YELLOW}{f['status']}{RESET}"
        print(f"  {status} {f['family']} ({f['weight']} {f['style']})")
    report["fonts"] = fonts

    return report


def diff_reports(proto_report, lanvan_report):
    """Compare prototype vs Lanvan computed styles."""
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}  DIFF: Prototype vs Lanvan{RESET}")
    print(f"{BOLD}{'═'*60}")

    diffs = []
    for name in proto_report["computed"]:
        proto_styles = proto_report["computed"].get(name, {})
        lanvan_styles = lanvan_report["computed"].get(name, {})
        if not proto_styles or not lanvan_styles:
            continue

        for prop in CRITICAL_PROPS:
            pv = proto_styles.get(prop, "")
            lv = lanvan_styles.get(prop, "")
            if pv and lv and pv != lv:
                diffs.append({"element": name, "property": prop, "prototype": pv, "lanvan": lv})

    if diffs:
        print(f"\n  {RED}{len(diffs)} visual differences found:{RESET}")
        for d in diffs[:20]:
            print(f"  {d['element']}: {d['property']}")
            print(f"    {GREEN}Prototype:{RESET} {d['prototype']}")
            print(f"    {RED}Lanvan:{RESET}    {d['lanvan']}")
        if len(diffs) > 20:
            print(f"  ... and {len(diffs)-20} more")
        
        # Group by element for prioritization
        by_element = {}
        for d in diffs:
            by_element.setdefault(d["element"], []).append(d)
        
        print(f"\n  {BOLD}Priority by element:{RESET}")
        for name, issues in sorted(by_element.items(), key=lambda x: -len(x[1])):
            print(f"  {name}: {len(issues)} differences")
    else:
        print(f"\n  {GREEN}No visual differences detected!{RESET}")

    return diffs


# ── Main ──
print(f"\n{BOLD}{'═'*60}{RESET}")
print(f"{BOLD}  Playwright Runtime Diagnostics{RESET}")
print(f"{BOLD}{'═'*60}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 900})

    # Inspect Prototype
    proto_page = context.new_page()
    proto_report = inspect_page(proto_page, PROTO_URL, "PROTOTYPE")
    
    # Inspect Lanvan
    lanvan_page = context.new_page()
    lanvan_report = inspect_page(lanvan_page, LANVAN_URL, "LANVAN")

    # Diff
    diffs = diff_reports(proto_report, lanvan_report)

    # Save full report
    report_path = BASE / "testing" / "regression" / "runtime_css_report.json"
    with open(report_path, "w") as f:
        json.dump({
            "prototype": proto_report,
            "lanvan": lanvan_report,
            "diff_count": len(diffs),
            "diffs": diffs
        }, f, indent=2, default=str)

    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"\n  Full report saved: {report_path}")
    print(f"  Visual differences: {len(diffs)}")
    print(f"\n{BOLD}{'═'*60}{RESET}\n")

    browser.close()