"""
Comprehensive Endpoint & Route Alias Test Suite for Lanvan
Inspects app.routes directly and verifies all primary routes and legacy aliases exist.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

def run_route_alias_tests():
    print("=" * 60)
    print("  LANVAN FULL ENDPOINT & ROUTE ALIAS AUDIT")
    print("=" * 60)

    # Collect registered routes from FastAPI app
    registered_routes = {}
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            for method in route.methods:
                registered_routes[(method, route.path)] = route.name

    all_passed = True

    route_checks = [
        # (Name, Method, Path)
        ("Move API Primary", "POST", "/api/files/move"),
        ("Move API Alias 1", "POST", "/move"),
        ("Move API Alias 2", "POST", "/files/move"),

        ("Rename API Primary", "POST", "/api/files/rename"),
        ("Rename API Alias 1", "POST", "/rename"),
        ("Rename API Alias 2", "POST", "/files/rename"),

        ("Mkdir API Primary", "POST", "/api/files/mkdir"),
        ("Mkdir API Alias 1", "POST", "/mkdir"),
        ("Mkdir API Alias 2", "POST", "/files/mkdir"),

        ("Cancel Upload API Primary", "POST", "/api/cancel-upload"),
        ("Cancel Upload Alias 1", "POST", "/cancel-upload"),

        ("Clipboard Remove Primary", "DELETE", "/api/clipboard/remove/{item_id}"),
        ("Clipboard Delete Alias", "DELETE", "/api/clipboard/delete/{item_id}"),

        ("Download Zip Primary", "POST", "/api/files/download-zip"),
        ("Download Zip Alias", "POST", "/download-zip"),

        ("List Files Primary", "GET", "/api/files"),
        ("List Folders Primary", "GET", "/api/folders"),
        ("Server Status Primary", "GET", "/api/server-status"),
        ("Network Info Primary", "GET", "/api/network-info"),
    ]

    for name, method, path in route_checks:
        ok = (method, path) in registered_routes
        if not ok:
            all_passed = False

        status_str = "[PASS]" if ok else "[FAIL]"
        route_name = registered_routes.get((method, path), "<missing>")
        print(f"   {status_str} {name}: {method} {path} -> registered as '{route_name}'")

    print("\n" + "=" * 60)
    if all_passed:
        print("  RESULT: ALL ROUTE ALIASED ENDPOINTS AUDITED & REGISTERED 100%!")
    else:
        print("  RESULT: ROUTE ALIAS AUDIT FAILURE ENCOUNTERED.")
    print("=" * 60)

    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    run_route_alias_tests()
