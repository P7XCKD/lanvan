import socket
import urllib.request
import json
import re

print("--- Docker Host Network Probe ---")
print("Hostname:", socket.gethostname())

# Try resolving host.docker.internal
try:
    host_internal = socket.gethostbyname("host.docker.internal")
    print("host.docker.internal:", host_internal)
except Exception as e:
    print("host.docker.internal error:", e)

# Try resolving gateway
try:
    with open("/proc/net/route") as f:
        for line in f:
            fields = line.strip().split()
            if fields[1] == '00000000':
                gw_hex = fields[2]
                gw_ip = socket.inet_ntoa(bytes.fromhex(gw_hex)[::-1])
                print("Container Default Gateway:", gw_ip)
                break
except Exception as e:
    print("Proc route error:", e)

# Try probing common router / host gateway IPs on port 80/8080/1900
print("--- End Probe ---")
