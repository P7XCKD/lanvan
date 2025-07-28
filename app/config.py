# app/config.py

import os

# ❌ Blocked extensions (everything else allowed)
BLOCKED_EXTENSIONS = {'.exe', '.bat'}

# ✅ Allow all files except .exe and .bat
def is_allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext not in BLOCKED_EXTENSIONS
