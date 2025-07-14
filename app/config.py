# app/config.py

import os

MAX_CONTENT_LENGTH = 15 * 1024 * 1024 * 1024  # 15 GB
UPLOAD_FOLDER = 'uploads'

# Blocklist of forbidden extensions
BLOCKED_EXTENSIONS = {'.exe', '.bat'}

def is_allowed_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext not in BLOCKED_EXTENSIONS

class Config:
    # existing configs...
    COMPRESS_LEVEL = 6  # range: 1 (fast) to 9 (best)
    COMPRESS_MIN_SIZE = 500  # only compress responses > 500 bytes
