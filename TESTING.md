# 🧪 LanVan Automated Testing

This automated testing system will comprehensively test your LanVan application across all scenarios:

## What It Tests

### Protocols
- ✅ HTTP (port 5000)
- ✅ HTTPS (port 5443)

### File Sizes
- ✅ **Small files** (100KB) - Full upload only
- ✅ **Medium files** (5MB) - Full upload only  
- ✅ **Large files** (300MB) - Chunked upload (non-encrypted)

### Encryption
- ✅ **AES OFF** - Plain file upload/download
- ✅ **AES ON** - Encrypted file upload/download (HTTPS only)

### Device Types
- ✅ **Host device** - Larger chunk sizes, optimal performance
- ✅ **Guest device** - Smaller chunk sizes, bandwidth-limited simulation

## How to Run Tests

### Quick Test
```bash
python run.py test
```

### Manual Test Execution
```bash
python test_lanvan.py
```

## Test Scenarios

The system automatically tests **all combinations**:

1. **HTTP + No AES + Host + Small File** (Full Upload)
2. **HTTP + No AES + Host + Medium File** (Full Upload)
3. **HTTP + No AES + Host + Large File** (Chunked Upload)
4. **HTTP + No AES + Guest + Small File** (Full Upload)
5. **HTTP + No AES + Guest + Medium File** (Full Upload)
6. **HTTP + No AES + Guest + Large File** (Chunked Upload - smaller chunks)
7. **HTTPS + No AES + Host + All Sizes**
8. **HTTPS + No AES + Guest + All Sizes**
9. **HTTPS + AES + Host + All Sizes** (Full Upload only)
10. **HTTPS + AES + Guest + All Sizes** (Full Upload only)

*Note: AES over HTTP is skipped as it's not allowed by the application*

## Test Process

For each scenario, the test:

1. 🚀 **Starts** the appropriate server (HTTP/HTTPS)
2. 📄 **Creates** test files with known content and checksums
3. 📤 **Uploads** file using appropriate method (full/chunked)
4. 📥 **Downloads** the uploaded file
5. ✅ **Verifies** file integrity using SHA256 hash comparison
6. 📊 **Measures** upload/download speeds
7. 🧹 **Cleans** up temporary files

## Test Report

After completion, you get:

- ✅ **Pass/Fail status** for each scenario
- 📊 **Performance metrics** (upload/download speeds)
- 🚨 **Detailed error messages** for failures
- 📄 **JSON report** saved to `test_results.json`

## Expected Results

✅ **Should PASS:**
- All HTTP scenarios without AES
- All HTTPS scenarios (with and without AES)
- Chunked uploads for large files (non-encrypted)
- File integrity verification

❌ **Should FAIL/SKIP:**
- AES encryption over HTTP (security restriction)
- Invalid file types (.exe, .bat)
- Files larger than size limits

## Performance Benchmarks

The test provides speed benchmarks:
- **Upload speeds** for different scenarios
- **Download speeds** for different file sizes
- **Comparison** between chunked vs full uploads
- **Impact** of AES encryption on performance

## Troubleshooting

If tests fail:

1. **Check certificates** - HTTPS tests need valid certs in `certs/`
2. **Port conflicts** - Ensure ports 5000 and 5443 are available
3. **Dependencies** - Test auto-installs: `aiohttp`, `aiofiles`, `psutil`
4. **Disk space** - Large file tests need ~300MB free space

## Benefits

🎯 **Focus on coding** - No manual testing needed
⚡ **Catch regressions** - Automatically detect when changes break functionality  
📊 **Performance tracking** - Monitor speed improvements/degradations
🔒 **Security validation** - Ensure encryption works correctly
🌐 **Cross-protocol testing** - Verify HTTP and HTTPS compatibility
