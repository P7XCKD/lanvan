import socket
import urllib.request
import json
import time

def auto_discover_host_lan_ip():
    start_time = time.time()
    print("[DISCOVERY] Starting automatic host LAN IP discovery from inside Docker...")
    
    # 1. Discover active router IP
    common_subnets = ["192.168.1", "192.168.0", "192.168.2", "192.168.178", "10.0.0", "10.0.1", "172.16.0"]
    active_router_subnet = None
    
    for sub in common_subnets:
        router_ip = f"{sub}.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.15)
            res = s.connect_ex((router_ip, 80))
            s.close()
            if res == 0:
                active_router_subnet = sub
                print(f"[DISCOVERY] Found active LAN router at: {router_ip}")
                break
        except Exception:
            pass
            
    if not active_router_subnet:
        print("[DISCOVERY] Could not find active router.")
        return None
        
    # 2. Fast scan active subnet (1-254) for Lanvan server-status on port 80
    discovered_host_ip = None
    
    def check_ip(ip_str):
        try:
            url = f"http://{ip_str}/api/server-status"
            req = urllib.request.Request(url, headers={"User-Agent": "Lanvan-Host-Discovery"})
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("status") in ("online", "success", "running") or "status" in data:
                        return ip_str
        except Exception:
            pass
        return None

    import concurrent.futures
    ips = [f"{active_router_subnet}.{i}" for i in range(1, 255)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_ip, ip): ip for ip in ips}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                discovered_host_ip = res
                print(f"[DISCOVERY] SUCCESS! Auto-discovered host LAN IP: {discovered_host_ip} in {time.time() - start_time:.2f}s")
                break
                
    return discovered_host_ip

if __name__ == "__main__":
    ip = auto_discover_host_lan_ip()
    print("Final Auto-Discovered Host IP:", ip)
