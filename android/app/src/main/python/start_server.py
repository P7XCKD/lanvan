import sys
import os
import re
import uvicorn
import asyncio
from datetime import datetime
from app.core.logger import logger

# Inject paths so python can resolve local imports properly inside Android environment
sys.path.append(os.path.dirname(__file__))

def sanitize_log_message(message: str) -> str:
    """
    Sanitizes log messages at write-time to prevent sensitive file names,
    file paths, and raw user clipboard content from appearing in app logs.
    """
    if not message:
        return message

    sanitized = message

    # 1. Sanitize raw clipboard content & payloads
    sanitized = re.sub(r'(?i)(clipboard[\s_\-:=]+)[^\r\n]+', r'\1[Clipboard Data]', sanitized)
    sanitized = re.sub(r'(?i)(clipboard_data["\']?\s*:\s*["\']?)[^"\'\r\n]+', r'\1[Clipboard Data]', sanitized)
    sanitized = re.sub(r'(?i)("clipboard"\s*:\s*"?[^",\}\r\n]+)', r'"clipboard": "[Clipboard Data]"', sanitized)

    # 2. Sanitize file names & explicit file paths
    sanitized = re.sub(r'(?i)((?:filename|path|full_path|file|target_dir)[\s=:]+)([^\s;,\r\n]+)', r'\1[Sanitized File]', sanitized)
    sanitized = re.sub(r'(?i)(data/(?:uploads|clipboard|temp_chunks)/)([^\s;,\r\n]+)', r'\1[Sanitized File]', sanitized)
    sanitized = re.sub(r'(?i)([a-zA-Z]:\\(?:[^\\[\r\n]+\\)+)([^\s;,\r\n]+)', r'\1[Sanitized Path]', sanitized)
    sanitized = re.sub(r'(?i)(/(?:sdcard|storage|data/data)/[^\s;,\r\n]+)', r'[Sanitized Android Path]', sanitized)

    return sanitized

class LogWriter:
    def __init__(self, filepath, terminal):
        self.file = open(filepath, 'a', encoding='utf-8')
        self.terminal = terminal
        
    def write(self, message):
        sanitized_msg = sanitize_log_message(message)
        if self.terminal:
            self.terminal.write(sanitized_msg)
        self.file.write(sanitized_msg)
        self.file.flush()
        
    def flush(self):
        if self.terminal:
            self.terminal.flush()
        self.file.flush()

    def isatty(self):
        return False

def run_fastapi_server(port="5000", use_https="false", files_dir=None, is_debug=False, block_dangerous=None, lan_ip=None):
    """
    Launches uvicorn server in Android JVM thread.
    - is_debug=False by default: APK runs in Production mode automatically.
    """
    if is_debug:
        os.environ['LANVAN_ENV'] = 'development'
        os.environ['PRODUCTION'] = 'false'
    else:
        os.environ['LANVAN_ENV'] = 'production'
        os.environ['PRODUCTION'] = 'true'

    if block_dangerous is not None:
        os.environ['BLOCK_DANGEROUS'] = 'true' if str(block_dangerous).lower() == 'true' else 'false'
    elif 'BLOCK_DANGEROUS' not in os.environ:
        os.environ['BLOCK_DANGEROUS'] = 'true' if str(use_https).lower() == 'true' else 'false'

    if files_dir:
        log_path = os.path.join(files_dir, "lanvan_app.log")
        
        # Redirect stdout and stderr to the single persistent log file if not already wrapped
        if not isinstance(sys.stdout, LogWriter):
            orig_stdout = getattr(sys, '__stdout__', sys.stdout) or sys.stdout
            orig_stderr = getattr(sys, '__stderr__', sys.stderr) or sys.stderr
            sys.stdout = LogWriter(log_path, orig_stdout)
            sys.stderr = LogWriter(log_path, orig_stderr)
        
        # Change working directory so relative resource directories (like app/static) resolve
        os.chdir(files_dir)
        sys.path.insert(0, files_dir)
        
        # Print a clear separator for this execution session
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode_label = "Development (python run.py / run.py https)" if is_debug else "Production (python run.py prod)"
        print(f"\n==========================================")
        print(f" SERVER STARTUP AT {timestamp}")
        print(f" Mode: {mode_label}")
        print(f" Working Directory: {os.getcwd()}")
        print(f"==========================================\n")

        
        # Clean up stale .tmp files and orphaned chunks from cancelled uploads
        try:
            cleanup_count = 0
            cleanup_bytes = 0
            for cleanup_dir in ["data/uploads", "data/temp_chunks"]:
                cleanup_path = os.path.join(files_dir, cleanup_dir)
                if os.path.isdir(cleanup_path):
                    for f in os.listdir(cleanup_path):
                        fp = os.path.join(cleanup_path, f)
                        if os.path.isfile(fp) and (f.endswith('.tmp') or '.part' in f):
                            size = os.path.getsize(fp)
                            os.remove(fp)
                            cleanup_count += 1
                            cleanup_bytes += size
            if cleanup_count > 0:
                print(f"[CLEAN] Removed {cleanup_count} stale temp files ({cleanup_bytes / (1024*1024):.1f} MB)")
        except Exception as e:
            print(f"[WARN] Temp cleanup error: {e}")
        
    global _active_server
    
    # Import app module for Uvicorn runner
    try:
        import app.main
        app_instance = app.main.app
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    
    os.environ['PORT'] = str(port)
    os.environ['USE_HTTPS'] = str(use_https).lower()

    from app.core.network_state import ServerNetworkState

    # Probe the target port before touching any global state.
    # If port is already occupied (by our own running instance or another process),
    # skip startup entirely — do NOT modify ServerNetworkState, which would corrupt
    # the running server's status and trigger false "Server is Offline" overlays.
    import socket as _socket
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as _probe:
        _probe.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        if _probe.connect_ex(('127.0.0.1', int(port))) == 0:
            logger.info("SYSTEM", "Port already in use — server already running, skipping restart",
                        details={"Port": port})
            return

    current_status = ServerNetworkState.get_status()
    if current_status == "RUNNING" and _active_server is not None:
        logger.info("SYSTEM", "Server is already running, skipping duplicate initialization", details={"Status": current_status})
        return

    ServerNetworkState.increment_generation()
    if lan_ip and str(lan_ip).strip() and str(lan_ip).strip() != "127.0.0.1":
        ServerNetworkState.set_pinned_lan_ip(str(lan_ip).strip())
    
    uvicorn_kwargs = {
        "app": app_instance,
        "host": "0.0.0.0",
        "port": int(port),
        "log_level": "info",
        "timeout_keep_alive": 1,
        "timeout_graceful_shutdown": 1
    }
    
    if str(use_https).lower() == "true":
        ssl_key = os.path.join(files_dir, "certs", "key.pem") if files_dir else "certs/key.pem"
        ssl_cert = os.path.join(files_dir, "certs", "cert.pem") if files_dir else "certs/cert.pem"
        if os.path.exists(ssl_key) and os.path.exists(ssl_cert):
            uvicorn_kwargs["ssl_keyfile"] = ssl_key
            uvicorn_kwargs["ssl_certfile"] = ssl_cert
            logger.info("LOCK", "SSL certificates configured on Android")
        else:
            logger.warn("LOCK", "HTTPS requested but SSL certificates missing")
            
    # Track whether this invocation successfully owned the server lifecycle
    _owned_lifecycle = False
    try:
        config = uvicorn.Config(**uvicorn_kwargs)
        _active_server = uvicorn.Server(config)
        # Mark RUNNING only after we have created the server object and are
        # about to block inside run(). This is the point of no return.
        ServerNetworkState.set_status("RUNNING")
        _owned_lifecycle = True
        _active_server.run()
    except SystemExit as e:
        logger.info("SYSTEM", "Server thread received SystemExit")
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    finally:
        # Only update global state when we actually owned the lifecycle.
        # If binding failed before run() was called, _owned_lifecycle is False
        # and we must not overwrite state that belongs to a running instance.
        if _owned_lifecycle:
            ServerNetworkState.set_status("STOPPED")
        _active_server = None

_active_server = None

def get_active_server():
    global _active_server
    return _active_server

def force_stop_uvicorn_server():
    global _active_server
    from app.core.network_state import ServerNetworkState
    ServerNetworkState.set_status("STOPPING")
    if _active_server is not None:
        logger.info("SYSTEM", "Force-stopping Uvicorn server")
        _active_server.should_exit = True

def get_qr_matrix(data: str):
    """Generates and returns a 2D boolean matrix representing the QR Code."""
    import qrcode
    # Set ERROR_CORRECT_H to match backend error correction configuration
    qr = qrcode.QRCode(version=1, error_correction=qrcode.ERROR_CORRECT_H, box_size=1, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()
