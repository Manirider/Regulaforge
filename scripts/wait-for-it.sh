#!/bin/bash
# =============================================================================
# RegulaForge - Wait for service readiness
# Usage: ./wait-for-it.sh host:port [-t timeout] [-- command args]
# =============================================================================

set -euo pipefail

HOST=""
PORT=""
TIMEOUT=30
QUIET=0
CHILD_PID=""

usage() {
    echo "Usage: $0 host:port [-t timeout] [-- command args]"
    echo "  -t timeout    Timeout in seconds (default: 30)"
    echo "  -q            Quiet mode"
    echo "  -- command    Command to execute after service is ready"
    exit 1
}

wait_for() {
    local start_time=$(date +%s)
    local end_time=$((start_time + TIMEOUT))

    while true; do
        if timeout 1 bash -c "echo >/dev/tcp/$HOST/$PORT" 2>/dev/null; then
            break
        fi
        sleep 1
        local now=$(date +%s)
        if [ $now -ge $end_time ]; then
            echo "ERROR: Timeout after ${TIMEOUT}s waiting for $HOST:$PORT" >&2
            exit 1
        fi
    done
}

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        *:* )
            HOST="${1%:*}"
            PORT="${1##*:}"
            shift 1
            ;;
        -t)
            TIMEOUT="$2"
            shift 2
            ;;
        -q)
            QUIET=1
            shift 1
            ;;
        --)
            shift
            break
            ;;
        *)
            usage
            ;;
    esac
done

if [ -z "$HOST" ] || [ -z "$PORT" ]; then
    usage
fi

if [ $QUIET -eq 0 ]; then
    echo "Waiting for $HOST:$PORT (timeout: ${TIMEOUT}s)..."
fi

wait_for

if [ $QUIET -eq 0 ]; then
    echo "$HOST:$PORT is available"
fi

# Execute child command
if [ $# -gt 0 ]; then
    exec "$@"
fi
