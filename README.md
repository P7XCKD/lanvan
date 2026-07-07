<p align="center">
  <img src="app/static/images/icon.png" alt="Lanvan Logo" width="120" height="120">
</p>

# Lanvan — LAN File Transfer Server

> Demo video: [Watch on YouTube](https://www.youtube.com/watch?v=1M0Skoy42U4)

A fast, private file-sharing server that runs on your local network. No internet, no cloud, no accounts. Upload, download, and share files between any devices on the same Wi-Fi in seconds.

---

## Features

- **Fast LAN transfer** — direct device-to-device, no internet needed
- **Folder upload** — upload entire folder trees, subdirectories preserved
- **Mobile friendly** — works in any browser on phones, tablets, and PCs
- **Clipboard sync** — share copied text between devices in real time
- **QR codes** — scan to connect instantly on mobile
- **mDNS discovery** — access via `http://lanvan.local` on supported devices
- **Cross-platform** — Windows, Linux, macOS, Android (Termux)
- **No size limits** — only limited by your storage space

---

## Requirements for PC

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.9 | 3.11+ |
| Free disk space | 50 MB | 1 GB+ |
| Network | Local Wi-Fi or LAN | Wi-Fi 5 / Ethernet |

---

## Installation

### Windows, macOS, Linux

**1. Clone the repository**

```bash
git clone https://github.com/P7XCKD/lanvan.git
cd lanvan
```

**2. Create a virtual environment** (strongly recommended)

```bash
python -m venv .venv
```

**3. Activate the virtual environment**

```bash
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.\.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

**5. Run the server**

```bash
python run.py
```

> On Windows you can also use `py run.py` — the launcher will auto-activate the venv if it exists.

The terminal will display the server address and a QR code:

```
[OK] Server running at:
Local:  http://127.0.0.1
LAN:    http://192.168.1.x

[INFO] Type 'close' | quit | shut | stop  to stop. Or press Ctrl+C.
```

Open the LAN address in any browser on the same network to start transferring files.

---

### Android (Termux)

**1. Install Termux** from [F-Droid](https://f-droid.org/packages/com.termux/) (recommended) or Google Play.

**2. Open Termux and run the setup script**

```bash
pkg update && pkg install git python
git clone https://github.com/yourusername/lanvan.git ~/lanvan
cd ~/lanvan/termux
bash setup-android.sh
```

**3. Start the server**

```bash
cd ~/lanvan
python run.py
```

> Tip: Run `termux-wake-lock` before starting to prevent Android from killing the server.

On Android, use the direct IP address (`http://192.168.x.x`) — mDNS `.local` domains usually do not work on Android.

---

## Stopping the Server

| Method | Action |
|---|---|
| Keyboard shortcut | Press `Ctrl+C` in the terminal |
| Console command | Type `close`, `quit`, `shut`, `stop`, or `exit` and press Enter |

---

## Connecting from Other Devices

1. Make sure all devices are on the **same Wi-Fi network**.
2. Open a browser on the other device and go to:
   - `http://Lanvan.local` (Windows/macOS/iOS — via mDNS)
   - `http://192.168.x.x` (direct IP, works everywhere)
   - Scan the **QR code** shown in the terminal
3. Start uploading or downloading files.

**If other devices cannot connect (Windows host)**

Run the included connectivity fixer as Administrator:

```bash
fix_guest_connectivity.bat
```

---

## HTTPS / SSL (optional)

```bash
# Start with HTTPS
python run.py https

# iOS compatibility mode (HTTP, optimised for Safari)
python run.py ios
```

Certificates are auto-generated on first HTTPS run and stored in `certs/`.

> iOS Safari requires either HTTP mode or a trusted certificate. Use `python run.py ios` for the best iOS experience.

---

## ⚡ Speed & Performance Optimization

To achieve the absolute maximum file transfer rates over your local network:

1. **Use HTTP Mode (Default):** Run the server without `https` (`python run.py`). This avoids cryptographic CPU overhead on older/low-power devices, boosting speeds by 20% to 50%.
2. **Install `uvloop` (Linux, macOS, and Termux):**
   ```bash
   pip install uvloop
   ```
   This replaces Python's default event loop with a C-based loop built for speed, accelerating FastAPI throughput by 2-4x.
3. **Use a Wired Host Connection:** Connect the host machine via **Ethernet** instead of Wi-Fi. This eliminates wireless packet collisions and frees up bandwidth for receiving clients.
4. **Use 5 GHz Wi-Fi:** Ensure client devices are connected to the 5 GHz Wi-Fi band of your router rather than 2.4 GHz.

---

## Project Structure

```
lanvan/
  ├── app/                  # Main FastAPI Application Core
  │   ├── core/             # Cryptography, validation, streaming merge, and atomic locks
  │   ├── routers/          # API route controllers (files, pages, clipboard, etc.)
  │   ├── ws_manager/       # WebSocket states for real-time clipboard & updates
  │   ├── utils/            # Platform checks, memory limits, and Zeroconf mDNS
  │   ├── static/           # CSS styles, images, and client JS modules
  │   └── templates/        # Jinja2 layout components (base.html, index.html)
  ├── certs/                # SSL certificate config and generation scripts
  ├── data/                 # Operational user files & db stores (uploads, clipboards)
  ├── docs/                 # Platform setups and requirements manifests
  ├── termux/               # Automated setup assets for Android Termux
  ├── testing/              # Test workspace and unit diagnostic suites
  ├── run.py                # Platform-aware server launcher entry point
  └── qt.py                 # Core component reliability test runner
```

For detailed architecture descriptions, refer to the documentation in each folder:

* **[app/](./app/README.md)**: Main FastAPI application core, routes, assets, and Jinja2 views.
  * **[app/static/js/](./app/static/js/README.md)**: Client-side progressive JavaScript architecture.
  * **[app/templates/](./app/templates/README.md)**: Modular HTML views and skeleton inheritance files.
* **[certs/](./certs/README.md)**: SSL certificate creation configurations and local key generator scripts.
* **[docs/](./docs/README.md)**: Platform configuration checklists, troubleshooting, and setup scripts.
* **[testing/](./testing/test_workspace/TEST_README.md)**: Sandboxed test workspace assets and isolated diagnostic tools.
* **[termux/](./docs/TERMUX_SETUP.md)**: Setup assets and scripts for Android environments.
* **[run.py](run.py)**: Entry launcher that detects platform targets, sets up venv, and boots uvicorn.
* **[qt.py](qt.py)**: Standard automated component testing suite.


---

## Troubleshooting

| Problem | Fix |
|---|---|
| Other devices cannot connect | Run `fix_guest_connectivity.bat` as Administrator (Windows) |
| `Lanvan.local` does not resolve | Use the direct IP address instead |
| Upload fails with 500 error | Check available disk space; see server console for details |
| Server won't stop on Ctrl+C | Type `close` in the terminal and press Enter |
| Clipboard sync not working on Android | Android restricts background clipboard access — use manual copy/paste |

---

## Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `jinja2` | HTML templates |
| `python-multipart` | File upload handling |
| `cryptography` | AES encryption |
| `psutil` | System monitoring |
| `qrcode` | QR code generation |
| `zeroconf` | mDNS service discovery |
| `aiofiles` | Async file I/O |
| `pyperclip` | Clipboard operations (desktop) |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
