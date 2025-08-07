# SSL Certificates Directory

This directory contains SSL certificates and keys for HTTPS functionality in Lanvan.

## 🔒 Security Notice

**IMPORTANT**: All certificate files (`*.pem`, `*.key`, `*.crt`, `*.cert`) are automatically ignored by Git for security reasons. This prevents accidentally committing private keys to version control.

## Files in this directory:

- `openssl.conf` - OpenSSL configuration template
- `generate_certs.py` - Python script to generate certificates
- `README.md` - This documentation
- `cert.pem` - SSL certificate (auto-generated, gitignored)
- `key.pem` - Private key (auto-generated, gitignored)

## Quick Start

### Automatic Certificate Generation
The certificates will be automatically generated when you run the server in HTTPS mode if they don't exist:

```bash
python run.py https
```

### Manual Certificate Generation
You can also generate certificates manually:

```bash
# Generate with auto-detected IP
python certs/generate_certs.py

# Generate for specific IP address
python certs/generate_certs.py --ip 192.168.1.100

# Force regenerate existing certificates
python certs/generate_certs.py --force
```

## Requirements

- OpenSSL must be installed on your system
- Python 3.6+ for the generation script

### Installing OpenSSL:

**Windows**: 
- Download from https://slproweb.com/products/Win32OpenSSL.html
- Or use Windows Subsystem for Linux (WSL)

**macOS**: 
```bash
brew install openssl
```

**Ubuntu/Debian**: 
```bash
sudo apt-get install openssl
```

**CentOS/RHEL**: 
```bash
sudo yum install openssl
```

## Certificate Details

The generated certificates include:
- **Algorithm**: RSA 2048-bit
- **Validity**: 365 days
- **Subject**: CN=localhost
- **Subject Alternative Names (SAN)**:
  - DNS: localhost, 127.0.0.1, your_detected_IP
  - IP: 127.0.0.1, your_detected_IP

## Security Features

1. **Git Ignored**: All certificate files are automatically ignored by Git
2. **Local Generation**: Certificates are generated locally, never transmitted
3. **Secure Permissions**: Private keys have restrictive file permissions (Unix/Linux/macOS)
4. **Self-Signed**: Suitable for development; use CA-signed certificates for production

## Production Deployment

For production environments:
1. Use certificates from a trusted Certificate Authority (Let's Encrypt, etc.)
2. Place certificates in a secure location outside the application directory
3. Use environment variables to specify certificate paths
4. Ensure proper file permissions (600 for private keys)

## Troubleshooting

### "OpenSSL not found" error
- Install OpenSSL using the instructions above
- Make sure OpenSSL is in your system PATH

### "Certificate verification failed" in browsers
- This is expected for self-signed certificates
- Click "Advanced" and "Proceed" in your browser (development only)
- For production, use CA-signed certificates

### Permission errors (Unix/Linux/macOS)
```bash
chmod 600 certs/key.pem
chmod 644 certs/cert.pem
```

## Environment Variables (Optional)

You can override certificate paths using environment variables:

```bash
export SSL_CERT_PATH="/path/to/your/cert.pem"
export SSL_KEY_PATH="/path/to/your/key.pem"
```
