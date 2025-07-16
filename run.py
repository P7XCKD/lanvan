import os
import socket
import webbrowser
import platform
import subprocess
import multiprocessing
import uvicorn
import ssl

# === CONFIGURABLE ===
USE_HTTPS = False  # ✅ Toggle HTTPS
SSL_CERT_PATH = "cert.pem"
SSL_KEY_PATH = "key.pem"
PORT = 5000

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return ip

def is_android_termux():
    return "ANDROID_STORAGE" in os.environ or os.path.exists("/data/data/com.termux")

def get_worker_count():
    return str(max(2, multiprocessing.cpu_count() * 2 + 1))  # Gunicorn rule of thumb

def print_banner(ip, port, use_https):
    scheme = "https" if use_https else "http"
    print(f"\n[✔] Server running at:")
    print(f"🔗 Localhost:  {scheme}://127.0.0.1:{port}")
    print(f"🌐 LAN IP:    {scheme}://{ip}:{port}\n")

def open_browser(ip, port, use_https):
    scheme = "https" if use_https else "http"
    try:
        webbrowser.open(f"{scheme}://{ip}:{port}")
    except:
        print("[!] Failed to open browser")

if __name__ == "__main__":
    ip = get_ip()
    print_banner(ip, PORT, USE_HTTPS)

    if is_android_termux():
        print("[*] Android (Termux) detected: launching Waitress...")
        try:
            subprocess.run([
                "waitress-serve",
                "--host=0.0.0.0",
                "--port=" + str(PORT),
                "app.main:app"
            ])
        except FileNotFoundError:
            print("[!] Waitress not found. Falling back to Uvicorn...")
            subprocess.run([
                "uvicorn", "app.main:app",
                "--host", "0.0.0.0",
                "--port", str(PORT),
                "--ssl-keyfile", SSL_KEY_PATH if USE_HTTPS and os.path.exists(SSL_KEY_PATH) else "",
                "--ssl-certfile", SSL_CERT_PATH if USE_HTTPS and os.path.exists(SSL_CERT_PATH) else "",
            ])
    else:
        print("[*] PC (Windows) detected: launching Uvicorn...")
        open_browser(ip, PORT, USE_HTTPS)
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=PORT,
            reload=True,
            ssl_keyfile=SSL_KEY_PATH if USE_HTTPS and os.path.exists(SSL_KEY_PATH) else None,
            ssl_certfile=SSL_CERT_PATH if USE_HTTPS and os.path.exists(SSL_CERT_PATH) else None
        )
