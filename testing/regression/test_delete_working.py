"""
Playwright test: Verify delete actually deletes the file (not just no popup).
"""
import sys
import os
import time
import urllib.request
from playwright.sync_api import sync_playwright

LANVAN_DIR = r"c:\Users\Public\Probz\Code\lanvan"
os.chdir(LANVAN_DIR)

# Check server
print("[*] Checking server...")
try:
    r = urllib.request.urlopen("http://127.0.0.1:5000", timeout=3)
    print(f"[*] Server up (HTTP {r.status})")
except:
    print("[!] Server not running!")
    sys.exit(1)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="msedge")
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    # Capture ALL console messages
    console_logs = []
    page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

    # Track network responses and failures
    network_results = []
    def on_response(response):
        url = response.url
        if any(kw in url for kw in ['delete', 'upload', 'files', 'clear', 'remove']):
            network_results.append(f"[RESPONSE] {response.status} {response.request.method} {url}")
    def on_request_failed(request):
        network_results.append(f"[FAILED] {request.method} {request.url} - {request.failure}")
    page.on("response", on_response)
    page.on("requestfailed", on_request_failed)

    print("[1] Navigating to Lanvan...")
    page.goto("http://127.0.0.1:5000", wait_until="networkidle")
    page.wait_for_timeout(2000)
    print("   Page loaded")

    # Check JS console for errors
    js_errors = [l for l in console_logs if 'error' in l.lower() or 'ERR' in l or 'fail' in l.lower()]
    if js_errors:
        print(f"   JS errors found: {len(js_errors)}")
        for e in js_errors[:10]:
            print(f"     {e}")
    else:
        print("   No JS errors on page load")

    # Check if deleteSelected exists
    has_delete = page.evaluate("() => typeof window.deleteSelected")
    print(f"   window.deleteSelected exists: {has_delete}")

    # Upload a test file
    test_file_path = os.path.join(LANVAN_DIR, "testing", "test_workspace", "delete_test_verify.txt")
    os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
    with open(test_file_path, "w") as f:
        f.write("This file should be deleted by the Playwright test")

    print("[2] Uploading test file...")
    file_input = page.locator("#fileInput")
    if file_input.count() > 0:
        file_input.set_input_files(test_file_path)
        page.wait_for_timeout(3000)
        print("   File uploaded")
    else:
        print("   [!] #fileInput not found, trying prototype input")
        proto_input = page.locator("#hiddenFileInput")
        if proto_input.count() > 0:
            proto_input.set_input_files(test_file_path)
            page.wait_for_timeout(2000)

    page.wait_for_timeout(2000)

    # Find our file
    print("[3] Finding test file in list...")
    file_found = page.evaluate("""() => {
        const items = document.querySelectorAll('#nasFileList .m3-list-item');
        for (let item of items) {
            const title = item.querySelector('.item-title');
            if (title && title.textContent.includes('delete_test_verify')) {
                return {found: true, name: title.textContent.trim()};
            }
        }
        return {found: false};
    }""")
    print(f"   File found: {file_found}")

    if file_found.get("found"):
        target_name = file_found["name"]
        print(f"[4] Deleting file: {target_name}")

        # First approach: Use context menu delete
        # Right click on the file item
        print("   Right-clicking on file...")
        target_item = page.locator(f'.m3-list-item:has(.item-title:text-is("{target_name}"))')
        if target_item.count() == 0:
            target_item = page.locator(".m3-list-item").first

        target_item.click(button="right")
        page.wait_for_timeout(1000)

        # Check if context menu is visible
        ctx_visible = page.evaluate("""() => {
            const menu = document.getElementById('contextMenu');
            return menu ? menu.style.display : 'no-menu';
        }""")
        print(f"   Context menu visible: {ctx_visible}")

        # Try clicking context menu delete
        ctx_delete = page.locator("#itemMenuOptions .context-item[onclick*='deleteSelected']")
        if ctx_delete.count() > 0 and ctx_delete.first.is_visible():
            print("   Clicking 'Delete' in context menu...")
            ctx_delete.first.click()
            page.wait_for_timeout(2000)
        else:
            print("   Context menu delete not visible, trying toolbar...")
            # Click the file to select it
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            target_item.click()
            page.wait_for_timeout(500)
            
            # Check selection toolbar
            toolbar_visible = page.evaluate("""() => {
                const sel = document.getElementById('toolbarSelectionContent');
                return sel ? sel.style.display : 'no-toolbar';
            }""")
            print(f"   Selection toolbar visible: {toolbar_visible}")

            # Try toolbar delete button
            del_btn = page.locator('[onclick*="deleteSelected"]')
            if del_btn.count() > 0 and del_btn.first.is_visible():
                print("   Clicking toolbar delete button...")
                del_btn.first.click()
                page.wait_for_timeout(2000)

        # Check network results
        print("\n[5] Network activity:")
        for r in network_results:
            print(f"   {r}")

        # Check if delete was actually called
        delete_calls = [r for r in network_results if '/delete/' in r]
        print(f"\n   Delete API calls: {len(delete_calls)}")
        for d in delete_calls:
            print(f"     {d}")

        # Check if file is gone from the list
        page.wait_for_timeout(2000)
        file_still_there = page.evaluate("""() => {
            const items = document.querySelectorAll('#nasFileList .m3-list-item .item-title');
            for (let t of items) {
                if (t.textContent.includes('delete_test_verify')) return true;
            }
            return false;
        }""")
        print(f"\n[6] File still in list: {file_still_there}")

    else:
        print("   [!] Test file not found in list, checking raw page content...")
        # Check what's actually in the file list
        raw_list = page.evaluate("""() => {
            const container = document.getElementById('nasFileList');
            return container ? container.innerHTML.substring(0, 500) : 'no-nasFileList';
        }""")
        print(f"   nasFileList content: {raw_list[:300]}")

        # Also check production file grid
        grid = page.evaluate("""() => {
            const g = document.getElementById('fileGrid');
            return g ? g.innerHTML.substring(0, 300) : 'no-fileGrid';
        }""")
        print(f"   fileGrid content: {grid[:200]}")

    # Final console errors
    recent_errors = [l for l in console_logs if 'error' in l.lower()]
    print(f"\n[7] Total JS errors: {len(recent_errors)}")
    for e in recent_errors[:10]:
        print(f"   {e}")

    page.wait_for_timeout(1000)
    browser.close()
    print("\n[*] Test complete")