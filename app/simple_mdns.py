import socket
import threading
import time
import logging
import hashlib
import uuid
import platform
import os
from typing import Optional, Dict, Any
from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser

class SimpleMDNSManager:
    """
    Simple, robust mDNS service manager for LANVAN
    """
    
    def __init__(self, port: int = 5000, use_https: bool = False):
        self.port = port
        self._use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.zeroconf = None
        self.service_info = None
        self.service_name = "lanvan"
        self.base_service_name = "lanvan"
        self.service_type = "_http._tcp.local."  # Always use _http._tcp for mDNS, even for HTTPS
        self.domain = f"{self.service_name}.local"
        self.conflict_count = 0
        self.is_running = False
        self.lan_ip = None
        self.device_id = self._generate_device_id()
        self._lock = threading.Lock()
        self._announcement_thread = None
        self._stop_announcements = False
        
        # Setup simple logging
        self.logger = logging.getLogger(__name__)

    @property
    def use_https(self):
        return self._use_https
    
    @use_https.setter
    def use_https(self, value):
        self._use_https = value
        self.protocol = "https" if value else "http"

    def _generate_device_id(self) -> str:
        """Generate a unique, consistent device identifier for collision avoidance"""
        try:
            device_parts = []
            
            # Get hostname (most reliable)
            try:
                hostname = socket.gethostname().lower()
                # Clean hostname for mDNS compatibility (alphanumeric + hyphens only)
                hostname = ''.join(c if c.isalnum() or c == '-' else '' for c in hostname)
                if hostname and hostname != 'localhost':
                    device_parts.append(hostname[:8])  # Max 8 chars
            except:
                pass
            
            # Get MAC address (hardware-based, persistent)
            try:
                mac = uuid.getnode()
                mac_hex = format(mac, 'x')[-4:]  # Last 4 hex digits
                device_parts.append(mac_hex)
            except:
                pass
            
            # Get platform info for differentiation
            try:
                system = platform.system().lower()
                if 'android' in str(os.environ.get('PREFIX', '')).lower():
                    device_parts.append('termux')
                elif system == 'windows':
                    device_parts.append('win')
                elif system == 'linux':
                    device_parts.append('linux')
                elif system == 'darwin':
                    device_parts.append('mac')
                else:
                    device_parts.append('other')
            except:
                device_parts.append('unknown')
            
            # Create identifier from available parts
            if device_parts:
                primary = device_parts[0] if device_parts[0] != 'unknown' else 'device'
                # Create a short hash from all parts for uniqueness
                all_parts = ''.join(device_parts)
                short_hash = hashlib.md5(all_parts.encode()).hexdigest()[:3]
                return f"{primary}-{short_hash}"
            else:
                # Ultimate fallback
                import random
                return f"device-{random.randint(100, 999)}"
                
        except Exception as e:
            print(f"⚠️ Device identifier generation failed: {e}")
            return f"lanvan-{hash(str(time.time())) % 1000}"

    def _start_announcement_thread(self):
        """Start background thread for periodic mDNS announcements (instant guest loading)"""
        if self._announcement_thread and self._announcement_thread.is_alive():
            return
            
        self._stop_announcements = False
        self._announcement_thread = threading.Thread(target=self._announcement_worker, daemon=True)
        self._announcement_thread.start()
        
    def _announcement_worker(self):
        """Background worker for periodic mDNS announcements"""
        try:
            announcement_count = 0
            while not self._stop_announcements and self.is_running:
                time.sleep(1)
                announcement_count += 1
                
                # Announce every 10 seconds for first minute (instant loading)
                if announcement_count <= 60 and announcement_count % 10 == 0:
                    try:
                        if self.service_info and self.zeroconf:
                            self.zeroconf.register_service(self.service_info)
                    except:
                        pass  # Ignore re-registration errors
                        
                # Then announce every 30 seconds (maintenance)
                elif announcement_count > 60 and announcement_count % 30 == 0:
                    try:
                        if self.service_info and self.zeroconf:
                            self.zeroconf.register_service(self.service_info)
                    except:
                        pass
                        
        except Exception as e:
            print(f"⚠️ Announcement thread error: {e}")

    def _stop_announcement_thread(self):
        """Stop the announcement thread"""
        self._stop_announcements = True
        if self._announcement_thread and self._announcement_thread.is_alive():
            self._announcement_thread.join(timeout=1.0)

    def _detect_collision(self, service_name: str) -> tuple[str, bool]:
        """Detect if service name is already in use and suggest alternative"""
        try:
            # Quick check - browse for existing services
            zeroconf_browser = Zeroconf()
            services_found = []
            collision_detected = False
            
            def service_added(zeroconf, service_type, name):
                services_found.append(name)
            
            try:
                browser = ServiceBrowser(zeroconf_browser, self.service_type, handlers=[service_added])
                # Wait briefly for discovery
                time.sleep(0.5)
                browser.cancel()
                
                # Check if our desired name conflicts
                target_service = f"{service_name}.{self.service_type}"
                collision_detected = target_service in services_found
                
                if collision_detected:
                    # Generate alternative name with device ID
                    alternative_name = f"{service_name}-{self.device_id}"
                    print(f"⚠️ Name collision detected! '{service_name}' is already in use")
                    print(f"🔄 Using alternative name: '{alternative_name}'")
                    return alternative_name, True
                else:
                    return service_name, False
                    
            finally:
                zeroconf_browser.close()
                
        except Exception as e:
            print(f"⚠️ Collision detection failed: {e}")
            # If collision detection fails, add device identifier as safety measure
            safe_name = f"{service_name}-{self.device_id}"
            print(f"🔧 Using safe unique name: '{safe_name}'")
            return safe_name, False
        self._lock = threading.Lock()
        
        # Setup simple logging
        self.logger = logging.getLogger(__name__)
        
    def get_lan_ip(self) -> str:
        """Get the LAN IP address"""
        try:
            if self.lan_ip:
                return self.lan_ip
                
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.lan_ip = s.getsockname()[0]
            s.close()
            return self.lan_ip
        except Exception as e:
            print(f"❌ Failed to get LAN IP: {e}")
            return "127.0.0.1"
    
    def generate_service_name(self) -> str:
        """Generate unique service name with collision resolution"""
        base_name = self.base_service_name  # Use same base name for both HTTP and HTTPS
        
        # Use collision detection for the base name
        final_name, collision_resolved = self._detect_collision(base_name)
        
        if collision_resolved:
            self.conflict_count += 1
        
        return final_name
    
    def start_service(self) -> bool:
        """Start mDNS service with collision detection and performance optimizations"""
        try:
            with self._lock:
                if self.is_running:
                    return True
                
                # Create zeroconf instance with optimizations
                self.zeroconf = Zeroconf()  # Use default interfaces
                
                # Generate service details with collision detection
                self.service_name = self.generate_service_name()
                self.domain = f"{self.service_name}.local"
                
                # Get network info
                hostname = socket.gethostname()
                lan_ip = self.get_lan_ip()
                
                # Create service name
                service_name_full = f"{self.service_name}.{self.service_type}"
                
                # Enhanced properties with more information
                properties = {
                    b'version': b'1.0.0',
                    b'service': b'lanvan-file-server',
                    b'protocol': self.protocol.encode('utf-8'),
                    b'secure': b'true' if self.use_https else b'false',
                    b'features': b'file-transfer,clipboard,encryption',
                    b'device_id': self.device_id.encode('utf-8'),
                    b'collision_resolved': b'true' if self.conflict_count > 0 else b'false',
                    b'instant_ready': b'true'  # Indicate service is ready for immediate connections
                }
                
                # Create service info with optimization for instant loading
                self.service_info = ServiceInfo(
                    self.service_type,
                    service_name_full,
                    addresses=[socket.inet_aton(lan_ip)],
                    port=self.port,
                    properties=properties,
                    server=f"{self.service_name}.local."  # Use service name for better resolution
                )
                
                # Register the service
                self.zeroconf.register_service(self.service_info)
                self.is_running = True
                
                # Force immediate announcement with multiple broadcasts for instant loading
                time.sleep(0.1)  # Small delay to ensure registration
                
                # Send multiple quick announcements for faster guest discovery
                try:
                    # Re-announce the service multiple times for instant discovery
                    for i in range(3):
                        time.sleep(0.05)  # 50ms between announcements
                        self.zeroconf.register_service(self.service_info)
                except:
                    pass  # Ignore re-registration errors
                
                protocol_display = "HTTPS" if self.use_https else "HTTP"
                print(f"✅ mDNS service started: {self.domain}:{self.port} ({protocol_display})")
                print(f"   Available at: {self.protocol}://{self.domain}:{self.port}")
                print(f"⚡ Optimized for instant loading and guest connections")
                
                if self.conflict_count > 0:
                    print(f"ℹ️ Collision resolved - using unique name: {self.service_name}")
                
                # Start background thread for periodic announcements (instant guest loading)
                self._start_announcement_thread()
                
                return True
                
        except Exception as e:
            print(f"❌ mDNS service failed: {e}")
            if self.zeroconf:
                try:
                    self.zeroconf.close()
                except:
                    pass
                self.zeroconf = None
            return False
    
    def stop_service(self):
        """Stop the mDNS service"""
        try:
            with self._lock:
                if not self.is_running:
                    return
                
                # Stop announcement thread first
                self._stop_announcement_thread()
                
                if self.service_info and self.zeroconf:
                    self.zeroconf.unregister_service(self.service_info)
                    print(f"🔴 mDNS service stopped: {self.domain}")
                
                if self.zeroconf:
                    self.zeroconf.close()
                    
                self.is_running = False
                self.service_info = None
                self.zeroconf = None
                
        except Exception as e:
            print(f"❌ Error stopping mDNS service: {e}")
    
    def get_mdns_info(self) -> Dict[str, Any]:
        """Get mDNS service information"""
        if not self.is_running:
            return {
                "status": "disabled",
                "domain": None,
                "url": None,
                "service_name": None,
                "conflict_resolved": False
            }
        
        return {
            "status": "active",
            "domain": self.domain,
            "url": f"{self.protocol}://{self.domain}:{self.port}",
            "service_name": self.service_name,
            "conflict_resolved": self.conflict_count > 0,
            "conflict_count": self.conflict_count,
            "ip": self.get_lan_ip(),
            "port": self.port
        }
    
    def get_hybrid_url(self) -> str:
        """Get the best URL for QR code generation (mDNS first, fallback to IP)"""
        if self.is_running and self.domain:
            protocol = "https" if self.use_https else "http"
            return f"{protocol}://{self.domain}:{self.port}"
        else:
            protocol = "https" if self.use_https else "http"
            return f"{protocol}://{self.get_lan_ip()}:{self.port}"

# Global simple mDNS manager instance
mdns_manager = SimpleMDNSManager()
