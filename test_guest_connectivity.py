import socket
import subprocess
import requests
import time
from pathlib import Path

def test_guest_connectivity():
    """Comprehensive test for guest device connectivity"""
    print("LANVAN Guest Device Connectivity Test")
    print("=" * 60)
    
    # Get network info
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print(f"\nServer Information:")
    print(f"  Hostname: {hostname}")
    print(f"  Local IP: {local_ip}")
    print(f"  mDNS Domain: lanvan.local")
    
    # Test 1: Server availability
    print(f"\n1. Server Availability Test:")
    try:
        response = subprocess.run(['netstat', '-an'], capture_output=True, text=True, shell=True)
        listening_ports = [line for line in response.stdout.split('\n') if ':80 ' in line and 'LISTENING' in line]
        if listening_ports:
            print("[PASS] HTTP server is running on port 80")
        else:
            print("[FAIL] HTTP server not found - start server with 'python run.py'")
            return False
    except Exception as e:
        print(f"[ERROR] Cannot check server status: {e}")
        return False
    
    # Test 2: Windows Firewall check
    print(f"\n2. Windows Firewall Check:")
    try:
        result = subprocess.run(['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name="LANVAN File Server HTTP"'], 
                              capture_output=True, text=True, shell=True)
        if 'Rule Name:' in result.stdout:
            print("[PASS] Firewall rule exists for LANVAN")
        else:
            print("[WARN] No firewall rule found - run fix_guest_connectivity.bat as Administrator")
    except Exception as e:
        print(f"[INFO] Could not check firewall rules: {e}")
    
    # Test 3: Direct IP connectivity
    print(f"\n3. Direct IP Connectivity Test:")
    try:
        response = requests.get(f'http://{local_ip}', timeout=5)
        print(f"[PASS] Direct IP access works: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] Direct IP access failed: {e}")
        return False
    
    # Test 4: mDNS connectivity
    print(f"\n4. mDNS Connectivity Test:")
    try:
        response = requests.get('http://lanvan.local', timeout=5)
        print(f"[PASS] mDNS access works: {response.status_code}")
    except Exception as e:
        print(f"[FAIL] mDNS access failed: {e}")
        print("       This may be normal on some networks")
    
    # Test 5: Network discovery simulation
    print(f"\n5. Network Discovery Simulation:")
    print("   Testing how guest devices would discover the server...")
    
    # Simulate different device scenarios
    test_scenarios = [
        ("Modern smartphone", "http://lanvan.local"),
        ("Older device", f"http://{local_ip}"),
        ("Tablet with mDNS", "http://lanvan.local"),
        ("Laptop browser", f"http://{local_ip}")
    ]
    
    for device_type, url in test_scenarios:
        try:
            response = requests.get(url, timeout=3)
            print(f"   [PASS] {device_type}: {url} -> {response.status_code}")
        except Exception as e:
            print(f"   [FAIL] {device_type}: {url} -> {str(e)[:50]}...")
    
    # Generate QR code info
    print(f"\n6. Guest Access Information:")
    print(f"   Primary URL (mDNS): http://lanvan.local")
    print(f"   Backup URL (Direct): http://{local_ip}")
    print(f"   \n   QR Code URLs for guests:")
    print(f"   - Modern devices: http://lanvan.local")
    print(f"   - All devices: http://{local_ip}")
    
    # Network troubleshooting tips
    print(f"\n" + "=" * 60)
    print("GUEST DEVICE TROUBLESHOOTING GUIDE:")
    print("=" * 60)
    print("If guests can't connect:")
    print("1. Ensure they're on the SAME WiFi network")
    print("2. Run fix_guest_connectivity.bat as Administrator")
    print("3. Try direct IP instead of .local domain")
    print("4. Restart your router if needed")
    print("5. Check if guest WiFi isolation is enabled on router")
    print("6. Some corporate/hotel WiFi blocks device-to-device communication")
    print("\nMobile Device Specific:")
    print("- iOS: Should work with both URLs")
    print("- Android: May need direct IP on some networks")
    print("- Older devices: Use direct IP address")
    
    return True

if __name__ == "__main__":
    test_guest_connectivity()
    print(f"\nTest completed! Press Enter to continue...")
    input()