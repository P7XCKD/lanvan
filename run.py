import os
import socket
import webbrowser
import subprocess
import sys
import uvicorn

# === CONFIGURATION ===
SSL_CERT_PATH = "certs/cert.pem"
SSL_KEY_PATH = "certs/key.pem"
PORT = 5000

# === UTILITY FUNCTIONS ===
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

def certs_available():
    return os.path.exists(SSL_CERT_PATH) and os.path.exists(SSL_KEY_PATH)

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
        print("[!] Failed to open browser.")

# === MAIN ENTRY ===
if __name__ == "__main__":
    ip = get_ip()
    args = sys.argv
    use_https = len(args) > 1 and args[1].lower() == "https"

    if use_https and not certs_available():
        print("[⚠] HTTPS mode requested but cert.pem/key.pem not found. Falling back to HTTP.")
        use_https = False

    print_banner(ip, PORT, use_https)

    if is_android_termux():
        print("[*] Android (Termux) detected: launching Uvicorn...")
        
        # ⛔️ Waitress removed: FastAPI is ASGI and no longer supports WSGI servers like Waitress.
        # subprocess.run([
        #     "waitress-serve",
        #     "--host=0.0.0.0",
        #     "--port=" + str(PORT),
        #     "app.main:app"
        # ])

        cmd = [
            "uvicorn", "app.main:app",
            "--host", "0.0.0.0",
            "--port", str(PORT)
        ]
        if use_https:
            cmd += ["--ssl-keyfile", SSL_KEY_PATH, "--ssl-certfile", SSL_CERT_PATH]
        subprocess.run(cmd)

    else:
        print("[*] PC detected: launching Uvicorn with auto-reload...")
        open_browser(ip, PORT, use_https)
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=PORT,
            reload=True,
            ssl_keyfile=SSL_KEY_PATH if use_https else None,
            ssl_certfile=SSL_CERT_PATH if use_https else None
        )
