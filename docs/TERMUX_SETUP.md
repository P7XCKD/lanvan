# 📱 Lanvan Termux Setup Guide (No Pillow)
*Complete Android Termux installation for Lanvan file server*

## 🎯 Overview
This guide sets up Lanvan on Android Termux **without Pillow dependencies** for optimal performance and compatibility. The system uses browser-native image handling instead of server-side processing.

## 📋 Prerequisites
- Android device with Termux installed
- Stable internet connection
- At least 2GB free storage space

## 🚀 Quick Start (Fast Setup)

### 1. Prepare Termux (Install Git & Python)
Run this to update package lists and install core downloader tools:
```bash
pkg update -y && pkg install -y git python
```

### 2. Clone and Run Automated Setup
Clone the repository and execute the optimized, Pillow-free setup script:
```bash
git clone https://github.com/P7XCKD/lanvan.git ~/lanvan
cd ~/lanvan/docs/termux
bash setup-android.sh
```

### 3. Launch the Server
```bash
cd ~/lanvan
python run.py
```

---

## 🔧 Step-by-Step Manual Setup (Optional)

### 1. **Security & Networking Libraries**
```bash
pkg install -y openssl libffi zlib brotli python-cryptography python-psutil

# Network and process tools
pkg install -y lsof procps curl wget
```

### 3. **Optional Repositories** *(recommended)*
```bash
# Additional package repositories
pkg install -y root-repo x11-repo
```

### 4. **Python Environment Setup**
```bash
# Ensure pip is available and updated
python -m ensurepip --upgrade
pip install --upgrade pip setuptools wheel
```

### 5. **Lanvan Dependencies** *(No Pillow!)*
```bash
# Core Lanvan packages (optimized for Termux - excluding cryptography/psutil as they are installed via pkg)
pip install --no-build-isolation --no-cache-dir \
    fastapi \
    uvicorn \
    python-multipart \
    aiofiles \
    qrcode \
    requests \
    pycryptodome \
    zeroconf \
    python-socketio \
    websockets

# Optional performance packages
pip install --no-build-isolation --no-cache-dir \
    uvloop \
    brotli
```

## 📁 **Lanvan Installation**
```bash
# Clone Lanvan repository
git clone https://github.com/P7XCKD/lanvan.git
cd lanvan

# Install dependencies from requirements.txt (Pillow-free)
pip install -r requirements.txt

# Set executable permissions
chmod +x run.py
```

## 🏃 **Running Lanvan**
```bash
# Start Lanvan server
python run.py

# Or with specific configuration
python run.py --host 0.0.0.0 --port 8000
```

## 🔧 **Termux-Specific Optimizations**

### **Storage Permissions**
```bash
# Allow Termux to access Android storage
termux-setup-storage
```

### **Network Configuration**
```bash
# Check available network interfaces
ip addr show

# Get device IP for LAN access
hostname -I
```

### **Background Execution**
```bash
# Install wake lock to prevent sleep
pkg install -y termux-api
termux-wake-lock

# Run Lanvan in background
nohup python run.py &
```

## ✅ **What's Included (No Pillow)**

### **✅ WORKING FEATURES:**
- 📁 **File Upload/Download** - All file types supported
- 📋 **Clipboard Sync** - Text, files, and images
- 🖼️ **Image Previews** - Browser-native rendering (no server processing)
- 🔒 **AES Encryption** - Secure file transfers
- 🌐 **mDNS Discovery** - Auto-discovery on LAN
- 📱 **Mobile Optimized** - Touch-friendly interface
- 🎥 **Video Support** - MP4, AVI, MKV, and 30+ formats

### **🚫 REMOVED (Pillow Dependencies):**
- ❌ Server-side image processing
- ❌ Image format conversion
- ❌ Thumbnail generation on server
- ❌ Complex image manipulation

### **🎨 IMAGE HANDLING:**
- Uses **base64 encoding** + browser display
- **Faster** than server-side processing
- **Lower memory usage** on Android
- **All formats** supported by browser (PNG, JPEG, GIF, WebP, etc.)

## 🐛 **Troubleshooting**

### **Common Issues:**

**1. Build Failures:**
```bash
# If cryptography fails to build
pkg install -y rust
pip install --upgrade pip setuptools wheel
```

**2. Permission Denied:**
```bash
# Fix storage permissions
termux-setup-storage
chmod -R 755 ~/storage
```

**3. Network Issues:**
```bash
# Check if port is available
lsof -i :8000

# Kill existing processes
pkill -f python
```

**4. Memory Issues:**
```bash
# Check available memory
free -h

# Close unnecessary apps
# Restart Termux if needed
```

## 📊 **Performance Tips**

### **Memory Optimization:**
- Lanvan uses **~50MB RAM** without Pillow (vs ~150MB with Pillow)
- Image previews handled by browser (zero server memory)
- Streaming uploads for large files

### **Storage Management:**
```bash
# Clean pip cache
pip cache purge

# Remove unnecessary packages
pkg autoremove

# Check disk usage
du -sh ~/
```

### **Network Performance:**
- Use **5GHz WiFi** for better performance
- **Wired connection** recommended for large file transfers
- **QR codes** work without PIL for easy device connection

## 🔄 **Updates & Maintenance**

### **Update Lanvan:**
```bash
cd ~/lanvan
git pull origin main
pip install -r requirements.txt --upgrade
```

### **Update Termux:**
```bash
pkg update && pkg upgrade
pip install --upgrade pip
```

## 🎯 **Key Differences from Desktop Version**

| Feature | Desktop | Termux (This Guide) |
|---------|---------|-------------------|
| **Pillow** | ❌ Removed | ❌ Not installed |
| **Image Previews** | ✅ Browser-based | ✅ Browser-based |
| **Memory Usage** | ~50MB | ~40MB |
| **Build Time** | 30 seconds | 2 minutes |
| **Dependencies** | 15 packages | 12 packages |
| **Storage Required** | 200MB | 150MB |

## 📱 **Android-Specific Features**

- **Storage Access:** Full access to Android filesystem
- **Background Running:** Continues when screen off (with wake lock)
- **Network Sharing:** Share files between Android and other devices
- **Mobile Interface:** Touch-optimized design
- **QR Code Access:** Easy device pairing

## ✨ **Success Verification**

After installation, verify everything works:

```bash
# Test Lanvan startup
python run.py

# Should see:
# ✅ Lanvan File Server starting...
# ✅ Clipboard functionality enabled
# ✅ Image previews working (no Pillow)
# ✅ Server running on http://0.0.0.0:8000
```

---

## 🎉 **Conclusion**

This setup provides a **lightweight, efficient Lanvan installation** on Android Termux without the complexity and resource overhead of Pillow. You get all the functionality you need with better performance and easier maintenance.

**Key Benefits:**
- ⚡ **Faster installation** (no image library compilation)
- 💾 **Lower memory usage** (~40MB vs ~150MB)
- 🔄 **Easier updates** (fewer dependencies)
- 🖼️ **Same image preview experience** (browser-powered)
- 📱 **Better Android compatibility** (no native library issues)

**Ready to use for:**
- File sharing across devices
- Clipboard synchronization
- Media streaming (videos, music)
- Document transfer
- Secure file encryption
