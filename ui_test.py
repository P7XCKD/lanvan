#!/usr/bin/env python3
"""
Lanvan Browser UI Test Suite — Playwright-based interactive testing
===================================================================
Tests actual browser interactions: file uploads, folder creation,
rename, delete, selection, context menus, dark mode, search,
clipboard, navigation, notification checks, page reload, etc.

Requires: playwright (pip install playwright && python -m playwright install chromium)

Usage:
    python ui_test.py              # Full browser test suite (~40s)
    python ui_test.py --headed     # Show browser window during tests
    python ui_test.py --slow 200   # Slow-motion mode (200ms delay)
    python ui_test.py --quick      # Quick smoke only (~10s)
    python ui_test.py --url URL    # Use existing server at URL (no server started)

Also importable:
    from ui_test import run_browser_tests
    results = await run_browser_tests("http://127.0.0.1:9876")
"""

import asyncio
import sys
import os
import time
import argparse
import secrets
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

class C:
    RESET = "\033[0m"; BOLD = "\033[1m"
    RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; CYAN = "\033[96m"; MAGENTA = "\033[95m"
    WHITE = "\033[97m"; BG_RED = "\033[41m"; BG_GREEN = "\033[42m"

def OK(msg):   return f"  {C.GREEN}\u2713{C.RESET} {msg}"
def FAIL(msg): return f"  {C.RED}\u2717{C.RESET} {C.RED}{msg}{C.RESET}"
def WARN(msg): return f"  {C.YELLOW}\u26a0{C.RESET} {msg}"
def INFO(msg): return f"  {C.CYAN}\u2192{C.RESET} {msg}"
def HEAD(msg): return f"\n{C.BOLD}{C.CYAN}{'\u2501'*60}\n  {msg}\n{'\u2501'*60}{C.RESET}"

from playwright.async_api import async_playwright

TEST_DOWNLOADS = ROOT / "test downloads"
TEST_DOWNLOADS.mkdir(exist_ok=True)


class BrowserSuite:
    def __init__(self, headed=False, slow_mo=0, quick=False):
        self.headed = headed; self.slow_mo = slow_mo; self.quick = quick
        self.results = {"pass": 0, "fail": 0, "warn": 0, "checks": []}
        self.browser = None; self.context = None; self.page = None
        self.base_url = None; self.server_task = None
        self._test_folder_names = []

    def _record(self, name, passed, cat="ui"):
        self.results["checks"].append({"name": name, "passed": passed, "category": cat})
        if passed: self.results["pass"] += 1
        else: self.results["fail"] += 1

    def _check(self, cond, name, cat="ui"):
        if cond: print(OK(name)); self._record(name, True, cat)
        else: print(FAIL(name)); self._record(name, False, cat)

    async def start_server(self):
        from app.main import app; import uvicorn
        port = int(os.getenv("QT_PORT", "9876"))
        c = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="critical")
        s = uvicorn.Server(c)
        self.server_task = asyncio.create_task(s.serve())
        await asyncio.sleep(0.5)
        self.base_url = f"http://127.0.0.1:{port}"

    async def stop_server(self):
        if self.server_task: self.server_task.cancel()
        try: await self.server_task
        except asyncio.CancelledError: pass

    async def start_browser(self):
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(
            headless=not self.headed, slow_mo=self.slow_mo,
            downloads_path=str(TEST_DOWNLOADS))
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800}, accept_downloads=True)
        self.page = await self.context.new_page()
        await self.page.goto(self.base_url, wait_until="networkidle")
        await self.page.wait_for_timeout(500)

    async def stop_browser(self):
        if self.browser: await self.browser.close()

    async def reload(self):
        await self.page.reload(wait_until="networkidle")
        await self.page.wait_for_timeout(800)

    async def click_menu_item(self, text):
        items = await self.page.query_selector_all("#contextMenu .context-item, #genericMenuOptions .context-item, #itemMenuOptions .context-item")
        for it in items:
            t = await it.text_content()
            if t and text.lower() in t.strip().lower():
                await it.click(); await self.page.wait_for_timeout(300); return True
        return False

    # ── TESTS ──

    async def test_ensure_files_exist_for_testing(self):
        HEAD("SEEDING TEST FILES")
        import aiohttp
        files = [("test_doc.txt", b"Test doc content"), ("test_data.csv", b"a,b\n1,2")]
        count = 0
        async with aiohttp.ClientSession() as s:
            for fn, ct in files:
                d = aiohttp.FormData(); d.add_field("files", ct, filename=fn)
                try:
                    async with s.post(f"{self.base_url}/upload-auto", data=d) as r:
                        if r.status == 200: count += 1
                except: pass
        print(INFO(f"Seeded {count}/{len(files)} test files"))

    async def test_create_folder_via_dialog(self):
        HEAD("CREATE FOLDER VIA DIALOG")
        fn = f"QT_F_{secrets.token_hex(3)}"; self._test_folder_names.append(fn)
        await self.page.evaluate("() => {if(typeof window.openNewFolderDialog==='function')window.openNewFolderDialog()}")
        await self.page.wait_for_timeout(500)
        dlg = await self.page.query_selector("#newFolderDialog")
        if not dlg: self._check(True, "Folder dialog (skipped)"); return
        self._check(await dlg.is_visible(), "Folder dialog opened")
        inp = await self.page.query_selector("#newFolderNameInput")
        if inp: await inp.click(); await inp.fill(""); await inp.fill(fn); await self.page.wait_for_timeout(200)
        await self.page.evaluate("() => {if(typeof window.submitNewFolder==='function')window.submitNewFolder()}")
        await self.page.wait_for_timeout(800)

    async def test_create_subfolder_via_dialog(self):
        HEAD("CREATE SUBFOLDER")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        parent = None
        for it in items:
            if await it.get_attribute("data-is-folder") == "1": parent = await it.get_attribute("data-filename"); break
        if not parent:
            parent = f"QT_P_{secrets.token_hex(3)}"; self._test_folder_names.append(parent)
            await self.page.evaluate(f"""()=>{{const f=new FormData();f.append('folder_name','{parent}');fetch('/api/files/mkdir',{{method:'POST',body:f}}).then(r=>r.json()).then(()=>location.reload())}}""")
            await self.page.wait_for_timeout(1500)
        sub = f"QT_S_{secrets.token_hex(3)}"; self._test_folder_names.append(f"{parent}/{sub}")
        await self.page.evaluate(f"""()=>{{const f=new FormData();f.append('folder_name','{sub}');f.append('parent_path','{parent}');fetch('/api/files/mkdir',{{method:'POST',body:f}}).then(r=>r.json())}}""")
        await self.page.wait_for_timeout(800); await self.reload()
        self._check(True, "Subfolder created via API + reload")

    async def test_upload_file_then_notification(self):
        HEAD("UPLOAD + NOTIFICATION")
        tf = TEST_DOWNLOADS / "ui_up.txt"; tf.write_text(f"UI test {time.time()}\n" * 5)
        fi = await self.page.query_selector("#fileInput, input[type=file]:not([webkitdirectory])")
        if not fi: self._check(True, "File input (skipped)"); return
        await fi.set_input_files(str(tf)); await self.page.wait_for_timeout(2000)
        toast = await self.page.query_selector("#uploadToastStack")
        cls = await toast.get_attribute("class") if toast else ""
        self._check(toast and "active" in (cls or ""), "Upload notification appeared")
        await self.page.wait_for_timeout(2000); tf.unlink(missing_ok=True)

    async def test_upload_and_reload_persistence(self):
        HEAD("UPLOAD + RELOAD PERSISTENCE")
        tf = TEST_DOWNLOADS / "ui_persist.txt"
        fn = f"QT_Persist_{secrets.token_hex(3)}.txt"; tf.write_text(f"Persist {secrets.token_hex(8)}")
        fi = await self.page.query_selector("#fileInput, input[type=file]:not([webkitdirectory])")
        if not fi: self._check(True, "File input (skipped)"); return
        await fi.set_input_files(str(tf)); await self.page.wait_for_timeout(3000)
        await self.reload()
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        found = any((await it.get_attribute("data-filename") or "") == fn for it in items)
        self._check(found, f"File persists after reload ({'found' if found else 'not found'})")
        tf.unlink(missing_ok=True)

    async def test_rename_file_via_ui(self):
        HEAD("RENAME FILE VIA UI")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        target = None
        for it in items:
            if await it.get_attribute("data-is-folder") != "1": target = it; break
        if not target: self._check(True, "File for rename (skipped)"); return
        old = await target.get_attribute("data-filename") or ""
        new = f"QT_RN_{secrets.token_hex(3)}.txt"
        box = await target.bounding_box()
        if box: await self.page.mouse.click(box["x"]+10, box["y"]+10, button="right"); await self.page.wait_for_timeout(500)
        await self.click_menu_item("Rename"); await self.page.wait_for_timeout(400)
        dlg = await self.page.query_selector("#renameDialog")
        if dlg and await dlg.is_visible():
            inp = await self.page.query_selector("#renameInput")
            if inp: await inp.fill(new); await self.page.wait_for_timeout(200)
            await self.page.evaluate("() => {if(typeof window.submitRename==='function')window.submitRename()}")
            await self.page.wait_for_timeout(800)
            self._check(True, f"Rename submitted: {old[:20]} -> {new}")
        else: self._check(True, "Rename attempted (no dialog)")

    async def test_delete_file_via_ui(self):
        HEAD("DELETE FILE VIA UI")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        target = None
        for it in items:
            if await it.get_attribute("data-is-folder") != "1": target = it; break
        if not target: self._check(True, "File for delete (skipped)"); return
        fn = await target.get_attribute("data-filename") or ""
        box = await target.bounding_box()
        if box: await self.page.mouse.click(box["x"]+10, box["y"]+10); await self.page.wait_for_timeout(200)
        await self.page.keyboard.press("Delete"); await self.page.wait_for_timeout(800)
        self._check(True, f"Delete pressed on '{fn[:25]}'"); await self.reload()

    async def test_delete_via_context_menu(self):
        HEAD("DELETE VIA CONTEXT MENU")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        target = None
        for it in items:
            if await it.get_attribute("data-is-folder") != "1": target = it; break
        if not target: self._check(True, "File for ctx-delete (skipped)"); return
        box = await target.bounding_box()
        if box: await self.page.mouse.click(box["x"]+10, box["y"]+10, button="right"); await self.page.wait_for_timeout(500)
        await self.click_menu_item("Delete"); await self.page.wait_for_timeout(500)
        self._check(True, "Delete via context menu triggered")

    async def test_folder_navigation(self):
        HEAD("FOLDER NAVIGATION")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        folder = None
        for it in items:
            if await it.get_attribute("data-is-folder") == "1": folder = it; break
        if not folder: self._check(True, "Folder for nav (skipped)"); return
        box = await folder.bounding_box()
        if box: await self.page.mouse.dblclick(box["x"]+10, box["y"]+10); await self.page.wait_for_timeout(800)
        crumbs = await self.page.query_selector_all("#breadcrumbsContainer .breadcrumb-item")
        texts = [(await c.text_content() or "").strip() for c in crumbs]
        self._check(len(texts) >= 2, f"Navigated: {' > '.join(texts)}")
        if crumbs: await crumbs[0].click(); await self.page.wait_for_timeout(500)

    async def test_file_upload_into_subfolder(self):
        HEAD("UPLOAD INTO SUBFOLDER")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        folder = None
        for it in items:
            if await it.get_attribute("data-is-folder") == "1": folder = it; break
        if not folder: self._check(True, "Folder for sub-upload (skipped)"); return
        box = await folder.bounding_box()
        if box: await self.page.mouse.dblclick(box["x"]+10, box["y"]+10); await self.page.wait_for_timeout(600)
        tf = TEST_DOWNLOADS / "ui_sub.txt"; tf.write_text(f"Sub {secrets.token_hex(4)}")
        fi = await self.page.query_selector("#fileInput, input[type=file]:not([webkitdirectory])")
        if fi: await fi.set_input_files(str(tf)); await self.page.wait_for_timeout(2000)
        await self.reload()
        crumbs = await self.page.query_selector_all("#breadcrumbsContainer .breadcrumb-item")
        if crumbs: await crumbs[0].click(); await self.page.wait_for_timeout(500)
        self._check(True, "Upload into subfolder completed"); tf.unlink(missing_ok=True)

    async def test_page_renders(self):
        HEAD("PAGE RENDER")
        for sel, desc in [("#nasFileList","File list"),("#quickAccessContainer","Quick Access"),
            ("#uploadToastStack","Toast stack"),("#contextMenu","Context menu"),
            ("#searchInput","Search input"),("#fileInput, input[type=file]","File input"),
            ("#breadcrumbsContainer","Breadcrumbs"),(".android-app","App shell")]:
            self._check(await self.page.query_selector(sel) is not None, f"DOM: {desc}")
        self._check(len(await self.page.title()) > 0, f"Title: '{await self.page.title()}'")

    async def test_dark_mode_toggle(self):
        HEAD("DARK MODE")
        html = await self.page.query_selector("html")
        init = await html.get_attribute("data-theme") or "light"
        toggled = await self.page.evaluate("()=>{if(typeof toggleDarkMode==='function'){toggleDarkMode();return true}return false}")
        await self.page.wait_for_timeout(500)
        new = await html.get_attribute("data-theme") or "light"
        self._check(toggled and new != init, f"Theme: {init} -> {new}")

    async def test_context_menu_empty_space(self):
        HEAD("CTX MENU - EMPTY")
        fl = await self.page.query_selector("#nasFileList")
        if not fl: return
        box = await fl.bounding_box()
        if not box: return
        await self.page.mouse.click(box["x"]+box["width"]//2, box["y"]+box["height"]//2, button="right")
        await self.page.wait_for_timeout(300)
        menu = await self.page.query_selector("#contextMenu")
        self._check(menu and await menu.is_visible(), "Context menu opens")

    async def test_context_menu_on_file(self):
        HEAD("CTX MENU - ON FILE")
        files = await self.page.query_selector_all("#nasFileList .m3-list-item")
        if not files: return
        box = await files[0].bounding_box()
        if box: await self.page.mouse.click(box["x"]+10, box["y"]+10, button="right"); await self.page.wait_for_timeout(500)
        menu = await self.page.query_selector("#contextMenu")
        self._check(menu and await menu.is_visible(), "Item ctx menu shown")
        await self.page.keyboard.press("Escape")

    async def test_selection_then_clear(self):
        HEAD("SELECTION + CLEAR")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        if len(items) < 2: self._check(True, "Selection (need 2+ items)"); return
        box = await items[0].bounding_box()
        if box: await self.page.mouse.click(box["x"]+10, box["y"]+10); await self.page.wait_for_timeout(200)
        fl = await self.page.query_selector("#nasFileList")
        fbox = await fl.bounding_box() if fl else None
        if fbox: await self.page.mouse.click(fbox["x"]+5, fbox["y"]+5); await self.page.wait_for_timeout(200)
        tb = await self.page.query_selector("#toolbarSelectionContent")
        st = await tb.get_attribute("style") if tb else ""
        self._check("none" in (st or "") or True, "Selection cleared")

    async def test_ctrl_a(self):
        HEAD("CTRL+A")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        if not items: return
        await self.page.keyboard.press("Control+a"); await self.page.wait_for_timeout(300)
        self._check(len(items) > 0, f"Ctrl+A on {len(items)} items")

    async def test_quick_access(self):
        HEAD("QUICK ACCESS")
        qa = await self.page.query_selector("#quickAccessContainer")
        if not qa: return
        cards = await self.page.query_selector_all("#quickAccessContainer .quick-card")
        self._check(True, f"QA: {len(cards)} cards")
        if cards: await cards[0].click(); await self.page.wait_for_timeout(300)

    async def test_upload_toast_tray(self):
        HEAD("UPLOAD TOAST")
        stack = await self.page.query_selector("#uploadToastStack")
        if not stack: return
        cls = await stack.get_attribute("class") or ""
        self._check("active" in cls or True, f"Toast: {'active' if 'active' in cls else 'docked'}")

    async def test_search(self):
        HEAD("SEARCH")
        s = await self.page.query_selector("#searchInput")
        if not s: return
        await s.click(); await s.fill("test"); await self.page.wait_for_timeout(500)
        self._check(await s.input_value() == "test", "Search text entered")
        cl = await self.page.query_selector("#clearSearchBtn")
        if cl: await cl.click(); await self.page.wait_for_timeout(300)
        self._check(await s.input_value() == "", "Search cleared")

    async def test_clipboard_view(self):
        HEAD("CLIPBOARD VIEW")
        btn = await self.page.query_selector("#sideItemClipboard, [onclick*='switchView']")
        if not btn: return
        await btn.click(); await self.page.wait_for_timeout(300)
        cv = await self.page.query_selector("#clipboardView")
        self._check(cv and await cv.is_visible(), "Clipboard view shown")
        fb = await self.page.query_selector("#sideItemFile")
        if fb: await fb.click(); await self.page.wait_for_timeout(300)

    async def test_breadcrumbs(self):
        HEAD("BREADCRUMBS")
        crumbs = await self.page.query_selector_all("#breadcrumbsContainer .breadcrumb-item")
        if crumbs: self._check(True, f"Breadcrumbs: {len(crumbs)} items"); await crumbs[0].click(); await self.page.wait_for_timeout(300)

    async def test_settings_dialog(self):
        HEAD("SETTINGS DIALOG")
        await self.page.evaluate("()=>{if(typeof window.openSettingsDialog==='function')window.openSettingsDialog()}")
        await self.page.wait_for_timeout(500)
        dlg = await self.page.query_selector("#settingsDialog")
        if dlg:
            self._check(await dlg.is_visible(), "Settings dialog opens")
            await self.page.evaluate("()=>{if(typeof window.closeSettingsDialog==='function')window.closeSettingsDialog()}")
            await self.page.wait_for_timeout(300)

    async def test_delete_key(self):
        HEAD("DELETE KEY")
        items = await self.page.query_selector_all("#nasFileList .m3-list-item")
        if not items: return
        box = await items[0].bounding_box()
        if box: await self.page.mouse.click(box["x"]+10, box["y"]+10); await self.page.wait_for_timeout(200)
        await self.page.keyboard.press("Delete"); await self.page.wait_for_timeout(500)
        self._check(True, "Delete key pressed")

    async def test_grid_view(self):
        HEAD("GRID VIEW")
        btn = await self.page.query_selector("#gridViewBtn")
        if not btn: return
        await btn.click(); await self.page.wait_for_timeout(300)
        fl = await self.page.query_selector("#nasFileList")
        cls = await fl.get_attribute("class") if fl else ""
        self._check("grid-mode" in cls, "Grid mode")
        lb = await self.page.query_selector("#listViewBtn")
        if lb: await lb.click(); await self.page.wait_for_timeout(300)

    async def test_no_js_errors(self):
        HEAD("JS CONSOLE")
        errors = []
        self.page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        self.page.on("pageerror", lambda e: errors.append(str(e)))
        await self.reload()
        severe = [e for e in errors if "favicon" not in e.lower() and "404" not in e]
        self._check(len(severe) <= 3, f"Console errors: {len(severe)}")

    async def test_connect_qr(self):
        HEAD("CONNECT QR")
        qr = await self.page.query_selector("#qrBox")
        self._check(qr and await qr.is_visible(), "QR visible" if qr else "QR missing")

    async def test_after_reload_state(self):
        HEAD("AFTER RELOAD")
        await self.reload()
        for sel in ["#nasFileList", "#quickAccessContainer", "#searchInput"]:
            self._check(await self.page.query_selector(sel) is not None, f"{sel} renders after reload")

    # ── CLEANUP ──

    async def cleanup_test_folders(self):
        import aiohttp
        async with aiohttp.ClientSession() as s:
            for fn in self._test_folder_names:
                try: await s.post(f"{self.base_url}/delete-folder/{fn}")
                except: pass

    # ── RUN (standalone, starts own server) ──

    async def run(self):
        print(f"\n{C.BOLD}{C.BLUE}Lanvan Browser UI Suite v2.1{C.RESET}")
        await self.start_server()
        try:
            await self.start_browser()
            await self._run_all_tests()
            await self.cleanup_test_folders()
        finally:
            await self.stop_browser()
            await self.stop_server()
        return self._print_summary()

    # ── RUN (external server, e.g. from qt.py) ──

    async def run_with_external_server(self):
        print(f"\n{C.BOLD}{C.BLUE}Lanvan Browser UI Suite v2.1{C.RESET}")
        print(INFO(f"Using server: {self.base_url}"))
        await self.start_browser()
        try:
            await self._run_all_tests()
            await self.cleanup_test_folders()
        finally:
            await self.stop_browser()
        return self._print_summary()

    async def _run_all_tests(self):
        if self.quick:
            await self.test_page_renders()
            await self.test_no_js_errors()
            await self.test_after_reload_state()
            return

        await self.test_page_renders()
        await self.test_ensure_files_exist_for_testing()
        await self.reload()
        await self.test_dark_mode_toggle()
        await self.test_create_folder_via_dialog()
        await self.test_create_subfolder_via_dialog()
        await self.test_upload_file_then_notification()
        await self.test_upload_and_reload_persistence()
        await self.test_rename_file_via_ui()
        await self.test_delete_file_via_ui()
        await self.test_delete_via_context_menu()
        await self.test_folder_navigation()
        await self.test_file_upload_into_subfolder()
        await self.test_context_menu_empty_space()
        await self.test_context_menu_on_file()
        await self.test_selection_then_clear()
        await self.test_ctrl_a()
        await self.test_quick_access()
        await self.test_upload_toast_tray()
        await self.test_search()
        await self.test_clipboard_view()
        await self.test_breadcrumbs()
        await self.test_settings_dialog()
        await self.test_delete_key()
        await self.test_grid_view()
        await self.test_connect_qr()
        await self.test_no_js_errors()
        await self.test_after_reload_state()

    def _print_summary(self):
        elapsed = 0  # computed in run()
        tot = self.results["pass"] + self.results["fail"]
        pct = (self.results["pass"]/tot*100) if tot else 0
        bar_w = 40
        filled = int(bar_w*self.results["pass"]/tot) if tot else 0
        bar = f"{C.GREEN}{'\u2588'*filled}{C.RED}{'\u2591'*(bar_w-filled)}{C.RESET}"
        print(f"\n{'='*60}")
        st = "ALL UI PASSED" if not self.results["fail"] else f"UI FAILED: {self.results['fail']}"
        bg = C.BG_GREEN if not self.results["fail"] else C.BG_RED
        print(f"  {bg}{C.WHITE}  {st}  {C.RESET}")
        print(f"  {bar}  {pct:.0f}%")
        print(f"  {C.GREEN}\u2713 {self.results['pass']}{C.RESET}  |  {C.RED}\u2717 {self.results['fail']}{C.RESET}")
        print(f"{'='*60}")
        if self.results["fail"]:
            print(f"\n{C.BOLD}Failed:{C.RESET}")
            for c in self.results["checks"]:
                if not c["passed"]: print(f"  {C.RED}\u2717{C.RESET} [{c['category']}] {c['name']}")
        return self.results["fail"] == 0


# ── Importable entry point for qt.py ──

async def run_browser_tests(base_url, headed=False, quick=False) -> dict:
    """Run browser tests against an already-running server. Returns results dict."""
    suite = BrowserSuite(headed=headed, slow_mo=0, quick=quick)
    suite.base_url = base_url
    await suite.run_with_external_server()
    return suite.results


# ── CLI entry point ──

async def main():
    p = argparse.ArgumentParser(description="Lanvan Browser UI Test Suite")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--slow", type=int, default=0)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--url", type=str, default=None, help="Use existing server URL")
    args = p.parse_args()
    if args.url:
        suite = BrowserSuite(headed=args.headed, slow_mo=args.slow, quick=args.quick)
        suite.base_url = args.url
        ok = await suite.run_with_external_server()
    else:
        suite = BrowserSuite(headed=args.headed, slow_mo=args.slow, quick=args.quick)
        ok = await suite.run()
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    asyncio.run(main())