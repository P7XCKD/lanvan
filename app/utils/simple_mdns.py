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
from app.utils.termux_compat import is_android_environment

# Zeroconf version compatibility check
try:
    # Check zeroconf version to handle callback signature changes
    import zeroconf
    ZEROCONF_VERSION = getattr(zeroconf, '__version__', '0.0.0')
    ZEROCONF_NEW_API = tuple(map(int, ZEROCONF_VERSION.split('.')[:2])) >= (0, 132)
except Exception:
    ZEROCONF_NEW_API = True  # Assume newer version if can't detect

def check_mdns_dependencies() -> tuple[bool, str]:
    """Check if mDNS dependencies are available, especially for Termux"""
    try:
        from zeroconf import Zeroconf
        
        # Test basic Zeroconf functionality
        test_zc = Zeroconf()
        test_zc.close()
        
        # Check for Android/Termux specific requirements
        is_android = is_android_environment()
        
        if is_android:
            # Check if avahi is available (recommended for Termux)
            try:
                import subprocess
                result = subprocess.run(['which', 'avahi-daemon'], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    return True, "[WARN] mDNS on Android/Termux has limitations. Consider IP access instead."
            except Exception:
                pass
            
            # Additional warning for Android/Termux users
            print("[MOBILE] Android/Termux mDNS Limitations:")
            print("   • .local domains often don't work due to system restrictions")
            print("   • Use direct IP access instead: [IP]:5000 or [IP]:5001")
            print("   • QR codes will show IP-based URLs for better compatibility")
        
        return True, "[OK] mDNS dependencies available"
    
    except ImportError as e:
        return False, f"[ERR] mDNS not available: {e}. Install with: pip install zeroconf"
    except Exception as e:
        return False, f"[ERR] mDNS test failed: {e}"

def force_cleanup_mdns_resources():
    """Force cleanup of any lingering mDNS resources (useful for Termux restarts)"""
    try:
        import gc
        import threading
        
        # Force garbage collection
        gc.collect()
        
        # Log any daemon threads that might be lingering
        daemon_threads = [t for t in threading.enumerate() 
                         if t.daemon and 'zeroconf' in str(t).lower()]
        
        if daemon_threads:
            print(f"[CLEAN] Found {len(daemon_threads)} zeroconf daemon threads (will be cleaned up on exit)")
        
        print("[CLEAN] Forced cleanup of mDNS resources")
        return True
    except Exception as e:
        print(f"[WARN] Cleanup warning: {e}")
        return False

class SimpleMDNSManager:
    """
    Simple, robust mDNS service manager for Lanvan
    """
    
    def __init__(self, port: int = 80, use_https: bool = False):
        self.port = port
        self._use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.zeroconf = None
        self.service_info = None
        self.service_name = "Lanvan"
        self.base_service_name = "Lanvan"
        # [TARGET] Universal Service Type: Always use _http._tcp for mDNS compatibility
        self.service_type = "_http._tcp.local."  
        self.domain = f"{self.service_name}.local"
        self.conflict_count = 0
        self.is_running = False
        self.lan_ip = None
        self.device_id = self._generate_device_id()
        self._lock = threading.Lock()
        self._announcement_thread = None
        self._stop_announcements = False
        
        #  Universal Port Redirect: Track both HTTP and HTTPS services
        self.actual_port = port
        self.actual_protocol = self.protocol
        
        # Setup simple logging
        self.logger = logging.getLogger(__name__)
        
        # Check mDNS availability on init
        self.mdns_available, self.mdns_status = check_mdns_dependencies()
        if not self.mdns_available:
            self.logger.warning(self.mdns_status)
        elif "avahi-daemon not found" in self.mdns_status:
            self.logger.warning(self.mdns_status)

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
            except Exception:
                pass
            
            # Get MAC address (hardware-based, persistent)
            try:
                mac = uuid.getnode()
                mac_hex = format(mac, 'x')[-4:]  # Last 4 hex digits
                device_parts.append(mac_hex)
            except Exception:
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
            except Exception:
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
            print(f"[WARN] Device identifier generation failed: {e}")
            return f"Lanvan-{hash(str(time.time())) % 1000}"

    def _start_announcement_thread(self):
        """Start background thread for periodic mDNS announcements (instant guest loading)"""
        if self._announcement_thread and self._announcement_thread.is_alive():
            return
            
        self._stop_announcements = False
        self._announcement_thread = threading.Thread(target=self._announcement_worker, daemon=True)
        self._announcement_thread.start()
        
    def _announcement_worker(self):
        """Background worker for periodic mDNS announcements - optimized for guest devices"""
        try:
            announcement_count = 0
            while not self._stop_announcements and self.is_running:
                time.sleep(2)  # More frequent for guest device discovery
                announcement_count += 1
                
                # More frequent announcements for first 5 minutes (guest device discovery)
                if announcement_count <= 150 and announcement_count % 3 == 0:
                    try:
                        if self.service_info and self.zeroconf:
                            self.zeroconf.register_service(self.service_info)
                    except Exception:
                        pass  # Ignore re-registration errors
                        
                # Then announce every 30 seconds (maintenance)
                elif announcement_count > 150 and announcement_count % 15 == 0:
                    try:
                        if self.service_info and self.zeroconf:
                            self.zeroconf.register_service(self.service_info)
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"[WARN] Announcement thread error (non-critical): {e}")

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
            
            def service_added(zeroconf, service_type, name, state_change=None, **kwargs):
                """Handle service discovery with compatibility for different zeroconf versions"""
                # Accept any additional keyword arguments that newer versions might pass
                services_found.append(name)
            
            try:
                # Create zeroconf with local-only interfaces to work offline
                zeroconf_browser = Zeroconf()
                
                try:
                    browser = ServiceBrowser(zeroconf_browser, self.service_type, handlers=[service_added])
                    
                    # Wait briefly for discovery (reduced time for offline scenarios)
                    time.sleep(0.3)  # Reduced from 0.5s for offline
                    
                    try:
                        browser.cancel()
                    except Exception:
                        pass  # Ignore cancel errors
                        
                except Exception as browser_error:
                    print(f"[WARN] Service browser error (non-critical): {browser_error}")
                    # Continue without collision detection
                
                # Check if our desired name conflicts
                target_service = f"{service_name}.{self.service_type}"
                collision_detected = target_service in services_found
                
                if collision_detected:
                    # Generate alternative name with device ID
                    alternative_name = f"{service_name}-{self.device_id}"
                    print(f"[WARN] Name collision detected! '{service_name}' is already in use")
                    print(f"[RETRY] Using alternative name: '{alternative_name}'")
                    return alternative_name, True
                else:
                    return service_name, False
                    
            except Exception as browse_error:
                print(f"[WARN] Collision detection failed (possibly offline): {browse_error}")
                # If collision detection fails, add device identifier as safety measure
                safe_name = f"{service_name}-{self.device_id}"
                print(f"[CFG] Using safe unique name for offline: '{safe_name}'")
                return safe_name, False
            finally:
                if zeroconf_browser:
                    try:
                        zeroconf_browser.close()
                    except Exception:
                        pass
                
        except Exception as e:
            print(f"[WARN] Collision detection system failure: {e}")
            # If collision detection completely fails, add device identifier as safety measure
            safe_name = f"{service_name}-{self.device_id}"
            print(f"[CFG] Using safe unique name: '{safe_name}'")
            return safe_name, False
        self._lock = threading.Lock()
        
        # Setup simple logging
        self.logger = logging.getLogger(__name__)
    
    def _get_android_network_ip(self):
        """Enhanced Android/Termux network IP detection"""
        try:
            import subprocess
            import socket
            
            # Method 1: Try ip route command (most reliable on Android)
            try:
                result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'src' in line:
                            parts = line.split()
                            src_idx = parts.index('src')
                            if src_idx + 1 < len(parts):
                                ip = parts[src_idx + 1]
                                if not ip.startswith('127.') and ip != '192.0.0.4':
                                    return ip
            except Exception as e:
                print(f"[Android] IP route method failed: {e}")
            
            # Method 2: Connect to external service to get our IP
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(3)
                    s.connect(('8.8.8.8', 80))
                    ip = s.getsockname()[0]
                    if not ip.startswith('127.') and ip != '192.0.0.4':
                        return ip
            except Exception as e:
                print(f"[Android] Socket method failed: {e}")
            
            # Method 3: Parse network interfaces directly
            try:
                result = subprocess.run(['ip', 'addr', 'show'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'inet ' in line and 'wlan' in line:
                            # Extract IP from line like "inet 192.168.1.100/24"
                            parts = line.strip().split()
                            for part in parts:
                                if '/' in part and not part.startswith('127.') and '192.0.0.4' not in part:
                                    ip = part.split('/')[0]
                                    if ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.'):
                                        return ip
            except Exception as e:
                print(f"[Android] Interface parsing failed: {e}")
            
            return None
        except Exception as e:
            print(f"[Android] All network detection methods failed: {e}")
            return None
        
    def get_lan_ip(self) -> str:
        """Get the LAN IP address - works offline by scanning local interfaces, optimized for Termux"""
        try:
            # Return cached IP if available and still valid
            if self.lan_ip:
                # Quick test to see if IP is still valid
                try:
                    import socket
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    test_socket.bind((self.lan_ip, 0))
                    test_socket.close()
                    return self.lan_ip
                except Exception:
                    # IP no longer valid, clear cache
                    self.lan_ip = None
            
            # Check if we're on Android/Termux for special handling
            is_android = is_android_environment()
            
            if is_android:
                print("[MOBILE] Detecting network interface on Android/Termux...")
                
                # Use enhanced Android network detection
                try:
                    android_ip = self._get_android_network_ip()
                    if android_ip and android_ip != '192.0.0.4':
                        self.lan_ip = android_ip
                        print(f"[MOBILE] Enhanced Android detection found: {android_ip}")
                        return self.lan_ip
                except Exception as android_error:
                    print(f"[MOBILE] Enhanced Android detection failed: {android_error}")
                
            # Method 1: Try to get IP without external connection (offline-compatible)
            # Get all network interfaces
            import socket
            hostname = socket.gethostname()
            
            # Try getting IP from hostname resolution (works offline on most systems)
            try:
                host_ip = socket.gethostbyname(hostname)
                # Check if it's a valid local IP (not loopback) and not the problematic 192.0.0.4
                if host_ip and not host_ip.startswith('127.') and host_ip != '192.0.0.4':
                    self.lan_ip = host_ip
                    return self.lan_ip
                elif is_android and host_ip == '192.0.0.4':
                    print("[MOBILE] Detected problematic IP 192.0.0.4, trying alternatives...")
            except Exception:
                pass
            
            # Method 2: Scan network interfaces manually (offline-compatible)
            # Try multiple router addresses for better Termux compatibility
            router_addresses = [
                "192.168.1.1",   # Most common
                "192.168.0.1",   # Common alternative
                "10.0.0.1",      # Some networks
                "172.16.0.1",    # Corporate networks
                "192.168.43.1"   # Android hotspot default
            ]
            
            for router_ip in router_addresses:
                try:
                    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    temp_socket.settimeout(1.0)  # Quick timeout for faster detection
                    temp_socket.connect((router_ip, 80))
                    local_ip = temp_socket.getsockname()[0]
                    temp_socket.close()
                    
                    if local_ip and not local_ip.startswith('127.'):
                        self.lan_ip = local_ip
                        if is_android:
                            print(f"[MOBILE] Android IP detected: {local_ip}")
                        return self.lan_ip
                except Exception:
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
            print("[WARN] Could not detect LAN IP offline, using localhost")
            return "127.0.0.1"
            
        except Exception as e:
            print(f"[ERR] Failed to get LAN IP offline: {e}")
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
        """Start mDNS service with offline support, collision detection, and Termux compatibility"""
        try:
            with self._lock:
                if self.is_running:
                    print("ℹ mDNS service already running")
                    return True
                
                # Check if mDNS is available
                if not self.mdns_available:
                    print(f"[ERR] {self.mdns_status}")
                    return False
                
                print("[SEARCH] Starting mDNS service (offline-compatible, Termux-optimized)...")
                print(f"   {self.mdns_status}")
                
                # Check if we're on Android/Termux for special handling
                is_android = is_android_environment()
                
                # Enhanced cleanup before start (important for Termux restarts)
                force_cleanup_mdns_resources()
                
                if self.zeroconf:
                    try:
                        self.zeroconf.close()
                    except Exception:
                        pass
                    self.zeroconf = None
                
                # Create zeroconf instance with Android/Termux optimizations
                try:
                    if is_android:
                        print("[MOBILE] Android/Termux detected - using optimized mDNS settings")
                        # Use more conservative settings for Android
                        time.sleep(0.5)  # Give time for network interfaces to stabilize
                    
                    # Initialize with local interfaces only for offline support
                    self.zeroconf = Zeroconf()
                    
                except Exception as zc_error:
                    print(f"[WARN] Zeroconf initialization warning: {zc_error}")
                    print("[CFG] Attempting alternative zeroconf setup...")
                    try:
                        # Brief pause for Android/Termux network stability
                        time.sleep(1.0)
                        # Fallback zeroconf initialization
                        self.zeroconf = Zeroconf()
                    except Exception as zc_fallback_error:
                        print(f"[ERR] mDNS service failed to initialize: {zc_fallback_error}")
                        if is_android:
                            print("[TIP] On Android/Termux, try: pkg install avahi")
                            print("[TIP] Or restart Termux and try again")
                        return False
                
                # Generate service details with collision detection
                self.service_name = self.generate_service_name()
                self.domain = f"{self.service_name}.local"
                
                # Get network info (offline-compatible)
                hostname = socket.gethostname()
                lan_ip = self.get_lan_ip()
                
                print(f"[NET] Detected LAN IP: {lan_ip}")
                print(f"[TAG] Service name: {self.service_name}")
                
                # Create service name
                service_name_full = f"{self.service_name}.{self.service_type}"
                
                # Enhanced properties for guest device compatibility
                properties = {
                    b'version': b'1.0.0',
                    b'service': b'Lanvan-file-server',
                    b'protocol': self.protocol.encode('utf-8'),
                    b'supports_http': b'true' if not self.use_https else b'false',
                    b'supports_https': b'true' if self.use_https else b'false',
                    b'secure': b'true' if self.use_https else b'false',
                    b'features': b'file-transfer,clipboard,encryption,guest-friendly',
                    b'device_id': self.device_id.encode('utf-8'),
                    b'collision_resolved': b'true' if self.conflict_count > 0 else b'false',
                    b'offline_ready': b'true',
                    b'local_network': b'true',
                    b'guest_access': b'enabled',  # Indicate guest device support
                    b'cross_platform': b'true',   # Cross-platform compatibility
                    b'actual_port': str(self.actual_port).encode('utf-8'),
                    b'actual_protocol': self.actual_protocol.encode('utf-8'),
                    b'single_protocol': b'true',
                    b'auto_redirect': b'false',
                    b'firewall_friendly': b'true'  # Indicate firewall configuration
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
                    print(f"[ERR] Service info creation failed: {si_error}")
                    return False
                
                # Register the service
                try:
                    self.zeroconf.register_service(self.service_info)
                    self.is_running = True
                    print("[OK] mDNS service registered successfully")
                except Exception as reg_error:
                    print(f"[WARN] Service registration warning: {reg_error}")
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
                        print("[MDNS] mDNS service announcement sent")
                except Exception as announce_error:
                    print(f"[WARN] Announcement warning (non-critical): {announce_error}")
                    # Non-critical - continue
                
                # [NET] Protocol-Specific Access Information
                protocol_name = "HTTPS" if self.use_https else "HTTP"
                print(f"[OK] mDNS service started: {self.domain}")
                print(f"[NET] Guest devices can now discover this server!")
                
                # Check if we're on Android/Termux for special messaging
                is_android = is_android_environment()
                
                if is_android:
                    print(f"[MOBILE] Android/Termux {protocol_name} Server:")
                    print(f"[!] mDNS (.local) may not work on Android/Termux!")
                    print(f"[OK] RECOMMENDED - Use Direct IP Access:")
                    if self.use_https:
                        https_ip_url = self._format_url(lan_ip)
                        print(f"   [MOBILE] Mobile Access: {https_ip_url}")
                        print(f"   [PC] Desktop Access: {https_ip_url}")
                        print(f"[LOCK] HTTPS-only mode")
                    else:
                        http_ip_url = self._format_url(lan_ip)
                        print(f"   [MOBILE] Mobile Access: {http_ip_url}")
                        print(f"   [PC] Desktop Access: {http_ip_url}")
                        print(f"[NET] HTTP-only mode")
                    print(f"[WARN]  Avoid using {self.domain} - use IP instead")
                else:
                    print(f"[NET] {protocol_name} Server Access:")
                    if self.use_https:
                        # HTTPS-only mode
                        https_url = self._format_url(self.domain)
                        https_ip_url = self._format_url(lan_ip)
                        print(f"   HTTPS access: {https_url}")
                        print(f"   Direct IP (HTTPS): {https_ip_url}")
                        print(f"[LOCK] HTTPS-only mode - HTTP requests will not work")
                    else:
                        # HTTP-only mode  
                        http_url = self._format_url(self.domain)
                        http_ip_url = self._format_url(lan_ip)
                        print(f"   HTTP access:  {http_url}")
                        print(f"   Direct IP (HTTP):  {http_ip_url}")
                        print(f"[NET] HTTP-only mode - HTTPS requests will not work")
                
                print(f"[TARGET] Single protocol mode - no redirects needed")
                
                if self.conflict_count > 0:
                    print(f"ℹ Collision resolved - using unique name: {self.service_name}")
                
                # Start background thread for periodic announcements (offline-friendly)
                self._start_announcement_thread()
                
                return True
                
        except Exception as e:
            print(f"[ERR] mDNS service failed: {e}")
            print("[CFG] Service will continue with IP-only access")
            if self.zeroconf:
                try:
                    self.zeroconf.close()
                except Exception:
                    pass
                self.zeroconf = None
            return False
    
    def stop_service(self):
        """Stop the mDNS service with enhanced cleanup for Termux/Android"""
        try:
            with self._lock:
                if not self.is_running:
                    return
                
                print(" Stopping mDNS service...")
                
                # Stop announcement thread first
                self._stop_announcement_thread()
                
                # Unregister service with retry for Termux compatibility
                if self.service_info and self.zeroconf:
                    try:
                        self.zeroconf.unregister_service(self.service_info)
                        print(f"[OK] mDNS service unregistered: {self.domain}")
                    except Exception as unreg_error:
                        print(f"[WARN] Unregister warning (non-critical): {unreg_error}")
                
                # Close zeroconf with enhanced cleanup for Android/Termux
                if self.zeroconf:
                    try:
                        # Force close all sockets and cleanup
                        self.zeroconf.close()
                        print("[OK] Zeroconf resources cleaned up")
                    except Exception as close_error:
                        print(f"[WARN] Zeroconf close warning: {close_error}")
                    
                    # Additional cleanup for Android/Termux
                    try:
                        # Force garbage collection to free network resources
                        import gc
                        gc.collect()
                    except Exception:
                        pass
                
                # Reset all state
                self.is_running = False
                self.service_info = None
                self.zeroconf = None
                self.lan_ip = None  # Reset IP cache for next run
                
                print(" mDNS service stopped and cleaned up")
                
        except Exception as e:
            print(f"[ERR] Error stopping mDNS service: {e}")
            # Force reset even if there were errors
            self.is_running = False
            self.service_info = None
            self.zeroconf = None
            self.lan_ip = None
    
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
            "url": self._format_url(self.domain),
            "service_name": self.service_name,
            "conflict_resolved": self.conflict_count > 0,
            "conflict_count": self.conflict_count,
            "ip": self.get_lan_ip(),
            "port": self.port
        }
    
    def _format_url(self, host: str) -> str:
        """Format URL correctly, omitting standard ports"""
        protocol = self.protocol
        # Don't include port for standard HTTP/HTTPS ports
        if (self.port == 80 and protocol == "http") or (self.port == 443 and protocol == "https"):
            return f"{protocol}://{host}"
        else:
            return f"{protocol}://{host}:{self.port}"
    
    def get_hybrid_url(self) -> str:
        """Get the best URL for QR code generation - prioritize IP on Android/Termux"""
        # Check if we're on Android/Termux
        is_android = is_android_environment()
        
        if is_android:
            # On Android/Termux, always prefer IP-based URLs since .local often fails
            return self._format_url(self.get_lan_ip())
        else:
            # On other platforms, prefer mDNS with IP fallback
            if self.is_running and self.domain:
                return self._format_url(self.domain)
            else:
                return self._format_url(self.get_lan_ip())
    
    def get_android_optimized_info(self) -> Dict[str, Any]:
        """Get Android/Termux optimized connection info"""
        lan_ip = self.get_lan_ip()
        ip_url = self._format_url(lan_ip)
        
        return {
            "status": "android_optimized",
            "recommended_url": ip_url,
            "ip": lan_ip,
            "port": self.port,
            "protocol": self.protocol,
            "warning": "Use IP address instead of .local domain on Android/Termux",
            "mdns_domain": self.domain if self.is_running else None,
            "mdns_working": False,  # Assume mDNS doesn't work on Android
            "access_methods": [
                f"Direct IP: {ip_url}",
                f"QR Code: Scan for {ip_url}",
                f"Manual: Enter {lan_ip}:{self.port} in browser"
            ]
        }

# Global simple mDNS manager instance
mdns_manager = SimpleMDNSManager()
