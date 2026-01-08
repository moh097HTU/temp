#!/bin/bash
# Run MAVProxy with TELEM1 serial and UDP outputs
# Usage: ./run_mavproxy.sh [GCS_IP]

set -e

# Configuration
SERIAL_PORT="${SERIAL_PORT:-/dev/ttyTHS1}"
BAUDRATE="${BAUDRATE:-57600}"
LOCAL_PORT="${LOCAL_PORT:-14551}"
GCS_IP="${1:-${GCS_IP:-192.168.1.100}}"
GCS_PORT="${GCS_PORT:-14550}"

echo "Starting MAVProxy..."
echo "  Serial: ${SERIAL_PORT} @ ${BAUDRATE}"
echo "  Local UDP: 127.0.0.1:${LOCAL_PORT}"
echo "  GCS UDP: ${GCS_IP}:${GCS_PORT}"

mavproxy.py \
    --master="${SERIAL_PORT}" \
    --baudrate="${BAUDRATE}" \
    --out="udp:127.0.0.1:${LOCAL_PORT}" \
    --out="udp:${GCS_IP}:${GCS_PORT}" \
    --daemon \
    --non-interactive \
    --logfile="/var/log/mavproxy.log"

echo "MAVProxy started in daemon mode"
