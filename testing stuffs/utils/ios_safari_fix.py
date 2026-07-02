#!/usr/bin/env python3
"""
iOS Safari Connection Helper
============================

This script helps with iOS Safari connectivity issues by:
1. Starting both HTTP and HTTPS servers simultaneously
2. Providing multiple connection options
3. Generating iOS-compatible certificates
4. Showing QR codes for easy mobile access

Usage:
    python ios_safari_fix.py
"""

import os
import sys
import socket
import subprocess
import threading
import time
import qrcode
from io import StringIO

def get_local_ip():
    """Get the local IP address"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def print_qr_code(url):
    """Print a QR code to terminal"""
    try:
        qr = qrcode.QRCode(version=1, box_size=1, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create QR code as text
        f = StringIO()
        qr.print_ascii(out=f, tty=False)
        f.seek(0)
        qr_text = f.read()
        
        print(f"\n[MOBILE] QR Code for {url}:")
        print(qr_text)
        
    except ImportError:
        print("[MOBILE] Install qrcode library for QR codes: pip install qrcode")
    except Exception as e:
        print(f"[MOBILE] QR Code generation failed: {e}")

def start_server(port, use_https=False):
    """Start a server on specified port"""
    protocol = "https" if use_https else "http"
    cmd = [sys.executable, "run.py"]
    if use_https:
        cmd.append("https")
    cmd.extend(["--port", str(port)])
    
    try:
        print(f"[START] Starting {protocol.upper()} server on port {port}...")
        # Get the project root directory (parent of utils)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        process = subprocess.Popen(cmd, cwd=project_root)
        time.sleep(2)  # Give server time to start
        return process
    except Exception as e:
        print(f"[ERR] Failed to start {protocol} server: {e}")
        return None

def main():
    print(" iOS Safari Connection Helper")
    print("=" * 50)
    
    ip = get_local_ip()
    print(f"[MDNS] Local IP: {ip}")
    
    print("\n[CFG] Regenerating iOS-compatible certificates...")
    try:
        # Get the project root directory (parent of utils)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.run([sys.executable, "certs/generate_certs_python.py", "--ip", ip, "--force"], 
                      check=True, cwd=project_root)
        print("[OK] iOS-compatible certificates generated!")
    except Exception as e:
        print(f"[WARN] Certificate generation warning: {e}")
    
    # Start both HTTP and HTTPS servers
    print("\n[START] Starting dual servers for maximum iOS compatibility...")
    
    http_process = None
    https_process = None
    
    try:
        # Start HTTP server (port 5000)
        http_process = start_server(5000, use_https=False)
        
        # Start HTTPS server (port 5001) 
        https_process = start_server(5001, use_https=True)
        
        time.sleep(3)  # Give servers time to fully start
        
        print("\n" + "="*60)
        print("[MOBILE] iOS SAFARI CONNECTION OPTIONS")
        print("="*60)
        
        # Option 1: HTTP (most reliable for iOS)
        http_url = f"http://{ip}:5000"
        print(f"\n OPTION 1 (RECOMMENDED): HTTP")
        print(f"   URL: {http_url}")
        print(f"   Status: Most reliable for iOS Safari")
        print(f"   Security: Basic (local network only)")
        print_qr_code(http_url)
        
        # Option 2: HTTPS with IP
        https_ip_url = f"https://{ip}:5001"
        print(f"\n OPTION 2: HTTPS with IP")
        print(f"   URL: {https_ip_url}")
        print(f"   Status: May show security warning")
        print(f"   Action: Tap 'Advanced' → 'Continue to {ip}'")
        print_qr_code(https_ip_url)
        
        # Option 3: HTTPS with mDNS
        mdns_url = "https://lanvan.local:5001"
        print(f"\n OPTION 3: HTTPS with mDNS")
        print(f"   URL: {mdns_url}")
        print(f"   Status: May not resolve on iOS")
        print(f"   Fallback: Use Options 1 or 2")
        
        print(f"\n" + "="*60)
        print("[INFO] TROUBLESHOOTING TIPS FOR iOS SAFARI:")
        print("="*60)
        print("1.  Try HTTP first (Option 1) - most reliable")
        print("2.  For HTTPS, accept security warnings")
        print("3. [RETRY] If page won't load, try refreshing")
        print("4. [MOBILE] Ensure iPhone is on same WiFi network")
        print("5. [CFG] Try turning WiFi off/on if mDNS fails")
        print("6. [NET] Use IP addresses instead of .local domains")
        print("7.  Visit http://10.110.4.169:5000/ios-help for detailed help")
        print("8. [CLEAN] Clear Safari cache: Settings → Safari → Clear History")
        print("9. [RETRY] Try other browsers (Chrome, Firefox) if Safari fails")
        print("10. [MDNS] Check if you're on a guest network (may block connections)")
        
        print(f"\n[WAIT] Servers running... Press Ctrl+C to stop")
        
        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n Stopping servers...")
            
    except KeyboardInterrupt:
        print("\n Stopping servers...")
        
    finally:
        # Clean up processes
        for process in [http_process, https_process]:
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                    except:
                        pass
        
        print("[OK] All servers stopped.")

if __name__ == "__main__":
    main()
