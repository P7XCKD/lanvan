#!/usr/bin/env python3
"""
Mobile/Termux Networking Fixes for LANVAN
Addresses port binding and mDNS reliability issues on Android/Termux
"""

import os
import socket
import subprocess
import threading
import time
from typing import Optional, Tuple

def is_termux_environment() -> bool:
    """Enhanced Termux detection"""
    return any([
        "ANDROID_STORAGE" in os.environ,
        os.path.exists("/data/data/com.termux"),
        "termux" in os.environ.get("PREFIX", "").lower(),
        "android" in os.environ.get("HOME", "").lower()
    ])

def get_termux_safe_ports() -> Tuple[int, int]:
    """Get safe ports for Termux that work reliably"""
    # Termux-friendly ports that usually work
    base_port = 8080  # Common alternative to 80
    https_port = 8443  # Common alternative to 443
    
    # Find available ports starting from these bases
    http_port = find_available_port(base_port, range(8080, 8090))
    https_port = find_available_port(https_port, range(8443, 8453))
    
    return http_port, https_port

def find_available_port(preferred: int, port_range: range) -> int:
    """Find an available port in the given range"""
    for port in [preferred] + list(port_range):
        if is_port_available(port):
            return port
    # If all preferred ports are taken, find any available
    for port in range(8000, 9000):
        if is_port_available(port):
            return port
    return 8080  # Fallback

def is_port_available(port: int) -> bool:
    """Check if a port is available for binding"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
            return True
    except (OSError, PermissionError):
        return False

def setup_termux_networking():
    """Setup networking optimizations for Termux"""
    print("🔧 Setting up Termux networking optimizations...")
    
    try:
        # Install required packages if not present
        packages_to_check = [
            ("python", "python"),
            ("python-pip", "pip"),
            ("termux-api", "termux-api")
        ]
        
        for pkg_name, check_cmd in packages_to_check:
            if not check_command_exists(check_cmd):
                print(f"📦 Installing {pkg_name}...")
                subprocess.run(["pkg", "install", "-y", pkg_name], 
                             capture_output=True, check=False)
        
        # Enable wake lock to prevent killing
        try:
            subprocess.run(["termux-wake-lock"], check=False, capture_output=True)
            print("🔋 Wake lock enabled to prevent service termination")
        except:
            print("⚠️ Wake lock not available (install termux-api)")
        
        # Set networking environment variables
        os.environ['ANDROID_NETWORKING_MODE'] = 'true'
        os.environ['DISABLE_PRIVILEGED_PORTS'] = 'true'
        
        print("✅ Termux networking setup complete")
        return True
        
    except Exception as e:
        print(f"⚠️ Termux setup warning: {e}")
        return False

def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH"""
    try:
        subprocess.run([command, "--version"], 
                      capture_output=True, check=True)
        return True
    except:
        return False

class TermuxMDNSManager:
    """Enhanced mDNS manager specifically for Termux/Android"""
    
    def __init__(self, port: int, service_name: str = "lanvan"):
        self.port = port
        self.service_name = service_name
        self.is_running = False
        self._stop_event = threading.Event()
        self._thread = None
        
    def start(self) -> bool:
        """Start mDNS service with Termux optimizations"""
        if self.is_running:
            return True
            
        print("🔍 Starting Termux-optimized mDNS service...")
        
        try:
            # First try standard zeroconf
            success = self._start_zeroconf_mdns()
            if success:
                print("✅ Standard mDNS service started")
                return True
                
            # Fallback to manual announcement
            print("🔄 Falling back to manual mDNS announcements...")
            success = self._start_manual_mdns()
            if success:
                print("✅ Manual mDNS announcements started")
                return True
                
            print("❌ mDNS service failed to start")
            return False
            
        except Exception as e:
            print(f"❌ mDNS startup error: {e}")
            return False
    
    def _start_zeroconf_mdns(self) -> bool:
        """Try to start standard zeroconf mDNS"""
        try:
            from zeroconf import Zeroconf, ServiceInfo
            import socket
            
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Create service info
            service_type = "_http._tcp.local."
            service_name = f"{self.service_name}.{service_type}"
            
            info = ServiceInfo(
                service_type,
                service_name,
                addresses=[socket.inet_aton(local_ip)],
                port=self.port,
                properties={
                    'path': '/',
                    'platform': 'termux',
                    'version': '1.0'
                }
            )
            
            # Register service
            zeroconf = Zeroconf()
            zeroconf.register_service(info)
            
            self.zeroconf = zeroconf
            self.service_info = info
            self.is_running = True
            return True
            
        except Exception as e:
            print(f"⚠️ Standard mDNS failed: {e}")
            return False
    
    def _start_manual_mdns(self) -> bool:
        """Start manual mDNS announcements as fallback"""
        try:
            self._thread = threading.Thread(
                target=self._manual_announce_loop,
                daemon=True
            )
            self._thread.start()
            self.is_running = True
            return True
        except Exception as e:
            print(f"⚠️ Manual mDNS failed: {e}")
            return False
    
    def _manual_announce_loop(self):
        """Manually send mDNS announcements"""
        sock = None
        try:
            # Create multicast socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Enable broadcast
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            while not self._stop_event.is_set():
                try:
                    # Simple broadcast announcement
                    message = f"LANVAN:{self.service_name}:{self.port}:HTTP"
                    sock.sendto(message.encode(), ('<broadcast>', 5353))
                    
                    # Also try local multicast
                    sock.sendto(message.encode(), ('224.0.0.251', 5353))
                    
                except Exception as e:
                    print(f"⚠️ Broadcast failed: {e}")
                
                # Wait before next announcement
                self._stop_event.wait(30)  # Announce every 30 seconds
                
        except Exception as e:
            print(f"⚠️ Manual announce error: {e}")
        finally:
            if sock:
                sock.close()
    
    def stop(self):
        """Stop mDNS service"""
        if not self.is_running:
            return
            
        self._stop_event.set()
        
        if hasattr(self, 'zeroconf') and self.zeroconf:
            try:
                if self.service_info:
                    self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
            except:
                pass
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        self.is_running = False
        print("🔍 mDNS service stopped")

def get_network_interfaces():
    """Get available network interfaces for mDNS"""
    interfaces = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get('addr')
                    if ip and not ip.startswith('127.'):
                        interfaces.append((iface, ip))
    except ImportError:
        # Fallback without netifaces
        import socket
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            interfaces.append(('default', ip))
    
    return interfaces

def print_termux_networking_info(http_port: int, https_port: int, ip: str):
    """Print Termux-specific networking information"""
    print("\n" + "="*60)
    print("📱 TERMUX/ANDROID NETWORKING INFO")
    print("="*60)
    print(f"🌍 Local IP: {ip}")
    print(f"🔌 HTTP Port: {http_port}")
    print(f"🔒 HTTPS Port: {https_port}")
    print()
    print("📋 Access URLs:")
    print(f"   Local: http://localhost:{http_port}")
    print(f"   Network: http://{ip}:{http_port}")
    print(f"   Secure: https://{ip}:{https_port}")
    print()
    print("🔧 Termux-Specific Notes:")
    print("   • Ports 80/443 require root (not available in Termux)")
    print("   • Using high ports (8000+) for better compatibility")
    print("   • mDNS may be limited due to Android restrictions")
    print("   • Use direct IP access for most reliable connection")
    print("   • Keep terminal open to prevent service termination")
    print()
    print("💡 Troubleshooting:")
    print("   • If connection fails, try: termux-wake-lock")
    print("   • Check firewall/router settings for port access")
    print("   • Use 'ip addr' to verify network interface")
    print("   • Restart service if ports become unavailable")
    print("="*60)

if __name__ == "__main__":
    # Test the fixes
    if is_termux_environment():
        print("📱 Termux environment detected")
        setup_termux_networking()
        http_port, https_port = get_termux_safe_ports()
        print(f"🔌 Recommended ports: HTTP={http_port}, HTTPS={https_port}")
        
        # Test mDNS
        mdns = TermuxMDNSManager(http_port)
        success = mdns.start()
        print(f"🔍 mDNS test: {'✅ Success' if success else '❌ Failed'}")
        
        time.sleep(2)
        mdns.stop()
    else:
        print("💻 Not a Termux environment")
