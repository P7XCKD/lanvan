#!/usr/bin/env python3
"""
SSL Certificate Generator for LanVan Clipy
==========================================

This script generates self-signed SSL certificates for HTTPS functionality.
The certificates are automatically generated when not present.

Security Features:
- Certificates are locally generated only
- Private keys never leave your machine
- Git ignores all certificate files
- Automatic IP detection for Subject Alternative Names (SAN)

Usage:
    python generate_certs.py [--ip YOUR_IP] [--force]

Arguments:
    --ip IP_ADDRESS    : Specify custom IP address for certificate
    --force           : Regenerate certificates even if they exist
    --help            : Show this help message

Note: This generates self-signed certificates suitable for development.
For production, use certificates from a trusted Certificate Authority.
"""

import os
import sys
import socket
import subprocess
import argparse
import tempfile
from pathlib import Path


def get_local_ip():
    """Get the local IP address"""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def check_openssl():
    """Check if OpenSSL is available"""
    try:
        result = subprocess.run(['openssl', 'version'], 
                              capture_output=True, text=True, check=True)
        print(f"[OK] OpenSSL found: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] OpenSSL not found!")
        print("\nTo install OpenSSL:")
        print("- Windows: Download from https://slproweb.com/products/Win32OpenSSL.html")
        print("- macOS: brew install openssl")
        print("- Ubuntu/Debian: sudo apt-get install openssl")
        print("- CentOS/RHEL: sudo yum install openssl")
        return False


def create_openssl_config(ip_address="127.0.0.1"):
    """Create OpenSSL configuration with dynamic IP"""
    config_content = f"""[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = US
ST = Local
L = Local
O = LanVan
CN = localhost

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = 127.0.0.1
DNS.3 = {ip_address}
IP.1 = 127.0.0.1
IP.2 = {ip_address}
"""
    return config_content


def generate_certificates(ip_address=None, force=False):
    """Generate SSL certificates"""
    certs_dir = Path(__file__).parent
    cert_file = certs_dir / "cert.pem"
    key_file = certs_dir / "key.pem"
    
    # Check if certificates already exist
    if cert_file.exists() and key_file.exists() and not force:
        print("[OK] SSL certificates already exist")
        print(f"  Certificate: {cert_file}")
        print(f"  Private Key: {key_file}")
        print("\nUse --force to regenerate")
        return True
    
    if not check_openssl():
        return False
    
    # Get IP address
    if not ip_address:
        ip_address = get_local_ip()
    
    print(f"[INFO] Generating SSL certificates for IP: {ip_address}")
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write(create_openssl_config(ip_address))
        config_path = f.name
    
    try:
        # Generate private key and certificate in one command
        cmd = [
            'openssl', 'req',
            '-newkey', 'rsa:2048',
            '-nodes',
            '-keyout', str(key_file),
            '-x509',
            '-days', '365',
            '-out', str(cert_file),
            '-config', config_path
        ]
        
        print("[INFO] Running OpenSSL command...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Set secure permissions on private key (Unix-like systems)
        if os.name != 'nt':  # Not Windows
            os.chmod(key_file, 0o600)
        
        print("[OK] SSL certificates generated successfully!")
        print(f"   Certificate: {cert_file}")
        print(f"   Private Key: {key_file}")
        print(f"   Valid for IP: {ip_address}")
        print("   Valid for: localhost, 127.0.0.1")
        print("   Expires: 365 days from now")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to generate certificates: {e}")
        print(f"   stderr: {e.stderr}")
        return False
    finally:
        # Clean up temporary config file
        try:
            os.unlink(config_path)
        except:
            pass


def verify_certificates():
    """Verify the generated certificates"""
    certs_dir = Path(__file__).parent
    cert_file = certs_dir / "cert.pem"
    
    if not cert_file.exists():
        return False
    
    try:
        cmd = ['openssl', 'x509', '-in', str(cert_file), '-text', '-noout']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        print("\n[INFO] Certificate Information:")
        lines = result.stdout.split('\n')
        for line in lines:
            if 'Subject:' in line or 'DNS:' in line or 'IP Address:' in line or 'Not After:' in line:
                print(f"   {line.strip()}")
        
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    parser = argparse.ArgumentParser(description='Generate SSL certificates for LanVan Clipy')
    parser.add_argument('--ip', help='IP address to include in certificate')
    parser.add_argument('--force', action='store_true', help='Force regenerate certificates')
    
    args = parser.parse_args()
    
    print("[INFO] LanVan Clipy - SSL Certificate Generator")
    print("=" * 50)
    
    success = generate_certificates(args.ip, args.force)
    
    if success:
        print("\n[INFO] Verifying certificates...")
        verify_certificates()
        
        print("\n[OK] Setup Complete!")
        print("Your server can now run in HTTPS mode securely.")
        print("The certificates are gitignored and won't be committed to version control.")
    else:
        print("\n[ERROR] Certificate generation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
