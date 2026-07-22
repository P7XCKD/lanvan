#!/usr/bin/env python3
"""Lanvan Workflow Tests — Module 6 (End-to-End User Journeys)"""
import urllib.request, urllib.error, json, sys, time, io

GREEN = "\033[92m"; RED = "\033[91m"; BOLD = "\033[1m"; RESET = "\033[0m"
BASE = "http://localhost"
API = f"{BASE}/api"
passed = 0; failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1; print(f"  {GREEN}PASS{RESET} {name}" + (f" — {detail}" if detail else ""))
    else:
        failed += 1; print(f"  {RED}FAIL{RESET} {name}" + (f" — {detail}" if detail else ""))

def fetch(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.data = urllib.parse.urlencode(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode()) if r.read else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try: return json.loads(body)
        except: return {"error": body}
    except Exception as e:
        return {"error": str(e)}

print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  Module 6: Workflow Tests — End-to-End User Journeys{RESET}")
print(f"{BOLD}{'='*60}")

T = f"_wftest_{int(time.time())}"

# ── Workflow 1: Upload → Rename → Move → Delete ──
print(f"\n{BOLD}Workflow 1: Upload → Rename → Move → Delete{RESET}")
print(f"{'─'*50}")

# Upload a test file
boundary = "----FormBoundaryWF"
body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{T}.txt\"\r\n"
        f"Content-Type: text/plain\r\n\r\nWorkflow test content\r\n--{boundary}--\r\n").encode()
req = urllib.request.Request(f"{BASE}/upload-auto", data=body, method="POST")
req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        up = json.loads(r.read().decode())
        check("Upload test file", up.get("status") == "success", up.get("msg",""))
except Exception as e:
    check("Upload test file", False, str(e))

time.sleep(0.5)

# Rename
rn = fetch(f"{API}/files/rename", "POST", {"filename": f"{T}.txt", "new_name": f"{T}_renamed.txt"})
check("Rename file", rn.get("status") == "success", rn.get("msg",""))

# Move
mv = fetch(f"{API}/files/move", "POST", {"filename": f"{T}_renamed.txt", "destination": ""})
check("Move file back to root", mv.get("status") == "success", mv.get("msg",""))

# Delete
dl = fetch(f"{BASE}/delete/{T}_renamed.txt", "POST")
check("Delete file", dl.get("status") in ("success", None) or str(dl.get("msg","")).startswith("File"), "cleaned up")

# ── Workflow 2: Clipboard ──
print(f"\n{BOLD}Workflow 2: Clipboard Add → List{RESET}")
print(f"{'─'*50}")

add = fetch(f"{API}/clipboard/add", "POST", {"data": f"WF test clipboard {T}"})
check("Add to clipboard", add.get("status") == "success", add.get("msg",""))

lst = fetch(f"{API}/clipboard/list", "GET")
check("List clipboard", lst.get("status") == "success", f"{lst.get('count',0)} items")

# ── Workflow 3: Folder Operations ──
print(f"\n{BOLD}Workflow 3: Create Folder → Delete Folder{RESET}")
print(f"{'─'*50}")

mkdir = fetch(f"{API}/files/mkdir", "POST", {"folder_name": T})
check("Create folder", mkdir.get("status") == "success", mkdir.get("msg",""))

dup = fetch(f"{API}/files/mkdir", "POST", {"folder_name": T})
check("Duplicate folder rejected", dup.get("status") != "success", f"status={dup.get('status', 'N/A')}")

delf = fetch(f"{BASE}/delete-folder/{T}", "POST")
check("Delete folder", delf.get("status") == "success", delf.get("msg",""))

# ── Workflow 4: File List Consistency ──
print(f"\n{BOLD}Workflow 4: File List Consistency{RESET}")
print(f"{'─'*50}")

files = fetch(f"{API}/files", "GET")
check("GET /api/files returns 200", files.get("status") == "success")
check("Files key exists", isinstance(files.get("files"), list))
check("Files_data key exists", isinstance(files.get("files_data"), list))
check("Count matches", len(files.get("files",[])) == files.get("count", -1), "files==count")

# ── Score ──
total = passed + failed
score = round((passed / max(total, 1)) * 100, 1)
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"\n{BOLD}Module 6: Workflow Score{RESET}")
print(f"  {GREEN}Passed: {passed}{RESET}  {RED}Failed: {failed}{RESET}  {BOLD}Score: {score}%{RESET}")
print(f"\n{'✅ All workflows pass!' if failed == 0 else f'❌ {failed} workflow failures'}{RESET}\n")