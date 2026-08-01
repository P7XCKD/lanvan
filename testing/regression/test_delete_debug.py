"""Playwright debug test: Watch exactly what happens on delete click"""
import sys, os, time, urllib.request
from playwright.sync_api import sync_playwright

os.chdir(r"c:\Users\Public\Probz\Code\lanvan")

try:
    r = urllib.request.urlopen("http://127.0.0.1:5000", timeout=3)
    print(f"[*] Server up (HTTP {r.status})")
except:
    print("[!] Server not running")
    sys.exit(1)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="msedge")
    page = browser.new_page(viewport={"width": 1280, "height": 800})

    # Capture everything
    all_console = []
    all_network = []

    page.on("console", lambda m: all_console.append(f"[{m.type}] {m.text}"))
    page.on("request", lambda req: all_network.append(f"[REQ] {req.method} {req.url}") if any(k in req.url for k in ['delete','files','clear']) else None)
    page.on("response", lambda resp: all_network.append(f"[RESP {resp.status}] {resp.request.method} {resp.url}") if any(k in resp.url for k in ['delete','files','clear']) else None)
    page.on("requestfailed", lambda req: all_network.append(f"[FAIL] {req.method} {req.url} - {req.failure}") if any(k in req.url for k in ['delete','files','clear']) else None)

    print("[1] Loading Lanvan...")
    page.goto("http://127.0.0.1:5000", wait_until="networkidle")
    page.wait_for_timeout(2000)

    # Check critical globals
    js_state = page.evaluate("""() => {
        return {
            deleteSelected: typeof window.deleteSelected,
            selectedItems: window.selectedItems || 'N/A',
            appInitLoaded: window.__appInitLoaded,
            updateFileDisplay: typeof window.updateFileDisplay,
        };
    }""")
    print(f"   JS state: {js_state}")

    # Upload a file first so we have something to delete
    test_file = os.path.join(r"c:\Users\Public\Probz\Code\lanvan", "testing", "test_workspace", "del_debug.txt")
    os.makedirs(os.path.dirname(test_file), exist_ok=True)
    with open(test_file, "w") as f:
        f.write("debug")

    print("[2] Uploading test file...")
    file_input = page.locator("#fileInput")
    if file_input.count() > 0:
        file_input.set_input_files(test_file)
        page.wait_for_timeout(3000)
        print("   Upload done")
    else:
        print("   [!] #fileInput not found")

    page.wait_for_timeout(3000)

    # Check what's in the file list
    file_list_html = page.evaluate("""() => {
        const fl = document.getElementById('nasFileList');
        return fl ? fl.innerHTML.substring(0, 500) : 'NO NAS FILE LIST!';
    }""")
    print(f"   nasFileList HTML (first 500): {file_list_html[:500]}")

    # Find our file
    file_name = page.evaluate("""() => {
        const items = document.querySelectorAll('#nasFileList .m3-list-item .item-title');
        for (let t of items) {
            if (t.textContent.includes('del_debug')) return t.textContent.trim();
        }
        return null;
    }""")
    print(f"   Found test file: {file_name}")

    if file_name:
        # Method: Click to select, then use the toolbar delete button
        print("[3] Clicking file to select it...")
        item = page.locator(f'.m3-list-item').first
        item.click()
        page.wait_for_timeout(500)

        # Check selection state
        selected = page.evaluate("""() => {
            const items = document.querySelectorAll('#nasFileList .m3-list-item.selected');
            const sel = window.selectedItems || [];
            return {selectedElements: items.length, selectedItems: sel};
        }""")
        print(f"   Selection state: {selected}")

        # Check toolbar
        toolbar_state = page.evaluate("""() => {
            const sel = document.getElementById('toolbarSelectionContent');
            const def = document.getElementById('toolbarDefaultContent');
            return {
                toolbarSelectionDisplay: sel ? sel.style.display : 'none',
                toolbarDefaultDisplay: def ? def.style.display : 'none',
                toolbarSelectionHTML: sel ? sel.innerHTML.substring(0, 300) : 'none'
            };
        }""")
        print(f"   Toolbar state: {toolbar_state}")

        # Now click delete button
        print("[4] Looking for delete button...")
        # Try multiple selectors
        del_selectors = [
            '#toolbarSelectionContent [onclick*="deleteSelected"]',
            'button[onclick*="deleteSelected"]',
            '[onclick="deleteSelected()"]',
        ]
        for sel in del_selectors:
            btn = page.locator(sel)
            count = btn.count()
            print(f"   Selector '{sel}': {count} matches, first visible: {btn.first.is_visible() if count > 0 else 'N/A'}")

        # Click first visible delete button
        del_btn = page.locator('#toolbarSelectionContent [onclick*="deleteSelected"]')
        if del_btn.count() > 0 and del_btn.first.is_visible():
            print("   Clicking toolbar delete button...")
            del_btn.first.click()
            page.wait_for_timeout(2000)
        else:
            # Try using JS evaluate to call deleteSelected directly
            print("   Delete button not found/visible, calling deleteSelected() directly via JS...")
            result = page.evaluate("""() => {
                try {
                    window.deleteSelected();
                    return 'called';
                } catch(e) {
                    return 'error: ' + e.message;
                }
            }""")
            print(f"   Direct call result: {result}")

    # Wait for any network activity
    page.wait_for_timeout(2000)

    # Show all console output
    print("\n[5] CONSOLE OUTPUT:")
    for l in all_console[-20:]:
        print(f"   {l}")

    # Show network activity
    print("\n[6] NETWORK (relevant):")
    for n in all_network:
        print(f"   {n}")

    # Check if file still exists after delete
    file_still_exists = page.evaluate("""() => {
        const items = document.querySelectorAll('#nasFileList .m3-list-item .item-title');
        for (let t of items) {
            if (t.textContent.includes('del_debug')) return true;
        }
        return false;
    }""")
    print(f"\n[7] File still visible after delete: {file_still_exists}")

    # Check if there were errors
    errors = [l for l in all_console if l.startswith('[error]') or '[level:error' in l]
    print(f"\n[8] Console errors: {len(errors)}")
    for e in errors[:10]:
        print(f"   {e}")

    page.wait_for_timeout(1000)
    browser.close()
    print("\n[*] Done. Check the Edge browser window for visual confirmation.")