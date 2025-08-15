#!/usr/bin/env python3
"""
Python-based SSL Certificate Generator (No OpenSSL Required)
============================================================

This script generates self-signed SSL certificates using Python's cryptography library.
No external OpenSSL installation required - works on any system with Python.

Usage:
    python generate_certs_python.py [--ip YOUR_IP] [--force]

Arguments:
    --ip IP_ADDRESS    : Specify custom IP address for certificate
    --force           : Regenerate certificates even if they exist
    --help            : Show this help message
"""

import os
import sys
import socket
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import ipaddress

def get_local_ip():
    """Get the local IP address"""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def generate_certificates_python(ip_address=None, force=False):
    """Generate SSL certificates using Python cryptography library"""
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
    
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        print("[ERROR] cryptography library not found!")
        print("Installing cryptography library...")
        try:
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"], check=True)
            from cryptography import x509
            from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            print("[OK] cryptography library installed successfully")
        except Exception as e:
            print(f"[ERROR] Failed to install cryptography: {e}")
            return False
    
    # Get IP address
    if not ip_address:
        ip_address = get_local_ip()
    
    print(f"[INFO] Generating SSL certificates for IP: {ip_address}")
    
    try:
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate subject
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LanVan"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        # Create Subject Alternative Names (iOS Safari compatible)
        san_list = [
            x509.DNSName("localhost"),
            x509.DNSName("127.0.0.1"),
            x509.DNSName("lanvan.local"),  # Add mDNS domain for iOS
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]
        
        # Add the detected IP address
        try:
            san_list.extend([
                x509.DNSName(ip_address),
                x509.IPAddress(ipaddress.IPv4Address(ip_address))
            ])
        except ValueError:
            # If IP parsing fails, just add as DNS name
            san_list.append(x509.DNSName(ip_address))
        
        # Add additional iOS Safari compatibility domains
        san_list.extend([
            x509.DNSName("*.local"),  # Wildcard for mDNS
            x509.DNSName(f"{socket.gethostname().lower()}.local"),  # Host-based mDNS
        ])
        
        # Create certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).add_extension(
            x509.KeyUsage(
                key_encipherment=True,
                data_encipherment=False,
                digital_signature=True,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=True,
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).sign(private_key, hashes.SHA256())
        
        # Write private key
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Write certificate
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # Set secure permissions on private key (Unix-like systems)
        if os.name != 'nt':  # Not Windows
            os.chmod(key_file, 0o600)
        
        print("[OK] SSL certificates generated successfully!")
        print(f"   Certificate: {cert_file}")
        print(f"   Private Key: {key_file}")
        print(f"   Valid for IP: {ip_address}")
        print("   Valid for: localhost, 127.0.0.1")
        print("   Expires: 365 days from now")
        print("   Method: Python cryptography library (no OpenSSL required)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to generate certificates: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description='Generate SSL certificates for LanVan Clipy (Python method)')
    parser.add_argument('--ip', help='IP address to include in certificate')
    parser.add_argument('--force', action='store_true', help='Force regenerate certificates')
    
    args = parser.parse_args()
    
    print("[INFO] LanVan Clipy - SSL Certificate Generator (Python)")
    print("=" * 60)
    
    success = generate_certificates_python(args.ip, args.force)
    
    if success:
        print("\n[OK] Setup Complete!")
        print("Your server can now run in HTTPS mode securely.")
        print("The certificates are gitignored and won't be committed to version control.")
    else:
        print("\n[ERROR] Certificate generation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
