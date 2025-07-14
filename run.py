import platform
import subprocess
import sys
import os
import socket
from app import app

def is_android():
    return 'ANDROID_ROOT' in os.environ or (platform.system() == 'Linux' and 'com.termux' in sys.executable)

def is_windows():
    return platform.system() == 'Windows'

def get_ip():
    """Get LAN IP address for browser access"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return ip

def print_links():
    ip = get_ip()
    print("\n[✔] Server is running!")
    print(f"🔗 Localhost:  http://127.0.0.1:5000")
    print(f"🌐 LAN IP:    http://{ip}:5000\n")

def run_with_waitress():
    app.debug = False
    from waitress import serve
    print("[INFO] Running with Waitress (Windows/Android mode)")
    print_links()
    serve(
        app,
        host='0.0.0.0',
        port=5000,
        threads=4,
        max_request_body_size=15 * 1024 * 1024 * 1024  # 15 GB
    )

def run_with_gunicorn():
    app.debug = False
    print("[INFO] Running with Gunicorn (Linux/Server mode)")
    print_links()
    subprocess.run(["gunicorn", "app:app", "-b", "0.0.0.0:5000", "--workers", "2", "--timeout", "120"])

if __name__ == "__main__":
    if is_android():
        run_with_waitress()
    elif is_windows():
        run_with_waitress()
    else:
        run_with_gunicorn()
