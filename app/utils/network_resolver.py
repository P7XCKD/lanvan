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
    """Check if an IP belongs to Docker container bridge network or virtual adapter"""
    if not ip_str or ip_str.startswith('127.') or ip_str.startswith('169.254.'):
        return True
    parts = ip_str.split('.')
    if len(parts) == 4:
        # Docker Desktop WSL2 internal virtual subnet (192.168.65.x)
        if parts[0] == '192' and parts[1] == '168' and parts[2] == '65':
            return True
        # Docker Desktop Hyper-V internal virtual subnet (10.0.75.x)
        if parts[0] == '10' and parts[1] == '0' and parts[2] == '75':
            return True
        # Docker standard bridge subnets (172.16.x.x - 172.31.x.x)
        if parts[0] == '172':
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
    Scans local router subnets for the active Lanvan server status endpoint.
    """
    global _cached_discovered_host_ip
    if _cached_discovered_host_ip:
        return _cached_discovered_host_ip

    try:
        import urllib.request
        import json
        import concurrent.futures

        # 1. Try host.docker.internal resolution first
        try:
            host_internal_ip = socket.gethostbyname('host.docker.internal')
            if host_internal_ip and not host_internal_ip.startswith('127.'):
                parts = host_internal_ip.split('.')
                if len(parts) == 4 and parts[0] in ('192', '10', '172') and not is_docker_bridge_ip(host_internal_ip):
                    _cached_discovered_host_ip = host_internal_ip
                    return host_internal_ip
        except Exception:
            pass

        # 2. Fast scan common LAN subnets directly for host machine running Lanvan
        common_subnets = ["192.168.1", "192.168.0", "192.168.2", "192.168.178", "10.0.0", "10.0.1", "172.16.0"]
        discovered_host_ip = None

        def check_host_ip(ip_str):
            for check_port in (80, 8080, 443, 5000):
                try:
                    url = f"http://{ip_str}:{check_port}/api/server-status" if check_port != 80 else f"http://{ip_str}/api/server-status"
                    req = urllib.request.Request(url, headers={"User-Agent": "Lanvan-Host-Discovery"})
                    with urllib.request.urlopen(req, timeout=0.2) as resp:
                        if resp.status == 200:
                            data = json.loads(resp.read().decode())
                            if data.get("status") in ("online", "success", "running") or "status" in data:
                                return ip_str
                except Exception:
                    pass
            return None

        candidate_ips = []
        for sub in common_subnets:
            for i in range(1, 255):
                candidate_ips.append(f"{sub}.{i}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = {executor.submit(check_host_ip, ip): ip for ip in candidate_ips}
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    discovered_host_ip = res
                    break

        from app.core.logger import logger
        if discovered_host_ip:
            _cached_discovered_host_ip = discovered_host_ip
            logger.info("NETWORK", "Docker host LAN IP auto-discovered", details={"IP": discovered_host_ip})
            return discovered_host_ip

    except Exception as e:
        from app.core.logger import logger
        logger.warn("NETWORK", "Docker host IP auto-discovery warning", details={"Reason": str(e)})

    return None

_cached_resolved_result: Optional[Dict[str, Any]] = None

def resolve_advertise_host(force_refresh: bool = False, req_host: Optional[str] = None) -> Dict[str, Any]:
    """
    Single authoritative address resolution for Lanvan.
    Returns dictionary with:
      - 'lan_ip': valid physical LAN IP string, or None if unavailable
      - 'is_docker': bool
      - 'is_override': bool (whether LANVAN_HOST / LANVAN_ADVERTISE_HOST was provided)
      - 'display_ip': display string (lan_ip or '127.0.0.1')
    """
    global _cached_resolved_result
    if not force_refresh and _cached_resolved_result is not None and not req_host:
        return _cached_resolved_result

    is_docker = is_docker_environment()
    env_host = os.getenv("LANVAN_HOST") or os.getenv("LANVAN_ADVERTISE_HOST") or os.getenv("ADVERTISE_HOST") or os.getenv("LAN_IP")
    
    if env_host and env_host.strip():
        val = env_host.strip()
        if not is_docker_bridge_ip(val):
            res = {
                "lan_ip": val,
                "is_docker": is_docker,
                "is_override": True,
                "display_ip": val
            }
            if not req_host:
                _cached_resolved_result = res
            return res

    if is_docker:
        # If client connected using a valid physical LAN IP (not localhost/127.0.0.1/bridge)
        if req_host and not req_host.startswith("127.") and req_host != "localhost" and not is_docker_bridge_ip(req_host):
            return {
                "lan_ip": req_host,
                "is_docker": True,
                "is_override": False,
                "display_ip": req_host
            }

        discovered_ip = auto_discover_host_lan_ip()
        if discovered_ip:
            res = {
                "lan_ip": discovered_ip,
                "is_docker": True,
                "is_override": False,
                "display_ip": discovered_ip
            }
            if not req_host:
                _cached_resolved_result = res
            return res
        
        res = {
            "lan_ip": None,
            "is_docker": True,
            "is_override": False,
            "display_ip": "127.0.0.1"
        }
        if not req_host:
            _cached_resolved_result = res
        return res

    # Native Windows / Linux / Termux / Android execution
    # Method 1: Instant UDP route query to public DNS / gateway targets (does not send packets, queries OS routing table)
    probe_targets = ["8.8.8.8", "1.1.1.1", "192.168.1.1", "192.168.0.1", "10.0.0.1", "192.168.43.1"]
    for target in probe_targets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.05)
            s.connect((target, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith('127.') and not is_docker_bridge_ip(ip):
                res = {
                    "lan_ip": ip,
                    "is_docker": False,
                    "is_override": False,
                    "display_ip": ip
                }
                _cached_resolved_result = res
                return res
        except Exception:
            continue

    # Method 2: Hostname resolution
    try:
        hostname = socket.gethostname()
        host_ip = socket.gethostbyname(hostname)
        if host_ip and not host_ip.startswith('127.') and host_ip != '192.0.0.4' and not is_docker_bridge_ip(host_ip):
            res = {
                "lan_ip": host_ip,
                "is_docker": False,
                "is_override": False,
                "display_ip": host_ip
            }
            _cached_resolved_result = res
            return res
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
                        res = {
                            "lan_ip": ip,
                            "is_docker": False,
                            "is_override": False,
                            "display_ip": ip
                        }
                        _cached_resolved_result = res
                        return res
    except Exception:
        pass

    res = {
        "lan_ip": None,
        "is_docker": False,
        "is_override": False,
        "display_ip": "127.0.0.1"
    }
    _cached_resolved_result = res
    return res
