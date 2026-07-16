import sys
import os
import uvicorn
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

def run_fastapi_server(port="5000", use_https="false", files_dir=None):
    """
    Launches uvicorn server in Android JVM thread.
    """
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
        print(f"\n==========================================")
        print(f" SERVER STARTUP AT {timestamp}")
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
        
    # Import app after changing directory so initialization takes place in correct context
    try:
        from app.main import app
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    
    os.environ['PORT'] = str(port)
    os.environ['USE_HTTPS'] = str(use_https).lower()
    
    try:
        # Configure and launch Uvicorn on all local network interfaces
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=int(port),
            log_level="info",
            timeout_keep_alive=5,
            timeout_graceful_shutdown=3
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

def get_qr_matrix(data: str):
    """Generates and returns a 2D boolean matrix representing the QR Code."""
    import qrcode
    # Set ERROR_CORRECT_H to match backend error correction configuration
    qr = qrcode.QRCode(version=1, error_correction=qrcode.ERROR_CORRECT_H, box_size=1, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()
