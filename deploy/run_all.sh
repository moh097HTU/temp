#!/bin/bash

# run_all.sh
# Starts MAVProxy and ALL vision stack components.
# Run this INSIDE the Docker container.

# =========================
# CONFIG - Edit these
# =========================
GCS_IP="${GCS_IP:-172.20.10.4}"
#GCS_IP="${GCS_IP:-172.20.10.5}"
GCS_PORT=14550
SERIAL_PORT="/dev/ttyTHS1"
BAUDRATE=57600

# =========================
# Start MAVProxy in background
# =========================
echo "=========================================================="
echo "Starting MAVProxy..."
echo "  Serial: $SERIAL_PORT @ $BAUDRATE"
echo "  GCS: $GCS_IP:$GCS_PORT"
echo "=========================================================="

# Install mavproxy if not present
pip show mavproxy > /dev/null 2>&1 || pip install mavproxy future

mavproxy.py \
    --master=$SERIAL_PORT \
    --baudrate $BAUDRATE \
    --out=udp:$GCS_IP:$GCS_PORT \
    --out=udp:127.0.0.1:14551 \
    --daemon &

MAVPROXY_PID=$!
echo "MAVProxy started (PID: $MAVPROXY_PID)"

# Wait a moment for MAVProxy to initialize
sleep 2

# =========================
# Start ALL Vision Stack Components
# =========================
# This runs: perception, targeting, control, mavlink, video, gpio
# All communicate via ZMQ internally
echo "=========================================================="
echo "Starting ALL Vision Stack Components..."
echo "  Components: perception, targeting, control, mavlink, video, gpio"
echo "  GCS IP: $GCS_IP"
echo "=========================================================="

cd /workspace/vision_stack
python3 -m src.main all --config-dir configs --gcs-ip $GCS_IP

# Cleanup on exit
kill $MAVPROXY_PID 2>/dev/null
echo "Stopped."
