"""
[TARGET] Simple Platform Detection and Utilities
Provides clean, simple platform detection functions for Lanvan
"""

import os
import sys
import platform as py_platform


def detect_platform() -> str:
    """
    [SEARCH] Detect the current platform
    Returns: 'windows', 'linux', 'darwin', 'android', 'termux', or 'unknown'
    """
    system = py_platform.system().lower()
    
    # Check for Android/Termux first (more specific)
    if is_termux():
        return 'termux'
    elif is_android():
        return 'android'
    elif system == 'windows':
        return 'windows'
    elif system == 'linux':
        return 'linux'
    elif system == 'darwin':
        return 'darwin'
    else:
        return 'unknown'


def is_android() -> bool:
    """
    [BOT] Detect Android environment (broader than just Termux)
    """
    return any([
        is_termux(),
        "ANDROID_STORAGE" in os.environ,
        "ANDROID_ROOT" in os.environ,
        os.path.exists("/system/build.prop"),
        os.path.exists("/android_asset"),
        "android" in sys.platform.lower()
    ])


def is_termux() -> bool:
    """
    [SEARCH] Detect Termux environment specifically
    """
    return any([
        "TERMUX_VERSION" in os.environ,
        "ANDROID_STORAGE" in os.environ,
        os.path.exists("/data/data/com.termux"),
        os.path.exists("/system/bin/termux-setup-storage"),
        "com.termux" in os.environ.get("PREFIX", ""),
        "/data/data/com.termux" in sys.executable
    ])


def is_windows() -> bool:
    """Check if running on Windows"""
    return py_platform.system().lower() == 'windows'


def is_linux() -> bool:
    """Check if running on Linux (excluding Android)"""
    return py_platform.system().lower() == 'linux' and not is_android()


def is_macos() -> bool:
    """Check if running on macOS"""
    return py_platform.system().lower() == 'darwin'


def get_platform_info() -> dict:
    """
    [STATS] Get comprehensive platform information
    """
    return {
        'platform': detect_platform(),
        'system': py_platform.system(),
        'machine': py_platform.machine(),
        'processor': py_platform.processor(),
        'python_version': py_platform.python_version(),
        'is_android': is_android(),
        'is_termux': is_termux(),
        'is_windows': is_windows(),
        'is_linux': is_linux(),
        'is_macos': is_macos()
    }