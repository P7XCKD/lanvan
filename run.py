import os
import socket
import uvicorn
from app.main import app

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return ip

if __name__ == "__main__":
    ip = get_ip()
    print(f"\n[✔] Server running at:")
    print(f"🔗 Localhost:  http://127.0.0.1:5000")
    print(f"🌐 LAN IP:    http://{ip}:5000\n")

    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=False)
