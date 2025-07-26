# 🚀 LANVan File Transfer Strategy Implementation

## 📦 Overview
LANVan now implements a comprehensive file transfer strategy that optimizes performance, security, and reliability based on file size, protocol, and file type.

## 🔐 Transfer Matrix

| File Type | Size | HTTP Support | HTTPS Support | Strategy |
|-----------|------|--------------|---------------|----------|
| **Regular files** | < 250MB | ✅ Full upload/download | ✅ Full upload/download | Standard transfer |
| **Regular files** | ≥ 250MB | ✅ **Chunked** upload/download | ✅ **Chunked** upload/download | Optimized for large files |
| **.enc files** | Any size | ❌ Not recommended | ✅ **Full** upload/download only | Preserves encryption integrity |

## 🛠️ Implementation Details

### 1. **Chunked Download (≥250MB)**
- **HTTP & HTTPS**: Streams large files in 1MB chunks using `StreamingResponse`
- **Excludes .enc files**: Always uses full download to preserve decryption integrity
- **Memory efficient**: Prevents server memory overload for large files

### 2. **Chunked Upload (≥250MB)**
- **HTTP & HTTPS**: Uploads large files in 5MB chunks
- **Client-side**: JavaScript handles chunking and progress tracking
- **Server-side**: Assembles chunks into final file with integrity checks
- **Excludes .enc files on HTTPS**: Prevents corruption of encrypted data

### 3. **Protocol-Aware Features**
- **HTTP**: Chunked uploads/downloads available, AES encryption disabled
- **HTTPS**: All features available, AES encryption enabled, .enc file restrictions enforced

### 4. **AES Encryption Rules**
- **HTTPS Only**: AES encryption requires secure connection
- **Size Limit**: Maximum 200MB for AES-encrypted files
- **No Chunking**: .enc files always use full transfer to maintain integrity

## 📋 Enforcement Rules

### File Size Detection
```javascript
const CHUNK_THRESHOLD = 250 * 1024 * 1024; // 250MB
const hasLargeFiles = files.some(file => file.size >= CHUNK_THRESHOLD);
```

### Protocol Detection
```javascript
const isHTTPS = location.protocol === 'https:';
```

### .enc File Handling
```python
is_enc_file = filename.endswith(".enc")
if is_enc_file and is_https:
    # Force full upload/download (no chunking)
```

## 🔧 Backend Implementation

### Smart Download Routing
```python
@router.get("/download/{filename}")
async def download_file(filename: str, request: Request):
    is_https = request.url.scheme == "https"
    is_enc_file = filename.endswith(".enc")
    is_large_file = file_size >= 250 * 1024 * 1024
    
    if is_large_file and not is_enc_file:
        return await chunked_download_file(...)
    else:
        return await full_download_file(...)
```

### Protocol-Aware Upload Validation
```python
# Enforce HTTPS for AES encryption
if encrypt and not is_https:
    return JSONResponse(status_code=400, content={
        "msg": "AES encryption requires HTTPS connection"
    })

# Block chunked upload for .enc files on HTTPS
if is_https and filename.endswith(".enc"):
    return JSONResponse(status_code=400, content={
        "msg": "Chunked upload disabled for .enc files"
    })
```

## 🎯 Frontend Implementation

### Smart Upload Logic
```javascript
function autoUpload(files) {
    const isHTTPS = location.protocol === 'https:';
    const hasLargeFiles = files.some(file => file.size >= CHUNK_THRESHOLD);
    const hasEncFiles = files.some(file => file.name.endsWith('.enc'));
    
    if (hasEncFiles && isHTTPS) {
        // .enc files on HTTPS - always full upload
        uploadFilesRegular(files, isAESEnabled);
    } else if (hasLargeFiles && !hasEncFiles) {
        // Large files (≥250MB) - use chunked upload
        uploadFilesChunked(files, isAESEnabled);
    } else {
        // Small files - regular upload
        uploadFilesRegular(files, isAESEnabled);
    }
}
```

### Protocol Status Indicator
- **HTTP**: 🌐 HTTP (yellow) - "Chunked uploads available, AES requires HTTPS"
- **HTTPS**: 🔒 HTTPS (green) - "Secure connection - All features available"

## 📊 User Experience Features

### Smart Notifications
- **Protocol Detection**: Automatic detection and appropriate messaging
- **Transfer Type**: Clear indication of chunked vs full transfer
- **Progress Tracking**: Real-time progress with speed calculation
- **Error Handling**: Specific error messages for different scenarios

### Transfer Statistics
- **Protocol Used**: HTTP/HTTPS indication
- **Transfer Method**: Chunked vs Full
- **Performance Metrics**: Speed, duration, file size
- **AES Status**: Encryption enabled/disabled

## 🔒 Security Considerations

### HTTPS Enforcement
- AES encryption only available over HTTPS
- .enc file restrictions apply only to HTTPS (maintains integrity)
- Protocol status clearly visible to users

### Data Integrity
- .enc files never chunked on HTTPS (prevents corruption)
- Chunk assembly includes integrity verification
- Background file scanning after upload completion

## 🚀 Performance Optimizations

### Memory Management
- Streaming downloads for large files (1MB chunks)
- Chunked uploads prevent memory overflow (5MB chunks)
- Automatic cleanup of temporary chunk files

### Network Efficiency
- Optimal chunk sizes for different operations
- Progress tracking with minimal UI updates (anti-blink)
- Concurrent chunk processing where possible

## 📈 Monitoring & Debugging

### Transfer Logs
- Local storage of transfer statistics
- Detailed logs including protocol, method, and performance
- Click-to-expand toast notifications with full details

### Debug Headers
- `X-Download-Type: chunked` header for chunked downloads
- Protocol information in API responses
- Detailed error messages for troubleshooting

## 🎉 Benefits

1. **Performance**: Large files transfer efficiently via chunking
2. **Reliability**: Smart fallbacks and error handling
3. **Security**: HTTPS enforcement for sensitive operations
4. **Transparency**: Clear indication of transfer methods and protocols
5. **Flexibility**: Automatic optimization based on file characteristics

This implementation provides a robust, secure, and user-friendly file transfer system that adapts to different scenarios while maintaining optimal performance and data integrity.
