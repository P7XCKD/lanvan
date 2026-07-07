#!/data/data/com.termux/files/usr/bin/bash

cd ~/lanvan || exit
sleep 0.5

PORT=5001

# Kill any existing uvicorn or python run.py https processes using port 5001
for pid in $(ps aux | grep -E 'uvicorn|run.py' | grep -v grep | awk '{print $2}'); do
    kill -9 "$pid" 2>/dev/null
done
sleep 1

# Start HTTPS server and listen for LAN URL
PYTHONWARNINGS=ignore python -u run.py https | tee /data/data/com.termux/files/usr/tmp/lanvan_https_log.txt | while read -r line; do
    echo "$line"

    if echo "$line" | grep -q "^LAN:\s*https://"; then
        LAN_URL=$(echo "$line" | grep -oE 'https://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+')

        if echo "$LAN_URL" | grep -qE '^https://192\.0\.0\.'; then
            FINAL_URL="https://127.0.0.1:$PORT"
        else
            FINAL_URL="$LAN_URL"
        fi

        echo -n "$FINAL_URL" | termux-clipboard-set
        am start -a android.intent.action.VIEW -d "$FINAL_URL" com.android.chrome
        break
    fi
done
