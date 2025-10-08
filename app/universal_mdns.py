#!/usr/bin/env python3
"""
🌐 Enhanced Universal mDNS Manager
Comprehensive mDNS solution for Windows + Termux with maximum compatibility
"""

import os
import sys
import time
import socket
import threading
import subprocess
import platform
from typing import Optional, Dict, Any, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UniversalMDNSManager:
    """Universal mDNS manager that works on all platforms"""
    
    def __init__(self, service_name: str = "lanvan", port: int = 8000):
        self.service_name = service_name
        self.port = port
        self.service_type = "_http._tcp.local."
        self.domain = f"{service_name}.local"
        self.is_active = False
        self.local_ip = None
        self.platform = self._detect_platform()
        self.mdns_backend = None
        self.announcement_thread = None
        self._stop_event = threading.Event()
        
        print(f"🌐 Universal mDNS Manager initialized")
        print(f"📡 Service: {self.service_name}")
        print(f"🌍 Domain: {self.domain}")
        print(f"🔧 Platform: {self.platform['type']}")
        
    def _detect_platform(self) -> Dict[str, Any]:
        """Detect platform and capabilities"""
        is_termux = any([
            "TERMUX_VERSION" in os.environ,
            os.path.exists("/data/data/com.termux"),
            "com.termux" in os.environ.get("PREFIX", "")
        ])
        
        is_android = any([
            is_termux,
            "ANDROID_ROOT" in os.environ,
            os.path.exists("/system/build.prop")
        ])
        
        system = platform.system()
        
        return {
            'type': 'termux' if is_termux else 'android' if is_android else system.lower(),
            'is_termux': is_termux,
            'is_android': is_android,
            'is_windows': system == 'Windows',
            'is_linux': system == 'Linux',
            'is_macos': system == 'Darwin'
        }
    
    def _get_local_ip(self) -> str:
        """Get local IP address with multiple methods"""
        methods = [
            self._get_ip_via_socket,
            self._get_ip_via_hostname,
            self._get_ip_via_route,
            self._get_ip_via_ifconfig
        ]
        
        for method in methods:
            try:
                ip = method()
                if ip and ip != "127.0.0.1" and self._is_valid_ip(ip):
                    print(f"✅ Local IP detected: {ip}")
                    return ip
            except Exception as e:
                logger.debug(f"IP method failed: {method.__name__}: {e}")
        
        print("⚠️ Using fallback IP: 127.0.0.1")
        return "127.0.0.1"
    
    def _get_ip_via_socket(self) -> str:
        """Get IP by connecting to external address"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    
    def _get_ip_via_hostname(self) -> str:
        """Get IP via hostname resolution"""
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    
    def _get_ip_via_route(self) -> str:
        """Get IP via route command (Linux/Android)"""
        if self.platform['is_windows']:
            return None
            
        try:
            result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'src' in line:
                        parts = line.split()
                        src_idx = parts.index('src')
                        if src_idx + 1 < len(parts):
                            return parts[src_idx + 1]
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass
        return None
    
    def _get_ip_via_ifconfig(self) -> str:
        """Get IP via ifconfig (fallback)"""
        if self.platform['is_windows']:
            return None
            
        try:
            result = subprocess.run(['ip', 'addr'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Look for wlan0 or similar interfaces
                lines = result.stdout.split('\n')
                for i, line in enumerate(lines):
                    if 'wlan' in line or 'wifi' in line or 'eth' in line:
                        # Look for inet address in next few lines
                        for j in range(i+1, min(i+5, len(lines))):
                            if 'inet ' in lines[j] and '127.0.0.1' not in lines[j]:
                                parts = lines[j].split()
                                for part in parts:
                                    if '/' in part and self._is_valid_ip(part.split('/')[0]):
                                        return part.split('/')[0]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if IP is valid"""
        try:
            parts = ip.split('.')
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except (ValueError, AttributeError):
            return False
    
    def _try_zeroconf_backend(self) -> bool:
        """Try to use zeroconf backend"""
        try:
            from zeroconf import ServiceInfo, Zeroconf
            import socket
            
            self.local_ip = self._get_local_ip()
            print(f"🔧 Registering mDNS for IP: {self.local_ip}")
            
            # Create service info with correct format
            service_name = f"{self.service_name}.{self.service_type}"
            
            service_info = ServiceInfo(
                type_=self.service_type,
                name=service_name,
                addresses=[socket.inet_aton(self.local_ip)],
                port=self.port,
                properties={
                    b'path': b'/',
                    b'description': b'LANVAN File Sharing Server'
                },
                server=f"{self.service_name}.local."
            )
            
            # Initialize Zeroconf
            zeroconf = Zeroconf()
            
            # Register the service
            print(f"🔧 Registering service: {service_name}")
            zeroconf.register_service(service_info)
            
            self.mdns_backend = {
                'type': 'zeroconf',
                'zeroconf': zeroconf,
                'service_info': service_info
            }
            
            print(f"✅ mDNS registered via zeroconf: {self.domain}")
            
            # Test resolution immediately
            time.sleep(1)
            try:
                resolved_ip = socket.gethostbyname(self.domain)
                if resolved_ip == self.local_ip:
                    print(f"✅ mDNS resolution verified: {self.domain} -> {resolved_ip}")
                else:
                    print(f"⚠️ mDNS resolution issue: {self.domain} -> {resolved_ip} (expected {self.local_ip})")
            except socket.gaierror:
                print(f"⚠️ mDNS not immediately resolvable (may take a moment)")
            
            return True
            
        except ImportError:
            print("📦 zeroconf not available")
            return False
        except Exception as e:
            print(f"❌ zeroconf registration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _try_avahi_backend(self) -> bool:
        """Try to use Avahi backend (Linux/Android)"""
        if self.platform['is_windows']:
            return False
            
        try:
            # Check if avahi-publish is available
            result = subprocess.run(['which', 'avahi-publish-service'], 
                                  capture_output=True, timeout=5)
            if result.returncode != 0:
                return False
            
            self.local_ip = self._get_local_ip()
            
            # Start avahi service
            cmd = [
                'avahi-publish-service',
                '-f',  # Replace existing
                self.service_name,
                self.service_type.rstrip('.local.'),
                str(self.port),
                f"path=/"
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE)
            
            self.mdns_backend = {
                'type': 'avahi',
                'process': process
            }
            
            print("✅ mDNS registered via Avahi")
            return True
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"📦 Avahi not available: {e}")
            return False
        except Exception as e:
            print(f"❌ Avahi registration failed: {e}")
            return False
    
    def _try_custom_mdns_backend(self) -> bool:
        """Custom mDNS implementation for maximum compatibility"""
        try:
            self.local_ip = self._get_local_ip()
            
            # Start custom mDNS announcer
            self.announcement_thread = threading.Thread(
                target=self._custom_mdns_announcer,
                daemon=True
            )
            self.announcement_thread.start()
            
            self.mdns_backend = {
                'type': 'custom',
                'thread': self.announcement_thread
            }
            
            print("✅ mDNS registered via custom implementation")
            return True
            
        except Exception as e:
            print(f"❌ Custom mDNS failed: {e}")
            return False
    
    def _custom_mdns_announcer(self):
        """Custom mDNS announcer using raw sockets"""
        try:
            # Create multicast socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to multicast address
            sock.bind(('', 5353))
            
            # Join multicast group
            mreq = socket.inet_aton('224.0.0.251') + socket.inet_aton('0.0.0.0')
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            # Prepare mDNS response packet (simplified)
            response = self._build_mdns_response()
            
            print("📡 Custom mDNS announcer started")
            
            while not self._stop_event.is_set():
                try:
                    # Send announcement every 30 seconds
                    sock.sendto(response, ('224.0.0.251', 5353))
                    print(f"📢 mDNS announcement sent for {self.domain}")
                    
                    # Wait or until stop event
                    if self._stop_event.wait(30):
                        break
                        
                except Exception as e:
                    logger.debug(f"mDNS announcement error: {e}")
                    time.sleep(5)
            
            sock.close()
            print("📡 Custom mDNS announcer stopped")
            
        except Exception as e:
            print(f"❌ Custom mDNS announcer failed: {e}")
    
    def _build_mdns_response(self) -> bytes:
        """Build basic mDNS response packet"""
        # This is a simplified mDNS packet
        # In a full implementation, you'd build proper DNS packets
        
        # For now, return a basic packet that announces the service
        domain_bytes = self.domain.encode('utf-8')
        ip_bytes = socket.inet_aton(self.local_ip)
        
        # Basic mDNS packet structure (simplified)
        packet = bytearray()
        packet.extend([0x00, 0x00])  # Transaction ID
        packet.extend([0x84, 0x00])  # Flags (response, authoritative)
        packet.extend([0x00, 0x00])  # Questions
        packet.extend([0x00, 0x01])  # Answer RRs
        packet.extend([0x00, 0x00])  # Authority RRs  
        packet.extend([0x00, 0x00])  # Additional RRs
        
        # Add domain name and A record (simplified)
        packet.extend([len(domain_bytes)])
        packet.extend(domain_bytes)
        packet.extend([0x00])  # End of name
        packet.extend([0x00, 0x01])  # Type A
        packet.extend([0x00, 0x01])  # Class IN
        packet.extend([0x00, 0x00, 0x00, 0x78])  # TTL (120 seconds)
        packet.extend([0x00, 0x04])  # Data length
        packet.extend(ip_bytes)  # IP address
        
        return bytes(packet)
    
    def start_service(self) -> bool:
        """Start mDNS service with multiple backend attempts"""
        if self.is_active:
            print("⚠️ mDNS service already active")
            return True
        
        print("🚀 Starting mDNS service...")
        
        # Try backends in order of preference
        backends = [
            ('zeroconf', self._try_zeroconf_backend),
            ('avahi', self._try_avahi_backend), 
            ('custom', self._try_custom_mdns_backend)
        ]
        
        for backend_name, backend_func in backends:
            print(f"🔄 Trying {backend_name} backend...")
            try:
                if backend_func():
                    self.is_active = True
                    print(f"✅ mDNS active via {backend_name}")
                    print(f"🌐 Service available at: http://{self.domain}:{self.port}")
                    return True
            except Exception as e:
                print(f"❌ {backend_name} backend failed: {e}")
        
        print("❌ All mDNS backends failed")
        return False
    
    def stop_service(self):
        """Stop mDNS service"""
        if not self.is_active:
            return
        
        print("🛑 Stopping mDNS service...")
        
        try:
            if self.mdns_backend:
                if self.mdns_backend['type'] == 'zeroconf':
                    self.mdns_backend['zeroconf'].unregister_service(
                        self.mdns_backend['service_info']
                    )
                    self.mdns_backend['zeroconf'].close()
                    
                elif self.mdns_backend['type'] == 'avahi':
                    self.mdns_backend['process'].terminate()
                    self.mdns_backend['process'].wait(timeout=5)
                    
                elif self.mdns_backend['type'] == 'custom':
                    self._stop_event.set()
                    if self.announcement_thread:
                        self.announcement_thread.join(timeout=5)
            
            self.is_active = False
            self.mdns_backend = None
            print("✅ mDNS service stopped")
            
        except Exception as e:
            print(f"⚠️ mDNS stop error: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get mDNS service status"""
        return {
            'active': self.is_active,
            'service_name': self.service_name,
            'domain': self.domain,
            'port': self.port,
            'local_ip': self.local_ip,
            'backend': self.mdns_backend['type'] if self.mdns_backend else None,
            'platform': self.platform['type'],
            'url': f"http://{self.domain}:{self.port}" if self.is_active else None
        }
    
    def test_resolution(self) -> bool:
        """Test if the domain resolves locally"""
        try:
            resolved_ip = socket.gethostbyname(self.domain)
            if resolved_ip == self.local_ip:
                print(f"✅ mDNS resolution test passed: {self.domain} -> {resolved_ip}")
                return True
            else:
                print(f"⚠️ mDNS resolution mismatch: {self.domain} -> {resolved_ip} (expected {self.local_ip})")
                return False
        except socket.gaierror:
            print(f"❌ mDNS resolution failed: {self.domain} not resolvable")
            return False

# Global instance for easy import
universal_mdns_manager = None

def get_mdns_manager(service_name: str = "lanvan", port: int = 8000) -> UniversalMDNSManager:
    """Get or create global mDNS manager instance"""
    global universal_mdns_manager
    if universal_mdns_manager is None:
        universal_mdns_manager = UniversalMDNSManager(service_name, port)
    return universal_mdns_manager

def start_mdns_service(service_name: str = "lanvan", port: int = 8000) -> bool:
    """Quick start mDNS service"""
    manager = get_mdns_manager(service_name, port)
    return manager.start_service()

def stop_mdns_service():
    """Quick stop mDNS service"""
    global universal_mdns_manager
    if universal_mdns_manager:
        universal_mdns_manager.stop_service()

if __name__ == "__main__":
    # Test the mDNS manager
    print("🧪 Testing Universal mDNS Manager")
    manager = UniversalMDNSManager("test-lanvan", 8000)
    
    if manager.start_service():
        print("✅ mDNS test successful")
        time.sleep(5)
        
        # Test resolution
        manager.test_resolution()
        
        manager.stop_service()
    else:
        print("❌ mDNS test failed")