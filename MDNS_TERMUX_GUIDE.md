# mDNS Termux Troubleshooting Guide

## Issues Fixed

### 1. **"Works once, then fails" Problem**
**Root Cause**: Incomplete resource cleanup causing port binding conflicts and zeroconf resource leaks.

**Solutions Implemented**:
- Enhanced resource cleanup in `stop_service()`
- Force garbage collection before restart
- Clear IP cache to detect network changes
- Proper zeroconf socket cleanup

### 2. **Termux-Specific Network Issues**
**Root Cause**: Android network interfaces behave differently than desktop systems.

**Solutions Implemented**:
- Added Android hotspot IP detection (`192.168.43.1`)
- Multiple router address scanning for IP detection
- Optimized timeouts for mobile networks
- Enhanced network interface validation

### 3. **Offline Functionality**
**Root Cause**: mDNS should work completely offline on local network.

**Solutions Implemented**:
- Removed external internet dependency checks
- Local router IP scanning for offline networks
- Psutil interface scanning as fallback
- Works without internet connection

## Termux Setup Instructions

### Prerequisites
```bash
# Update packages
pkg update && pkg upgrade

# Install Python and required packages
pkg install python
pip install fastapi uvicorn zeroconf

# Optional but recommended: Install Avahi for better mDNS support
pkg install avahi

# If avahi fails, try alternative:
pkg install dbus
```

### Network Configuration
```bash
# Check your network interface
ip addr show

# Check if mDNS ports are free
netstat -ln | grep :5353

# If port 5353 is busy, restart network:
# (Note: This requires root or may not work on all Android versions)
# sudo service network-manager restart
```

### Troubleshooting Commands

#### 1. Test mDNS Dependencies
```python
python -c "
from app.simple_mdns import check_mdns_dependencies
available, status = check_mdns_dependencies()
print(f'Available: {available}')
print(f'Status: {status}')
"
```

#### 2. Test Network Detection
```python
python -c "
from app.simple_mdns import SimpleMDNSManager
manager = SimpleMDNSManager()
ip = manager.get_lan_ip()
print(f'Detected IP: {ip}')
"
```

#### 3. Manual Resource Cleanup
```python
python -c "
from app.simple_mdns import force_cleanup_mdns_resources
force_cleanup_mdns_resources()
print('Cleanup completed')
"
```

#### 4. Full mDNS Test
```python
python -c "
from app.simple_mdns import SimpleMDNSManager
import time

# Create manager
manager = SimpleMDNSManager(port=5000, use_https=False)

# Start service
result = manager.start_service()
print(f'Start result: {result}')

if result:
    # Let it run for 5 seconds
    time.sleep(5)
    
    # Check status
    info = manager.get_mdns_info()
    print(f'Status: {info[\"status\"]}')
    print(f'URL: {info[\"url\"]}')
    
    # Stop service
    manager.stop_service()
    print('Service stopped successfully')
else:
    print('Service failed to start')
"
```

## Common Issues & Solutions

### Issue: "Zeroconf initialization failed"
**Solution**:
1. Restart Termux completely
2. Run: `force_cleanup_mdns_resources()`
3. Check if avahi is installed: `pkg install avahi`
4. Try running as: `python run.py --port 8080` (non-privileged port)

### Issue: "Service works once, then fails on restart"
**Solution**:
1. The new code automatically handles this with enhanced cleanup
2. If still failing, restart Termux session
3. Check for lingering processes: `ps aux | grep python`

### Issue: "IP detection fails"
**Solution**:
1. Check network interface: `ip addr`
2. Make sure you're connected to WiFi (not mobile data only)
3. Try connecting to a different network
4. Test manual IP: `python run.py --port 5000` then check console output

### Issue: "mDNS not working offline"
**Solution**:
1. Ensure both devices are on same WiFi network
2. Check router allows mDNS/Bonjour (most do by default)
3. Test direct IP access first: `http://192.168.x.x:5000`
4. Some corporate/school networks block mDNS

## Performance Tips for Termux

1. **Close other apps**: Android memory management can interfere
2. **Keep Termux in foreground**: Prevents Android from killing the process
3. **Use wake lock**: `termux-wake-lock` to prevent sleep
4. **Stable WiFi**: Avoid switching between networks while running

## Verification Steps

After running the server:

1. **Check console output** for mDNS status:
   ```
   ✅ mDNS service started: lanvan.local:5000 (HTTP)
   Available at: http://lanvan.local:5000
   Direct IP: http://192.168.x.x:5000
   ```

2. **Test from another device**:
   - Try: `http://lanvan.local:5000` (mDNS)
   - Fallback: `http://192.168.x.x:5000` (direct IP)

3. **Verify cleanup on exit**:
   ```
   🔴 Stopping mDNS service...
   ✅ mDNS service unregistered: lanvan.local
   ✅ Zeroconf resources cleaned up
   ```

## Android Network Limitations

- **Mobile Data**: mDNS doesn't work over mobile data (WiFi only)
- **Hotspot Mode**: When phone is hotspot, may use `192.168.43.x` range
- **Corporate WiFi**: Some networks block mDNS broadcasts
- **VPN**: VPN connections may interfere with local mDNS

## Working Offline

The mDNS system is designed to work completely offline:
- ✅ No internet connection required
- ✅ Local WiFi network only
- ✅ Devices on same subnet can discover each other
- ✅ Works with router in "offline" mode

## Final Notes

The enhanced mDNS implementation should now:
1. ✅ Work reliably on repeated starts/stops
2. ✅ Properly detect Android/Termux environment
3. ✅ Handle network interface changes
4. ✅ Work completely offline
5. ✅ Provide clear error messages and solutions

If issues persist, the fallback is always direct IP access, which works universally.
