"""
Lanvan Authoritative Server Network State Management
Single Source of Truth for protocol, host, port, lan_ip, base_url, mdns_hostname, server_generation.
"""
import os
import socket
import threading
from typing import Dict, Any, Optional
from app.core.logger import logger

class ServerNetworkState:
    _lock = threading.Lock()
    _server_generation: int = 1
    _status: str = "STOPPED"  # STOPPED, STARTING, RUNNING, STOPPING
    _pinned_lan_ip: Optional[str] = None

    @classmethod
    def increment_generation(cls) -> int:
        with cls._lock:
            cls._server_generation += 1
            cls._status = "STARTING"
            logger.info("SYSTEM", f"Server generation updated to {cls._server_generation}", details={"Gen": cls._server_generation})
            return cls._server_generation

    @classmethod
    def get_generation(cls) -> int:
        with cls._lock:
            return cls._server_generation

    @classmethod
    def set_status(cls, status: str):
        with cls._lock:
            cls._status = status
            logger.info("SYSTEM", f"Server lifecycle status set to {status}", details={"Status": status, "Gen": cls._server_generation})

    @classmethod
    def get_status(cls) -> str:
        with cls._lock:
            return cls._status

    @classmethod
    def set_pinned_lan_ip(cls, ip: str):
        if ip and ip.strip() and ip.strip() != "127.0.0.1":
            clean_ip = ip.strip()
            with cls._lock:
                cls._pinned_lan_ip = clean_ip
                os.environ['LANVAN_HOST'] = clean_ip
                logger.info("NET", f"Pinned authoritative LAN IP set to {clean_ip}", details={"IP": clean_ip})

    @classmethod
    def get_canonical_ip(cls) -> str:
        with cls._lock:
            if cls._pinned_lan_ip:
                return cls._pinned_lan_ip
            env_host = os.environ.get('LANVAN_HOST')
            if env_host and env_host.strip() and env_host.strip() != "127.0.0.1":
                return env_host.strip()

        return cls._detect_valid_lan_ip()

    @classmethod
    def _detect_valid_lan_ip(cls) -> str:
        # 1. Environment variable override
        env_host = os.environ.get('LANVAN_HOST')
        if env_host and env_host.strip() and env_host.strip() != "127.0.0.1":
            return env_host.strip()

        # 2. UDP socket connection test
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127.") and not cls._is_invalid_ip(ip):
                return ip
        except Exception:
            pass

        # 3. Interface enumeration filtering out virtual/container/docker interfaces
        try:
            import psutil
            for net_name, adapters in psutil.net_if_addrs().items():
                name_lower = net_name.lower()
                if any(x in name_lower for x in ["docker", "vethernet", "vbox", "vmware", "wg", "tun", "tap", "loopback", "dummy", "rmnet", "p2p"]):
                    continue
                for adapter in adapters:
                    if adapter.family == socket.AF_INET:
                        ip = adapter.address
                        if ip and not ip.startswith("127.") and not cls._is_invalid_ip(ip):
                            return ip
        except Exception:
            pass

        # 4. Fallback hostname lookup
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127.") and not cls._is_invalid_ip(ip):
                return ip
        except Exception:
            pass

        return "127.0.0.1"

    @classmethod
    def _is_invalid_ip(cls, ip: str) -> bool:
        if not ip:
            return True
        if ip.startswith("127.") or ip.startswith("169.254."):
            return True
        return False

    @classmethod
    def get_canonical_port(cls) -> int:
        return int(os.environ.get('PORT', 5000))

    @classmethod
    def get_canonical_protocol(cls) -> str:
        use_https = os.environ.get('USE_HTTPS', 'false').lower() == 'true'
        return "https" if use_https else "http"

    @classmethod
    def get_canonical_base_url(cls) -> str:
        protocol = cls.get_canonical_protocol()
        ip = cls.get_canonical_ip()
        port = cls.get_canonical_port()
        if (protocol == "http" and port == 80) or (protocol == "https" and port == 443):
            return f"{protocol}://{ip}"
        return f"{protocol}://{ip}:{port}"

    @classmethod
    def get_mdns_hostname(cls) -> str:
        return "Lanvan.local"

    @classmethod
    def get_network_state(cls) -> Dict[str, Any]:
        with cls._lock:
            gen = cls._server_generation
            status = cls._status
        return {
            "protocol": cls.get_canonical_protocol(),
            "host": cls.get_canonical_ip(),
            "port": cls.get_canonical_port(),
            "lan_ip": cls.get_canonical_ip(),
            "base_url": cls.get_canonical_base_url(),
            "mdns_hostname": cls.get_mdns_hostname(),
            "server_generation": gen,
            "status": status
        }
