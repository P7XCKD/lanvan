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

## Running the Server

### Launcher Modes & Command-Line Flags

Lanvan features an intelligent launcher system (`run.py`) supporting development and production modes with order-independent flags:

```bash
# Development Mode (HTTP, unminified source assets from app/static)
python run.py

# Development Mode with HTTPS / SSL
python run.py https

# Production Mode (HTTP, optimized minified assets from dist/static)
python run.py prod

# Production Mode with HTTPS / SSL (flags can be in any order)
python run.py prod https
python run.py https prod

# Force Rebuild Production Assets
python run.py prod force

# Clean Production Build Output
python run.py clean
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

## 🐳 Docker Support & Deployment

Lanvan includes first-class Docker and Docker Compose support. Running via Docker Desktop or Compose boots in **Production Mode** using minified assets, persistent volume storage (`./data:/app/data`), and port `80:80` pre-configured.

### 1. Recommended Launch (Docker Compose — 1 Command)

```bash
# Start Lanvan Production Container (HTTP, Port 80, Persistent Storage)
docker compose up -d
```

> **Note on Docker Desktop GUI:**
> Using Docker Desktop's `Images → Run` button opens a generic dialog that requires manually typing host port `80` into the port field. Standard OCI `EXPOSE 80` metadata documents port usage but does not auto-bind host ports without user input. **`docker compose up -d`** is the recommended one-click / one-command launcher because it pre-configures `80:80` and `./data:/app/data` automatically.

### 2. Common Docker Compose Commands

```bash
# View Container Status & Published Ports
docker compose ps

# View Real-Time Server Logs
docker compose logs -f

# Stop Container
docker compose down

# Optional: Run Production with HTTPS Profile (Port 443)
docker compose --profile https up -d lanvan-https
```

### 3. Alternative CLI Commands (`docker run`)

```bash
# Standard Production Container (HTTP)
docker run -d --name lanvan-app -p 80:80 -v "${PWD}\data:/app/data" lanvan

# Production Container with HTTPS / SSL
docker run -d --name lanvan-app -p 443:443 -v "${PWD}\data:/app/data" lanvan --https

# Production Container with Dangerous File Blocking
docker run -d --name lanvan-app -p 80:80 -v "${PWD}\data:/app/data" lanvan --block-dangerous

# Opt-In Development Container (Unminified Assets)
docker run -it --rm -p 80:80 -v "${PWD}\data:/app/data" lanvan --dev
```

### Docker Security Matrix & Specifications

- **Default Production Runtime**: Docker runs `python run.py prod` automatically unless `--dev` is explicitly passed.
- **Persistent Storage**: `./data:/app/data` ensures uploads, clipboards, and version history survive container recreation.
- **Security Policy**: Use `--block-dangerous` or set `BLOCK_DANGEROUS=true` environment variable to block `.exe`, `.bat`, `.dll`, `.sys`, and executable scripts. HTTPS mode blocks dangerous file extensions by default.
- **Healthcheck**: Container health is monitored automatically via `GET /api/server-status`.

---

## Production Build Pipeline

Lanvan includes a zero-dependency production build pipeline (`build.py`) that minifies frontend assets while leaving the development source tree (`app/`) 100% untouched as the single source of truth.

```bash
# Generate production bundle manually in dist/
python build.py
```

- **Isolated Output**: Generated assets reside strictly inside `dist/`.
- **Automatic Build Detection**: `python run.py prod` automatically checks SHA-256 asset hashes and rebuilds `dist/` only when source files change.
- **Zero Internet / Offline Native**: 100% self-contained local dependencies with strict Content Security Policy.
- **No Source Maps**: Production mode generates zero `.map` files for maximum performance.

---

## Automated Testing & Quality Audit

Lanvan maintains a 100% automated test pass rate for reliability and architecture.

```bash
# Run fast regression test suite (162 tests)
python qt.py --fast

# Run full test suite
python qt.py

# Run architectural defect scanner
python testing/tools/arch_scan.py
```

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
   - Scan the **QR code** shown in the terminal or browser modal
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
```

Certificates are auto-generated on first HTTPS run and stored in `certs/`.

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
  ├── android/              # Native Android App & Chaquopy bridge source
  ├── app/                  # Main FastAPI Application Core (Development Source of Truth)
  │   ├── core/             # Cryptography, validation, streaming merge, and atomic locks
  │   ├── routers/          # API route controllers (files, pages, clipboard, etc.)
  │   ├── ws_manager/       # WebSocket states for real-time clipboard & updates
  │   ├── utils/            # Platform checks, memory limits, and Zeroconf mDNS
  │   ├── static/           # Unminified CSS styles, images, and JS modules
  │   └── templates/        # Jinja2 layout components (base.html, index.html)
  ├── certs/                # SSL certificate config and generation scripts
  ├── data/                 # Operational user files & db stores (uploads, clipboards)
  ├── dist/                 # Generated production output (minified JS/CSS, isolated)
  ├── docs/                 # Platform setups and requirements manifests
  │   └── termux/           # Automated setup assets for Android Termux
  ├── scratch/              # Sandboxed scratch scripts and temporary analysis notes
  ├── testing/              # Standard automated test workspace
  │   ├── regression/       # End-to-end regression test scripts
  │   ├── tools/            # Security matrices, route alias audits, and platform scanners
  │   └── test_workspace/   # Isolated test data directories
  ├── build.py             # Industry-standard production build system
  ├── docker-entrypoint.sh  # Docker production entrypoint runner
  ├── Dockerfile            # Container build definition
  ├── fix_guest_connectivity.bat # Windows host network firewall helper
  ├── qt.py                 # Core component reliability test runner
  └── run.py                # Platform-aware server launcher entry point (dev & prod)
```

For detailed architecture descriptions, refer to the documentation in each folder:

* **[app/](./app/README.md)**: Main FastAPI application core, routes, assets, and Jinja2 views.
  * **[app/static/js/](./app/static/js/README.md)**: Client-side progressive JavaScript architecture.
  * **[app/templates/](./app/templates/README.md)**: Modular HTML views and skeleton inheritance files.
* **[certs/](./certs/README.md)**: SSL certificate creation configurations and local key generator scripts.
* **[docs/](./docs/README.md)**: Platform configuration checklists, troubleshooting, and setup scripts.
  * **[docs/termux/](./docs/termux/)**: Automated setup assets and scripts for Android Termux.
* **[testing/](./testing/test_workspace/TEST_README.md)**: Sandboxed test workspace assets and isolated diagnostic tools.
* **[run.py](run.py)**: Entry launcher that detects platform targets, sets up venv, and boots uvicorn.
* **[qt.py](qt.py)**: Standard automated component testing suite.


---

## 🐞 Debugging & Client Logging

Lanvan runs in **silent production mode** by default, suppressing verbose client-side console logs while preserving warnings, errors, network failures, and browser exceptions.

If you need to enable full client-side debug logging at any time:

### Live Toggle via Browser Console (No Reload Required)

Open the browser Developer Console (`F12` or `Ctrl+Shift+I` / `Cmd+Option+I`) and run:

```javascript
enableDebug();
```
* **Instant:** Debug logs start printing immediately in the console.
* **Persistent:** Saves `localStorage.debug = "true"`, so debug mode stays active across reloads and tab navigation.

To return to silent production mode:
```javascript
disableDebug();
```

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
