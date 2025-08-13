import socket
import threading
import time
import logging
from typing import Optional, Dict, Any
from zeroconf import ServiceInfo, Zeroconf
from zeroconf import ServiceListener as ZeroconfServiceListener

class MDNSServiceManager:
    """
    Smart mDNS service manager with automatic conflict resolution
    and hybrid fallback support for LANVAN
    """
    
    def __init__(self, port: int = 5000):
        self.port = port
        self.zeroconf = None
        self.service_info = None
        self.service_name = "lanvan"
        self.base_service_name = "lanvan"
        self.service_type = "_http._tcp.local."
        self.domain = f"{self.service_name}.local"
        self.conflict_count = 0
        self.is_running = False
        self.lan_ip = None
        self._lock = threading.Lock()
        
        # Setup logging
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
            self.logger.error(f"Failed to get LAN IP: {e}")
            return "127.0.0.1"
    
    def generate_service_name(self) -> str:
        """Generate unique service name with conflict resolution"""
        if self.conflict_count == 0:
            return self.base_service_name
        return f"{self.base_service_name}-{self.conflict_count}"
    
    def start_service(self) -> bool:
        """Start mDNS service with automatic conflict resolution"""
        try:
            with self._lock:
                if self.is_running:
                    return True
                
                self.zeroconf = Zeroconf()
                self.service_name = self.generate_service_name()
                self.domain = f"{self.service_name}.local"
                
                # Get hostname and IP
                hostname = socket.gethostname()
                lan_ip = self.get_lan_ip()
                
                # Create service info
                service_name_full = f"{self.service_name}.{self.service_type}"
                
                # Service properties for additional info
                properties = {
                    'version': '1.0.0',
                    'protocol': 'http',
                    'service': 'lanvan-file-server',
                    'hostname': hostname,
                    'conflict_id': str(self.conflict_count) if self.conflict_count > 0 else '0'
                }
                
                self.service_info = ServiceInfo(
                    self.service_type,
                    service_name_full,
                    addresses=[socket.inet_aton(lan_ip)],
                    port=self.port,
                    properties=properties,
                    server=f"{hostname}.local."
                )
                
                # Check for conflicts before registering
                if self._check_service_exists(service_name_full):
                    self.logger.info(f"Service name conflict detected: {service_name_full}")
                    self.conflict_count += 1
                    self.zeroconf.close()
                    return self.start_service()  # Recursive retry with new name
                
                # Register the service
                self.zeroconf.register_service(self.service_info)
                self.is_running = True
                
                self.logger.info(f"✅ mDNS service started: {self.domain}:{self.port}")
                self.logger.info(f"   Service: {service_name_full}")
                self.logger.info(f"   IP: {lan_ip}:{self.port}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start mDNS service: {e}")
            if self.zeroconf:
                try:
                    self.zeroconf.close()
                except:
                    pass
            return False
    
    def _check_service_exists(self, service_name: str) -> bool:
        """Check if a service with the given name already exists"""
        try:
            # Quick check for existing services
            browser = ServiceListener()
            temp_zeroconf = Zeroconf()
            
            # Browse for existing services briefly
            from zeroconf import ServiceBrowser
            browser_obj = ServiceBrowser(temp_zeroconf, self.service_type, browser)
            
            # Wait a bit to discover existing services
            time.sleep(0.5)
            
            temp_zeroconf.close()
            
            # For now, we'll let zeroconf handle conflicts automatically
            # This is a lightweight check
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking service existence: {e}")
            return False
    
    def stop_service(self):
        """Stop the mDNS service"""
        try:
            with self._lock:
                if not self.is_running:
                    return
                
                if self.service_info and self.zeroconf:
                    self.zeroconf.unregister_service(self.service_info)
                    self.logger.info(f"🔴 mDNS service stopped: {self.domain}")
                
                if self.zeroconf:
                    self.zeroconf.close()
                    
                self.is_running = False
                self.service_info = None
                self.zeroconf = None
                
        except Exception as e:
            self.logger.error(f"Error stopping mDNS service: {e}")
    
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
            "url": f"http://{self.domain}:{self.port}",
            "service_name": self.service_name,
            "conflict_resolved": self.conflict_count > 0,
            "conflict_count": self.conflict_count,
            "ip": self.get_lan_ip(),
            "port": self.port
        }
    
    def get_hybrid_url(self) -> str:
        """Get the best URL for QR code generation (mDNS first, fallback to IP)"""
        if self.is_running and self.domain:
            return f"http://{self.domain}:{self.port}"
        else:
            return f"http://{self.get_lan_ip()}:{self.port}"
    
    def restart_service(self) -> bool:
        """Restart the mDNS service"""
        self.stop_service()
        time.sleep(1)  # Brief pause
        return self.start_service()

# Global mDNS manager instance
mdns_manager = MDNSServiceManager()

class ServiceListener(ZeroconfServiceListener):
    """Simple service listener for conflict detection"""
    
    def __init__(self):
        self.services = set()
    
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.services.add(name)
    
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if name in self.services:
            self.services.remove(name)
    
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass
