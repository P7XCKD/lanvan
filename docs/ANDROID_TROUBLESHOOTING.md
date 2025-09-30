# Android/Termux Troubleshooting Guide

## Common Issues and Solutions

### 1. QR Code Generation Issues

**Problem**: QR codes not generating or displaying
**Solutions**:
- Install Pillow: `pip install pillow`
- If that fails, try: `pkg install libjpeg-turbo-dev && pip install pillow`
- Text-based QR codes are automatically provided as fallback
- Use direct IP address instead of mDNS (.local) domains

### 2. WebSocket Warnings

**Problem**: "websockets library not available" warnings
**Solutions**:
- Install WebSocket support: `pip install websockets uvicorn[standard]`
- Build dependencies: `pkg install clang make cmake`
- Alternative: Use basic HTTP mode (WebSocket features will be disabled)

### 3. Network IP Detection Issues

**Problem**: Server shows wrong IP (like 192.0.0.4) or can't detect network
**Solutions**:
- The app now automatically detects Android environment
- Multiple IP detection methods are tried in sequence
- WiFi IP is prioritized over cellular when available
- Manual IP override available in config

### 4. Storage Access Issues

**Problem**: Can't access external storage or save files
**Solutions**:
```bash
termux-setup-storage
# Grant storage permissions when prompted
```

### 5. Server Keeps Stopping

**Problem**: Server shuts down when Termux app goes to background
**Solutions**:
```bash
# Prevent device sleep
termux-wake-lock

# Keep Termux in foreground or use notification
# Enable "Run in background" for Termux in Android settings
```

### 6. mDNS/Bonjour Not Working

**Problem**: .local domains don't resolve on Android
**Solutions**:
- This is normal on Android - mDNS support is limited
- Use direct IP addresses instead
- QR codes automatically use IP addresses
- Consider using port forwarding apps if needed

### 7. Large File Upload Issues

**Problem**: Large files fail to upload or cause crashes
**Solutions**:
- Ensure sufficient storage space
- Use WiFi instead of cellular data
- Close other apps to free memory
- Break large uploads into smaller chunks (automatic)

### 8. Permission Denied Errors

**Problem**: Can't write to certain directories
**Solutions**:
```bash
# Use Termux home directory
cd $HOME

# Or set up shared storage
termux-setup-storage
cd $HOME/storage/shared
```

### 9. SSL/HTTPS Issues

**Problem**: Certificate errors or HTTPS not working
**Solutions**:
- Use HTTP mode for local network (still secure via LAN)
- Self-signed certificates may not work on Android
- Consider using reverse proxy if HTTPS is required

### 10. Build/Compilation Errors

**Problem**: Python packages fail to install with compilation errors
**Solutions**:
```bash
# Install build tools
pkg install clang python-dev cmake make

# Install headers for common libraries
pkg install libjpeg-turbo-dev zlib-dev libffi-dev

# Use pre-compiled wheels when available
pip install --only-binary=all package_name
```

## Android-Specific Optimizations

### Performance Tips
- Close unnecessary apps before running server
- Use WiFi for better network performance
- Keep device plugged in during long operations
- Monitor temperature to avoid overheating

### Battery Management
```bash
# Prevent sleep during server operation
termux-wake-lock

# Release wake lock when done
termux-wake-unlock
```

### Network Configuration
- Use WiFi hotspot mode for direct device connections
- Configure router for port forwarding if needed
- Check firewall settings on router/network

### Storage Management
```bash
# Check available space
df -h

# Clean up temporary files
rm -rf /tmp/*
rm -rf ~/lanvan/app/uploads/temp_chunks/*
```

## Quick Setup Commands

### Complete Setup
```bash
# Run the setup script
chmod +x setup-android.sh
./setup-android.sh
```

### Manual Setup
```bash
# Update packages
pkg update && pkg upgrade -y

# Install Python and pip
pkg install python python-pip

# Install build dependencies
pkg install clang make cmake libjpeg-turbo-dev

# Install LANVAN dependencies
pip install -r requirements-android.txt

# Set up storage
termux-setup-storage
```

### Run Server
```bash
cd ~/lanvan
python run.py
```

## Testing Your Setup

### 1. Check Python Installation
```bash
python --version
pip --version
```

### 2. Test Network Detection
```bash
python -c "import socket; print(socket.gethostbyname(socket.gethostname()))"
```

### 3. Test QR Code Generation
```bash
python -c "import qrcode; print('QR code support: OK')"
```

### 4. Test WebSocket Support
```bash
python -c "import websockets; print('WebSocket support: OK')" 2>/dev/null || echo "WebSocket support: Not available"
```

## Getting Help

If you're still experiencing issues:

1. Check the main README.md for general troubleshooting
2. Look at the server logs for specific error messages
3. Try running with debug mode: `python run.py --debug`
4. Use the Android requirements file: `pip install -r requirements-android.txt`

## Known Limitations on Android

- mDNS (.local domains) may not work reliably
- Some WebRTC features are not available
- Clipboard synchronization may be limited
- Background execution depends on Android version and settings
- USB debugging features are not available
- Some networking features may require root access