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

def check_mdns_dependencies() -> tuple[bool, str]:
    """Check if mDNS dependencies are available, especially for Termux"""
    try:
        from zeroconf import Zeroconf
        
        # Test basic Zeroconf functionality
        test_zc = Zeroconf()
        test_zc.close()
        
        # Check for Android/Termux specific requirements
        is_android = ("ANDROID_STORAGE" in os.environ or 
                     os.path.exists("/data/data/com.termux") or 
                     "TERMUX_VERSION" in os.environ)
        
        if is_android:
            # Check if avahi is available (recommended for Termux)
            try:
                import subprocess
                result = subprocess.run(['which', 'avahi-daemon'], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    return True, "⚠️ mDNS available but avahi-daemon not found. Install with: pkg install avahi"
            except:
                pass
        
        return True, "✅ mDNS dependencies available"
    
    except ImportError as e:
        return False, f"❌ mDNS not available: {e}. Install with: pip install zeroconf"
    except Exception as e:
        return False, f"❌ mDNS test failed: {e}"

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
            print(f"🧹 Found {len(daemon_threads)} zeroconf daemon threads (will be cleaned up on exit)")
        
        print("🧹 Forced cleanup of mDNS resources")
        return True
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")
        return False

class SimpleMDNSManager:
    """
    Simple, robust mDNS service manager for LANVAN
    """
    
    def __init__(self, port: int = 80, use_https: bool = False):
        self.port = port
        self._use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.zeroconf = None
        self.service_info = None
        self.service_name = "lanvan"
        self.base_service_name = "lanvan"
        # 🎯 Universal Service Type: Always use _http._tcp for mDNS compatibility
        self.service_type = "_http._tcp.local."  
        self.domain = f"{self.service_name}.local"
        self.conflict_count = 0
        self.is_running = False
        self.lan_ip = None
        self.device_id = self._generate_device_id()
        self._lock = threading.Lock()
        self._announcement_thread = None
        self._stop_announcements = False
        
        # 🔀 Universal Port Redirect: Track both HTTP and HTTPS services
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
                except:
                    # IP no longer valid, clear cache
                    self.lan_ip = None
            
            # Check if we're on Android/Termux for special handling
            is_android = ("ANDROID_STORAGE" in os.environ or 
                         os.path.exists("/data/data/com.termux") or 
                         "TERMUX_VERSION" in os.environ)
            
            if is_android:
                print("📱 Detecting network interface on Android/Termux...")
                
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
                            print(f"📱 Android IP detected: {local_ip}")
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
        """Start mDNS service with offline support, collision detection, and Termux compatibility"""
        try:
            with self._lock:
                if self.is_running:
                    print("ℹ️ mDNS service already running")
                    return True
                
                # Check if mDNS is available
                if not self.mdns_available:
                    print(f"❌ {self.mdns_status}")
                    return False
                
                print("🔍 Starting mDNS service (offline-compatible, Termux-optimized)...")
                print(f"   {self.mdns_status}")
                
                # Check if we're on Android/Termux for special handling
                is_android = ("ANDROID_STORAGE" in os.environ or 
                             os.path.exists("/data/data/com.termux") or 
                             "TERMUX_VERSION" in os.environ)
                
                # Enhanced cleanup before start (important for Termux restarts)
                force_cleanup_mdns_resources()
                
                if self.zeroconf:
                    try:
                        self.zeroconf.close()
                    except:
                        pass
                    self.zeroconf = None
                
                # Create zeroconf instance with Android/Termux optimizations
                try:
                    if is_android:
                        print("📱 Android/Termux detected - using optimized mDNS settings")
                        # Use more conservative settings for Android
                        time.sleep(0.5)  # Give time for network interfaces to stabilize
                    
                    # Initialize with local interfaces only for offline support
                    self.zeroconf = Zeroconf()
                    
                except Exception as zc_error:
                    print(f"⚠️ Zeroconf initialization warning: {zc_error}")
                    print("🔧 Attempting alternative zeroconf setup...")
                    try:
                        # Brief pause for Android/Termux network stability
                        time.sleep(1.0)
                        # Fallback zeroconf initialization
                        self.zeroconf = Zeroconf()
                    except Exception as zc_fallback_error:
                        print(f"❌ mDNS service failed to initialize: {zc_fallback_error}")
                        if is_android:
                            print("💡 On Android/Termux, try: pkg install avahi")
                            print("💡 Or restart Termux and try again")
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
                
                # Enhanced properties with universal port redirect info
                properties = {
                    b'version': b'1.0.0',
                    b'service': b'lanvan-file-server',
                    b'protocol': self.protocol.encode('utf-8'),
                    b'secure': b'true' if self.use_https else b'false',
                    b'features': b'file-transfer,clipboard,encryption',
                    b'device_id': self.device_id.encode('utf-8'),
                    b'collision_resolved': b'true' if self.conflict_count > 0 else b'false',
                    b'offline_ready': b'true',  # Indicate offline compatibility
                    b'local_network': b'true',  # Local network only
                    # 🎯 Universal Port Redirect: Add actual service details
                    b'actual_port': str(self.actual_port).encode('utf-8'),
                    b'actual_protocol': self.actual_protocol.encode('utf-8'),
                    b'redirect_capable': b'true'  # Indicates smart redirect support
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
        """Stop the mDNS service with enhanced cleanup for Termux/Android"""
        try:
            with self._lock:
                if not self.is_running:
                    return
                
                print("🔴 Stopping mDNS service...")
                
                # Stop announcement thread first
                self._stop_announcement_thread()
                
                # Unregister service with retry for Termux compatibility
                if self.service_info and self.zeroconf:
                    try:
                        self.zeroconf.unregister_service(self.service_info)
                        print(f"✅ mDNS service unregistered: {self.domain}")
                    except Exception as unreg_error:
                        print(f"⚠️ Unregister warning (non-critical): {unreg_error}")
                
                # Close zeroconf with enhanced cleanup for Android/Termux
                if self.zeroconf:
                    try:
                        # Force close all sockets and cleanup
                        self.zeroconf.close()
                        print("✅ Zeroconf resources cleaned up")
                    except Exception as close_error:
                        print(f"⚠️ Zeroconf close warning: {close_error}")
                    
                    # Additional cleanup for Android/Termux
                    try:
                        # Force garbage collection to free network resources
                        import gc
                        gc.collect()
                    except:
                        pass
                
                # Reset all state
                self.is_running = False
                self.service_info = None
                self.zeroconf = None
                self.lan_ip = None  # Reset IP cache for next run
                
                print("🔴 mDNS service stopped and cleaned up")
                
        except Exception as e:
            print(f"❌ Error stopping mDNS service: {e}")
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
        """Get the best URL for QR code generation (mDNS first, fallback to IP)"""
        if self.is_running and self.domain:
            return self._format_url(self.domain)
        else:
            return self._format_url(self.get_lan_ip())

# Global simple mDNS manager instance
mdns_manager = SimpleMDNSManager()
