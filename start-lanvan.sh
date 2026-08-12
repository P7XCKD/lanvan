#!/usr/bin/env bash
set -e

echo ""
echo "  Lanvan Docker Launcher (Linux/macOS)"
echo "  ===================================="
echo ""

# 1. Respect pre-set LANVAN_HOST override
if [ -n "$LANVAN_HOST" ]; then
    DETECTED_IP="$LANVAN_HOST"
    echo "  [OVERRIDE] Using manually configured LANVAN_HOST: $DETECTED_IP"
else
    # 2. Auto-detect host physical LAN IPv4
    DETECTED_IP=""
    
    # Try ip route default interface first (Linux)
    if command -v ip >/dev/null 2>&1; then
        DEFAULT_IFACE=$(ip route show default 2>/dev/null | awk '/default/ {print $5}' | head -n1)
        if [ -n "$DEFAULT_IFACE" ]; then
            DETECTED_IP=$(ip -4 addr show "$DEFAULT_IFACE" 2>/dev/null | awk '/inet / {print $2}' | cut -d/ -f1 | head -n1)
        fi
    fi

    # Try route/ifconfig fallback (macOS)
    if [ -z "$DETECTED_IP" ] && command -v route >/dev/null 2>&1; then
        DEFAULT_IFACE=$(route -n get default 2>/dev/null | awk '/interface:/ {print $2}')
        if [ -n "$DEFAULT_IFACE" ] && command -v ifconfig >/dev/null 2>&1; then
            DETECTED_IP=$(ifconfig "$DEFAULT_IFACE" 2>/dev/null | awk '/inet / {print $2}' | head -n1)
        fi
    fi

    # Final fallback if detection fails
    if [ -z "$DETECTED_IP" ]; then
        echo "  [WARN] Physical LAN IP auto-detection failed."
        echo "  Defaulting to 127.0.0.1 (Localhost)"
        DETECTED_IP="127.0.0.1"
    else
        echo "  [OK] Detected Host LAN IP: $DETECTED_IP"
    fi
fi

export LANVAN_HOST="$DETECTED_IP"
export LANVAN_ADVERTISE_HOST="$DETECTED_IP"

# 3. Ensure local data volume directory exists
mkdir -p ./data/uploads ./data/temp_chunks ./data/clipboards

# 4. Remove previous container if present and run Docker Compose
docker rm -f lanvan-app 2>/dev/null || true

docker compose up -d

if [ $? -eq 0 ]; then
    echo ""
    echo "  ========================================"
    echo "  Lanvan"
    echo "  ------"
    echo "  Docker   : Running"
    echo "  LAN IP   : $DETECTED_IP"
    echo "  LAN URL  : http://$DETECTED_IP"
    echo "  Local    : http://localhost"
    echo "  Data     : ./data"
    echo "  QR       : Ready"
    echo "  ========================================"
    echo ""
else
    echo ""
    echo "  [ERROR] Docker Compose failed to start."
    echo ""
    exit 1
fi
