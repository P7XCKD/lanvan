import socket
import urllib.request
import struct

print("=== DEEP DOCKER HOST IP PROBE ===")

# Test NetBIOS Node Status Query (Port 137) to host.docker.internal or gateway
def get_netbios_name(ip):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.5)
        # NBNS Node Status Query packet
        packet = b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x20\x43\x4b\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x00\x00\x21\x00\x01'
        sock.sendto(packet, (ip, 137))
        data, addr = sock.recvfrom(1024)
        print(f"[NetBIOS] Reply from {ip}: {data[:60]}")
        return data
    except Exception as e:
        print(f"[NetBIOS] Error querying {ip}: {e}")
        return None

# Test HTTP to host.docker.internal or gateways
for target in ["host.docker.internal", "192.168.65.254", "172.17.0.1", "192.168.65.2"]:
    try:
        ip = socket.gethostbyname(target)
        print(f"\nProbing target {target} ({ip})...")
        get_netbios_name(ip)
    except Exception as e:
        print(f"Target {target} failed: {e}")

# Try scanning local subnets (e.g. 192.168.1.1 - 192.168.1.254 or common router IPs 192.168.1.1, 192.168.0.1, 10.0.0.1)
common_routers = ["192.168.1.1", "192.168.0.1", "192.168.1.254", "10.0.0.1", "192.168.8.1"]
print("\nProbing common routers...")
for r in common_routers:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)
        res = s.connect_ex((r, 80))
        s.close()
        if res == 0:
            print(f"  [ROUTER FOUND] Active router on port 80: {r}")
    except Exception:
        pass

print("=== END DEEP PROBE ===")
