# 📱 Lanvan Termux Setup Guide

A lightweight, high-performance guide to running **Lanvan File Transfer Server** on Android using Termux. 

---

## 🚀 One-Line Installation (Recommended)

### Option A: Fresh Installation (Clones the code)
```bash
pkg update -y && pkg upgrade -y && pkg install -y git python rust clang cmake make python-pip python-psutil python-cryptography && export ANDROID_API_LEVEL=24 && git clone https://github.com/P7XCKD/lanvan.git ~/lanvan && cd ~/lanvan/docs/termux && bash setup-android.sh && cd ~/lanvan && python run.py
```

### Option B: Existing Installation (If code is already present in `~/lanvan`)
```bash
cd ~/lanvan && pkg install -y rust python-psutil python-cryptography && export ANDROID_API_LEVEL=24 && python run.py
```

---

## 🏃 Launching the Server

Once installed, you can start the server anytime with:

```bash
cd ~/lanvan
python run.py
```

### Quick Launch Scripts (Recommended)
The `setup-android.sh` script automatically copies and configures two launch scripts in your home directory (`~/`). These scripts automatically resolve port conflicts, copy the server LAN URL to your clipboard, and open Chrome on your device:

* **Start HTTP Server (Default):**
  ```bash
  ~/start_server.sh
  ```

* **Start HTTPS Server:**
  ```bash
  ~/start_server1.sh
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
  If the server fails to bind to port 5000, another process is using it. (Note: Using the **Quick Launch Scripts** above completely avoids this, as they terminate any lingering server instances automatically). 
  Otherwise, run:
  ```bash
  pkill -f python
  ```
