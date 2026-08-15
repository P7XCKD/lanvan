#!/usr/bin/env python3
"""
Stress Test: Protocol Switching & Rapid Start/Stop Cycle (5 Cycles)
Tests starting and stopping Lanvan across HTTP (port 5000) and HTTPS (port 5001) repeatedly.
"""

import time
import urllib.request
import ssl
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from testing.tools import test_android

ADB = test_android.ADB_PATH

def query_endpoint(url: str, is_https: bool = False, timeout: float = 2.0):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LanvanStressClient/1.0"})
        if is_https:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                return resp.status, resp.read().decode('utf-8', errors='ignore')
        else:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""

def main():
    print("=" * 65)
    print("   LANVAN RAPID START/STOP & PROTOCOL SWITCH STRESS TEST (5 CYCLES)   ")
    print("=" * 65)

    test_android.run_cmd(f'"{ADB}" forward tcp:5000 tcp:5000')
    test_android.run_cmd(f'"{ADB}" forward tcp:5001 tcp:5001')
    test_android.run_cmd(f'"{ADB}" shell am force-stop com.probz.lanvan')
    time.sleep(1)

    # Sequence of 5 protocol cycles: HTTP -> HTTPS -> HTTP -> HTTPS -> HTTP
    cycles = [
        (1, False, 5000, "HTTP"),
        (2, True, 5001, "HTTPS"),
        (3, False, 5000, "HTTP"),
        (4, True, 5001, "HTTPS"),
        (5, False, 5000, "HTTP")
    ]

    all_passed = True

    for cycle_num, use_https, port, proto_name in cycles:
        print(f"\n--- CYCLE {cycle_num}/5: [{proto_name} MODE - Port {port}] ---")
        
        # 1. Start Server
        t_start = time.perf_counter()
        test_android.run_cmd(f'"{ADB}" shell am start -n com.probz.lanvan/.MainActivity --ez AUTO_START_SERVER true --ez USE_HTTPS {str(use_https).lower()}')
        
        started = False
        scheme = "https" if use_https else "http"
        url = f"{scheme}://127.0.0.1:{port}/api/server-status"
        
        for attempt in range(15):
            time.sleep(1.2)
            st, body = query_endpoint(url, is_https=use_https, timeout=2.0)
            if st == 200:
                elapsed = (time.perf_counter() - t_start) * 1000
                print(f"[PASS] Cycle {cycle_num} Server STARTED successfully ({proto_name} on port {port}) in {elapsed:.0f}ms (attempt {attempt+1})")
                started = True
                break
        
        if not started:
            print(f"[FAIL] Cycle {cycle_num} Server FAILED to start ({proto_name} on port {port})")
            all_passed = False
            break

        # Quick operational check
        st_home, home_body = query_endpoint(f"{scheme}://127.0.0.1:{port}/", is_https=use_https, timeout=2.0)
        if st_home == 200 and "<html" in home_body.lower():
            print(f"[PASS] Cycle {cycle_num} Homepage verified (200 OK)")
        else:
            print(f"[WARN] Cycle {cycle_num} Homepage returned st={st_home}")

        # 2. Stop Server
        t_stop = time.perf_counter()
        test_android.run_cmd(f'"{ADB}" shell am force-stop com.probz.lanvan')
        
        stopped = False
        for attempt in range(10):
            time.sleep(0.5)
            st, _ = query_endpoint(url, is_https=use_https, timeout=1.0)
            if st == 0:
                elapsed_stop = (time.perf_counter() - t_stop) * 1000
                print(f"[PASS] Cycle {cycle_num} Server STOPPED and port released in {elapsed_stop:.0f}ms (attempt {attempt+1})")
                stopped = True
                break
        
        if not stopped:
            print(f"[FAIL] Cycle {cycle_num} Server did not unbind port {port} in time")
            all_passed = False
            break

        time.sleep(1.0)

    print("\n" + "=" * 65)
    if all_passed:
        print("[SUCCESS] ALL 5 RAPID PROTOCOL SWITCH & START/STOP CYCLES PASSED!")
    else:
        print("[FAILURE] RAPID START/STOP STRESS TEST ENCOUNTERED FAILURES.")
    print("=" * 65)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
