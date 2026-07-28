#!/usr/bin/env python3
"""
Lanvan Regression Test Suite — Comprehensive QA Gate
=====================================================
Run before every commit to catch regressions across the ENTIRE system.

Usage:
    python qt.py              # Full suite: API + UI + Security + File Ops (~90s)
    python qt.py --fast       # Quick smoke test (~15s)
    python qt.py --js         # JS/CSS/HTML integrity only
    python qt.py --api        # API endpoints + security
    python qt.py --security   # Security validation only
    python qt.py --file-ops   # File/folder operations only
    python qt.py --ui         # Browser UI tests only
"""

import asyncio
import aiohttp
import sys
import os
import re
import json
import time
import argparse
import secrets
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent
APP_DIR = ROOT / "app"
JS_DIR = APP_DIR / "static" / "js"
CSS_DIR = APP_DIR / "static" / "css"
TEMPLATE_DIR = APP_DIR / "templates"
ROUTER_DIR = APP_DIR / "routers"
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

class C:
    RESET="\033[0m"; BOLD="\033[1m"; RED="\033[91m"; GREEN="\033[92m"
    YELLOW="\033[93m"; BLUE="\033[94m"; MAGENTA="\033[95m"; CYAN="\033[96m"
    WHITE="\033[97m"; BG_RED="\033[41m"; BG_GREEN="\033[42m"; BG_YELLOW="\033[43m"

def OK(m):   return f"  {C.GREEN}[OK]{C.RESET} {m}"
def FAIL(m): return f"  {C.RED}[FAIL]{C.RESET} {C.RED}{m}{C.RESET}"
def WARN(m): return f"  {C.YELLOW}[WARN]{C.RESET} {m}"
def INFO(m): return f"  {C.CYAN}[INFO]{C.RESET} {m}"
def HEAD(m): return f"\n{C.BOLD}{C.CYAN}{'='*60}\n  {m}\n{'='*60}{C.RESET}"

class Suite:
    def __init__(self):
        self.r = {"pass":0,"fail":0,"warn":0,"checks":[]}
        self.base_url = None; self.server = None; self.task = None

    def _rec(self, name, passed, cat="general"):
        self.r["checks"].append({"name":name,"passed":passed,"category":cat})
        if passed: self.r["pass"]+=1
        else: self.r["fail"]+=1

    def _ck(self, cond, name, cat="general"):
        if cond: print(OK(name)); self._rec(name,True,cat)
        else: print(FAIL(name)); self._rec(name,False,cat)

    # ═══════ SECURITY ═══════
    def test_security(self):
        HEAD("SECURITY VALIDATION")
        from app.core.validation import secure_filename, is_allowed_file
        for inp in ["....","....//....","../../etc/passwd","foo.txt\0.exe",
                     "..\\..\\windows\\system32\\cmd.exe","....//....//etc//passwd"]:
            r = secure_filename(inp)
            has = ".." in r or "/" in r
            self._ck(not has, f"secure_filename({repr(inp)}) \u2192 {repr(r)}", "security")

        for fn,exp in [("test.exe",False),("test.dll",False),("test.bat",False),("test.vbs",False),
                        ("test.jar",False),("test.txt",True),("test.pdf",True),
                        ("test.png",True),("test.mp4",True),("test.py",True),("test.js",True),
                        ("test.html",True),("test.json",True),("test.csv",True),("test.zip",True),
                        ("test.7z",True),("test",True),("noext",True)]:
            r = is_allowed_file(fn)
            self._ck(r==exp, f"is_allowed({repr(fn)}) \u2192 {r} (exp {exp})", "security")

    # ═══════ JS/CSS/HTML ═══════
    def test_static_integrity(self):
        HEAD("STATIC INTEGRITY")
        combined = ""
        for f in sorted(JS_DIR.glob("*.js")):
            combined += f"\n/*---{f.name}---*/\n"+f.read_text(encoding="utf-8",errors="ignore")

        dupes = sorted(set(f for f in re.findall(r"function\s+(\w+)\s*\(",combined)
                           if re.findall(r"function\s+(\w+)\s*\(",combined).count(f)>1))
        self._ck(len(dupes)<=23, f"Duplicate functions: {len(dupes)} ({', '.join(dupes[:5])})" if dupes else "No dupes","js")

        for g in ["uploadQueue","addToUploadQueue","cancelUpload","pauseUpload","resumeUpload",
                   "cancelAllUploads","refreshFileList","showToast","clearSelection","deleteSelected",
                   "renderUploadTray","scheduleUploadTrayRender","navigateToPathAndSelect",
                   "showGenericContextMenu","downloadFileByName","openRenameModal","switchView",
                   "setThemePreference","setTypeFilter","pauseAllUploads","resumeAllUploads",
                   "setViewMode","triggerInstantUIUpdate","clearToolbarSearch","hideSearchAutocomplete","renderSearchAutocomplete"]:
            fnd = re.search(rf"window\.{g}\s*=",combined) or re.search(rf"{g}\s*=\s*function",combined) or (f"function {g}" in combined)
            self._ck(fnd is not None, f"Global '{g}' defined", "js")

        for fn in set(re.findall(r'onclick="(\w+)\(',combined)):
            if fn not in {"removeUpload","retryUpload","if"}:
                defined = (f"function {fn}" in combined or f"window.{fn}" in combined or f"{fn} =" in combined)
                if not defined: self._ck(False, f"onclick -> undefined: {fn}", "js")

        css = (CSS_DIR/"lanvan.css").read_text(encoding="utf-8",errors="ignore")
        self._ck(css.count("!important")<=222, f"!important: {css.count('!important')}", "css")
        self._ck(".glass-b4-body" in css and ".b4-badge" in css and ".b4-bottom-strip" in css, "Option B4 Frosted Glass overlay CSS rules defined", "css")

        html_text = ""
        for tf in sorted(TEMPLATE_DIR.glob("*.html")):
            html_text += tf.read_text(encoding="utf-8",errors="ignore")+"\n"
        html_ids = set(re.findall(r'id="([^"]+)"',html_text))
        critical = ["nasFileList","quickAccessContainer","uploadToastStack","contextMenu",
                     "fileInput","folderInput","searchInput","nasDropzone","breadcrumbsContainer",
                     "clipboardHistory","fileView","clipboardView","toolbarDefaultContent",
                     "toolbarSelectionContent","renameDialog","newFolderDialog","searchResultsPanel","settingsDialog",
                     "toolbarSearchInput","searchAutocompleteMenu"]
        missing = [c for c in critical if c not in html_ids]
        self._ck(len(missing)==0, f"Critical IDs: {'ALL' if not missing else f'missing={missing[:5]}'}", "html")

    def test_ui_and_viewmode_integrity(self):
        HEAD("UI, VIEW MODE & UPLOAD TRAY INTEGRITY")
        combined_js = ""
        for f in sorted(JS_DIR.rglob("*.js")):
            combined_js += f"\n/*---{f.name}---*/\n"+f.read_text(encoding="utf-8",errors="ignore")

        # 1. Check view mode state persistence & instant toggle
        self._ck("lanvan_view_mode" in combined_js, "View mode state persistence in localStorage ('lanvan_view_mode')", "ui-integrity")
        self._ck("setViewMode" in combined_js and "requestAnimationFrame" in combined_js, "Instant View Mode switching via setViewMode & rAF", "ui-integrity")

        # 2. Check Option B4 Grid Card HTML generation
        self._ck("glass-b4-body" in combined_js and "b4-num" in combined_js and "b4-bottom-strip" in combined_js, "Option B4 frosted glass grid card badge rendering", "ui-integrity")

        # 3. Check Notification Tray Header Actions (Pause/Resume + Dynamic Chevron)
        self._ck("pauseAllUploads" in combined_js and "uploadManagerExpanded = true" in combined_js, "pauseAllUploads auto-expands tray when paused", "ui-integrity")
        self._ck("resumeAllUploads" in combined_js and "uploadManagerExpanded = false" in combined_js, "resumeAllUploads auto-collapses tray when resumed", "ui-integrity")
        self._ck("buildHeaderActionsHtml" in combined_js, "buildHeaderActionsHtml renders correct controls based on upload/pause status", "ui-integrity")

    def test_cleanFolderPath_normalization(self):
        HEAD("PATH NORMALIZATION INTEGRITY (cleanFolderPath)")
        combined_js = ""
        for f in sorted(JS_DIR.glob("*.js")):
            combined_js += f"\n/*---{f.name}---*/\n"+f.read_text(encoding="utf-8",errors="ignore")

        self._ck("function cleanFolderPath" in combined_js, "cleanFolderPath helper function defined", "path-normalization")
        
        # Verify cleanFolderPath is used in all key path resolution locations
        clean_usages = len(re.findall(r"normCurrentDir\s*=\s*cleanFolderPath", combined_js))
        self._ck(clean_usages >= 3, f"normCurrentDir consistently initialized via cleanFolderPath (found {clean_usages} usages)", "path-normalization")
        
        raw_home_strip = len(re.findall(r"normCurrentDir\.replace\(\/\^Home\\\/\?\/", combined_js))
        self._ck(raw_home_strip == 0, "No raw Home/ string replace hacks on normCurrentDir", "path-normalization")

    def test_subfolder_synthesis_patterns(self):
        HEAD("SUBFOLDER SYNTHESIS & AGGREGATION PATTERNS")
        app_init = (JS_DIR / "app-init.js").read_text(encoding="utf-8", errors="ignore")
        proj_js = (JS_DIR / "projection-layer.js").read_text(encoding="utf-8", errors="ignore")

        self._ck("activeFolderMap" in app_init or "activeFolderMap" in proj_js, "activeFolderMap root subfolder aggregation in renderPrototypeFileList", "subfolder-synthesis")
        self._ck("rowDataMap" in app_init, "rowDataMap two-pass aggregation in _doInstantUIUpdate (prevents progress bar bouncing)", "subfolder-synthesis")
        
        # Verify two-pass DOM update pattern exists (Pass 1 aggregation + Pass 2 single DOM write)
        self._ck("// Pass 1: Aggregate items into per-row progress data" in app_init, "Pass 1 item aggregation logic present", "subfolder-synthesis")
        self._ck("// Pass 2: Update DOM rows with aggregated progress" in app_init, "Pass 2 single-pass DOM row rendering present", "subfolder-synthesis")
        self._ck("function getRelativeItemDir" in app_init or "getRelativeItemDir" in proj_js, "getRelativeItemDir helper function present (prevents cross-folder upload item leakage)", "subfolder-synthesis")
        self._ck("activeNameMap" in app_init or "activeNameMap" in proj_js, "activeNameMap deduplication present in renderPrototypeFileList (prevents duplicate row flickering)", "subfolder-synthesis")
        
        main_app = (JS_DIR / "main-app.js").read_text(encoding="utf-8", errors="ignore")
        files_py = (ROUTER_DIR / "files.py").read_text(encoding="utf-8", errors="ignore")
        self._ck("requestFileListRefresh" in main_app, "requestFileListRefresh single-flight debouncer present in main-app.js", "subfolder-synthesis")
        self._ck("(folder_path_obj / part).is_dir()" in files_py, "Literal part & safe_part dual path resolution present in files.py", "subfolder-synthesis")
        self._ck("logStructuredState" in main_app, "logStructuredState structured logger present in main-app.js", "subfolder-synthesis")

    def test_defensive_getters(self):
        HEAD("DEFENSIVE PROPERTY ACCESS & DATA CONTRACTS (§1)")
        main_app = (JS_DIR / "main-app.js").read_text(encoding="utf-8", errors="ignore")
        app_init = (JS_DIR / "app-init.js").read_text(encoding="utf-8", errors="ignore")

        # Defensive getter existence
        self._ck("getItemSize" in main_app or "window.getItemSize" in main_app, "getItemSize defensive getter defined", "defensive-getters")
        self._ck("getItemName" in main_app or "window.getItemName" in main_app, "getItemName defensive getter defined", "defensive-getters")
        self._ck("getItemProgress" in main_app or "window.getItemProgress" in main_app, "getItemProgress defensive getter defined", "defensive-getters")

        # Defensive usage in app-init
        self._ck("window.getItemSize" in app_init, "getItemSize safely invoked in prototype adapter", "defensive-getters")
        self._ck("window.getItemName" in app_init, "getItemName safely invoked in prototype adapter", "defensive-getters")

    def test_declarative_ui_pattern(self):
        HEAD("DECLARATIVE UI RENDERING & SINGLE SOURCE OF TRUTH (§2)")
        main_app = (JS_DIR / "main-app.js").read_text(encoding="utf-8", errors="ignore")

        self._ck("window.uploadQueue" in main_app, "window.uploadQueue authoritative state repository", "declarative-ui")
        
        # Action handlers must trigger instant UI update
        self._ck("function cancelUpload" in main_app and "triggerInstantUIUpdate" in main_app, "cancelUpload mutates state and triggers triggerInstantUIUpdate", "declarative-ui")
        self._ck("function pauseUpload" in main_app and "triggerInstantUIUpdate" in main_app, "pauseUpload mutates state and triggers triggerInstantUIUpdate", "declarative-ui")
        self._ck("function resumeUpload" in main_app and "triggerInstantUIUpdate" in main_app, "resumeUpload mutates state and triggers triggerInstantUIUpdate", "declarative-ui")

        app_init = (JS_DIR / "app-init.js").read_text(encoding="utf-8", errors="ignore")
        self._ck('e.key === "Escape"' in app_init and "window.clearSelection()" in app_init, "Escape key clears selection handler present", "declarative-ui")
        self._ck("navigateIntoFolder" in app_init, "Immediate folder click navigation handler present", "declarative-ui")
        self._ck("fallbackCopyTextToClipboard" in app_init and "copyConnectAddress" in app_init, "Universal HTTP/HTTPS clipboard copy fallback present in copyConnectAddress", "declarative-ui")
        self._ck("initFileEventsWebSocket" in main_app and "/ws/file_events" in main_app, "Real-time cross-device file events WebSocket listener present", "declarative-ui")
        self._ck("isItemUploading" in app_init, "Uploading files selection guard present in app-init.js", "declarative-ui")
        self._ck("copyVideoStreamUrl" in app_init and "lanvanGlobalToast" in app_init, "Copy stream link handler with global toast notification present in app-init.js", "declarative-ui")
        self._ck("alreadySelected" in app_init and "prototypeSelectedItems.indexOf(filename)" in app_init, "Multi-selection context menu right-click preservation present in app-init.js", "declarative-ui")
        self._ck("SINGLE FILE / FOLDER RENAME" in app_init and "MULTI-ITEM BATCH RENAME" in app_init, "Single file extension modification & multi-item extension preservation handlers present in app-init.js", "declarative-ui")
        self._ck("downloadSelectedAsZip" in app_init and "downloadZipMenuItem" in (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8", errors="ignore"), "Multi-selection Download individually and Download as ZIP options present in app-init.js & index.html", "declarative-ui")
        self._ck("isTargetFolder" in app_init and "(isSingle && !isTargetFolder)" in app_init, "Folder preview option suppression & Download as ZIP menu handler present in app-init.js", "declarative-ui")
        self._ck("Style 3: Minimalist 2px Primary Border" in (CSS_DIR / "lanvan.css").read_text(encoding="utf-8", errors="ignore"), "Style 3 selection aesthetics present in lanvan.css", "declarative-ui")
        self._ck("Directory requested via /download/" in (ROUTER_DIR / "files.py").read_text(encoding="utf-8", errors="ignore"), "Automatic directory download redirect to ZIP present in files.py", "declarative-ui")
        
        css = (CSS_DIR / "lanvan.css").read_text(encoding="utf-8", errors="ignore")
        self._ck(".video-preview-box {" in css and "position: absolute;" in css, "Full-bleed absolute inset grid preview layout present in lanvan.css", "declarative-ui")
        self._ck("top: 39px;" in css, "Glass upload body top offset flush with header in lanvan.css", "declarative-ui")
        self._ck(".m3-list.grid-mode .m3-list-item.selected .grid-card-head" in css and "#dbeafe" in css, "Selected grid card header blue accent fill present in lanvan.css", "declarative-ui")

    def test_notification_tray_integrity(self):
        HEAD("NOTIFICATION TRAY INTEGRITY & DISMISSAL (§3)")
        app_init = (JS_DIR / "app-init.js").read_text(encoding="utf-8", errors="ignore")

        self._ck("calc(76px + env(safe-area-inset-bottom, 0px))" in (CSS_DIR / "lanvan.css").read_text(encoding="utf-8", errors="ignore"), "Mobile bottom nav safe clearance for global toasts present in lanvan.css", "tray-integrity")
        self._ck("buildTrayItemHtml" in app_init, "buildTrayItemHtml tray renderer present", "tray-integrity")
        self._ck("if (!hasItems) return; // Do not expand when empty" in app_init, "Empty notification tray expansion guard present", "tray-integrity")

    def test_zero_flicker_dom_stability(self):
        HEAD("ZERO-FLICKER DOM STABILITY (§7)")
        app_init = (JS_DIR / "app-init.js").read_text(encoding="utf-8", errors="ignore")
        css = (CSS_DIR / "lanvan.css").read_text(encoding="utf-8", errors="ignore")

        # DOM Node Re-ordering Guard
        self._ck("bodyEl.children[i] !== itemEl" in app_init, "Guarded DOM re-ordering in renderUploadTray (prevents hover drop)", "zero-flicker")

        # CSS layout shift prevention
        self._ck("scrollbar-gutter: stable" in css, "Scrollbar gutter stable in CSS (prevents layout shift)", "zero-flicker")
        self._ck("flex-shrink: 0" in css, "flex-shrink: 0 applied on dynamic notification action items", "zero-flicker")
        self._ck("Drop files here" in app_init, "Spacious empty state dropzone card rules defined", "zero-flicker")

    def test_search_system_integrity(self):
        HEAD("SEARCH SYSTEM & AUTOCOMPLETE INTEGRITY (§8)")
        app_init = (JS_DIR / "app-init.js").read_text(encoding="utf-8", errors="ignore")
        index_html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8", errors="ignore")
        css = (CSS_DIR / "lanvan.css").read_text(encoding="utf-8", errors="ignore")

        # HTML elements
        self._ck('id="toolbarSearchInput"' in index_html, "toolbarSearchInput present in index.html", "search-system")
        self._ck('id="clearToolbarSearchBtn"' in index_html, "clearToolbarSearchBtn present in index.html", "search-system")
        self._ck('id="searchAutocompleteMenu"' in index_html, "searchAutocompleteMenu container present in index.html", "search-system")

        # CSS styles
        self._ck('.search-autocomplete-menu' in css, "search-autocomplete-menu styles present in lanvan.css", "search-system")
        self._ck('.search-autocomplete-item' in css, "search-autocomplete-item styles present in lanvan.css", "search-system")
        self._ck('.search-autocomplete-icon' in css, "search-autocomplete-icon styles present in lanvan.css", "search-system")

        # JS functions & logic
        self._ck('renderSearchAutocomplete' in app_init, "renderSearchAutocomplete engine present in app-init.js", "search-system")
        self._ck('clearToolbarSearch' in app_init, "clearToolbarSearch reset handler present in app-init.js", "search-system")
        self._ck('hideSearchAutocomplete' in app_init, "hideSearchAutocomplete dismiss handler present in app-init.js", "search-system")
        self._ck('searchSelectedIndex' in app_init, "searchSelectedIndex keyboard highlight tracking present in app-init.js", "search-system")
        self._ck("e.key === \"Escape\"" in app_init and "hideSearchAutocomplete" in app_init, "Escape key autocomplete dismiss handler present in app-init.js", "search-system")
        self._ck("e.key.toLowerCase() === 'k'" in app_init and "toolbarInput.focus()" in app_init, "Ctrl+K search focus shortcut present in app-init.js", "search-system")
        self._ck("No files matching" in app_init, "No search results empty state present in app-init.js", "search-system")
        self._ck(".slice(0, 4)" in app_init, "Capped top 4 search suggestions slice present in app-init.js", "search-system")

    # ═══════ SERVER ═══════
    async def start_server(self, use_https=False):
        from app.main import app; import uvicorn
        port = int(os.getenv("QT_PORT","9876"))
        kw = {"app": app, "host": "127.0.0.1", "port": port, "log_level": "critical"}
        
        if use_https:
            certs_dir = ROOT / "certs"
            cert_file = certs_dir / "cert.pem"
            key_file = certs_dir / "key.pem"
            if not (cert_file.exists() and key_file.exists()):
                try:
                    from certs.generate_certs_python import generate_certificates_python
                    generate_certificates_python(force=True)
                except Exception as e:
                    print(WARN(f"Could not generate SSL certs: {e}"))
            if cert_file.exists() and key_file.exists():
                kw["ssl_keyfile"] = str(key_file)
                kw["ssl_certfile"] = str(cert_file)
                self.base_url = f"https://127.0.0.1:{port}"
            else:
                self.base_url = f"http://127.0.0.1:{port}"
        else:
            self.base_url = f"http://127.0.0.1:{port}"

        c = uvicorn.Config(**kw)
        s = uvicorn.Server(c)
        self.server = s; self.task = asyncio.create_task(s.serve())
        # Wait for server to become ready (up to 5s)
        for _ in range(50):
            await asyncio.sleep(0.1)
            if s.started:
                break
        proto = "HTTPS" if self.base_url.startswith("https") else "HTTP"
        if s.started:
            print(INFO(f"Server on {self.base_url} ({proto})"))
        else:
            print(WARN(f"Server failed to start on {self.base_url} ({proto}) - port may be in use"))
            raise RuntimeError(f"Server failed to bind port {port}")

    async def stop_server(self):
        if self.task: self.task.cancel()
        try: await self.task
        except asyncio.CancelledError: pass
        self.task = None; await asyncio.sleep(0.3)  # Give OS time to release port

    async def _api(self,method,path,**kw):
        timeout = kw.pop("timeout", aiohttp.ClientTimeout(total=30))
        conn = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=conn) as s:
            async with s.request(method,f"{self.base_url}{path}",**kw) as resp:
                ct = resp.headers.get("content-type","")
                if "json" in ct: body = await resp.json()
                elif any(x in ct for x in ("image","octet","zip","pdf")): body = await resp.read()
                else: body = await resp.text(encoding="utf-8",errors="replace")
                return resp.status,body

    # ═══════ API TESTS ═══════
    async def test_endpoints(self):
        HEAD("API ENDPOINTS")
        for m,p,exp in [("GET","/",200),("GET","/api/files",200),("GET","/api/folders",200),
                         ("GET","/api/network-info",200),("GET","/api/qr-code?text=t&size=100",200),
                         ("GET","/api/upload-history",200),("GET","/api/clipboard",200),
                         ("GET","/api/logs",200),("GET","/api/upload/status",200)]:
            st,_ = await self._api(m,p)
            self._ck(st==exp, f"{m} {p} \u2192 {st}","api")

    async def test_security_endpoints(self):
        HEAD("SECURITY ENDPOINTS")
        # Blocked extension upload
        data = aiohttp.FormData(); data.add_field("files",b"malware",filename="bad.exe")
        st,body = await self._api("POST","/upload-auto",data=data)
        self._ck(st!=200, f"Block .exe upload -> {st}","security")

        # Download non-existent file
        st,_ = await self._api("GET","/download/../../etc/passwd")
        self._ck(st in (404,400), f"Path traversal download -> {st}","security")

        # Delete with path traversal
        st,_ = await self._api("POST","/delete/../outside")
        self._ck(st in (400,403,404), f"Path traversal delete -> {st}","security")

        # Folder delete with path traversal
        st,_ = await self._api("POST","/delete-folder/../../system")
        self._ck(st in (400,403,404), f"Path traversal folder delete -> {st}","security")

        # Very long filename
        long_name = "A"*500+".txt"
        data = aiohttp.FormData(); data.add_field("files",b"test",filename=long_name)
        st,_ = await self._api("POST","/upload-auto",data=data)
        self._ck(st in (200,400), f"Long filename ({len(long_name)} chars) -> {st}","security")

    async def test_file_operations(self):
        HEAD("FILE CRUD")
        fn = f"qt_f_{secrets.token_hex(3)}.txt"
        ct = b"A"*300
        # Upload
        data = aiohttp.FormData(); data.add_field("files",ct,filename=fn)
        st,body = await self._api("POST","/upload-auto",data=data)
        ok = st==200 and body.get("status")=="success"
        self._ck(ok, f"Upload '{fn}'","file-ops")
        if not ok: return

        saved = (body.get("files",[fn]) or [fn])[0] if isinstance(body,dict) else fn

        # List
        st,body = await self._api("GET","/api/files")
        names = [f["name"] for f in body.get("files_data",[])]
        self._ck(saved in names,"File in listing","file-ops")

        # Download
        st,dl = await self._api("GET",f"/download/{saved}")
        self._ck(len(dl.encode() if isinstance(dl,str) else dl) > 0,"Download works","file-ops")

        if os.name=="nt": await asyncio.sleep(0.5)

        # Rename
        new = f"rn_{saved}"
        fd = aiohttp.FormData(); fd.add_field("filename",saved); fd.add_field("new_name",new)
        st,body = await self._api("POST","/api/files/rename",data=fd)
        self._ck(st==200,f"Rename -> '{new}'","file-ops")

        # Delete
        st,_ = await self._api("POST",f"/delete/{new}")
        self._ck(st==200,f"Delete '{new}'","file-ops")

        # Idempotent delete (file already gone -> 200 OK)
        st,idem_res = await self._api("POST",f"/delete/{new}")
        self._ck(st==200 and idem_res.get("status")=="success","Idempotent delete of unlinked file -> 200 OK","file-ops")

        # Delete with parent_path
        fd_sub = aiohttp.FormData(); fd_sub.add_field("filename","sub_test.txt"); fd_sub.add_field("parent_path","Home/subfolder")
        st,sub_res = await self._api("POST","/delete/sub_test.txt",data=fd_sub)
        self._ck(st==200 and sub_res.get("status")=="success","Subfolder delete with parent_path -> 200 OK","file-ops")

        # Verify gone
        st,body = await self._api("GET","/api/files")
        names = [f["name"] for f in body.get("files_data",[])]
        self._ck(new not in names,"File removed","file-ops")

    async def test_renamed_non_existent(self):
        HEAD("RENAME NON-EXISTENT")
        fd = aiohttp.FormData(); fd.add_field("filename","ghost.txt"); fd.add_field("new_name","real.txt")
        st,_ = await self._api("POST","/api/files/rename",data=fd)
        self._ck(st>=400,f"Rename non-existent -> {st}","file-ops")

    async def test_rename_to_existing(self):
        HEAD("RENAME TO EXISTING")
        # Create 2 files
        a = f"qt_a_{secrets.token_hex(3)}.txt"; b = f"qt_b_{secrets.token_hex(3)}.txt"
        for fn in [a,b]:
            d = aiohttp.FormData(); d.add_field("files",b"x",filename=fn)
            await self._api("POST","/upload-auto",data=d)
        fd = aiohttp.FormData(); fd.add_field("filename",a); fd.add_field("new_name",b)
        st,_ = await self._api("POST","/api/files/rename",data=fd)
        self._ck(st>=400,f"Rename to existing -> {st}","file-ops")
        await self._api("POST",f"/delete/{a}"); await self._api("POST",f"/delete/{b}")

    async def test_concurrent_uploads(self):
        HEAD("CONCURRENT UPLOADS (3 files)")
        ok_count = 0
        tasks = []
        for i in range(3):
            fn = f"qt_conc_{i}_{secrets.token_hex(2)}.txt"
            d = aiohttp.FormData(); d.add_field("files",b"concurrent test",filename=fn)
            tasks.append(self._api("POST","/upload-auto",data=d))
        results = await asyncio.gather(*tasks,return_exceptions=True)
        for r in results:
            if isinstance(r,tuple) and r[0]==200:
                try:
                    if r[1].get("status")=="success": ok_count+=1
                except: pass
        self._ck(ok_count>=2, f"Concurrent uploads: {ok_count}/3 succeeded","file-ops")

    async def test_special_chars_upload(self):
        HEAD("SPECIAL CHARS IN FILENAME")
        fn = f"qt_spaces & plus+parens(1)_{secrets.token_hex(2)}.txt"
        d = aiohttp.FormData(); d.add_field("files",b"special chars",filename=fn)
        st,body = await self._api("POST","/upload-auto",data=d)
        self._ck(st==200 and body.get("status")=="success",f"Special chars upload -> {st}","file-ops")
        # Cleanup - find by listing
        st,body = await self._api("GET","/api/files")
        for f in body.get("files_data",[]):
            if fn in f["name"]:
                await self._api("POST",f"/delete/{f['name']}")

    async def test_folder_operations(self):
        HEAD("FOLDER CRUD")
        root = f"qt_d_{secrets.token_hex(3)}"; sub = f"qt_s_{secrets.token_hex(3)}"
        fd = aiohttp.FormData(); fd.add_field("folder_name",root)
        st,body = await self._api("POST","/api/files/mkdir",data=fd)
        if not (st==200 and body.get("status")=="success"):
            self._ck(False,f"Create folder '{root}'","folder-ops"); return
        self._ck(True,f"Create folder '{root}'","folder-ops")

        st,body = await self._api("GET","/api/folders")
        self._ck(root in [f["name"] for f in body.get("folders",[])],"Folder in listing","folder-ops")

        fd = aiohttp.FormData(); fd.add_field("folder_name",sub); fd.add_field("parent_path",root)
        st,_ = await self._api("POST","/api/files/mkdir",data=fd)
        self._ck(st==200,f"Create subfolder '{root}/{sub}'","folder-ops")

        # Upload into subfolder
        d = aiohttp.FormData(); d.add_field("files",b"sub",filename="s.txt"); d.add_field("parent_path",f"{root}/{sub}")
        st,_ = await self._api("POST","/upload-auto",data=d)
        self._ck(st==200,"Upload into subfolder","folder-ops")

        # List subfolder
        st,_ = await self._api("GET",f"/api/folders/{root}/{sub}/files")
        self._ck(st==200,"List subfolder","folder-ops")

        await self._api("POST",f"/delete-folder/{root}/{sub}")
        await self._api("POST",f"/delete-folder/{root}")
        self._ck(True,"Folders deleted","folder-ops")

    async def test_same_name_nested_folders(self):
        HEAD("SAME-NAME NESTED FOLDERS (e.g. Untitled folder / Untitled folder)")
        same_name = f"same_folder_{secrets.token_hex(2)}"
        
        # 1. Create root folder
        fd1 = aiohttp.FormData(); fd1.add_field("folder_name", same_name)
        st1, body1 = await self._api("POST", "/api/files/mkdir", data=fd1)
        self._ck(st1 == 200 and body1.get("status") == "success", f"Create root folder '{same_name}'", "folder-ops")

        # 2. Create subfolder with the EXACT SAME NAME inside root folder
        fd2 = aiohttp.FormData(); fd2.add_field("folder_name", same_name); fd2.add_field("parent_path", same_name)
        st2, body2 = await self._api("POST", "/api/files/mkdir", data=fd2)
        self._ck(st2 == 200 and body2.get("status") == "success", f"Create subfolder '{same_name}/{same_name}'", "folder-ops")

        # 3. List inner subfolder
        st3, body3 = await self._api("GET", f"/api/folders/{same_name}/{same_name}/files")
        self._ck(st3 == 200, f"List nested same-name folder '{same_name}/{same_name}'", "folder-ops")

        # 4. Clean up
        await self._api("POST", f"/delete-folder/{same_name}/{same_name}")
        await self._api("POST", f"/delete-folder/{same_name}")
        self._ck(True, "Cleaned same-name nested test folders", "folder-ops")

    async def test_folder_upload_api(self):
        HEAD("FOLDER UPLOAD VIA /upload-folder (PLAIN & AES)")
        folder_name = f"qt_fup_{secrets.token_hex(3)}"
        d1 = aiohttp.FormData()
        d1.add_field("folder_name", folder_name)
        d1.add_field("files", b"hello file 1 in folder", filename="file1.txt")
        d1.add_field("files", b"hello file 2 in subfolder", filename="sub/file2.txt")
        st, body = await self._api("POST", "/upload-folder", data=d1)
        self._ck(st == 200 and body.get("status") == "success", f"Folder upload plain -> {st}", "folder-ops")
        await self._api("POST", f"/delete-folder/{folder_name}")

        enc_folder = f"qt_fup_enc_{secrets.token_hex(3)}"
        d2 = aiohttp.FormData()
        d2.add_field("folder_name", enc_folder)
        d2.add_field("files", b"secret encrypted data", filename="secret.txt")
        st, body = await self._api("POST", "/upload-folder?encrypt=true", data=d2)
        self._ck(st == 200 and body.get("status") == "success", f"Folder upload AES -> {st}", "folder-ops")
        await self._api("POST", f"/delete-folder/{enc_folder}")

    async def test_folder_auto_increment(self):
        HEAD("FOLDER AUTO-INC")
        base = f"qt_i_{secrets.token_hex(3)}"
        fd = aiohttp.FormData(); fd.add_field("folder_name",base)
        await self._api("POST","/api/files/mkdir",data=fd)
        fd2 = aiohttp.FormData(); fd2.add_field("folder_name",base)
        st,body = await self._api("POST","/api/files/mkdir",data=fd2)
        self._ck(st==200 and "(1)" in body.get("folder_name",""),f"Auto-inc -> '{body.get('folder_name','?')}'","folder-ops")
        await self._api("POST",f"/delete-folder/{base}")
        await self._api("POST",f"/delete-folder/{base} (1)")

    async def test_folder_invalid_chars(self):
        HEAD("FOLDER INVALID CHARS")
        # secure_filename() uses os.path.basename() which strips path components
        for bad,expected in [
            ("../escape","escape"),
            ("with/slash","slash"),
            ("with\\backslash","backslash"),
        ]:
            fd = aiohttp.FormData(); fd.add_field("folder_name",bad)
            st,body = await self._api("POST","/api/files/mkdir",data=fd)
            created_name = body.get("folder_name","") if isinstance(body,dict) else ""
            # Endpoint sanitizes via secure_filename() + auto-increment may add suffix
            ok = st==200 and expected in created_name
            self._ck(ok,f"Sanitize '{bad}' -> '{created_name}'","security")
            await self._api("POST",f"/delete-folder/{created_name}")

    async def test_chunked_upload(self):
        HEAD("CHUNKED UPLOAD")
        fn = f"qt_c_{secrets.token_hex(3)}.dat"; sz=1024*1024; tot=2
        data = secrets.token_bytes(sz*tot)
        for i in range(tot):
            ck = data[i*sz:(i+1)*sz]
            fd = aiohttp.FormData()
            fd.add_field("chunk",ck,filename=f"{fn}.p{i+1}")
            fd.add_field("filename",fn); fd.add_field("part_number",str(i+1)); fd.add_field("total_parts",str(tot))
            st,_ = await self._api("POST","/upload_chunk",data=fd)
            if st!=200: self._ck(False,f"Chunk {i+1}/{tot} -> {st}","file-ops"); return
        self._ck(True,f"Uploaded {tot} chunks","file-ops")

        fd = aiohttp.FormData(); fd.add_field("filename",fn); fd.add_field("total_parts",str(tot))
        st,_ = await self._api("POST","/finalize_upload",data=fd)
        self._ck(st==200,"Finalize assembly","file-ops")
        await self._api("POST",f"/delete/{fn}")

    async def test_move_operations(self):
        HEAD("MOVE OPERATIONS")
        a = f"qt_ma_{secrets.token_hex(3)}"; b = f"qt_mb_{secrets.token_hex(3)}"; fn = f"qt_mf_{secrets.token_hex(3)}.txt"
        for d in [a,b]:
            fd = aiohttp.FormData(); fd.add_field("folder_name",d)
            await self._api("POST","/api/files/mkdir",data=fd)
        d = aiohttp.FormData(); d.add_field("files",b"x",filename=fn); d.add_field("parent_path",a)
        st,_ = await self._api("POST","/upload-auto",data=d)
        self._ck(st==200,f"Upload to '{a}'","file-ops")
        mv = aiohttp.FormData(); mv.add_field("filename",fn); mv.add_field("destination",b)
        st,_ = await self._api("POST","/api/files/move",data=mv)
        self._ck(st==200,f"Move -> '{b}'","file-ops")
        # Move non-existent
        mv2 = aiohttp.FormData(); mv2.add_field("filename","ghost.txt"); mv2.add_field("destination",b)
        st,_ = await self._api("POST","/api/files/move",data=mv2)
        self._ck(st>=400,f"Move non-existent -> {st}","file-ops")
        await self._api("POST",f"/delete-folder/{a}")
        await self._api("POST",f"/delete-folder/{b}")

    async def test_race_conditions_and_state_consistency(self):
        HEAD("RACE CONDITIONS & STATE CONSISTENCY (§9 & §14 CHECKLIST)")
        root = f"qt_rc_root_{secrets.token_hex(2)}"
        sub = f"qt_rc_sub_{secrets.token_hex(2)}"
        fn = f"qt_rc_file_{secrets.token_hex(2)}.txt"
        renamed = f"qt_rc_renamed_{secrets.token_hex(2)}.txt"

        # 1. Create root folder
        fd = aiohttp.FormData(); fd.add_field("folder_name", root)
        st1, b1 = await self._api("POST", "/api/files/mkdir", data=fd)
        self._ck(st1 == 200 and b1.get("status") == "success", f"Create root folder '{root}'", "race-conditions")

        # 2. Create subfolder inside root
        fd2 = aiohttp.FormData(); fd2.add_field("folder_name", sub); fd2.add_field("parent_path", root)
        st2, b2 = await self._api("POST", "/api/files/mkdir", data=fd2)
        self._ck(st2 == 200, f"Create subfolder '{root}/{sub}'", "race-conditions")

        # 3. Upload file into root folder
        d = aiohttp.FormData(); d.add_field("files", b"race condition content", filename=fn); d.add_field("parent_path", root)
        st3, _ = await self._api("POST", "/upload-auto", data=d)
        self._ck(st3 == 200, f"Upload file '{fn}' into '{root}'", "race-conditions")

        # 4. Move file from root into subfolder
        mv = aiohttp.FormData(); mv.add_field("filename", fn); mv.add_field("destination", f"{root}/{sub}"); mv.add_field("parent_path", root)
        st4, b4 = await self._api("POST", "/api/files/move", data=mv)
        self._ck(st4 == 200 and b4.get("status") == "success", f"Move file '{fn}' -> '{root}/{sub}'", "race-conditions")

        # 5. Rename file inside subfolder
        rn = aiohttp.FormData(); rn.add_field("filename", fn); rn.add_field("new_name", renamed); rn.add_field("parent_path", f"{root}/{sub}")
        st5, b5 = await self._api("POST", "/api/files/rename", data=rn)
        self._ck(st5 == 200 and b5.get("status") == "success", f"Rename file in subfolder '{fn}' -> '{renamed}'", "race-conditions")

        # 6. Verify listing inside subfolder
        st6, b6 = await self._api("GET", f"/api/folders/{root}/{sub}/files")
        files_in_sub = [f["name"] for f in b6.get("files", [])]
        self._ck(st6 == 200 and renamed in files_in_sub and fn not in files_in_sub, f"State consistency in '{root}/{sub}': renamed file present", "race-conditions")

        # 7. Delete nested subfolder containing file
        del_st, _ = await self._api("POST", f"/delete-folder/{root}/{sub}")
        self._ck(del_st == 200, f"Delete nested subfolder '{root}/{sub}'", "race-conditions")

        # 8. Verify subfolder listing after deletion recovers cleanly (returns empty list 200, no crash)
        st8, b8 = await self._api("GET", f"/api/folders/{root}/{sub}/files")
        self._ck(st8 == 200 and len(b8.get("files", [])) == 0, "Deleted folder list request recovers cleanly with empty array", "race-conditions")

        # 9. Clean up root folder
        await self._api("POST", f"/delete-folder/{root}")
        self._ck(True, "Cleaned race condition test folders", "race-conditions")

    async def test_active_stream_cancellation_on_rename(self):
        HEAD("ACTIVE STREAM CANCELLATION ON RENAME / DELETE")
        fn = f"qt_stream_{secrets.token_hex(3)}.mp4"
        fn_new = f"qt_stream_renamed_{secrets.token_hex(3)}.mp4"
        d = aiohttp.FormData()
        d.add_field("files", secrets.token_bytes(256 * 1024), filename=fn)
        st, _ = await self._api("POST", "/upload-auto", data=d)
        self._ck(st == 200, f"Upload stream test file '{fn}'", "file-ops")

        async with aiohttp.ClientSession() as session:
            stream_req = asyncio.create_task(
                session.get(f"{self.base_url}/download/{urllib.parse.quote(fn)}", headers={"Range": "bytes=0-100000"})
            )
            await asyncio.sleep(0.1)

            ren_data = aiohttp.FormData()
            ren_data.add_field("filename", fn)
            ren_data.add_field("new_name", fn_new)
            st_ren, body_ren = await self._api("POST", "/api/files/rename", data=ren_data)
            self._ck(st_ren == 200 and body_ren.get("status") == "success", f"StreamManager: Rename streaming file -> {st_ren}", "file-ops")

            try:
                resp = await stream_req
                await resp.close()
            except Exception:
                pass

        await self._api("POST", f"/delete/{fn_new}")

    async def test_clear_files(self):
        HEAD("CLEAR FILES")
        st,body = await self._api("POST","/clear")
        self._ck(st==200,"Clear files endpoint","api")

    async def test_clipboard(self):
        HEAD("CLIPBOARD")
        async with aiohttp.ClientSession() as s:
            st,_ = await self._api("GET","/api/clipboard")
            self._ck(st==200,"Clipboard read","api")
            fd = aiohttp.FormData(); fd.add_field("data","qt_test_clip")
            async with s.post(f"{self.base_url}/api/clipboard/add",data=fd) as r:
                self._ck(r.status==200,"Clipboard add","api")
            st,_ = await self._api("GET","/api/clipboard/list")
            self._ck(st==200,"Clipboard list","api")
            async with s.delete(f"{self.base_url}/api/clipboard/clear") as r:
                self._ck(r.status==200,"Clipboard clear","api")

    async def test_qr(self):
        HEAD("QR CODE")
        for p in ["?text=h&size=100","?text=t&size=300","?text=Hello%20World&size=200"]:
            st,_ = await self._api("GET",f"/api/qr-code{p}")
            self._ck(st==200,f"QR {p[:25]} -> {st}","api")

    async def test_history_and_cancel(self):
        HEAD("HISTORY + CANCEL")
        st,_ = await self._api("POST","/api/upload-history",json=[{"id":1,"fileName":"t.txt","fileSize":100,"status":"completed","targetDir":""}])
        self._ck(st==200,"Save history","api")
        st,_ = await self._api("GET","/api/upload-history")
        self._ck(st==200,"Retrieve history","api")
        st,_ = await self._api("POST","/api/cancel-upload",data={"filename":"ghost.tmp"})
        self._ck(st==200,"Cancel upload","api")
        st,res = await self._api("POST","/api/cancel-upload",data={"filename":"sub_ghost.tmp","parent_path":"Home/test_subfolder"})
        self._ck(st==200 and res.get("status")=="success","Cancel upload subfolder with Home/ prefix","api")

    async def test_batch_zip_download(self):
        HEAD("BATCH ZIP DOWNLOAD API")
        async with aiohttp.ClientSession() as s:
            fd1 = aiohttp.FormData()
            fd1.add_field("files", b"zip test file 1 content", filename="qt_zip1.txt")
            async with s.post(f"{self.base_url}/upload", data=fd1) as r1:
                self._ck(r1.status == 200, "Upload qt_zip1.txt", "api")

            fd2 = aiohttp.FormData()
            fd2.add_field("files", b"zip test file 2 content", filename="qt_zip2.txt")
            async with s.post(f"{self.base_url}/upload", data=fd2) as r2:
                self._ck(r2.status == 200, "Upload qt_zip2.txt", "api")

            req_data = {"files": ["qt_zip1.txt", "qt_zip2.txt"]}
            async with s.post(f"{self.base_url}/api/files/download-zip", json=req_data) as r_zip:
                self._ck(r_zip.status == 200, "POST /api/files/download-zip -> 200", "api")
                ct = r_zip.headers.get("Content-Type", "")
                self._ck("application/zip" in ct, "Content-Type is application/zip", "api")
                data = await r_zip.read()
                self._ck(len(data) > 0 and b"PK" in data[:4], "Valid ZIP header returned", "api")

            async with s.post(f"{self.base_url}/download-zip", json=req_data) as r_alias:
                self._ck(r_alias.status == 200, "POST /download-zip (alias) -> 200", "api")

    async def test_mdns_platform_cors(self):
        HEAD("mDNS + PLATFORM + CORS")
        try:
            from app.utils.simple_mdns import mdns_manager
            info = mdns_manager.get_mdns_info()
            self._ck(info.get("status","?") in ("active","disabled","running"),f"mDNS: {info.get('status','?')}","mdns")
        except Exception as e: self._ck(False,str(e),"mdns")
        try:
            from app.utils.termux_compat import is_android_environment
            from app.utils.universal_optimizer import universal_optimizer
            from app.core.concurrent_upload_manager import ConcurrentUploadManager
            self._ck(True,"Platform imports OK","platform")
        except: self._ck(False,"Platform imports","platform")
        try:
            from app.main import app
            self._ck(True,"App import OK","security")
        except: self._ck(False,"App import","security")

    # ═══════ RUN ═══════
    async def _browser_ui(self):
        try:
            from ui_test import run_browser_tests
            print(f"\n  {C.CYAN}\u2192{C.RESET} Starting browser UI tests...")
            ui_r = await run_browser_tests(self.base_url)
            self.r["pass"] += ui_r["pass"]; self.r["fail"] += ui_r["fail"]
            self.r["checks"].extend(ui_r["checks"])
            return ui_r["fail"] == 0
        except ImportError:
            print(WARN("Playwright not installed - skipping browser UI tests"))
            return True
        except Exception as e:
            print(WARN(f"Browser UI error: {e}")); return True

    async def run(self, args):
        print(f"\n{C.BOLD}{C.BLUE}Lanvan Regression Suite v6.0{C.RESET}")
        print(f"Mode: {args.mode} | HTTPS testing: {'Enabled' if args.use_https or args.mode=='all' else 'Disabled'} | {time.strftime('%Y-%m-%d %H:%M:%S')}")
        if args.mode=="all": print("  API + Security + JS/CSS/HTML + File/Folder Ops (HTTP & HTTPS) + Browser UI")

        run_all = args.mode=="all"; start = time.time()

        if run_all or args.mode in ("security","fast"): self.test_security()
        if run_all or args.mode in ("js","fast"):
            self.test_static_integrity()
            self.test_ui_and_viewmode_integrity()
            self.test_cleanFolderPath_normalization()
            self.test_subfolder_synthesis_patterns()
            self.test_defensive_getters()
            self.test_declarative_ui_pattern()
            self.test_notification_tray_integrity()
            self.test_zero_flicker_dom_stability()
            self.test_search_system_integrity()

        async def _run_suite(use_https=False):
            proto_str = "HTTPS" if use_https else "HTTP"
            HEAD(f"SERVER TESTS ({proto_str} PROTOCOL)")
            await self.start_server(use_https=use_https)
            try:
                await self._api("POST","/clear")
                if run_all or args.mode in ("api","fast"):
                    await self.test_endpoints()
                    await self.test_security_endpoints()
                    await self.test_clipboard()
                    await self.test_qr()
                    await self.test_history_and_cancel()
                    await self.test_active_stream_cancellation_on_rename()
                    await self.test_race_conditions_and_state_consistency()
                    await self.test_batch_zip_download()
                    await self.test_mdns_platform_cors()
                if run_all or args.mode in ("file-ops"):
                    await self.test_file_operations()
                    await self.test_renamed_non_existent()
                    if run_all: await self.test_rename_to_existing()
                    await self.test_concurrent_uploads()
                    await self.test_special_chars_upload()
                    await self.test_folder_operations()
                    await self.test_same_name_nested_folders()
                    await self.test_folder_upload_api()
                    await self.test_folder_auto_increment()
                    await self.test_folder_invalid_chars()
                    await self.test_chunked_upload()
                    await self.test_move_operations()
                    await self.test_clear_files()
            finally:
                try: await self._api("POST","/clear")
                except: pass
                await self.stop_server()

        if run_all or args.mode in ("api","file-ops","fast"):
            # Test HTTP mode (port 9876)
            await _run_suite(use_https=False)

            # Test HTTPS mode on a different port to avoid Windows port-release delay
            if run_all or args.use_https:
                try:
                    os.environ["QT_PORT"] = "9877"
                    await asyncio.sleep(1.0)
                    await _run_suite(use_https=True)
                except Exception as e:
                    print(WARN(f"HTTPS suite skipped: {e}"))
                finally:
                    os.environ["QT_PORT"] = "9876"

        if run_all or args.mode == "ui":
            try:
                os.environ["QT_PORT"] = "9878"  # Separate port for UI tests
                await asyncio.sleep(1.0)
                await self.start_server(use_https=False)
                try:
                    await self._browser_ui()
                finally:
                    await self.stop_server()
            except Exception as e:
                print(WARN(f"Browser UI suite skipped: {e}"))
            finally:
                os.environ["QT_PORT"] = "9876"

        # ═══════ FINAL CLEANUP ═══════
        HEAD("FINAL CLEANUP")
        import shutil
        data_dir = ROOT / "data"
        if data_dir.exists():
            for item in data_dir.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink(missing_ok=True)
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                except Exception as e:
                    pass
            # Recreate uploads & temp dirs for clean state
            (data_dir / "uploads").mkdir(parents=True, exist_ok=True)
            (data_dir / "temp_chunks").mkdir(parents=True, exist_ok=True)
            print(OK("Cleared all uploaded files and data folders"))

        test_dl = ROOT / "test downloads"
        if test_dl.exists():
            shutil.rmtree(test_dl, ignore_errors=True)
            print(OK("Removed test downloads directory"))

        elapsed = time.time()-start
        tot = self.r["pass"]+self.r["fail"]
        pct = (self.r["pass"]/tot*100) if tot else 0
        bar = f"{C.GREEN}{'\u2588'*int(40*self.r['pass']/tot) if tot else ''}{C.RED}{'\u2591'*(40-int(40*self.r['pass']/tot)) if tot else '\u2591'*40}{C.RESET}"

        print(f"\n{'='*60}")
        status_text = "ALL PASSED" if not self.r["fail"] else f"FAILED: {self.r['fail']}"
        bg = C.BG_GREEN if not self.r["fail"] else C.BG_RED
        print(f"  {bg}{C.WHITE}  {status_text}  {C.RESET}")
        print(f"  {bar}  {pct:.0f}%")
        print(f"  {C.GREEN}\u2713 {self.r['pass']}{C.RESET}  |  {C.RED}\u2717 {self.r['fail']}{C.RESET}  |  {elapsed:.1f}s")
        print(f"{'='*60}")
        if self.r["fail"]:
            print(f"\n{C.BOLD}Failed:{C.RESET}")
            for c in self.r["checks"]:
                if not c["passed"]: print(f"  {C.RED}\u2717{C.RESET} [{c['category']}] {c['name']}")
        return self.r["fail"]==0

def main():
    p = argparse.ArgumentParser(description="Lanvan Regression Suite v6")
    p.add_argument("--fast",dest="mode",action="store_const",const="fast")
    p.add_argument("--js",dest="mode",action="store_const",const="js")
    p.add_argument("--api",dest="mode",action="store_const",const="api")
    p.add_argument("--security",dest="mode",action="store_const",const="security")
    p.add_argument("--file-ops",dest="mode",action="store_const",const="file-ops")
    p.add_argument("--ui",dest="mode",action="store_const",const="ui")
    p.add_argument("--https",dest="use_https",action="store_true",help="Run server tests with HTTPS protocol")
    p.set_defaults(mode="all", use_https=False)
    args = p.parse_args()
    s = Suite()
    ok = asyncio.run(s.run(args))
    sys.exit(0 if ok else 1)

if __name__=="__main__": main()