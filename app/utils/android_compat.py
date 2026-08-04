import os
from pathlib import Path

def get_base_data_dir() -> Path:
    """
    Returns the appropriate directory for storing application data.
    - On Android (Chaquopy): returns context.getFilesDir().getAbsolutePath()
    - On Desktop/Termux: returns local workspace root
    """
    try:
        # Check if we are running in Android (Chaquopy environment)
        from com.chaquo.python import Python
        context = Python.getPlatform().getApplication()
        android_dir = context.getFilesDir().getAbsolutePath()
        return Path(android_dir)
    except Exception:
        # Fallback to local working directory
        return Path(".")

def update_android_progress(percent: int, title: str = ""):
    """No-op. Progress bar feature disabled."""
    pass
