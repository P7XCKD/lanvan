#!/usr/bin/env python3
"""
CORS Security Test - Verify the secure CORS implementation
Tests both allowed and rejected origins according to security audit recommendations
"""

import requests
import sys
import time
from urllib.parse import urlparse

def test_cors_headers(base_url, test_origins):
    """Test CORS headers for various origins"""
    print(f"\n[AUTH] Testing CORS Security for {base_url}")
    print("=" * 60)
    
    results = {
        'allowed': [],
        'rejected': [],
        'errors': []
    }
    
    for origin_desc, origin in test_origins.items():
        try:
            # Test with preflight OPTIONS request
            headers = {
                'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            }
            
            response = requests.options(base_url, headers=headers, timeout=5)
            
            # Check if CORS headers are present and origin is allowed
            cors_origin = response.headers.get('Access-Control-Allow-Origin')
            
            if cors_origin == origin:
                results['allowed'].append((origin_desc, origin))
                print(f"[OK] {origin_desc}: ALLOWED ({origin})")
            elif response.status_code == 403:
                results['rejected'].append((origin_desc, origin))
                print(f" {origin_desc}: REJECTED ({origin}) - Security working")
            else:
                results['rejected'].append((origin_desc, origin))
                print(f" {origin_desc}: REJECTED ({origin}) - No CORS header")
                
        except Exception as e:
            results['errors'].append((origin_desc, origin, str(e)))
            print(f"[ERR] {origin_desc}: ERROR ({origin}) - {e}")
    
    return results

def main():
    """Main CORS testing function"""
    
    # Test against local server - try both localhost and 127.0.0.1
    base_url = "http://127.0.0.1:5000"
    
    # Define test origins - mix of allowed and disallowed
    test_origins = {
        # Should be ALLOWED (local network)
        "Localhost": "http://localhost:3000",
        "Localhost HTTPS": "https://localhost:3000", 
        "127.0.0.1": "http://127.0.0.1:8080",
        "Local Network": "http://192.168.1.100:3000",
        "Local Network HTTPS": "https://192.168.1.50:4000",
        "Private Network 10.x": "http://10.0.1.5:3000",
        "Private Network 172.x": "http://172.16.0.10:3000",
        "mDNS Domain": "http://lanvan.local:3000",
        "Local Domain": "http://myapp.local",
        "Link Local": "http://169.254.1.1:3000",
        
        # Should be REJECTED (external/public)
        "External Site": "https://evil.com",
        "Public IP": "http://8.8.8.8:3000",
        "External Domain": "https://attacker.example.com",
        "Different TLD": "https://lanvan.com",
        "Public Network": "http://203.0.113.1:3000",
    }
    
    print("[SEARCH] CORS Security Validation Test")
    print("Testing secure CORS implementation against security audit requirements")
    
    try:
        # First check if server is running
        response = requests.get(base_url, timeout=5)
        if response.status_code != 200:
            print(f"[ERR] Server not responding properly at {base_url}")
            return
            
        print(f"[OK] Server is running at {base_url}")
        
        # Test CORS configuration
        results = test_cors_headers(base_url, test_origins)
        
        # Summary
        print(f"\n[STATS] CORS Security Test Results:")
        print(f"[OK] Allowed Origins: {len(results['allowed'])}")
        print(f" Rejected Origins: {len(results['rejected'])}")
        print(f"[ERR] Errors: {len(results['errors'])}")
        
        # Verify security expectations
        allowed_count = len(results['allowed'])
        rejected_count = len(results['rejected'])
        
        if allowed_count >= 7 and rejected_count >= 4:  # Expect ~7 local origins allowed, ~4+ external rejected
            print(f"\n[DONE] CORS Security: EXCELLENT")
            print(f"   Local network access: [OK] Working ({allowed_count} origins)")
            print(f"   External protection: [OK] Working ({rejected_count} origins blocked)")
            print(f"   Security audit requirement: [OK] SATISFIED")
        else:
            print(f"\n[WARN]  CORS Security: NEEDS REVIEW")
            print(f"   Expected: ~7 local allowed, ~4 external rejected")
            print(f"   Actual: {allowed_count} allowed, {rejected_count} rejected")
            
        # Show allowed origins for verification
        if results['allowed']:
            print(f"\n[OK] Allowed Origins (Local Network):")
            for desc, origin in results['allowed']:
                print(f"   • {desc}: {origin}")
                
        # Show rejected origins for verification  
        if results['rejected']:
            print(f"\n Rejected Origins (Security Protection):")
            for desc, origin in results['rejected']:
                print(f"   • {desc}: {origin}")
                
        if results['errors']:
            print(f"\n[ERR] Connection Errors:")
            for desc, origin, error in results['errors']:
                print(f"   • {desc} ({origin}): {error}")
                
    except requests.exceptions.ConnectionError:
        print(f"[ERR] Cannot connect to server at {base_url}")
        print("[TIP] Please start the LANVan server first with: python run.py")
        sys.exit(1)
    except Exception as e:
        print(f"[ERR] Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()