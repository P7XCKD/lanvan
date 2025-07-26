# app/config.py

import os

# Maximum file size: 15 GB
MAX_CONTENT_LENGTH = 15 * 1024 * 1024 * 1024  # 15 GB

# Upload directory (relative to app root)
UPLOAD_FOLDER = 'uploads'

# ❌ Blocked extensions (everything else allowed)
BLOCKED_EXTENSIONS = {'.exe', '.bat'}

# ✅ Allow all files except .exe and .bat
def is_allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext not in BLOCKED_EXTENSIONS

# SSL Configuration
SSL_CERT_PATH = "certs/cert.pem"
SSL_KEY_PATH = "certs/key.pem"

def ssl_certs_available() -> bool:
    """Check if SSL certificates are available"""
    return os.path.exists(SSL_CERT_PATH) and os.path.exists(SSL_KEY_PATH)

# Optional compression config (if middleware added later)
class Config:
    COMPRESS_LEVEL = 6        # Range: 1 (fast) → 9 (best compression)
    COMPRESS_MIN_SIZE = 500   # Only compress if response > 500 bytes
