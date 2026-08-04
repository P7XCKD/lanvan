import sys
import os
import uvicorn
import asyncio
from datetime import datetime

# Inject paths so python can resolve local imports properly inside Android environment
sys.path.append(os.path.dirname(__file__))

class LogWriter:
    def __init__(self, filepath, terminal):
        self.file = open(filepath, 'a', encoding='utf-8')
        self.terminal = terminal
        
    def write(self, message):
        self.terminal.write(message)
        self.file.write(message)
        self.file.flush()
        
    def flush(self):
        self.terminal.flush()
        self.file.flush()

    def isatty(self):
        return False

def run_fastapi_server(port="5000", use_https="false", files_dir=None, is_debug=True):
    """
    Launches uvicorn server in Android JVM thread.
    - is_debug=True: Development mode (python run.py / run.py https) using app/static
    - is_debug=False: Production mode (python run.py prod) using dist/static
    """
    if is_debug:
        os.environ['LANVAN_ENV'] = 'development'
        os.environ['PRODUCTION'] = 'false'
    else:
        os.environ['LANVAN_ENV'] = 'production'
        os.environ['PRODUCTION'] = 'true'

    if files_dir:
        log_path = os.path.join(files_dir, "lanvan_app.log")
        
        # Redirect stdout and stderr to the single persistent log file
        writer = LogWriter(log_path, sys.stderr)
        sys.stdout = LogWriter(log_path, sys.stdout)
        sys.stderr = writer
        
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
    
    # Create and set a fresh asyncio event loop for this server thread in Chaquopy
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception as e:
        print(f"[WARN] Failed to reset asyncio event loop: {e}")

    # Re-import and reload app module so fresh FastAPI app and lifespan are created
    try:
        import importlib
        import app.main
        importlib.reload(app.main)
        app_instance = app.main.app
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    
    os.environ['PORT'] = str(port)
    os.environ['USE_HTTPS'] = str(use_https).lower()
    
    # Configure SSL arguments dynamically if HTTPS protocol is selected
    uvicorn_kwargs = {
        "app": app_instance,
        "host": "0.0.0.0",
        "port": int(port),
        "log_level": "info",
        "timeout_keep_alive": 5,
        "timeout_graceful_shutdown": 3
    }
    
    if str(use_https).lower() == "true":
        ssl_key = os.path.join(files_dir, "certs", "key.pem") if files_dir else "certs/key.pem"
        ssl_cert = os.path.join(files_dir, "certs", "cert.pem") if files_dir else "certs/cert.pem"
        if os.path.exists(ssl_key) and os.path.exists(ssl_cert):
            uvicorn_kwargs["ssl_keyfile"] = ssl_key
            uvicorn_kwargs["ssl_certfile"] = ssl_cert
            print(f"[LOCK] SSL certificates configured successfully on Android")
        else:
            print(f"[WARN] HTTPS requested but SSL certificates not found at {ssl_key} / {ssl_cert}")
            
    try:
        config = uvicorn.Config(**uvicorn_kwargs)
        _active_server = uvicorn.Server(config)
        # Configure and launch Uvicorn on all local network interfaces
        _active_server.run()
    except SystemExit as e:
        print(f"[!] Server thread received SystemExit")
        raise e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    finally:
        _active_server = None

_active_server = None

def get_active_server():
    global _active_server
    return _active_server

def force_stop_uvicorn_server():
    global _active_server
    if _active_server is not None:
        print("[HOT] Force-stopping Uvicorn server from Python code...")
        _active_server.should_exit = True

def get_qr_matrix(data: str):
    """Generates and returns a 2D boolean matrix representing the QR Code."""
    import qrcode
    # Set ERROR_CORRECT_H to match backend error correction configuration
    qr = qrcode.QRCode(version=1, error_correction=qrcode.ERROR_CORRECT_H, box_size=1, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()
