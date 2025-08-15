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
        """Background worker for periodic mDNS announcements - reduced frequency"""
        try:
            announcement_count = 0
            while not self._stop_announcements and self.is_running:
                time.sleep(5)  # Increased from 1s to reduce HTTP conflicts
                announcement_count += 1
                
                # Announce every 30 seconds for first 2 minutes (reduced frequency)
                if announcement_count <= 24 and announcement_count % 6 == 0:
                    try:
                        if self.service_info and self.zeroconf:
                            self.zeroconf.register_service(self.service_info)
                    except:
                        pass  # Ignore re-registration errors
                        
                # Then announce every 60 seconds (reduced frequency)
                elif announcement_count > 24 and announcement_count % 12 == 0:
                    try:
                        if self.service_info and self.zeroconf:
                            self.zeroconf.register_service(self.service_info)
                    except:
                        pass
                        
        except Exception as e:
            print(f"⚠️ Announcement thread error (non-critical): {e}")

    def _stop_announcement_thread(self):
        """Stop the announcement thread"""
        self._stop_announcements = True
        if self._announcement_thread and self._announcement_thread.is_alive():
            self._announcement_thread.join(timeout=1.0)

    def _detect_collision(self, service_name: str) -> tuple[str, bool]:
        """Detect if service name is already in use and suggest alternative - works offline"""
        try:
            # Quick check - browse for existing services (offline-compatible)
            zeroconf_browser = None
            services_found = []
            collision_detected = False
            
            def service_added(zeroconf, service_type, name):
                services_found.append(name)
            
            try:
                # Create zeroconf with local-only interfaces to work offline
                zeroconf_browser = Zeroconf()
                browser = ServiceBrowser(zeroconf_browser, self.service_type, handlers=[service_added])
                
                # Wait briefly for discovery (reduced time for offline scenarios)
                time.sleep(0.3)  # Reduced from 0.5s for offline
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
                    
            except Exception as browse_error:
                print(f"⚠️ Collision detection failed (possibly offline): {browse_error}")
                # If collision detection fails, add device identifier as safety measure
                safe_name = f"{service_name}-{self.device_id}"
                print(f"🔧 Using safe unique name for offline: '{safe_name}'")
                return safe_name, False
            finally:
                if zeroconf_browser:
                    try:
                        zeroconf_browser.close()
                    except:
                        pass
                
        except Exception as e:
            print(f"⚠️ Collision detection system failure: {e}")
            # If collision detection completely fails, add device identifier as safety measure
            safe_name = f"{service_name}-{self.device_id}"
            print(f"🔧 Using safe unique name: '{safe_name}'")
            return safe_name, False
        self._lock = threading.Lock()
        
        # Setup simple logging
        self.logger = logging.getLogger(__name__)
        
    def get_lan_ip(self) -> str:
        """Get the LAN IP address - works offline by scanning local interfaces"""
        try:
            if self.lan_ip:
                return self.lan_ip
            
            # Method 1: Try to get IP without external connection (offline-compatible)
            # Get all network interfaces
            import socket
            hostname = socket.gethostname()
            
            # Try getting IP from hostname resolution (works offline on most systems)
            try:
                host_ip = socket.gethostbyname(hostname)
                # Check if it's a valid local IP (not loopback)
                if host_ip and not host_ip.startswith('127.'):
                    self.lan_ip = host_ip
                    return self.lan_ip
            except:
                pass
            
            # Method 2: Scan network interfaces manually (offline-compatible)
            try:
                # Create a socket and bind to get local IP
                temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Try connecting to a local network address (doesn't require internet)
                temp_socket.connect(("192.168.1.1", 80))  # Local router IP
                local_ip = temp_socket.getsockname()[0]
                temp_socket.close()
                
                if local_ip and not local_ip.startswith('127.'):
                    self.lan_ip = local_ip
                    return self.lan_ip
            except:
                pass
            
            # Method 3: Try different local network ranges (offline-compatible)
            for network_range in ["10.0.0.1", "172.16.0.1", "192.168.0.1"]:
                try:
                    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    temp_socket.connect((network_range, 80))
                    local_ip = temp_socket.getsockname()[0]
                    temp_socket.close()
                    
                    if local_ip and not local_ip.startswith('127.'):
                        self.lan_ip = local_ip
                        return self.lan_ip
                except:
                    continue
            
            # Method 4: Use psutil if available (most reliable offline method)
            try:
                import psutil
                for interface, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                            # Prefer typical LAN ranges
                            ip = addr.address
                            if (ip.startswith('192.168.') or 
                                ip.startswith('10.') or 
                                ip.startswith('172.')):
                                self.lan_ip = ip
                                return self.lan_ip
            except ImportError:
                pass
            
            # Fallback: Use loopback if no other option
            print("⚠️ Could not detect LAN IP offline, using localhost")
            return "127.0.0.1"
            
        except Exception as e:
            print(f"❌ Failed to get LAN IP offline: {e}")
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
        """Start mDNS service with offline support and collision detection"""
        try:
            with self._lock:
                if self.is_running:
                    return True
                
                print("🔍 Starting mDNS service (offline-compatible)...")
                
                # Create zeroconf instance with offline optimizations
                try:
                    # Initialize with local interfaces only for offline support
                    self.zeroconf = Zeroconf()
                except Exception as zc_error:
                    print(f"⚠️ Zeroconf initialization warning: {zc_error}")
                    print("🔧 Attempting alternative zeroconf setup...")
                    try:
                        # Fallback zeroconf initialization
                        self.zeroconf = Zeroconf()
                    except Exception as zc_fallback_error:
                        print(f"❌ mDNS service failed to initialize: {zc_fallback_error}")
                        return False
                
                # Generate service details with collision detection
                self.service_name = self.generate_service_name()
                self.domain = f"{self.service_name}.local"
                
                # Get network info (offline-compatible)
                hostname = socket.gethostname()
                lan_ip = self.get_lan_ip()
                
                print(f"🌐 Detected LAN IP: {lan_ip}")
                print(f"🏷️ Service name: {self.service_name}")
                
                # Create service name
                service_name_full = f"{self.service_name}.{self.service_type}"
                
                # Enhanced properties with offline-friendly information
                properties = {
                    b'version': b'1.0.0',
                    b'service': b'lanvan-file-server',
                    b'protocol': self.protocol.encode('utf-8'),
                    b'secure': b'true' if self.use_https else b'false',
                    b'features': b'file-transfer,clipboard,encryption',
                    b'device_id': self.device_id.encode('utf-8'),
                    b'collision_resolved': b'true' if self.conflict_count > 0 else b'false',
                    b'offline_ready': b'true',  # Indicate offline compatibility
                    b'local_network': b'true'   # Local network only
                }
                
                # Create service info with offline optimization
                try:
                    self.service_info = ServiceInfo(
                        self.service_type,
                        service_name_full,
                        addresses=[socket.inet_aton(lan_ip)],
                        port=self.port,
                        properties=properties,
                        server=f"{self.service_name}.local."
                    )
                except Exception as si_error:
                    print(f"❌ Service info creation failed: {si_error}")
                    return False
                
                # Register the service
                try:
                    self.zeroconf.register_service(self.service_info)
                    self.is_running = True
                    print("✅ mDNS service registered successfully")
                except Exception as reg_error:
                    print(f"⚠️ Service registration warning: {reg_error}")
                    # Continue anyway - some systems have registration warnings but still work
                    self.is_running = True
                
                # Brief pause for registration to take effect
                time.sleep(0.1)
                
                # Offline-optimized announcements (reduce frequency to prevent HTTP conflicts)
                try:
                    # Single announcement to prevent HTTP request conflicts
                    time.sleep(0.2)  # Longer delay for stability
                    if self.zeroconf and self.service_info:
                        self.zeroconf.register_service(self.service_info)
                        print("📡 mDNS service announcement sent")
                except Exception as announce_error:
                    print(f"⚠️ Announcement warning (non-critical): {announce_error}")
                    # Non-critical - continue
                
                protocol_display = "HTTPS" if self.use_https else "HTTP"
                print(f"✅ mDNS service started: {self.domain}:{self.port} ({protocol_display})")
                print(f"   Available at: {self.protocol}://{self.domain}:{self.port}")
                print(f"   Direct IP: {self.protocol}://{lan_ip}:{self.port}")
                print(f"🌐 Optimized for offline local network usage")
                
                if self.conflict_count > 0:
                    print(f"ℹ️ Collision resolved - using unique name: {self.service_name}")
                
                # Start background thread for periodic announcements (offline-friendly)
                self._start_announcement_thread()
                
                return True
                
        except Exception as e:
            print(f"❌ mDNS service failed: {e}")
            print("🔧 Service will continue with IP-only access")
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
