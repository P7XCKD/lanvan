import os
import socket
import subprocess
import sys
import signal

# Auto-activate virtual environment if not already activated
def ensure_venv():
    """Ensure we're running in the virtual environment"""
    venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".venv", "Scripts", "python.exe")
    
    # Check if we're already in venv or if current python is the venv python
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return  # Already in venv
    
    # Check if current executable is already the venv python
    if os.path.exists(venv_python) and os.path.abspath(sys.executable) == os.path.abspath(venv_python):
        return  # Already using venv python
    
    if os.path.exists(venv_python):
        print("[*] Switching to virtual environment...")
        try:
            # Re-run this script with venv python
            result = subprocess.run([venv_python] + sys.argv, check=False)
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            print("\n[WARNING] Virtual environment switch interrupted.")
            sys.exit(1)
        except Exception as e:
            print(f"[!] Failed to switch to virtual environment: {e}")
            print("[*] Continuing with system Python...")
            return

# Call this first before importing packages that might not be in system python
ensure_venv()

# Now safe to import venv-specific packages
try:
    import psutil
    import uvicorn
except ImportError as e:
    print(f"[!] Missing package: {e}")
    print("[!] Installing required packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "uvicorn[standard]", "fastapi", "jinja2", "python-multipart", "werkzeug", "cryptography", "pycryptodome"])
    import psutil
    import uvicorn

# === CONFIGURATION ===
SSL_CERT_PATH = "certs/cert.pem"
SSL_KEY_PATH = "certs/key.pem"
HTTP_PORT = 5000
HTTPS_PORT = 5001

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
    print(f"\n[OK] Server running at:")
    print(f"Local:  {scheme}://127.0.0.1:{port}")
    print(f"LAN:    {scheme}://{ip}:{port}\n")

def open_browser(ip, port, use_https):
    scheme = "https" if use_https else "http"
    try:
        import webbrowser
        webbrowser.open(f"{scheme}://{ip}:{port}")
    except:
        print("[!] Failed to open browser.")

def kill_servers_on_port(port):
    """Kill all servers running on the specified port"""
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                connections = proc.net_connections()
                if connections:
                    for conn in connections:
                        if hasattr(conn, 'laddr') and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                            print(f"[WARNING] Killing process {proc.info['pid']} ({proc.info['name']}) on port {port}")
                            proc.terminate()
                            proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception as e:
        print(f"[!] Error killing servers: {e}")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n[WARNING] Received signal {signum}. Shutting down servers...")
    kill_servers_on_port(HTTP_PORT)
    kill_servers_on_port(HTTPS_PORT)
    print("[OK] All servers stopped. Goodbye!")
    sys.exit(0)

# === MAIN ENTRY ===
if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    ip = get_ip()
    args = sys.argv
    
    # Parse arguments
    use_https = False
    port = HTTP_PORT
    
    # Check for https argument
    if "https" in [arg.lower() for arg in args[1:]]:
        use_https = True
        port = HTTPS_PORT
    
    # Check for custom port
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                print(f"[!] Invalid port number: {args[i + 1]}")
                sys.exit(1)
    
    # Kill any existing servers on our port first
    kill_servers_on_port(port)

    if use_https and not certs_available():
        print("[WARNING] HTTPS mode requested but cert.pem/key.pem not found. Falling back to HTTP.")
        use_https = False
        port = HTTP_PORT

    print_banner(ip, port, use_https)

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
            "--port", str(port),
            "--log-level", "warning"  # Suppress INFO logs
        ]
        if use_https:
            cmd += ["--ssl-keyfile", SSL_KEY_PATH, "--ssl-certfile", SSL_CERT_PATH]
        subprocess.run(cmd)

    else:
        print("[*] PC detected: launching Uvicorn with auto-reload...")
        open_browser(ip, port, use_https)
        try:
            uvicorn.run(
                "app.main:app",
                host="0.0.0.0",
                port=port,
                reload=True,
                ssl_keyfile=SSL_KEY_PATH if use_https else None,
                ssl_certfile=SSL_CERT_PATH if use_https else None,
                log_level="warning"  # Suppress INFO logs
            )
        except KeyboardInterrupt:
            print("\n[WARNING] Keyboard interrupt received. Shutting down...")
        except Exception as e:
            print(f"\n[!] Server error: {e}")
        finally:
            kill_servers_on_port(port)
            print("[OK] Server stopped gracefully.")
