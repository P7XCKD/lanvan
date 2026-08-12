"""
Lanvan Network Address Resolver - Single Source of Truth
Unified network interface inspection and LAN IP resolution across Docker, Windows, Linux, Termux, and Android.
"""
import os
import socket
from typing import Optional, Dict, Any

def is_docker_environment() -> bool:
    """Detect if running inside Docker container environment"""
    return os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'

def is_docker_bridge_ip(ip_str: Optional[str]) -> bool:
    """Check if an IP belongs to Docker container bridge network (172.17.x.x - 172.31.x.x)"""
    if not is_docker_environment():
        return False
    if not ip_str or ip_str.startswith('127.'):
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

def resolve_advertise_host() -> Dict[str, Any]:
    """
    Single authoritative address resolution for Lanvan.
    Returns dictionary with:
      - 'lan_ip': valid physical LAN IP string, or None if unavailable/Docker bridge
      - 'is_docker': bool
      - 'is_override': bool (whether LANVAN_ADVERTISE_HOST was provided)
      - 'display_ip': display string (lan_ip or '127.0.0.1')
    """
    is_docker = is_docker_environment()
    env_host = os.getenv("LANVAN_HOST") or os.getenv("LANVAN_ADVERTISE_HOST") or os.getenv("ADVERTISE_HOST") or os.getenv("LAN_IP")
    
    if env_host and env_host.strip():
        val = env_host.strip()
        if not is_docker_bridge_ip(val):
            return {
                "lan_ip": val,
                "is_docker": is_docker,
                "is_override": True,
                "display_ip": val
            }

    if is_docker:
        # Inside Docker Desktop bridge mode without explicit LANVAN_ADVERTISE_HOST,
        # container bridge IPs (172.17.x.x - 172.31.x.x) are REJECTED.
        return {
            "lan_ip": None,
            "is_docker": True,
            "is_override": False,
            "display_ip": "127.0.0.1"
        }

    # Native Windows / Linux / Termux / Android execution
    # Method 1: Try socket connection to local router
    router_targets = ["192.168.1.1", "192.168.0.1", "10.0.0.1", "192.168.43.1"]
    for target in router_targets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect((target, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith('127.') and not is_docker_bridge_ip(ip):
                return {
                    "lan_ip": ip,
                    "is_docker": False,
                    "is_override": False,
                    "display_ip": ip
                }
        except Exception:
            continue

    # Method 2: Hostname resolution
    try:
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if host_ip and not host_ip.startswith('127.') and host_ip != '192.0.0.4' and not is_docker_bridge_ip(host_ip):
            return {
                "lan_ip": host_ip,
                "is_docker": False,
                "is_override": False,
                "display_ip": host_ip
            }
    except Exception:
        pass

    # Method 3: psutil interface inspection
    try:
        import psutil
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and not addr.address.startswith('127.'):
                    ip = addr.address
                    if not is_docker_bridge_ip(ip):
                        return {
                            "lan_ip": ip,
                            "is_docker": False,
                            "is_override": False,
                            "display_ip": ip
                        }
    except Exception:
        pass

    return {
        "lan_ip": None,
        "is_docker": False,
        "is_override": False,
        "display_ip": "127.0.0.1"
    }
