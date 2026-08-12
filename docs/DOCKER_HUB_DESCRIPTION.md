# Lanvan — LAN File Transfer Server

Self-hosted file sharing over your local network. No internet, no cloud, no accounts. Run on one PC — every device on the same Wi-Fi, Ethernet, or hotspot can instantly upload and download files from a browser.

**No app required on receiving devices. Any browser works.**

---

## Quick Start

### Recommended (auto-detects your LAN IP)

**Windows (PowerShell):**
```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/P7XCKD/lanvan/main/start-lanvan.ps1" -OutFile "start-lanvan.ps1"
.\start-lanvan.ps1
```

**Linux / macOS:**
```bash
curl -O https://raw.githubusercontent.com/P7XCKD/lanvan/main/start-lanvan.sh
chmod +x start-lanvan.sh
./start-lanvan.sh
```

### Manual

```bash
docker run -d \
  --name lanvan-app \
  -p 80:80 \
  -e LANVAN_HOST=<YOUR_LAN_IP> \
  -v ./data:/app/data \
  devprobs/lanvan:latest
```

Then open `http://localhost` on your PC or `http://<YOUR_LAN_IP>` on your phone.

---

## Why LANVAN_HOST?

Docker containers cannot see your host PC's Wi-Fi IP automatically. Pass `-e LANVAN_HOST=<YOUR_LAN_IP>` so the QR code and connect panel show the correct address for phones on your network. The launcher scripts above handle this automatically.

---

## Persistent Storage

Your files are stored in the `./data` folder on your host machine — **not inside the Docker image**.

```
./data/
  uploads/      ← your uploaded files
  clipboards/   ← clipboard sync history
```

Deleting or recreating the container does **not** delete your files.

---

## Features

- Browser-based — no app needed on receiving devices
- Upload files and entire folder trees
- Real-time clipboard sync between devices
- QR code for instant mobile connection
- Works over Wi-Fi, Ethernet, and mobile hotspot
- HTTPS optional (self-signed certificate auto-generated)
- Block dangerous file extensions with `BLOCK_DANGEROUS=true`

---

## Environment Variables

| Variable | Purpose | Example |
|---|---|---|
| `LANVAN_HOST` | Your host PC's LAN IP for mobile QR access | `192.168.1.34` |
| `BLOCK_DANGEROUS` | Block `.exe`, `.bat`, `.dll` uploads | `true` |

---

## Ports

| Host | Container | Protocol |
|---|---|---|
| 80 | 80 | HTTP (default) |
| 443 | 443 | HTTPS (optional) |

If port 80 is in use, change the left side: `-p 8080:80`

---

## Updating

```bash
docker pull devprobs/lanvan:latest
docker rm -f lanvan-app
# Re-run using your launcher script or docker run command
```

Your `./data` folder is untouched during updates.

---

## Tags

| Tag | Description |
|---|---|
| `latest` | Current stable release |
| `v1.0.0` | Pinned release |

---

## Source & Documentation

GitHub: https://github.com/P7XCKD/lanvan

Demo: https://www.youtube.com/watch?v=1M0Skoy42U4

---

## Security Note

Lanvan has **no authentication** by default. Anyone on the same local network can access it while running. Do not expose port 80 to the internet without a reverse proxy and authentication layer.

---

## License

GNU General Public License v3.0
