import socket
import threading
import time
import logging
from typing import Optional, Dict, Any
from zeroconf import ServiceInfo, Zeroconf

class SimpleMDNSManager:
    """
    Simple, robust mDNS service manager for LANVAN
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
        """Generate unique service name with conflict resolution"""
        if self.conflict_count == 0:
            return self.base_service_name
        return f"{self.base_service_name}-{self.conflict_count}"
    
    def start_service(self) -> bool:
        """Start mDNS service"""
        try:
            with self._lock:
                if self.is_running:
                    return True
                
                # Create zeroconf instance
                self.zeroconf = Zeroconf()
                
                # Generate service details
                self.service_name = self.generate_service_name()
                self.domain = f"{self.service_name}.local"
                
                # Get network info
                hostname = socket.gethostname()
                lan_ip = self.get_lan_ip()
                
                # Create service name
                service_name_full = f"{self.service_name}.{self.service_type}"
                
                # Simple properties
                properties = {
                    b'version': b'1.0.0',
                    b'service': b'lanvan-file-server'
                }
                
                # Create service info
                self.service_info = ServiceInfo(
                    self.service_type,
                    service_name_full,
                    addresses=[socket.inet_aton(lan_ip)],
                    port=self.port,
                    properties=properties,
                    server=f"{hostname}.local."
                )
                
                # Register the service
                self.zeroconf.register_service(self.service_info)
                self.is_running = True
                
                print(f"✅ mDNS service started: {self.domain}:{self.port}")
                print(f"   Available at: http://{self.domain}:{self.port}")
                
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

# Global simple mDNS manager instance
mdns_manager = SimpleMDNSManager()
