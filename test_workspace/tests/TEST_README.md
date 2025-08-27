# 🧪 LANVAN Test Suite

Automated testing for LANVAN server functionality. These tests verify all server components work correctly before you start using the system.

## Test Files

### 1. `test_server_complete.py` - Complete Test Suite
**Full comprehensive testing of all server functionality.**

**Tests:**
- ✅ Server startup (HTTP/HTTPS modes)
- ✅ File upload/download functionality
- ✅ AES encryption/decryption
- ✅ mDNS service discovery
- ✅ QR code generation with image validation
- ✅ Clipboard functionality
- ✅ Web app UI components
- ✅ API endpoints
- ✅ Network connectivity

**Usage:**
```bash
# Run all tests
python test_server_complete.py

# Verbose output
python test_server_complete.py --verbose

# Skip mDNS tests (for Android/Termux)
python test_server_complete.py --skip-mdns
```

**Output Example:**
```
🧪 LANVAN Server Test Suite Starting...

✅ PASS Server Startup (HTTP): Server started successfully in 2.3s
✅ PASS Basic Connectivity: HTTP 200 - Main page loaded
✅ PASS API Endpoints: All 3 API endpoints responding
✅ PASS File Upload/Download: Upload/download successful (1536 bytes)
✅ PASS AES Encryption: AES encryption/decryption working correctly
✅ PASS QR Code Generation: QR code generation working (150x150 image)
⚠️ WARN mDNS Service Discovery: mDNS registered but lanvan.local not resolvable
✅ PASS Clipboard Functionality: Clipboard functionality working
✅ PASS Web App Components: All UI components and JS features present
✅ PASS Server Startup (HTTPS): Server started successfully in 1.8s

📊 TEST SUMMARY
==================================================
Total Tests: 9
Passed: 8
Failed: 1
Success Rate: 88.9%
Total Duration: 15.2s

🎉 MOSTLY SUCCESSFUL - Minor mDNS issue (expected on some networks)
```

### 2. `quick_test.py` - Quick Smoke Test
**Fast essential functionality check for daily use.**

**Tests:**
- ✅ Server startup
- ✅ Basic HTTP endpoints
- ✅ File upload functionality
- ✅ mDNS status (optional)

**Usage:**
```bash
# Quick test
python quick_test.py

# Android/Termux mode (skip mDNS)
python quick_test.py --android
```

**Output Example:**
```
ℹ️ Starting LANVAN quick test...
ℹ️ Starting server...
✅ Server started successfully
✅ Main page: OK
✅ Network info API: OK
✅ File list API: OK
✅ QR code API: OK
ℹ️ Testing file upload...
✅ File upload: OK
✅ mDNS service: Active
✅ 🎉 Quick test completed successfully!

🚀 Server is ready! You can continue with your work.
```

## Installation

Install test dependencies:
```bash
pip install -r test-requirements.txt
```

## When to Use Each Test

### Use `quick_test.py` when:
- ✅ Daily development work
- ✅ Quick functionality check
- ✅ Before sharing server with others
- ✅ After small code changes
- ✅ Android/Termux environments

### Use `test_server_complete.py` when:
- ✅ Major code changes
- ✅ Before releases/deployments
- ✅ Debugging complex issues
- ✅ Verifying all features work
- ✅ Testing new environments

## Platform-Specific Notes

### Windows/macOS/Linux (Desktop)
```bash
python test_server_complete.py --verbose
```

### Android/Termux
```bash
python quick_test.py --android
# OR
python test_server_complete.py --skip-mdns
```

## Troubleshooting

### Common Issues:

**Server startup fails:**
- Check if port 80/443 is already in use
- Run as administrator for privileged ports
- Try different ports with environment variables

**mDNS tests fail:**
- Normal on Android/Termux - use `--skip-mdns`
- Check firewall/router settings
- Install Bonjour on Windows if needed

**File upload fails:**
- Check uploads directory permissions
- Verify sufficient disk space
- Check file size limits

**AES encryption fails:**
- Verify cryptography library is installed
- Check Python version compatibility

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Test File Structure

```
test_files/          # Temporary test files (auto-created)
├── test_upload_file.txt
└── [other temporary files]
```

The test suite automatically creates and cleans up test files.

## Integration with CI/CD

You can integrate these tests into automated workflows:

```bash
# In your CI/CD pipeline
python test_server_complete.py --skip-mdns
if [ $? -eq 0 ]; then
    echo "✅ All tests passed - deployment ready"
else
    echo "❌ Tests failed - deployment blocked"
    exit 1
fi
```
