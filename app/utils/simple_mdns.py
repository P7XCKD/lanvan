"""
[NET] mDNS / Zeroconf Local Network Auto-Discovery Service
Enables zero-configuration host discovery so clients can connect via lanvan.local.

Key Features:
- Platform-optimized LAN IP auto-detection (Termux / Android / Windows / Linux)
- Callback signature resolution mapping older vs newer Zeroconf library APIs
- Automatic port conflicts detection and active resource cleanup
- Hybrid URL fallback outputting direct IPs if multicast DNS fails
"""

import socket
import threading
import time
import logging
import hashlib
import uuid
import platform
import os
from typing import Optional, Dict, Any
from app.utils.termux_compat import is_android_environment
from app.core.logger import logger

try:
    from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser
    import zeroconf
    ZEROCONF_VERSION = getattr(zeroconf, '__version__', '0.0.0')
    ZEROCONF_NEW_API = tuple(map(int, ZEROCONF_VERSION.split('.')[:2])) >= (0, 132)
    ZEROCONF_AVAILABLE = True
    HAS_ZEROCONF = True
except (ImportError, Exception) as e:
    ServiceInfo = Zeroconf = ServiceBrowser = None
    ZEROCONF_NEW_API = True
    ZEROCONF_AVAILABLE = False
    HAS_ZEROCONF = False


def check_mdns_dependencies() -> tuple[bool, str]:
    """Check if mDNS dependencies are available, especially for Termux"""
    if not ZEROCONF_AVAILABLE:
        return False, "[ERR] mDNS not available: Zeroconf library failed to load (blocked by security policy)."
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
            
            from app.core.logger import logger
            logger.info("ANDROID", "mDNS system limitations active", details={"Recommendation": "DIRECT_IP"})
        
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
            logger.debug("MDNS", "Active daemon threads detected during cleanup", details={"Count": len(daemon_threads)})
        
        logger.debug("MDNS", "Cleanup of mDNS resources executed")
        return True
    except Exception as e:
        logger.warn("MDNS", "Cleanup warning", details={"Reason": str(e)})
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
        self.ref_count = 0
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
            
            def service_added(zeroconf, service_type, name, state_change=None, **kwargs):
                """Handle service discovery with compatibility for different zeroconf versions"""
                services_found.append(name.lower())
            
            browser = None
            try:
                zeroconf_browser = Zeroconf()
                try:
                    browser = ServiceBrowser(zeroconf_browser, self.service_type, handlers=[service_added])
                    time.sleep(0.3)
                except Exception as browser_error:
                    print(f"[WARN] Service browser error (non-critical): {browser_error}")
                
                normalized_services = [s.split('.')[0] for s in services_found]
                base_lower = service_name.lower()
                
                if base_lower not in normalized_services:
                    return service_name, False
                
                counter = 2
                while True:
                    candidate = f"{service_name}-{counter}"
                    if candidate.lower() not in normalized_services:
                        logger.warn("MDNS", "Name collision detected, using alternative", details={"BaseName": service_name, "Candidate": candidate})
                        return candidate, True
                    counter += 1
                    if counter > 100:
                        break
                
                alternative_name = f"{service_name}-{self.device_id}"
                return alternative_name, True
                    
            except Exception as browse_error:
                safe_name = f"{service_name}-{self.device_id}"
                logger.info("MDNS", "Using unique name fallback", details={"SafeName": safe_name, "Reason": str(browse_error)})
                return safe_name, False
            finally:
                if browser:
                    try:
                        browser.cancel()
                    except Exception:
                        pass
                if zeroconf_browser:
                    try:
                        zeroconf_browser.close()
                    except Exception:
                        pass
                
        except Exception as e:
            safe_name = f"{service_name}-{self.device_id}"
            logger.warn("MDNS", "Collision detection system warning", details={"SafeName": safe_name, "Reason": str(e)})
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
                logger.debug("ANDROID", "IP route method failed", details={"Reason": str(e)})
            
            # Method 2: Connect to external service to get our IP
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(3)
                    s.connect(('8.8.8.8', 80))
                    ip = s.getsockname()[0]
                    if not ip.startswith('127.') and ip != '192.0.0.4':
                        return ip
            except Exception as e:
                logger.debug("ANDROID", "Socket method failed", details={"Reason": str(e)})
            
            # Method 3: Parse network interfaces directly
            try:
                result = subprocess.run(['ip', 'addr', 'show'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'inet ' in line and 'wlan' in line:
                            parts = line.strip().split()
                            for part in parts:
                                if '/' in part and not part.startswith('127.') and '192.0.0.4' not in part:
                                    ip = part.split('/')[0]
                                    if ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.'):
                                        return ip
            except Exception as e:
                logger.debug("ANDROID", "Interface parsing failed", details={"Reason": str(e)})
            
            return None
        except Exception as e:
            logger.debug("ANDROID", "All network detection methods failed", details={"Reason": str(e)})
            return None
        
    def _is_docker_bridge_ip(self, ip_str: str) -> bool:
        """Check if IP belongs to Docker container internal bridge network (172.17.x.x - 172.31.x.x)"""
        import os
        if not os.path.exists('/.dockerenv'):
            return False
        if not ip_str:
            return True
        parts = ip_str.split('.')
        if len(parts) == 4 and parts[0] == '172':
            try:
                second = int(parts[1])
                if 17 <= second <= 31:
                    return True
            except ValueError:
                pass
        return False

    def get_lan_ip(self) -> str:
        """Get the LAN IP address - delegates to authoritative ServerNetworkState"""
        try:
            from app.core.network_state import ServerNetworkState
            self.lan_ip = ServerNetworkState.get_canonical_ip()
            return self.lan_ip
        except Exception as e:
            logger.warn("MDNS", "Failed to get LAN IP from ServerNetworkState", details={"Reason": str(e)})
            return "127.0.0.1"
    
    def generate_service_name(self) -> str:
        """Generate unique service name with collision resolution"""
        base_name = self.base_service_name
        final_name, collision_resolved = self._detect_collision(base_name)
        if collision_resolved:
            self.conflict_count += 1
        return final_name
    
    def start_service(self) -> bool:
        """Start mDNS service with offline support, collision detection, and Termux compatibility"""
        try:
            with self._lock:
                if self.is_running:
                    logger.info("MDNS", "mDNS service already running")
                    return True
                
                self.ref_count = 1
                from app.utils.network_resolver import is_docker_environment
                if is_docker_environment():
                    logger.info("MDNS", "mDNS service disabled in Docker container mode")
                    return False

                if not self.mdns_available or not ZEROCONF_AVAILABLE:
                    logger.warn("MDNS", "mDNS/Zeroconf is unavailable")
                    return False


                
                logger.info("MDNS", "Starting service discovery", details={"Mode": self.protocol.upper()})
                
                is_android = is_android_environment()
                force_cleanup_mdns_resources()
                
                if self.zeroconf:
                    try:
                        self.zeroconf.unregister_all_services()
                        self.zeroconf.close()
                    except Exception:
                        pass
                    self.zeroconf = None
                
                self.service_name = self.generate_service_name()
                self.domain = f"{self.service_name}.local"

                # Sync port and protocol from the authoritative network state so the
                # advertised mDNS URL always matches the actual server endpoint.
                # The constructor default of port=80 is a placeholder; the real port
                # (e.g. 5000) is only known after the app starts and sets PORT env var.
                try:
                    from app.core.network_state import ServerNetworkState
                    self.port = ServerNetworkState.get_canonical_port()
                    self.actual_port = self.port
                    self.protocol = ServerNetworkState.get_canonical_protocol()
                    self.actual_protocol = self.protocol
                except Exception as ns_err:
                    logger.warn("MDNS", "Could not sync port from ServerNetworkState, using default",
                                details={"Reason": str(ns_err), "Port": self.port})

                lan_ip = self.get_lan_ip()
                if lan_ip == "127.0.0.1" or self._is_docker_bridge_ip(lan_ip):
                    logger.warn("MDNS", "Service discovery disabled: No physical LAN IP available", details={"IP": lan_ip})
                    return False

                # Bind Zeroconf exclusively to the authoritative LAN IP interface (prevents 172.18.x.x bridge leakage)
                try:
                    if is_android:
                        time.sleep(0.3)
                    self.zeroconf = Zeroconf(interfaces=[lan_ip])
                except Exception as zc_error:
                    try:
                        self.zeroconf = Zeroconf()
                    except Exception as zc_fallback_error:
                        logger.error("MDNS", "Service failed to initialize", details={"Reason": str(zc_fallback_error)})
                        return False

                service_name_full = f"{self.service_name}.{self.service_type}"
                
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
                    b'guest_access': b'enabled',
                    b'cross_platform': b'true',
                    b'actual_port': str(self.actual_port).encode('utf-8'),
                    b'actual_protocol': self.actual_protocol.encode('utf-8'),
                    b'single_protocol': b'true',
                    b'auto_redirect': b'false',
                    b'firewall_friendly': b'true'
                }
                
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
                    logger.error("MDNS", "Service info creation failed", details={"Reason": str(si_error)})
                    return False
                
                self.is_running = True
                def _async_register():
                    try:
                        if self.zeroconf and self.service_info:
                            self.zeroconf.register_service(self.service_info)
                            logger.info("MDNS", "Service registered", details={"Host": self.domain, "IP": lan_ip})
                    except Exception as reg_error:
                        logger.warn("MDNS", "Service registration warning", details={"Reason": str(reg_error)})

                threading.Thread(target=_async_register, daemon=True, name="mdns-register").start()
                
                protocol_name = "HTTPS" if self.use_https else "HTTP"
                logger.info("MDNS", "Service started", details={"Host": self.domain, "Protocol": protocol_name, "IP": lan_ip})
                
                self._start_announcement_thread()
                return True
                
        except Exception as e:
            logger.error("MDNS", "Service start failed", details={"Reason": str(e)})
            if self.zeroconf:
                try:
                    self.zeroconf.unregister_all_services()
                    self.zeroconf.close()
                except Exception:
                    pass
                self.zeroconf = None
            return False
    
    def stop_service(self):
        """Stop the mDNS service with enhanced cleanup for Termux/Android"""
        try:
            with self._lock:
                self.ref_count = 0
                if not self.is_running:
                    return
                
                logger.info("MDNS", "Stopping service")
                self._stop_announcement_thread()
                
                if self.zeroconf:
                    try:
                        if self.service_info:
                            self.zeroconf.unregister_service(self.service_info)
                        self.zeroconf.unregister_all_services()
                        logger.info("MDNS", "Service unregistered", details={"Host": self.domain})
                    except Exception as unreg_error:
                        logger.warn("MDNS", "Unregister warning", details={"Reason": str(unreg_error)})
                    
                    try:
                        self.zeroconf.close()
                        time.sleep(0.1)
                        logger.info("MDNS", "Zeroconf resources closed")
                    except Exception as close_error:
                        logger.warn("MDNS", "Zeroconf close warning", details={"Reason": str(close_error)})
                    
                    try:
                        import gc
                        gc.collect()
                    except Exception:
                        pass
                
                self.is_running = False
                self.service_info = None
                self.zeroconf = None
                self.lan_ip = None
                
                logger.info("MDNS", "Service stopped", details={"Status": "INACTIVE"})
                
        except Exception as e:
            logger.error("MDNS", "Error stopping mDNS service", details={"Reason": str(e)})
            self.ref_count = 0
            self.is_running = False
            self.service_info = None
            self.zeroconf = None
            self.lan_ip = None
    
    def get_mdns_info(self) -> Dict[str, Any]:
        """Get mDNS service information"""
        from app.utils.network_resolver import is_docker_environment
        if is_docker_environment() or not self.is_running:
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
        """Get the best URL for QR code generation - prioritize IP on Android/Termux or Docker container mode"""
        is_android = is_android_environment()
        is_docker = os.path.exists('/.dockerenv') or bool(os.getenv("LANVAN_ADVERTISE_HOST"))
        
        if is_android or is_docker:
            # On Android/Termux or Docker container mode, prefer IP-based URLs since mDNS multicast is bridge-isolated
            return self._format_url(self.get_lan_ip())
        else:
            # On native host platforms, prefer mDNS with IP fallback
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
