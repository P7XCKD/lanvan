# 📱 Lanvan Termux Setup Guide

A lightweight, high-performance guide to running **Lanvan File Transfer Server** on Android using Termux. 

---

## 🚀 One-Line Installation (Recommended)

### Option A: Fresh Installation (Clones the code)
```bash
pkg update -y && pkg install -y git python && git clone https://github.com/P7XCKD/lanvan.git ~/lanvan && cd ~/lanvan/docs/termux && bash setup-android.sh && cd ~/lanvan && python run.py
```

### Option B: Existing Installation (If code is already present in `~/lanvan`)
```bash
pkg update -y && pkg install -y python && cd ~/lanvan/docs/termux && bash setup-android.sh && cd ~/lanvan && python run.py
```

---

## 🏃 Launching the Server

Once installed, you can start the server anytime with:

```bash
cd ~/lanvan
python run.py
```

### Quick Launch Scripts
For convenience, you can copy the preconfigured script launchers to your home directory:

* **For HTTP (Default):**
  ```bash
  cp ~/lanvan/docs/termux/start-server.sh ~/start-server.sh
  chmod +x ~/start-server.sh
  ~/start-server.sh
  ```

* **For HTTPS:**
  ```bash
  cp ~/lanvan/docs/termux/start-server-https.sh ~/start-server-https.sh
  chmod +x ~/start-server-https.sh
  ~/start-server-https.sh
  ```

---

## 💡 Android / Termux Optimizations

* **Keep Server Alive:** Android aggressively puts Termux to sleep. Run `termux-wake-lock` inside Termux before starting your server to prevent downloads/uploads from pausing when your screen turns off.
* **Direct IP Access:** Android browsers often do not support `.local` mDNS domains. Scan the **IP Access QR Code** or enter `http://<your-lan-ip>:5000` directly.
* **Large File Uploads:** Uploading huge files (e.g., movies) is fully optimized using stream-to-disk chunking, meaning the server will not crash due to memory (OOM) limitations on Android.
* **Zero Compilation Required:** The setup script avoids compiling heavy C/C++ packages like Pillow. The QR code generator automatically uses SVG rendering to remain lightweight and fully compatible.

---

## 🛠️ Basic Troubleshooting

* **Permission Denied / Storage Issues:**
  If you cannot access your folders, grant storage permission to Termux:
  ```bash
  termux-setup-storage
  ```
* **Address Already in Use:**
  If the server fails to bind to port 5000, find and terminate any existing Python server processes:
  ```bash
  pkill -f python
  ```
