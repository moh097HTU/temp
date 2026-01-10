#!/bin/bash

# run_all.sh
# Starts MAVProxy and the Perception module together.
# Run this INSIDE the Docker container.

# =========================
# CONFIG - Edit these
# =========================
GCS_IP="${GCS_IP:-172.20.10.5}"
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
pip show mavproxy > /dev/null 2>&1 || pip install mavproxy

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
# Start Perception Module
# =========================
echo "=========================================================="
echo "Starting Perception Module..."
echo "=========================================================="

cd /workspace/vision_stack
python3 -m src.main perception

# Cleanup on exit
kill $MAVPROXY_PID 2>/dev/null
echo "Stopped."
