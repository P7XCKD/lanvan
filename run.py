# Lanvan - Secure Local File Transfer
# Copyright (C) 2025 P7XCKD

import os
import socket
import subprocess
import sys
import signal
import time
import json
import shutil
import threading
import datetime


# Lock shared by both tee threads so terminal lines never interleave.
_tee_lock = threading.Lock()


def setup_server_log():
    """
    Clear testing/logs/ and open a fresh server.log for this session.
    Returns the open log file handle (caller must close it).
    Active in development mode only — never called in production.
    """
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testing", "logs")

    # Wipe every file from the previous session, then recreate the directory.
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir, ignore_errors=True)
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, "server.log")
    # UTF-8, line-buffered so every line flushes immediately.
    log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    log_file.write(f"# Lanvan server log — started {datetime.datetime.now().isoformat()}\n")
    log_file.flush()
    print(f"[LOG] Backend output -> testing/logs/server.log")
    return log_file


def _tee_stream(src, dst_terminal, log_file):
    """
    Read raw bytes from *src* (subprocess pipe), forward each line to
    *dst_terminal* and write a UTF-8 decoded copy to *log_file*.

    Writing raw bytes to dst_terminal.buffer avoids Windows cp1252 codec
    errors when the server prints emoji or non-ASCII characters.
    Both threads share _tee_lock so output lines never interleave.
    """
    buf = getattr(dst_terminal, "buffer", None)
    try:
        for raw_line in src:
            decoded = raw_line.decode("utf-8", errors="replace")
            with _tee_lock:
                try:
                    if buf is not None:
                        buf.write(raw_line)
                        buf.flush()
                    else:
                        dst_terminal.write(decoded)
                        dst_terminal.flush()
                except Exception:
                    pass
                try:
                    log_file.write(decoded)
                except Exception:
                    pass
    except Exception:
        pass

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
            # Use Popen so we can keep waiting through Ctrl+C events.
            # DO NOT use signal.SIG_IGN here — on Windows it inherits to
            # child processes and breaks Ctrl+C in the actual server.
            child = subprocess.Popen([venv_python] + sys.argv)
            # When Ctrl+C fires, the child gets it too (same console group)
            # and handles shutdown.  The parent just keeps waiting.
            # NOTE: Must use timeout polling — on Windows, wait() with no
            # timeout calls WaitForSingleObject(INFINITE) which blocks the
            # OS thread and prevents Python from delivering KeyboardInterrupt.
            while child.poll() is None:
                try:
                    child.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
                except KeyboardInterrupt:
                    pass  # child got it too; let it handle shutdown
            sys.exit(child.returncode)
        except Exception as e:
            print(f"[!] Failed to switch to virtual environment: {e}")
            print("[*] Continuing with system Python...")
            return

# Call this first before importing packages that might not be in system python
ensure_venv()

# Check for Android/Termux environment
is_android = os.path.exists("/data/data/com.termux") or "ANDROID_ROOT" in os.environ

if is_android:
    # Ensure Android API level is available for Rust/maturin builds during runtime pip installs
    os.environ.setdefault("ANDROID_API_LEVEL", "24")
    os.environ.setdefault("ANDROID_API", "24")

    # On Android, verify required binary dependencies are pre-installed via pkg
    missing_sys_packages = []
    try:
        import psutil
    except ImportError:
        missing_sys_packages.append("python-psutil")
    try:
        import cryptography
    except ImportError:
        missing_sys_packages.append("python-cryptography")

    if missing_sys_packages:
        print("[!] ERROR: Missing required binary dependencies on Android.")
        print(f"[!] Please install them using the Termux package manager:\n")
        print(f"    pkg install {' '.join(missing_sys_packages)}\n")
        sys.exit(1)

    # Check remaining python packages individually
    pip_dependencies = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "jinja2": "jinja2",
        "multipart": "python-multipart",
        "aiofiles": "aiofiles",
        "qrcode": "qrcode",
        "zeroconf": "zeroconf",
        "websockets": "websockets",
        "wsproto": "wsproto",
        "brotli": "brotli",
        "pyperclip": "pyperclip",
        "uvloop": "uvloop"
    }

    missing_pip_packages = []
    for module_name, pip_name in pip_dependencies.items():
        try:
            __import__(module_name)
        except ImportError:
            missing_pip_packages.append(pip_name)

    if missing_pip_packages:
        print(f"[!] Missing Python package(s): {', '.join(missing_pip_packages)}")
        print("[!] Installing missing Python packages on Android...")
        try:
            # We install plain uvicorn (without [standard]) to avoid compile issues
            subprocess.run([sys.executable, "-m", "pip", "install"] + missing_pip_packages, check=True)
            print("[OK] Dependencies installed successfully!")
        except Exception as install_error:
            print(f"[ERROR] Failed to install packages: {install_error}")
            sys.exit(1)
else:
    # Standard desktop dependency installation flow
    try:
        import psutil
        import uvicorn
        import cryptography
    except ImportError as e:
        print(f"[!] Missing package: {e}")
        print("[!] Installing required packages from requirements.txt...")
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                                  check=True, capture_output=True, text=True)
            print("[OK] Dependencies installed successfully!")
            import psutil
            import uvicorn
        except subprocess.CalledProcessError as install_error:
            print(f"[ERROR] Failed to install from requirements.txt: {install_error}")
            print("[INSTALL] Trying individual package installation...")
            subprocess.run([sys.executable, "-m", "pip", "install", "psutil", "uvicorn[standard]", "fastapi", "jinja2", "python-multipart", "cryptography"])
            import psutil
            import uvicorn

# === CONFIGURATION ===
# SSL Certificate paths (can be overridden by environment variables)
SSL_CERT_PATH = os.getenv("SSL_CERT_PATH", "certs/cert.pem")
SSL_KEY_PATH = os.getenv("SSL_KEY_PATH", "certs/key.pem")

# Default ports - use standard HTTP/HTTPS ports when possible
# On Windows/most systems: requires admin privileges for ports < 1024
# Fallback to non-privileged ports if needed
DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443
FALLBACK_HTTP_PORT = 5000
FALLBACK_HTTPS_PORT = 5001

# Use environment variables to allow port override
HTTP_PORT = int(os.getenv("HTTP_PORT", DEFAULT_HTTP_PORT))
HTTPS_PORT = int(os.getenv("HTTPS_PORT", DEFAULT_HTTPS_PORT))

def _is_docker_container_ip(ip_str):
    """Check if an IP is a Docker internal bridge IP when running inside Docker container"""
    if not os.path.exists('/.dockerenv'):
        return False
    if not ip_str:
        return True
    parts = ip_str.split('.')
    if len(parts) == 4 and parts[0] == '172':
        try:
            second = int(parts[1])
            if 17 <= second <= 31:
                return True
        except ValueError:
            pass
    return False

def get_ip():
    """Get local IP address - works offline and rejects Docker internal bridge IPs"""
    env_host = os.getenv("LANVAN_ADVERTISE_HOST") or os.getenv("ADVERTISE_HOST") or os.getenv("LAN_IP")
    if env_host and env_host.strip():
        return env_host.strip()

    try:
        # Method 1: Try hostname resolution (works offline on most systems)
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if host_ip and not host_ip.startswith('127.') and not _is_docker_container_ip(host_ip):
            return host_ip
    except Exception:
        pass
    
    try:
        # Method 2: Create socket and connect to local router (offline-compatible)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 80))  # Local router IP - doesn't require internet
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.') and not _is_docker_container_ip(ip):
            return ip
    except Exception:
        pass
    
    try:
        # Method 3: Try other common local network ranges
        for network in ["10.0.0.1", "172.16.0.1"]:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((network, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith('127.') and not _is_docker_container_ip(ip):
                return ip
    except Exception:
        pass
    
    # Fallback to localhost if inside Docker bridge without host IP override
    return "127.0.0.1"

def can_bind_privileged_port(port):
    """Check if we can bind to a privileged port (< 1024)"""
    if port >= 1024:
        return True
    
    try:
        # Try to bind to the port briefly
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind(('0.0.0.0', port))
        test_socket.close()
        return True
    except (OSError, PermissionError):
        return False

def get_safe_port(preferred_port, fallback_port):
    """Get a safe port to use, falling back if privileged port can't be bound"""
    if can_bind_privileged_port(preferred_port):
        return preferred_port
    else:
        if preferred_port < 1024:
            print(f"[WARNING] Cannot bind to privileged port {preferred_port} (requires admin/root)")
            print(f"[INFO] Using fallback port {fallback_port}")
        return fallback_port

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

def check_and_run_build_if_needed(force=False, clean=False):
    """
    Automatic production build detection:
    - Uses SHA-256 build manifest tracking (dist/build-manifest.json).
    - Monitored watched frontend directories: app/static/js, app/static/css, app/templates.
    - Supports --force / rebuild flags and clean flag.
    - Automatically executes python build.py if missing or stale.
    - Returns build status string ('Up-to-date' or 'Rebuilt (0.14s)').
    """
    manifest_path = os.path.join("dist", "build-manifest.json")
    
    if clean and os.path.exists("dist"):
        print("[*] Cleaning dist/ directory...")
        shutil.rmtree("dist", ignore_errors=True)
        
    print("Checking production assets...\n")
    
    needs_rebuild = force or clean or not os.path.exists("dist") or not os.path.exists(manifest_path)
    
    if not needs_rebuild:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            stored_hash = manifest.get("frontend_hash", "")
            
            from build import compute_frontend_hash
            current_hash = compute_frontend_hash()
            
            if stored_hash != current_hash:
                needs_rebuild = True
                print("Source changes detected.\n")
        except Exception:
            needs_rebuild = True

    if needs_rebuild:
        print("Rebuilding...")
        start_t = time.time()
        res = subprocess.run([sys.executable, "build.py"])
        if res.returncode != 0:
            print("[!] Production build failed!")
            sys.exit(1)
        dur = time.time() - start_t
        print(f"\n✔ Build complete ({dur:.2f} s)\n")
        return f"Rebuilt ({dur:.2f}s)"
    else:
        print("✔ Production assets are up-to-date.\n")
        return "Up-to-date"

def print_banner(ip, port, use_https, is_production=False, build_status=None):
    protocol_str = "HTTPS" if use_https else "HTTP"
    mode_str = "Production" if is_production else "Development"
    assets_str = "dist/static" if is_production else "app/static"
    
    scheme = "https" if use_https else "http"
    show_port = not ((port == 80 and scheme == "http") or (port == 443 and scheme == "https"))
    url_local = f"{scheme}://127.0.0.1:{port}" if show_port else f"{scheme}://127.0.0.1"
    url_lan = f"{scheme}://{ip}:{port}" if show_port else f"{scheme}://{ip}"

    print("========================================")
    print("Lanvan v1.0")
    print()
    print(f"Mode      : {mode_str}")
    print(f"Protocol  : {protocol_str}")
    print(f"Assets    : {assets_str}")
    if is_production and build_status:
        print(f"Build     : {build_status}")
    print()
    print("URL")
    print(f"Local : {url_local}")
    print(f"LAN   : {url_lan}")
    print("========================================")
    print()

def open_browser(ip, port, use_https):
    scheme = "https" if use_https else "http"
    try:
        import webbrowser
        if (port == 80 and scheme == "http") or (port == 443 and scheme == "https"):
            webbrowser.open(f"{scheme}://{ip}")
        else:
            webbrowser.open(f"{scheme}://{ip}:{port}")
    except:
        print("[!] Failed to open browser.")

def kill_servers_on_port(port):
    """Kill all servers running on the specified port or fallback ports, and release socket hooks."""
    # Defensively clean up all possible ports for both HTTP and HTTPS
    target_ports = {port, 80, 443, 5000, 5001}
    
    # Try psutil process tree cleanup first
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Get connections safely
                try:
                    connections = proc.net_connections()
                except (psutil.AccessDenied, AttributeError):
                    try:
                        connections = proc.connections()
                    except (psutil.AccessDenied, AttributeError):
                        continue
                
                if connections:
                    for conn in connections:
                        if (hasattr(conn, 'laddr') and 
                            hasattr(conn.laddr, 'port') and 
                            conn.laddr.port in target_ports and 
                            hasattr(conn, 'status') and
                            conn.status == psutil.CONN_LISTEN):
                            
                            # Filter: Don't kill our own runner process
                            if proc.info['pid'] == os.getpid():
                                continue
                                
                            print(f"[CLEAN] Killing stale background server process {proc.info['pid']} ({proc.info['name']}) on port {conn.laddr.port}")
                            proc.kill() # Force kill immediately to release socket hook
                            proc.wait(timeout=2)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
                pass
    except Exception as e:
        print(f"[!] Process scan warning: {e}")
        
    # Fallback/Diagnostic: Double check via socket test
    for p in target_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', p))
            s.close()
        except OSError:
            # Port is still blocked, trigger a system terminal release call for Windows
            if platform.system() == 'Windows':
                try:
                    import subprocess
                    # Query process listening on the port
                    cmd = f'Get-NetTCPConnection -LocalPort {p} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess'
                    pid_out = subprocess.check_output(["powershell", "-Command", cmd], text=True).strip()
                    if pid_out:
                        for pid_str in pid_out.split():
                            pid = int(pid_str)
                            if pid > 0 and pid != os.getpid():
                                print(f"[CLEAN] Releasing port {p} by terminating process ID {pid}...")
                                subprocess.run(["powershell", "-Command", f"Stop-Process -Id {pid} -Force"], capture_output=True)
                except Exception:
                    pass


# === MAIN ENTRY ===
if __name__ == "__main__":
    
    ip = get_ip()
    args = sys.argv
    cli_flags = {a.lower() for a in args[1:]}
    
    is_production = any(flag in cli_flags for flag in ["prod", "production", "--prod", "--production"])
    use_https = any(flag in cli_flags for flag in ["https", "--https"])
    ios_mode = any(flag in cli_flags for flag in ["ios", "--ios", "--safari"])
    force_rebuild = any(flag in cli_flags for flag in ["force", "--force", "rebuild"])
    clean_build = "clean" in cli_flags
    block_dangerous_flag = any(flag in cli_flags for flag in ["block-dangerous", "--block-dangerous", "block_dangerous", "--block_dangerous"])

    if block_dangerous_flag:
        os.environ["BLOCK_DANGEROUS"] = "true"
    elif "BLOCK_DANGEROUS" not in os.environ:
        os.environ["BLOCK_DANGEROUS"] = "true" if use_https else "false"

    if is_production:
        os.environ["LANVAN_ENV"] = "production"
        os.environ["PRODUCTION"] = "true"
        build_status = check_and_run_build_if_needed(force=force_rebuild, clean=clean_build)
    else:
        os.environ["LANVAN_ENV"] = "development"
        os.environ["PRODUCTION"] = "false"
        build_status = None

    if use_https and not ios_mode:
        port = get_safe_port(HTTPS_PORT, FALLBACK_HTTPS_PORT)
    else:
        port = get_safe_port(HTTP_PORT, FALLBACK_HTTP_PORT)
        
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
            port = get_safe_port(HTTP_PORT, FALLBACK_HTTP_PORT)

    print_banner(ip, port, use_https, is_production, build_status)
    
    # Display connection information based on actual ports used
    if ios_mode:
        print("[iOS] iOS Safari Mode: HTTP optimized for maximum compatibility")
        print("[iOS] Features enabled:")
        print("   • HTTP-only for better iOS Safari compatibility")
        print("   • Enhanced CORS headers for mobile browsers")
        print("   • iOS Safari-specific caching and viewport handling")
        print("   • Automatic mDNS fallback to direct IP")
        
        if port == 80:
            print(f"[MOBILE] Primary: http://{ip}")
            print(f"[MOBILE] mDNS: http://lanvan.local")
        else:
            print(f"[MOBILE] Primary: http://{ip}:{port}")
            print(f"[MOBILE] mDNS: http://lanvan.local:{port}")
            
        print("[iOS] Troubleshooting tips:")
        print("   1. Ensure iPhone is on the same WiFi network")
        print("   2. If .local doesn't work, use direct IP address")
        print("   3. Clear Safari cache if page won't load")
        print("   4. Try turning WiFi off and on if connection fails")
    elif use_https:
        print("[MOBILE] iOS/Safari Users:")
        if port == 443:
            print(f"   Primary: https://lanvan.local")
            print(f"   Fallback: http://{ip}")
        else:
            print(f"   If Safari can't connect to https://lanvan.local:{port}")
            fallback_http_port = get_safe_port(HTTP_PORT, FALLBACK_HTTP_PORT)
            if fallback_http_port == 80:
                print(f"   Try: http://{ip} (HTTP fallback)")
            else:
                print(f"   Try: http://{ip}:{fallback_http_port} (HTTP fallback)")
            print(f"   Or: https://{ip}:{port} (direct IP)")
        print(f"   Or run: python run.py ios (iOS mode)")

    if is_android_termux():
        print("[*] Android (Termux) detected: launching Uvicorn...")
        
        # Set environment variable for the FastAPI app
        os.environ['PORT'] = str(port)
        os.environ['USE_HTTPS'] = str(use_https).lower()
        
        # [REMOVED] Waitress removed: FastAPI is ASGI and no longer supports WSGI servers like Waitress.
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
            "--log-level", "info"
        ]
        if use_https:
            cmd += ["--ssl-keyfile", SSL_KEY_PATH, "--ssl-certfile", SSL_CERT_PATH]
        subprocess.run(cmd)

    else:
        print("[*] PC detected: launching Uvicorn...")

        os.environ['PORT'] = str(port)
        os.environ['USE_HTTPS'] = str(use_https).lower()

        open_browser(ip, port, use_https)

        # Build the uvicorn command using the SAME python executable that is running run.py.
        # This guarantees we use the venv packages and avoids any PATH ambiguity.
        cmd = [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--log-level", "info",
            "--timeout-keep-alive", "5",
            "--timeout-graceful-shutdown", "3",
        ]
        if use_https:
            cmd += ["--ssl-keyfile", SSL_KEY_PATH, "--ssl-certfile", SSL_CERT_PATH]

        if not is_production:
            # Dev mode only: tee stdout + stderr to testing/logs/server.log.
            # Previous session log is cleared automatically on each startup.
            _log_file = setup_server_log()
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Two daemon threads relay each stream to the terminal AND the log file.
            threading.Thread(
                target=_tee_stream,
                args=(proc.stdout, sys.stdout, _log_file),
                daemon=True,
                name="tee-stdout",
            ).start()
            threading.Thread(
                target=_tee_stream,
                args=(proc.stderr, sys.stderr, _log_file),
                daemon=True,
                name="tee-stderr",
            ).start()
        else:
            # Production mode: no log file, no pipe — output goes straight to terminal.
            _log_file = None
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL)

        def _stdin_monitor():
            """Read stdin for 'close'/'quit' commands and terminate the server."""
            print("[INFO] Type 'close'  |  quit  |  shut  to stop. Or press Ctrl+C.")
            try:
                while proc.poll() is None:
                    try:
                        line = input().strip().lower()
                    except EOFError:
                        break
                    if line in ('close', 'quit', 'exit', 'shutdown', 'shut', 'stop'):
                        print(f"[INFO] '{line}' received - stopping server...")
                        proc.terminate()
                        break
            except (OSError, KeyboardInterrupt):
                pass

        stdin_thread = threading.Thread(target=_stdin_monitor, daemon=True)
        stdin_thread.start()

        print("[INFO] Server starting (Ctrl+C or type 'close' to stop)...")
        try:
            # Must poll with timeout — on Windows, wait() with no timeout
            # calls WaitForSingleObject(INFINITE) which blocks the OS thread
            # and prevents Python from delivering KeyboardInterrupt.
            while proc.poll() is None:
                try:
                    proc.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
        except KeyboardInterrupt:
            print("\n[INFO] Ctrl+C received - stopping server...")
            try:
                proc.terminate() # Actively stop the child uvicorn process
                proc.wait(timeout=8)   # give uvicorn time to finish gracefully
            except subprocess.TimeoutExpired:
                print("[WARN] Server did not stop in time - force killing...")
                proc.kill()



        print("[OK] Server stopped.")
        if _log_file is not None:
            try:
                _log_file.close()
            except Exception:
                pass
        os._exit(0)
