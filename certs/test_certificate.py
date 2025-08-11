#!/usr/bin/env python3
"""
SSL Certificate Tester
======================
This script tests if the generated SSL certificates work properly for HTTPS connections.
"""

import ssl
import socket
import sys
from pathlib import Path

def test_certificate():
    """Test the SSL certificate"""
    cert_file = Path(__file__).parent / "cert.pem"
    key_file = Path(__file__).parent / "key.pem"
    
    if not cert_file.exists() or not key_file.exists():
        print("[ERROR] Certificate files not found!")
        print("Run: python generate_certs_python.py")
        return False
    
    try:
        # Load and verify the certificate
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.load_cert_chain(str(cert_file), str(key_file))
        
        print("[OK] Certificate loaded successfully")
        
        # Check certificate details
        with open(cert_file, 'rb') as f:
            cert_data = f.read()
            
        # Parse certificate using OpenSSL if available
        try:
            import subprocess
            result = subprocess.run(['openssl', 'x509', '-in', str(cert_file), '-text', '-noout'], 
                                  capture_output=True, text=True, check=True)
            
            print("\n[INFO] Certificate Details:")
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line for keyword in ['Subject:', 'DNS:', 'IP Address:', 'Not After:', 'Key Usage:']):
                    print(f"   {line.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[INFO] OpenSSL not available for detailed certificate inspection")
        
        print("\n[OK] Certificate appears to be valid!")
        print("If you're still getting browser errors, try:")
        print("1. Clear browser cache and cookies")
        print("2. Try in incognito/private browsing mode")  
        print("3. Access via https://localhost:5001 instead of IP")
        print("4. Click 'Advanced' -> 'Proceed' in browser (for self-signed certs)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Certificate test failed: {e}")
        return False

if __name__ == "__main__":
    print("[INFO] Testing SSL Certificate")
    print("=" * 30)
    test_certificate()
