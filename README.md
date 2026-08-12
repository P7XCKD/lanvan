<p align="center">
  <img src="app/static/images/icon.png" alt="Lanvan Logo" width="120" height="120">
</p>

<h1 align="center">Lanvan</h1>

<p align="center">
  Self-hosted LAN file transfer server. Share files between any devices on your Wi-Fi — no internet, no cloud, no apps required on receiving devices.
</p>

<p align="center">
  <a href="https://hub.docker.com/r/devprobs/lanvan"><img alt="Docker Hub" src="https://img.shields.io/docker/pulls/devprobs/lanvan?label=Docker%20Hub&logo=docker"></a>
  <a href="LICENSE"><img alt="License: GPL-3.0" src="https://img.shields.io/badge/License-GPL--3.0-blue.svg"></a>
</p>

> **Demo video:** [Watch on YouTube](https://www.youtube.com/watch?v=1M0Skoy42U4)

---

## What is Lanvan?

You run Lanvan on one computer. Every other device on the same network can then open a browser and instantly upload or download files — no app, no account, no internet connection required.

Works over **Wi-Fi**, **Ethernet**, and **mobile hotspot** — any local network where devices can reach each other.

**Typical use case:** You want to move a photo from your Android phone to your Windows laptop, or drop a file from your PC onto your tablet, without emailing it to yourself or using a cloud service.

Lanvan stores files on the computer running it. Nothing is sent outside your local network.

---

## Features

| Feature | Notes |
|---|---|
| Browser-based | Receiving devices need no app — any modern browser works |
| Folder upload | Entire folder trees uploaded with subdirectories preserved |
| Clipboard sync | Share copied text between devices in real time over WebSocket |
| QR code connect | Scan the displayed QR code on mobile to open instantly |
| mDNS discovery | Access via `http://lanvan.local` on supported networks |
| Chunked upload | Large files split and reassembled for reliable transfer |
| Version history | Previous versions of uploaded files retained |
| HTTPS optional | Self-signed certificate auto-generated when enabled |
| Cross-platform server | Runs on Windows, Linux, macOS, Android (Termux) |
| Network support | Wi-Fi, Ethernet, and mobile hotspot (any local network) |
| Docker image | Pre-built image available on Docker Hub |

**No authentication is included by default.** Anyone on the same local network can access Lanvan while it is running. See [Security](#security--privacy).

---

## Quick Start

Lanvan has two ways to run. Choose the one that fits you:

| Method | Best for | Requires |
|---|---|---|
| **Docker** (recommended) | Most users — no Python setup needed | Docker Desktop (Windows/macOS) or Docker Engine (Linux) |
| **Python** (`python run.py`) | Developers, Android/Termux, no Docker | Python 3.9+ |

Jump to the right section:
- [Run with Docker →](#docker-installation)
- [Run with Python →](#python-installation)

---

## Docker Installation

> Files stored in `./data` survive container restarts and updates. Nothing is stored inside the Docker image itself.

### Prerequisites

- **Windows / macOS:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free)
- **Linux:** `sudo apt install docker.io docker-compose-plugin`

---

### Windows (Recommended Launcher)

Open **PowerShell** in any folder where you want to store your files. Run:

```powershell
# 1. Download the launcher script
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/P7XCKD/lanvan/main/start-lanvan.ps1" -OutFile "start-lanvan.ps1"

# 2. Start Lanvan
.\start-lanvan.ps1
```

The script automatically:
- Detects your PC's Wi-Fi / Ethernet IP address
- Creates a `data\` folder for your files
- Starts the Docker container

You will see:
```
  LAN IP   : 192.168.x.x
  LAN URL  : http://192.168.x.x
  Local    : http://localhost
  Data     : ./data
  QR       : Ready
```

Open `http://localhost` in your browser. Open `http://192.168.x.x` on your phone (same Wi-Fi).

**If the script is blocked by PowerShell execution policy**, run this first:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

### Linux / macOS (Recommended Launcher)

Open a terminal in any folder where you want to store your files. Run:

```bash
# 1. Download the launcher script
curl -O https://raw.githubusercontent.com/P7XCKD/lanvan/main/start-lanvan.sh

# 2. Make it executable
chmod +x start-lanvan.sh

# 3. Start Lanvan
./start-lanvan.sh
```

You will see:
```
  LAN IP   : 192.168.x.x
  LAN URL  : http://192.168.x.x
  Local    : http://localhost
  Data     : ./data
  QR       : Ready
```

Open `http://localhost` in your browser. Open `http://192.168.x.x` on your phone (same Wi-Fi).

---

### Manual `docker run` (All Platforms)

If you prefer to run the container without the launcher scripts, you need to pass your host PC's LAN IP manually using `-e LANVAN_HOST`.

> [!TIP]
> The easiest and most reliable way is `.\start-lanvan.ps1` — it already handles all of this automatically. Use the manual commands below only if you specifically need `docker run` instead of Compose.

**Find your LAN IP first:**

| Platform | Command |
|---|---|
| Windows (PowerShell) | See Step 1 below |
| Linux | `hostname -I \| awk '{print $1}'` |
| macOS | `ipconfig getifaddr en0` |

Then run:

**Windows (PowerShell)** — auto-detects IP:
```powershell
# Detect your Wi-Fi / Ethernet IP (skips virtual and loopback addresses)
$IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notlike "127.*" -and
    $_.IPAddress -notlike "172.*" -and
    $_.IPAddress -notlike "169.254.*"
} | Select-Object -ExpandProperty IPAddress -First 1)

Write-Host "Using LAN IP: $IP"

# Run the container
docker run -d --name lanvan-app -p 80:80 -e "LANVAN_HOST=$IP" -v "${PWD}/data:/app/data" devprobs/lanvan:latest
```

> [!NOTE]
> If `$IP` still shows a wrong address, set it manually: `$IP = "192.168.1.x"` (replace with your actual Wi-Fi IP from Settings → Wi-Fi → Properties).

**Linux / macOS** — auto-detects IP:
```bash
docker run -d \
  --name lanvan-app \
  -p 80:80 \
  -e LANVAN_HOST=$(hostname -I | awk '{print $1}') \
  -v ./data:/app/data \
  devprobs/lanvan:latest
```

**Windows (Command Prompt)** — replace `<YOUR_LAN_IP>` with your actual IP:
```cmd
docker run -d --name lanvan-app -p 80:80 -e LANVAN_HOST=<YOUR_LAN_IP> -v "%cd%\data:/app/data" devprobs/lanvan:latest
```

---

### Docker Desktop GUI

If you prefer the Docker Desktop visual interface:

1. Open Docker Desktop, go to the **Search** bar, type `devprobs/lanvan`, and click **Pull**.
2. Click **Run** on the pulled image.
3. Expand **Optional settings**:
   - **Host port:** `80`
   - **Volume — Host path:** Choose or create a local folder (e.g. `C:\lanvan\data`)
   - **Volume — Container path:** `/app/data`
   - **Environment variable:** Key `LANVAN_HOST`, Value = your LAN IP (e.g. `192.168.1.x`)
4. Click **Run**.
5. Open `http://localhost` in your browser.

---

## Connecting Your Phone

1. Start Lanvan on your PC (using any method above).
2. Make sure your phone is on the **same Wi-Fi network** as your PC.
3. On your phone browser, go to `http://192.168.x.x` (the IP shown in the Lanvan window).
4. Or scan the **QR code** shown in the Lanvan connect panel.

> The IP shown is your PC's current address on the local network. It may change if your router reassigns it (DHCP). If the URL stops working after a restart, re-run the launcher to get the updated IP.

**Phone cannot connect? Check these in order:**

| Problem | Fix |
|---|---|
| Phone is on mobile data | Switch phone to Wi-Fi |
| Phone is on a different Wi-Fi band or guest network | Connect phone to the same network as the PC |
| Windows Firewall is blocking | Run `fix_guest_connectivity.bat` as Administrator |
| VPN is active on either device | Disable VPN |
| QR code shows `localhost` | `LANVAN_HOST` was not set — re-run with the launcher script |
| Devices on router with client isolation | Disable client/AP isolation in router settings |

---

## Where Are My Files?

All uploaded files are stored in the `data` folder in the directory where you ran the launcher script or `docker run` command.

```
./data/
  uploads/        ← uploaded files
  temp_chunks/    ← temporary chunks during large file uploads (auto-cleaned)
  clipboards/     ← clipboard sync history
```

**This folder is mounted into the container as a volume.** This means:

- Stopping the container does NOT delete your files.
- Deleting and recreating the container does NOT delete your files.
- The Docker image itself does **not** store your files.

> [!IMPORTANT]
> If you delete the `data` folder on your host, your files are gone. Docker does not protect it.

**Backup:** Copy the `data` folder to a safe location.

**Restore:** Stop Lanvan, replace the `data` folder with your backup, restart Lanvan.

---

## Updating Lanvan

```bash
# 1. Pull the latest image
docker pull devprobs/lanvan:latest

# 2. Stop and remove the current container (your data is safe in ./data)
docker rm -f lanvan-app

# 3. Start fresh with the latest image using your launcher script
.\start-lanvan.ps1        # Windows
./start-lanvan.sh         # Linux / macOS
```

Or with Docker Compose:
```bash
docker compose pull
docker compose up -d
```

Your `data` folder is untouched during updates.

---

## Stopping and Restarting

**Stop:**
```bash
docker stop lanvan-app
```

**Start again (existing container):**
```bash
docker start lanvan-app
```

**Remove the container entirely** (data folder untouched):
```bash
docker rm -f lanvan-app
```

---

## Docker Reference

### Docker Hub Image

```
devprobs/lanvan:latest    — current recommended release
devprobs/lanvan:v1.0.0   — pinned release
```

Pull the image:
```bash
docker pull devprobs/lanvan:latest
```

### Ports

| Host port | Container port | Protocol |
|---|---|---|
| 80 | 80 | HTTP (default) |
| 443 | 443 | HTTPS (optional) |

> The left side (`80`) is the port opened on your computer. The right side (`80`) is the port inside the container. If port 80 is already in use on your machine, change the left side: `-p 8080:80` — then open `http://localhost:8080`.

### Environment Variables

| Variable | Purpose | Example |
|---|---|---|
| `LANVAN_HOST` | Host LAN IP to advertise for mobile/QR access | `192.168.1.34` |
| `BLOCK_DANGEROUS` | Block `.exe`, `.bat`, `.dll`, `.sys` uploads | `true` |

### Common Commands

```bash
# View running containers
docker ps

# View Lanvan logs in real time
docker logs -f lanvan-app

# Stop the container
docker stop lanvan-app

# Start the container again
docker start lanvan-app

# Remove the container (data folder untouched)
docker rm -f lanvan-app

# View container health status
docker inspect --format='{{.State.Health.Status}}' lanvan-app
```

### Docker Compose

The repository includes a `compose.yaml` file. If you have the source repository cloned:

**Windows (PowerShell)** — recommended method (auto-detects IP):
```powershell
.\start-lanvan.ps1
```

**Windows (PowerShell)** — manual IP override:
```powershell
$env:LANVAN_HOST = "192.168.1.x"
docker compose up -d
```

**Linux / macOS** — recommended method (auto-detects IP):
```bash
./start-lanvan.sh
```

**Linux / macOS** — manual IP override:
```bash
LANVAN_HOST=192.168.1.x docker compose up -d
```

**Common Compose commands (all platforms):**
```bash
# View logs in real time
docker compose logs -f

# Stop
docker compose down

# Optional HTTPS profile (port 443)
docker compose --profile https up -d lanvan-https
```

---

## Security & Privacy

**What Lanvan does:**
- Runs entirely on your local network — no data leaves your machine
- No accounts, no registration, no internet connection required
- Files are stored only in your `data` folder on the host

**What Lanvan does NOT do:**
- No authentication — anyone on the same network can upload or download files while Lanvan is running
- HTTPS is optional and uses a self-signed certificate (browsers will show a security warning)
- No rate limiting or per-user access controls

> [!WARNING]
> Do not expose Lanvan's port to the internet (e.g. via port forwarding in your router) without additional security measures such as a reverse proxy with authentication. Lanvan is designed for trusted local networks only.

**HTTPS mode** (optional, auto-generates self-signed certificate):
```bash
docker run -d --name lanvan-app -p 443:443 \
  -e LANVAN_HOST=<YOUR_LAN_IP> \
  -v ./data:/app/data \
  devprobs/lanvan:latest --https
```

**Block dangerous file extensions** (`.exe`, `.bat`, `.dll`, `.sys`, etc.):
```bash
docker run -d --name lanvan-app -p 80:80 \
  -e LANVAN_HOST=<YOUR_LAN_IP> \
  -e BLOCK_DANGEROUS=true \
  -v ./data:/app/data \
  devprobs/lanvan:latest
```

> HTTPS mode enables `BLOCK_DANGEROUS` automatically.

---

## Uploading & Downloading Files

**Uploading:**
- Drag and drop files or folders onto the browser window
- Right-click to create folders or upload via file picker
- Large files are chunked and reassembled automatically — no size limit beyond available disk space
- Folder uploads preserve the full directory structure
- Uploads can be paused or cancelled from the upload tray

**Downloading:**
- Click any file to preview or download
- Folders are downloaded as ZIP archives
- Multiple files can be selected and downloaded together

---

## Speed & Performance

| Method | Typical speed |
|---|---|
| Docker (HTTP) | Good — slight overhead from container networking |
| Python direct (`python run.py`) | Better — no container overhead |
| Android App / Termux | Best — native or near-native |

To maximize transfer speed with Docker:
1. Use HTTP (default), not HTTPS — avoids encryption CPU overhead
2. Connect the host PC via Ethernet instead of Wi-Fi
3. Ensure your phone connects to 5 GHz Wi-Fi rather than 2.4 GHz
4. On Linux/macOS: install `uvloop` for the Python path (`pip install uvloop`)

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Lanvan won't start | Run `docker ps` — check if another container or service uses port 80 |
| Port 80 already in use | Change host port: `-p 8080:80`, then open `http://localhost:8080` |
| Phone cannot connect | Check LAN URL, Wi-Fi, firewall — see [Connecting Your Phone](#connecting-your-phone) |
| QR code shows `localhost` | `LANVAN_HOST` not set — use launcher script or pass `-e LANVAN_HOST=<IP>` |
| Files seem missing | Check the `./data/uploads` folder on your host machine |
| Large upload fails | Check `docker logs lanvan-app` for disk space or timeout errors |
| Container keeps restarting | Run `docker logs lanvan-app` to see the error |
| `lanvan.local` doesn't work | Use the direct IP address instead — mDNS may be blocked by Docker bridge networking |
| Windows Firewall blocking | Run `fix_guest_connectivity.bat` as Administrator |
| Upload fails with 500 error | Check available disk space on the host |
| Server won't respond | Run `docker inspect --format='{{.State.Health.Status}}' lanvan-app` |

**View logs:**
```bash
docker logs -f lanvan-app
```

**Check container status:**
```bash
docker ps -a
```

---

## Python Installation

Use this method if you do not want to use Docker, are on Android/Termux, or are a developer contributing to Lanvan.

### Requirements

| | Minimum | Recommended |
|---|---|---|
| Python | 3.9 | 3.11+ |
| Free disk space | 50 MB | 1 GB+ |
| Network | Local Wi-Fi or LAN | Wi-Fi 5 / Ethernet |

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/P7XCKD/lanvan.git
cd lanvan

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.\.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

### Running

```bash
# Production mode (default — uses minified assets)
python run.py

# With HTTPS
python run.py --https

# Development mode (unminified source assets from app/)
python run.py --dev
```

> On Windows you can also use `py run.py`.

The terminal displays the server URL and a QR code. Open the LAN URL on your phone.

**Stopping the server:**

| Method | Action |
|---|---|
| Keyboard | Press `Ctrl+C` in the terminal |
| Console | Type `close`, `quit`, `stop`, or `exit` and press Enter |

### Android (Termux)

Setup scripts for Android Termux are available in [`docs/termux/`](docs/termux/).

---

## Development

For contributors and developers.

### Running tests

```bash
# Fast regression suite (173 tests)
python qt.py --fast

# Full test suite
python qt.py

# Architectural defect scan
python testing/tools/arch_scan.py
```

### Building production assets manually

```bash
python build.py
```

This generates minified JS/CSS into `dist/`. The `run.py` launcher auto-builds when needed.

### Project structure

```
lanvan/
  ├── android/              # Native Android App (Chaquopy)
  ├── app/                  # FastAPI application source
  │   ├── core/             # Cryptography, validation, streaming, locks
  │   ├── routers/          # API route controllers
  │   ├── ws_manager/       # WebSocket managers (clipboard, file events)
  │   ├── utils/            # Platform detection, mDNS, network resolver
  │   ├── static/           # Unminified CSS/JS source (dev reference)
  │   └── templates/        # Jinja2 HTML templates
  ├── certs/                # SSL certificate config and generators
  ├── data/                 # Runtime uploads and user data (gitignored)
  ├── dist/                 # Minified production output (gitignored)
  ├── docs/                 # Platform setup guides and Termux scripts
  ├── testing/              # Test suites and regression scripts
  ├── build.py              # Production asset build pipeline
  ├── compose.yaml          # Docker Compose configuration
  ├── docker-entrypoint.sh  # Container boot entrypoint
  ├── Dockerfile            # Container build definition
  ├── fix_guest_connectivity.bat  # Windows firewall helper
  ├── qt.py                 # Automated test runner
  ├── run.py                # Server launcher (dev & prod)
  ├── start-lanvan.ps1      # Windows Docker launcher
  └── start-lanvan.sh       # Linux/macOS Docker launcher
```

### Publishing a new Docker image

```bash
python build.py
docker build -t devprobs/lanvan:latest -t devprobs/lanvan:vX.Y.Z .
docker push devprobs/lanvan:latest
docker push devprobs/lanvan:vX.Y.Z
```

GitHub Actions (`/.github/workflows/docker-publish.yml`) handles automated publishing on tagged releases.

### Debug logging

Lanvan suppresses verbose client-side console output in production. To enable full debug logging in the browser:

```javascript
// Open browser DevTools console (F12) and run:
enableDebug();

// To disable:
disableDebug();
```

Debug mode is saved to `localStorage` and persists across page reloads.

---

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

In summary: you are free to use, modify, and distribute this software, but any distributed version must also be open source under the same license.
