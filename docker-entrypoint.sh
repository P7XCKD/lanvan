#!/bin/sh
set -e

# Ensure persistent data subdirectories exist on volume mount at boot
mkdir -p /app/data/uploads /app/data/temp_chunks /app/data/clipboards

# Default to production execution unless --dev is explicitly passed
if [ "$1" = "python" ] || [ "$1" = "sh" ] || [ "$1" = "bash" ]; then
    exec "$@"
fi

IS_DEV=false
USE_HTTPS=false
BLOCK_DANGEROUS=false
EXTRA_ARGS=""

for arg in "$@"; do
    case "$arg" in
        --dev|dev)
            IS_DEV=true
            ;;
        --https|https)
            USE_HTTPS=true
            ;;
        --block-dangerous|--block_dangerous|block-dangerous|block_dangerous)
            BLOCK_DANGEROUS=true
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $arg"
            ;;
    esac
done

if [ "$IS_DEV" = "true" ]; then
    echo "[DOCKER] Opting into Development Mode..."
    export LANVAN_ENV=development
    export PRODUCTION=false
    CMD="python run.py --dev"
else
    echo "[DOCKER] Running in Production Mode..."
    export LANVAN_ENV=production
    export PRODUCTION=true
    CMD="python run.py"
fi

if [ "$USE_HTTPS" = "true" ]; then
    CMD="$CMD --https"
    export USE_HTTPS=true
fi

if [ "$BLOCK_DANGEROUS" = "true" ]; then
    CMD="$CMD --block-dangerous"
    export BLOCK_DANGEROUS=true
fi

if [ -n "$EXTRA_ARGS" ]; then
    CMD="$CMD $EXTRA_ARGS"
fi

echo "[DOCKER] Executing: $CMD"
exec $CMD
