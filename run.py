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
    import cryptography  # Test for cryptography specifically
except ImportError as e:
    print(f"[!] Missing package: {e}")
    print("[!] Installing required packages from requirements.txt...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                              check=True, capture_output=True, text=True)
        print("✅ Dependencies installed successfully!")
        import psutil
        import uvicorn
    except subprocess.CalledProcessError as install_error:
        print(f"❌ Failed to install from requirements.txt: {install_error}")
        print("📦 Trying individual package installation...")
        subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "uvicorn[standard]", "fastapi", "jinja2", "python-multipart", "werkzeug", "cryptography", "pycryptodome"])
        import psutil
        import uvicorn

# === CONFIGURATION ===
# SSL Certificate paths (can be overridden by environment variables)
SSL_CERT_PATH = os.getenv("SSL_CERT_PATH", "certs/cert.pem")
SSL_KEY_PATH = os.getenv("SSL_KEY_PATH", "certs/key.pem")
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

def generate_certs_if_needed():
    """Generate SSL certificates if they don't exist"""
    if not certs_available():
        print("[INFO] SSL certificates not found. Generating new certificates...")
        try:
            import subprocess
            import sys
            
            # First try the OpenSSL-based generator
            script_path = os.path.join("certs", "generate_certs.py")
            if os.path.exists(script_path):
                result = subprocess.run([sys.executable, script_path], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print("[OK] SSL certificates generated successfully!")
                    return True
                else:
                    print(f"[WARNING] OpenSSL-based generation failed: {result.stderr}")
            
            # Fallback to Python-based generator (no OpenSSL required)
            python_script_path = os.path.join("certs", "generate_certs_python.py")
            if os.path.exists(python_script_path):
                print("[INFO] Trying Python-based certificate generation...")
                result = subprocess.run([sys.executable, python_script_path], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    print("[OK] SSL certificates generated successfully with Python method!")
                    return True
                else:
                    print(f"[ERROR] Python-based generation failed: {result.stderr}")
            
            print("[ERROR] No certificate generation method succeeded!")
            return False
        except Exception as e:
            print(f"[ERROR] Exception during certificate generation: {e}")
            return False
    return True

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
    """Handle Ctrl+C gracefully with immediate shutdown"""
    print(f"\n🚨 IMMEDIATE SHUTDOWN REQUESTED (signal {signum})")
    print("⚠️ Killing all server processes immediately...")
    
    # Kill servers on both ports immediately
    kill_servers_on_port(HTTP_PORT)
    kill_servers_on_port(HTTPS_PORT)
    
    # Also kill any uvicorn processes
    try:
        if psutil:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'uvicorn' in proc.info['name'].lower() or \
                       any('uvicorn' in str(cmd).lower() for cmd in proc.info['cmdline'] or []):
                        print(f"🔥 Killing uvicorn process {proc.info['pid']}")
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
    except Exception as e:
        print(f"Error killing uvicorn processes: {e}")
    
    print("✅ SHUTDOWN COMPLETE - All servers terminated!")
    os._exit(0)  # Force immediate exit

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
        print("[INFO] HTTPS mode requested but certificates not found.")
        if generate_certs_if_needed():
            print("[OK] Certificates generated. Starting HTTPS server...")
        else:
            print("[WARNING] Failed to generate certificates. Falling back to HTTP.")
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
        
        # Enhanced shutdown handling
        server_process = None
        try:
            import uvicorn
            
            # Configure uvicorn for immediate shutdown
            config = uvicorn.Config(
                "app.main:app",
                host="0.0.0.0",
                port=port,
                reload=True,
                ssl_keyfile=SSL_KEY_PATH if use_https else None,
                ssl_certfile=SSL_CERT_PATH if use_https else None,
                log_level="warning",  # Suppress INFO logs
                access_log=False,     # Disable access logs for better performance
                timeout_keep_alive=1, # Faster connection cleanup
                timeout_graceful_shutdown=1  # Quick graceful shutdown
            )
            
            server = uvicorn.Server(config)
            
            # Run server with immediate shutdown capability
            print("🚀 Server starting with enhanced shutdown handling...")
            server.run()
            
        except KeyboardInterrupt:
            print("\n🚨 KEYBOARD INTERRUPT - IMMEDIATE SHUTDOWN!")
            kill_servers_on_port(port)
            print("✅ Server force-stopped immediately.")
        except Exception as e:
            print(f"\n[!] Server error: {e}")
            print("🔥 Force-killing server processes...")
            kill_servers_on_port(port)
        finally:
            # Ensure complete cleanup
            try:
                kill_servers_on_port(port)
                print("✅ Final cleanup completed.")
            except:
                pass
