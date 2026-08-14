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
    is_android = 'ANDROID_STORAGE' in os.environ or 'PREFIX' in os.environ
    if not is_docker_environment() and not is_android:
        return False
    if not ip_str or ip_str.startswith('127.'):
        return True
    parts = ip_str.split('.')
    if len(parts) == 4 and parts[0] == '172':
        try:
            second = int(parts[1])
            if 16 <= second <= 31:
                return True
        except ValueError:
            pass
    return False

_cached_discovered_host_ip = None

def auto_discover_host_lan_ip() -> Optional[str]:
    """
    Auto-discover the host machine's physical LAN IPv4 address from inside a Docker container.
    Scans local router subnets (e.g. 192.168.1.x, 192.168.0.x, 10.0.0.x) for the active Lanvan server port 80.
    """
    global _cached_discovered_host_ip
    if _cached_discovered_host_ip:
        return _cached_discovered_host_ip

    try:
        import urllib.request
        import json
        import concurrent.futures

        # 1. Discover active router IP
        common_subnets = ["192.168.1", "192.168.0", "192.168.2", "192.168.178", "10.0.0", "10.0.1", "172.16.0"]
        active_router_subnet = None

        for sub in common_subnets:
            router_ip = f"{sub}.1"
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.12)
                res = s.connect_ex((router_ip, 80))
                s.close()
                if res == 0:
                    active_router_subnet = sub
                    break
            except Exception:
                pass

        if not active_router_subnet:
            return None

        # 2. Fast scan active subnet (1-254) for host machine running Lanvan on port 80
        discovered_host_ip = None

        def check_host_ip(ip_str):
            try:
                url = f"http://{ip_str}/api/server-status"
                req = urllib.request.Request(url, headers={"User-Agent": "Lanvan-Host-Discovery"})
                with urllib.request.urlopen(req, timeout=0.25) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        if data.get("status") in ("online", "success", "running") or "status" in data:
                            return ip_str
            except Exception:
                pass
            return None

        ips = [f"{active_router_subnet}.{i}" for i in range(1, 255)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(check_host_ip, ip): ip for ip in ips}
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    discovered_host_ip = res
                    break

        if discovered_host_ip:
            _cached_discovered_host_ip = discovered_host_ip
            print(f"[NET] Docker host LAN IP auto-discovered: {discovered_host_ip}")
            return discovered_host_ip

    except Exception as e:
        print(f"[NET] Docker host IP auto-discovery warning: {e}")

    return None

def resolve_advertise_host() -> Dict[str, Any]:
    """
    Single authoritative address resolution for Lanvan.
    Returns dictionary with:
      - 'lan_ip': valid physical LAN IP string, or None if unavailable
      - 'is_docker': bool
      - 'is_override': bool (whether LANVAN_HOST / LANVAN_ADVERTISE_HOST was provided)
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
        # Inside Docker Desktop bridge mode without explicit LANVAN_HOST,
        # attempt lightweight auto-discovery of the host's LAN IP across the local subnet.
        discovered_ip = auto_discover_host_lan_ip()
        if discovered_ip:
            return {
                "lan_ip": discovered_ip,
                "is_docker": True,
                "is_override": False,
                "display_ip": discovered_ip
            }
        
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
