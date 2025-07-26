# 🔧 LANVan HTTPS Setup Guide

## 🚨 SSL Protocol Error Fix

The `ERR_SSL_PROTOCOL_ERROR` occurs because:

1. **Wrong Port**: You might be accessing `https://localhost:443` instead of `https://localhost:5000`
2. **Certificate Trust**: Browser doesn't trust the self-signed certificate

## ✅ Correct HTTPS URLs:

- **Local HTTPS**: `https://127.0.0.1:5000`
- **LAN HTTPS**: `https://192.168.0.101:5000` (or your actual LAN IP)

## 🔒 Certificate Trust Issues

### For Chrome/Edge:
1. Visit `https://127.0.0.1:5000`
2. Click "Advanced" 
3. Click "Proceed to 127.0.0.1 (unsafe)"
4. Browser will remember this choice

### For Firefox:
1. Visit `https://127.0.0.1:5000`
2. Click "Advanced"
3. Click "Accept the Risk and Continue"

### Alternative: Add Certificate to Trust Store
```powershell
# Import certificate to Windows Certificate Store (Run as Administrator)
Import-Certificate -FilePath "certs/cert.pem" -CertStoreLocation Cert:\LocalMachine\Root
```

## 📊 Processing Time Fix

✅ **FIXED**: The toast notification now shows accurate timing:

- **Server Response**: Time for server to prepare file (actual processing)
- **Download Time**: Time to transfer file from server to browser
- **Total Time**: Complete operation time

### Before:
- ❌ "Processing: 2.5s" (actually total download time)

### After:  
- ✅ "Server: 0.1s • Download: 2.4s" (accurate breakdown)

## 🧪 Testing Steps

1. **Start HTTP Server**:
   ```powershell
   cd "c:\Probz\Project"
   python run.py
   ```
   Access: `http://127.0.0.1:5000`

2. **Start HTTPS Server**:
   ```powershell
   cd "c:\Probz\Project"
   python run.py https
   ```
   Access: `https://127.0.0.1:5000` (accept certificate warning)

3. **Test Features**:
   - Upload small file (<250MB) → Regular transfer
   - Upload large file (≥250MB) → Chunked transfer  
   - Try AES encryption (HTTPS only)
   - Download files and check timing in toast

## 🌐 Protocol Indicators

- **HTTP**: 🌐 HTTP (yellow badge) - Chunked transfers, no AES
- **HTTPS**: 🔒 HTTPS (green badge) - All features, AES available

The timing issue has been fixed and HTTPS should work correctly when accessing the right port!
